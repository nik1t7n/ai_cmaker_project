import asyncio
import logging
import uuid

import httpx
from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import URLInputFile
from aiogram.utils.formatting import Bold, Italic, Text, Url
from aiogram.utils.keyboard import InlineKeyboardBuilder
from arq import create_pool
from arq.connections import RedisSettings

from arq_jobs import WorkerSettings
from bot.constants import WEBHOOK_BASE_URL
from bot.init import get_bot
from bot.states import VideoCreation
from bot.utils.loading import animate
from bot.utils.merge import merge_video_and_music
from bot.utils.utils import download_from_url_and_to_s3

bot, dp = asyncio.run(get_bot())
router = Router()


@router.message(VideoCreation.video_editing)
async def proccess_video_editing(state: FSMContext):

    state_data = await state.get_data()
    chat_id = state_data.get("chat_id")

    text = Text("Начинаем монтаж видео...").as_markdown()

    waiting_message = await bot.send_message(
        chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2
    )

    stop_animation = asyncio.Event()

    animation_task = asyncio.create_task(
        animate("Делаем магию монтажа...", stop_animation, waiting_message)
    )

    state_data = await state.get_data()

    # with open("config.yml", "r") as f:
    #     config = yaml.safe_load(f)

    subtitle_template_id = state_data["video_editing"]["subtitle_template_id"]
    avatar_video_url = state_data["avatar"]["video_url"]

    try:
        redis_pool = await create_pool(WorkerSettings.redis_settings)
        job = await redis_pool.enqueue_job(
            "zapcap_edit_video_job",
            avatar_video_url,
            subtitle_template_id,
            _defer_by=0,
        )
        if job is None:
            raise RuntimeError("Job was not enqueued; possible duplicate job id?")
        download_url = await job.result(timeout=900)

        # download_url = r"https://zapcap-artifacts.532e842867d11b64714b6837669da82c.r2.cloudflarestorage.com/5b2fdb86-66c2-4854-bcac-d93736cca085?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=78e30473d9172a53f32746bf10677f2d%2F20250401%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250401T070322Z&X-Amz-Expires=3600&X-Amz-Signature=5e5e62a0ee47c29cf5e745c2bc3d6d384b56ff37bdc4f116c66048d44067a0f5&X-Amz-SignedHeaders=host&response-content-disposition=attachment%3B%20filename%3D%225b2fdb86-66c2-4854-bcac-d93736cca085-video.mp4%22&x-id=GetObject"

        logging.info(
            "Video processing completed. Download URL: '{}'".format(download_url)
        )

        # await bot.send_message(
        #     chat_id=chat_id,
        #     text=Text(
        #         Bold("Юхуу, монтаж завершен!!!"),
        #         "\n\n",
        #         "Вот ссылка:",
        #         "\n",
        #         Url(download_url),
        #     ).as_markdown(),
        #     parse_mode=ParseMode.MARKDOWN_V2,
        # )

        key = f"zapcap/edited-{uuid.uuid4()}.mp4"
        result = await download_from_url_and_to_s3(url=download_url, key=key)

        if not result:
            logging.error("Failed to upload zapcap video to S3!")

        video_editing_data = state_data["video_editing"]
        video_editing_data["zapcap_video_url"] = download_url
        await state.update_data(video_editing=video_editing_data)

    except Exception as e:
        await bot.send_message(
            chat_id=chat_id,
            text=Text(Bold("Что то пошло не так во время монтажа!")).as_markdown(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        # Сбрасываем флаг генерации
        await state.update_data(is_video_generating=False)
        
        logging.critical("Error during video generation: {}".format(e))
        print(f"Error: {e}")
        
        # Останавливаем анимацию и удаляем сообщение о загрузке
        stop_animation.set()
        await animation_task
        try:
            await waiting_message.delete()
        except Exception as e:
            logging.warning(f"Error during animation message deletion: {e}")
        
        # НЕ переходим к следующему шагу!
        return
    finally:

        stop_animation.set()
        await animation_task

        try:
            await waiting_message.delete()
        except Exception as e:
            logging.warning(f"Error during animation message deletion: {e}")

        await state.set_state(VideoCreation.create_music)
        await proccess_music_generation(state)


@router.message(VideoCreation.create_music)
async def proccess_music_generation(state: FSMContext):
    state_data = await state.get_data()

    script = state_data["script"]

    chat_id = state_data.get("chat_id")

    text = Text("Начинаем генерацию музыки...").as_markdown()

    waiting_message = await bot.send_message(
        chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2
    )

    stop_animation = asyncio.Event()

    animation_task = asyncio.create_task(
        animate("Создаем волшебную музыку...", stop_animation, waiting_message)
    )
    try:
        redis_pool = await create_pool(WorkerSettings.redis_settings)
        job = await redis_pool.enqueue_job("generate_music_job", script, _defer_by=0)
        if job is None:
            raise RuntimeError("Job was not enqueued; possible duplicate job id?")

        music_url = await job.result(timeout=600)
        # music_url = "https://cdn.aimlapi.com/octopus/files/df2910f128bf420d901dcf9df8a62cf3_tmpwid0ufe3.wav"

        key = f"aiml/music-{uuid.uuid4}.mp3"
        result = await download_from_url_and_to_s3(
            url=music_url, content_type="audio/mp3", key=key
        )
        if not result:
            logging.error("Failed to upload music to S3")

        video_editing_data = state_data["video_editing"]
        video_editing_data["music_url"] = music_url
        await state.update_data(video_editing=video_editing_data)

    except Exception as e:
        # Сбрасываем флаг генерации
        await state.update_data(is_video_generating=False)
        
        await bot.send_message(
            chat_id=chat_id,
            text=Text(Bold("Что то явно не то при генерации музыки...")).as_markdown(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        logging.critical("Error during music generation: {}".format(e))
        print(f"Error: {e}")
        
        # Останавливаем анимацию и удаляем сообщение о загрузке
        stop_animation.set()
        await animation_task
        try:
            await waiting_message.delete()
        except Exception as e:
            logging.warning(f"Error during animation message deletion: {e}")
        
        # НЕ переходим к следующему шагу!
        return
    finally:

        stop_animation.set()
        await animation_task

        try:
            await waiting_message.delete()
        except Exception as e:
            logging.warning(f"Error during animation message deletion: {e}")

        await state.set_state(VideoCreation.combine_music_and_video)
        await proccess_music_merging(state=state)


### Merging music and video
@router.message(VideoCreation.combine_music_and_video)
async def proccess_music_merging(state: FSMContext):

    state_data = await state.get_data()
    chat_id = state_data.get("chat_id")
    user_id = state_data.get("user_id")

    video_url = state_data["video_editing"]["zapcap_video_url"]
    music_url = state_data["video_editing"]["music_url"]

    text = Text("Продолжаем создание полноценного видео...").as_markdown()

    waiting_message = await bot.send_message(
        chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2
    )

    stop_animation = asyncio.Event()

    animation_task = asyncio.create_task(
        animate("Все еще работаем...", stop_animation, waiting_message)
    )
    try:
        merged_video_url = await merge_video_and_music(
            video_url=video_url, music_url=music_url
        )
        # merged_video_url = "https://s3.timeweb.cloud/c9f29c5b-3c3452a4-fb03-4813-a0b1-2fc03a79bc51/merged/07b22c88-1bec-4f90-91b6-bb781466d292.mp4"

        final_video_file = URLInputFile(merged_video_url, filename="your_video.mp4")

        # key = f"final/full-video-{uuid.uuid4()}.mp4"
        # result = await download_from_url_and_to_s3(url=merged_video_url, key=key)
        #
        # if not result:
        #     logging.error("Failed to upload final video to S3")
        try:
            builder = InlineKeyboardBuilder()
            builder.button(text="🔄 Сгенерировать еще видео", callback_data="demo")
            keyboard = builder.as_markup()

            caption = Text(
                Bold("✨ Ваше финальное видео готово! ✨"),
                "\n\n",
                "Вы можете посмотреть статус профиля через команду /profile",
                "\n\n" "Или же использовать кнопку ниже, чтобы создать новое видео. 👇",
            ).as_markdown()

            await bot.send_document(
                chat_id=chat_id,
                document=final_video_file,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=keyboard,
            )

            await state.update_data(is_video_generating=False)

            async with httpx.AsyncClient(timeout=5) as client:
                params = {"credits": 1}
                response = await client.post(
                    f"{WEBHOOK_BASE_URL}/api/users/{user_id}/credits/deduct",
                    params=params,
                )
                if response.status_code == 200:
                    logging.info("DEDUCTED ONE CREDIT")
                else:
                    logging.error(
                        f"Error during credits deducting. Status code: {response.status_code}.\n Details: {response.text}"
                    )
                    raise Exception("CANNOT DEDUCT VIDEO CREDIT")

        except Exception as e:
            await state.update_data(is_video_generating=False)
            text = f"ERROR DURING credits DEDUCT: {str(e)}"
            raise Exception(text)

        state_data = await state.get_data()
        preserved_data = {
            key: state_data.get(key)
            for key in ["chat_id", "user_id", "are_demo_credits_given", "is_video_generating"]
        }
        await state.clear()
        await state.update_data(**preserved_data)

    except Exception as e:
        # Сбрасываем флаг генерации
        await state.update_data(is_video_generating=False)
        
        await bot.send_message(
            chat_id=chat_id,
            text=Text(Bold("Не получилось отправить финальное видео")).as_markdown(),
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        logging.critical("Error during video merging: {}".format(e))
        print(f"Error: {e}")
        
        # Останавливаем анимацию и удаляем сообщение о загрузке
        stop_animation.set()
        await animation_task
        try:
            await waiting_message.delete()
        except Exception as e:
            logging.warning(f"Error during animation message deletion: {e}")
        
        # Очищаем состояние, сохраняя только необходимые данные
        state_data = await state.get_data()
        preserved_data = {
            key: state_data.get(key)
            for key in ["chat_id", "user_id", "are_demo_credits_given"]
        }
        await state.clear()
        await state.update_data(**preserved_data, is_video_generating=False)
        
        return
    finally:

        stop_animation.set()
        await animation_task

        try:
            await waiting_message.delete()
        except Exception as e:
            logging.warning(f"Error during animation message deletion: {e}")

        # await state.set_state(VideoCreation.create_music)
        # await proccess_music_generation(state)
