import asyncio
import logging
import os

import httpx
from aiogram import Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InputMediaVideo, URLInputFile
from aiogram.utils.formatting import (
    Bold,
    HashTag,
    Italic,
    Text,
    Url,
    as_list,
    as_marked_section,
)

from bot.api.user import add_credits, create_user
from bot.constants import GREETING_TEXT, WEBHOOK_BASE_URL
from bot.init import get_bot
from bot.keyboards.keyboards import (
    get_after_instructions_keyboard,
    get_greeting_inline_keyboard,
    get_payment_keyboard,
)

bot, dp = asyncio.run(get_bot())


async def send_reminder(chat_id: int, user_id: int):
    try:
        await asyncio.sleep(120)
        reminder_text = "⛴️ Корабль уже загрузили, выдвигаемся?"
        keyboard = get_greeting_inline_keyboard()
        await bot.send_message(chat_id, reminder_text, reply_markup=keyboard)
    except asyncio.CancelledError:
        # Если задача отменена – ничего не делаем
        pass


router = Router()


### Команда /start ###
@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):

    # await state.clear()

    await state.update_data(chat_id=message.chat.id, user_id=message.from_user.id)
    error_msg = Text(
        Bold("Произошла какая то странная ошибка."),
        "\n\n",
        Italic("Попробуйте, пожалуйста, заново выполнить команду /start"),
    ).as_markdown()

    # creating user
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            state_data = await state.get_data()
            user_id = state_data["user_id"]
            payload = {"user_id": user_id}
            response = await client.post(f"{WEBHOOK_BASE_URL}/api/users", json=payload)

            if response.status_code == 201:
                logging.info("User has been successfully created!")
                await state.update_data(user_id=user_id)
            elif response.status_code == 409:
                logging.debug(
                    "You are trying to create already existing user. Passing further"
                )
                pass  # because we have already registered this user
            else:
                logging.warning(
                    f"Unexpected server answer during user creation.\n"
                    f"Status: {response.status_code}\n"
                    f"Details: {response.text}"
                )
                await message.answer(error_msg, parse_mode=ParseMode.MARKDOWN_V2)
        except httpx.RequestError as exc:
            logging.critical("Critical error during user creation", f"Details: {exc}")
            raise Exception(f"Error during regitering user: {exc}")


    greeting_text = GREETING_TEXT

    keyboard = get_greeting_inline_keyboard()
    await message.answer(
        greeting_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2
    )


@router.callback_query(lambda c: c.data == "instruction")
async def handle_instruction_callback(callback: types.CallbackQuery, state: FSMContext):
    # Process steps with unique emojis
    generation_steps = as_list(
        as_marked_section(
            Bold("✨ Как происходит процесс генерации видео:\n"),
            "🤖 Вы выбираете аватара",
            "📝 Создается сценарий (генерируете с помощью ИИ или вводите вручную)",
            "🎨 Выбираете стиль субтитров",
            "⏱️ Ожидаете 5-10 минут",
            "🎬 Получаете готовое видео",
            marker="",
        ),
        sep="\n",
    )

    # Payment information
    payment_info = as_list(
        as_marked_section(
            Bold("💳 Информация об оплате:\n"),
            "Все платежи обрабатываются через FreedomPay - надежную и проверенную платежную систему",
            "Данные вашей карты надежно защищены современными технологиями шифрования",
            "Мгновенное зачисление средств и автоматическая активация выбранного тарифа",
            marker="🔐 ",
        ),
        sep="\n",
    )

    commands_info = as_list(
        as_marked_section(
            Bold("⌨️ Основные команды бота:\n"),
            "/start — перезагрузить бота",
            "/profile — посмотреть профиль",
            "/generate — сгенерировать видео",
            marker="▶️ ",
        ),
        sep="\n",
    )

    # Combine all sections into a beautifully formatted message
    message = Text(
        Bold("🔍 Как пользоваться ботом?"),
        "\n\n",
        "Всего у вас 3 демо генерации на то, чтобы попробовать функционал бота. После того, как они закончатся, вы можете выбрать наиболее подходящий для вас тариф использования бота.",
        "\n\n",
        Italic("💎 Ознакомиться с тарифами вы можете нажав кнопку "),
        Bold('"Тарифы"'),
        "\n",
        "=================",
        "\n\n",
        generation_steps,
        "\n",
        "=================",
        "\n\n",
        payment_info,
        "\n",
        "=================",
        "\n\n",
        commands_info,
        "\n",
        "=================",
        "\n\n",
        Bold("🌟 Готовы создать ваше первое видео? Нажмите 'Пробуем!'"),
    ).as_markdown()

    await callback.message.edit_reply_markup(reply_markup=None)

    # Send the response with appropriate keyboard
    keyboard = get_after_instructions_keyboard()
    await callback.message.answer(
        text=message, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard
    )


### Обработчик тарифа (кнопка "🏷️ Ознакомиться с тарифами") ###
@router.callback_query(lambda c: c.data == "pricing")
async def handle_pricing_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    price_img_path = "assets/imgs/prices.png"

    caption = (
        "✨ Выбери свой путь к созданию профессионального контента без лишних хлопот!\n\n"
        "📊 Наши тарифы:\n"
        "• 10 видео — 15$ 💰\n"
        "• 30 видео — 45$ 💰\n"
        "• 50 видео — 70$ 💰\n"
        "• 100 видео — 135$ 💰\n\n"
        "⏱ Важно: у вас есть ровно 28 дней, чтобы использовать приобретенные кредиты с момента покупки тарифа.\n\n"
        '👤 Хотите получить индивидуальный аватар с вашим лицом? Нажмите на кнопку "Индивидуальный тариф"!'
    )

    if os.path.exists(price_img_path):
        await bot.send_photo(
            callback.message.chat.id, photo=FSInputFile(price_img_path), caption=caption
        )
        await bot.send_message(
            callback.message.chat.id,
            text=Text(
                Bold("👇 Для оплаты выберите пакет на кнопках ниже 👇")
            ).as_markdown(),
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_payment_keyboard(),
        )
        await callback.message.edit_reply_markup(reply_markup=None)
    else:
        logging.warning(f"Файл с ценами не найден: {price_img_path}")
        caption += Text(
            "\n\n", Bold("👇 Для оплаты выберите пакет на кнопках ниже 👇")
        ).as_markdown()

        await bot.send_message(
            callback.message.chat.id,
            text=caption,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=get_payment_keyboard(),
        )
        await callback.message.edit_reply_markup(reply_markup=None)
