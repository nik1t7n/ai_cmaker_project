import asyncio
from typing import Union
import logging
import os
import uuid

import httpx
import yaml
from aiogram import F, Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InputMediaVideo, URLInputFile
from aiogram.utils.formatting import Bold, Italic, Text, Url
from aiogram.utils.keyboard import InlineKeyboardBuilder
from arq import create_pool
from arq.connections import RedisSettings

from arq_jobs import WorkerSettings
from bot.api.user import check_user_credits
from bot.constants import BOT_URL, WEBHOOK_BASE_URL
from bot.handlers.editing import proccess_video_editing
from bot.init import get_bot
from bot.keyboards.keyboards import (
    build_avatar_inline_keyboard,
    get_greeting_inline_keyboard,
    get_script_method_inline_keyboard,
)
from bot.states import VideoCreation
from bot.utils.loading import animate
from bot.utils.utils import download_from_url_and_to_s3
from services.heygen import HeygenProcessor, VideoGenerationConfig

bot, dp = asyncio.run(get_bot())
router = Router()


async def start_generation(callback_or_message: Union[types.CallbackQuery, types.Message], state: FSMContext):
    # Определяем тип переданного объекта и получаем нужные данные
    if isinstance(callback_or_message, types.CallbackQuery):
        # Для CallbackQuery
        await callback_or_message.answer()  # Подтверждаем коллбэк
        message = callback_or_message.message
        chat_id = message.chat.id
        original_text = Text(message.text)
        is_callback = True
    else:
        # Для Message
        message = callback_or_message
        chat_id = message.chat.id
        original_text = Text(message.text)
        is_callback = False
    
    # Объединяем тексты
    full_text = Text(
        original_text, "\n\n", Italic("==========\nПолетели генерировать!")
    ).as_markdown()
    
    avatar_img_path = "assets/imgs/avatars.png"
    if os.path.exists(avatar_img_path):
        caption = (
            "🎭 Выберите аватара для вашего видео.\n"
            "Каждый аватар имеет свой уникальный стиль и характер."
        )
        keyboard = build_avatar_inline_keyboard()
        await bot.send_photo(
            chat_id,
            photo=FSInputFile(avatar_img_path),
            caption=caption,
            reply_markup=keyboard,
        )
        
        # Редактируем или отправляем сообщение в зависимости от контекста
        try:
            if is_callback:
                await message.edit_text(
                    text=full_text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=None
                )
            else:
                # мы получаем сообщение, только если пользователь нажал /generate
                # поэтому нет смысла редактировать предыдущее сообщение, потому что его нет
                pass 
        except Exception as e:
            logging.warning(f"Не удалось отредактировать сообщение: {e}")
        
        await state.set_state(VideoCreation.choosing_avatar)
    else:
        logging.warning(f"Файл с аватарами не найден: {avatar_img_path}")
        await bot.send_message(
            chat_id,
            "К сожалению, изображения аватаров временно недоступны. Попробуйте позже или обратитесь в поддержку.",
        )
        keyboard = get_greeting_inline_keyboard()
        await bot.send_message(
            chat_id,
            "Хотите попробовать другие функции?",
            reply_markup=keyboard,
        )


### Обработчик демо-режима (кнопка "🚀 Полетели пробовать!") ###
@router.callback_query(lambda c: c.data == "demo")
async def handle_create_demo_callback(callback: types.CallbackQuery, state: FSMContext):
    state_data = await state.get_data()

    is_video_generating = state_data.get("is_video_generating")
    if is_video_generating is not None and is_video_generating:
        indempotency_error_msg = Text(
            Bold("Извините, но видео уже генерируется. Подождите, пока закончится предыдущая генерация, перед тем, как начать новую.")
        ).as_markdown()
        await callback.message.answer(text=indempotency_error_msg, parse_mode=ParseMode.MARKDOWN_V2)
        return



    access = await check_user_credits(user_id=state_data["user_id"])
    if access:
        await start_generation(callback_or_message=callback, state=state)
    else:

        builder = InlineKeyboardBuilder()
        builder.button(text="💎 Пополнить баланс", callback_data="pricing")
        # Форматируем сообщение
        no_access_msg = Text(
            Bold("⚠️ Ограничение доступа"),
            "\n\n",
            "К сожалению, у вас закончились кредиты или истек срок действия подписки.",
            "\n\n",
            "Вы можете проверить статус вашего аккаунта (/profile) или пополнить баланс, используя кнопки ниже.",
        ).as_markdown()

        # Отправляем сообщение с клавиатурой
        await callback.message.answer(
            text=no_access_msg,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=builder.as_markup(),
        )


@router.message(Command("generate"))
async def handle_start_avatar_generation(
    message: types.Message, state: FSMContext
):

    state_data = await state.get_data()

    is_video_generating = state_data.get("is_video_generating")
    if is_video_generating is not None and is_video_generating:
        indempotency_error_msg = Text(
            Bold("Извините, но видео уже генерируется. Подождите, пока закончится предыдущая генерация, перед тем, как начать новую.")
        ).as_markdown()
        await message.answer(text=indempotency_error_msg, parse_mode=ParseMode.MARKDOWN_V2)
        return



    user_id = state_data["user_id"]
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{WEBHOOK_BASE_URL}/api/users/{user_id}")

    if response.status_code == 404:
        warning_msg = Text(
            Bold(
                "Извините, но перед началом работы с ботом - вам следует активировать его, использовав команду /start"
            )
        ).as_markdown()
        await message.answer(
            text=warning_msg, parse_mode=ParseMode.MARKDOWN_V2
        )
    if response.status_code == 200:

        access = await check_user_credits(user_id=state_data["user_id"])
        if access:
            await start_generation(callback_or_message=message, state=state)
        else:
            profile_command_url = f"{BOT_URL}?start=profile"

            builder = InlineKeyboardBuilder()
            builder.button(text="👤 Мой профиль", url=profile_command_url)
            builder.button(text="💎 Пополнить баланс", callback_data="pricing")
            # Форматируем сообщение
            no_access_msg = Text(
                Bold("⚠️ Ограничение доступа"),
                "\n\n",
                "К сожалению, у вас закончились кредиты или истек срок действия подписки.",
                "\n\n",
                "Вы можете проверить статус вашего аккаунта или пополнить баланс, используя кнопки ниже.",
            ).as_markdown()

            # Отправляем сообщение с клавиатурой
            await message.answer(
                text=no_access_msg,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=builder.as_markup(),
            )


@router.callback_query(lambda c: c.data and c.data.startswith("avatar:"))
async def avatar_chosen(callback: types.CallbackQuery, state: FSMContext):
    avatar_key = callback.data.split(":", 1)[1]

    # Load avatar data from config.yml
    with open("config.yml", "r") as f:
        config = yaml.safe_load(f)

    avatar_credentials = config.get("avatar", {}).get("avatar_credentials", {})

    if avatar_key not in avatar_credentials:
        await callback.answer("Неверный выбор аватара.", show_alert=True)
        return

    credentials = avatar_credentials[avatar_key]

    avatar_data = {
        "key": avatar_key,
        "name": avatar_key.capitalize(),  # Using the key capitalized as name
        "voice_id": credentials["voice_id"],
        "avatar_id": credentials["avatar_id"],
    }
    await state.update_data(avatar=avatar_data)

    await callback.message.edit_caption(
        caption=Text(Bold("Выбран аватар: "), avatar_key.capitalize()).as_markdown(),
        reply_markup=None,
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    await callback.answer(text=f"Выбран аватар: {avatar_key.capitalize()}")

    # Предлагаем выбрать способ создания сценария через инлайн-клавиатуру
    text = Text(
        "Давай теперь напишем сценарий для видео! Каким способом мы сделаем это?",
    ).as_markdown()
    script_method_keyboard = get_script_method_inline_keyboard()

    await bot.send_message(
        callback.message.chat.id,
        text,
        reply_markup=script_method_keyboard,
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    await state.set_state(VideoCreation.choosing_script_method)


@router.callback_query(lambda c: c.data and c.data.startswith("subtitle_style:"))
async def generate_heygen_avatar(callback: types.CallbackQuery, state: FSMContext):

    error_happened = False

    state_data = await state.get_data()

    is_video_generating = state_data.get("is_video_generating")
    if is_video_generating is not None and is_video_generating:
        indempotency_error_msg = Text(
            Bold("Извините, но видео уже генерируется. Подождите, пока закончится предыдущая генерация, перед тем, как начать новую.")
        ).as_markdown()
        await callback.message.answer(text=indempotency_error_msg, parse_mode=ParseMode.MARKDOWN_V2)
        return

    style_number_str = callback.data.split(":", 1)[1]
    with open("config.yml", "r") as f:
        config = yaml.safe_load(f)
    subtitle_template_id = config["video_editing"]["subtitle_styles"][style_number_str][
        "id"
    ]
    video_editing_data = {"subtitle_template_id": subtitle_template_id}
    await state.update_data(video_editing=video_editing_data)

    waiting_message = await callback.message.answer("⏳ Начал генерировать видосик...")

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    stop_animation = asyncio.Event()

    animation_task = asyncio.create_task(
        animate("Генерирую видосик...", stop_animation, waiting_message)
    )

    state_data = await state.get_data()

    print(state_data)
    logging.info(state_data)

    processor = HeygenProcessor(api_key=os.getenv("HEYGEN_API_KEY"))
    config = VideoGenerationConfig(
        content=state_data["script"],
        voice_id=state_data["avatar"]["voice_id"],
        avatar_id=state_data["avatar"]["avatar_id"],
        dimensions=(720, 1280),
        speed=1.0,
    )

    await state.update_data(is_video_generating=True)
    try:
        redis_pool = await create_pool(WorkerSettings.redis_settings)
        job = await redis_pool.enqueue_job(
            "heygen_generate_video_job", processor, config, _defer_by=0
        )
        if job is None:
            raise RuntimeError("Job was not enqueued; possible duplicate job id?")
        video_url = await job.result(timeout=1200)

        if not isinstance(video_url, str):
            if video_url.get("code") == 400133:
                await callback.message.answer("Недостаточно кредитов HeyGen!")
            raise ValueError(f"Heygen returned an error payload: {video_url!r}")

        # video_url = "https://files2.heygen.ai/aws_pacific/avatar_tmp/9351014d20b44b408fd6952dc7c0ac42/a1ed538a42104eccb3f4b0c7e9772a1f.mp4?Expires=1744045988&Signature=AHSaTSipZ4X~ZzRm5yIh2zWXKK19UcKBvpRWB7bhQr5z8Nl-nNx9VRfPrNKHa~n4yGMsgMvviFOdOqAceKvTX8BkS61WGwCZLI8d1uHf3C6wVywgV7AA-irdms5QYzXEtIC-liUH9URhsw7aKvX6qhTvhjFIYh624cZX0t4pT79SjpFa9icpZSiLYw3ZAeR2~V8lgJEpeu4K1nzM0u85cIisYKj3OcEaAtcYyI~in5Gp1nv5QaFSh085Yw5DMilRyz~A~VPsJhKwzEMaAj7GXILbkSRnVfE6afuShvanHV8iLFof9rc0RFH0ahrq3EagB5inDOY87IitlbQl8XdwbA__&Key-Pair-Id=K38HBHX5LX3X2H"

        if not video_url:
            raise Exception("There is no VIDEO URL")

        key = f"heygen/generated-{uuid.uuid4()}.mp4"
        result = await download_from_url_and_to_s3(url=video_url, key=key)

        if not result:
            logging.error("Failed to load video to s3 (heygen)")

        logging.info("Generated video URL: '{}'.".format(video_url))
        logging.debug(f"Generated video URL: {video_url}")

        # await callback.message.answer(
        #     Text(Bold("Ваша ссылка:"), "\n\n", Url(video_url)).as_markdown(),
        #     parse_mode=ParseMode.MARKDOWN_V2,
        # )

        avatar_data = state_data.get("avatar")
        avatar_data["video_url"] = video_url
        await state.update_data(avatar=avatar_data)
        logging.debug("СОХРАНИЛИ ЮРЛ")

    except Exception as e:
        error_happened = True
        await state.update_data(is_video_generating=False)
        await callback.message.answer(Text(Bold("Что то явно не то...")).as_markdown(), parse_mode=ParseMode.MARKDOWN_V2)

        logging.critical("Error during video generation: {}".format(e))
        logging.debug(f"Error: {e}")
        
        # Останавливаем анимацию и удаляем сообщение о загрузке
        stop_animation.set()
        await animation_task
        try:
            await waiting_message.delete()
        except Exception as e:
            logging.warning(f"Error during animation message deletion: {e}")
        
        # Важно - НЕ переходим к следующему шагу
        return
    finally:
        stop_animation.set()
        await animation_task

        try:
            await waiting_message.delete()
        except Exception as e:
            logging.warning(f"Error during animation message deletion: {e}")

    if error_happened:
        return

    await state.set_state(VideoCreation.video_editing)
    await proccess_video_editing(state)
