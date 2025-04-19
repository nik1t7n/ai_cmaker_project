import os
import logging
import asyncio
from typing import Dict, List

from aiogram.enums import ParseMode
from aiogram.utils.formatting import Bold, Text
import aiohttp
from arq import Retry, create_pool

from arq.connections import RedisSettings
from dotenv import load_dotenv
import httpx
from bot.constants import WEBHOOK_BASE_URL
from bot.init import get_bot
from services.aiml import MusicGenerator
from services.heygen import AuthenticationError, HeygenAPIError, HeygenProcessor, InvalidParameterError, ResourceNotFoundError, VideoGenerationConfig
from services.openai import OpenAIInteractions
from services.zapcap import ZapcapProcessor


load_dotenv()


async def process_openai_call_job(
    _ctx,
    messages: List[Dict[str, str]],
    model: str = "gpt-4o",
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> str:
    """
    Worker function for sending an async HTTP request to the OpenAI API.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")

    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]


async def heygen_generate_video_job(
    _ctx, processor: HeygenProcessor, config: VideoGenerationConfig
):
    try:
        video_url = await processor.generate_video(config)
        return video_url
    except AuthenticationError as e:
        # Ошибка аутентификации (неверный API ключ)
        error_message = "Ошибка аутентификации в Heygen API. Проверьте правильность API ключа."
        logging.error(f"{error_message} Детали: {e}")
        # Возвращаем информативную ошибку, которую можно показать пользователю
        return {"error": True, "message": error_message, "code": "auth_error", "details": str(e)}
    
    except ResourceNotFoundError as e:
        # Определяем, какой ресурс не найден по сообщению об ошибке
        if "Avatar" in e.error_message and "not found" in e.error_message:
            error_message = f"Указанный аватар не найден или недоступен. ID: {config.avatar_id}"
        elif "Voice" in e.error_message and "not found" in e.error_message:
            error_message = f"Указанный голос не найден или недоступен. ID: {config.voice_id}"
        else:
            error_message = "Запрашиваемый ресурс не найден в Heygen API."
        
        logging.error(f"{error_message} Детали: {e}")
        return {"error": True, "message": error_message, "code": "not_found", "details": str(e)}
    
    except InvalidParameterError as e:
        # Ошибка неверных параметров
        error_message = "Один или несколько параметров для создания видео указаны неверно."
        logging.error(f"{error_message} Детали: {e}")
        return {"error": True, "message": error_message, "code": "invalid_params", "details": str(e)}
    
    except HeygenAPIError as e:
        # Общая ошибка API Heygen
        error_message = f"Ошибка при обращении к Heygen API: {e.error_message}"
        logging.error(f"{error_message} Статус: {e.status_code}, Код: {e.error_code}")
        return {"error": True, "message": error_message, "code": e.error_code, "details": str(e)}
    
    except Exception as e:
        # Прочие непредвиденные ошибки
        error_message = "Произошла непредвиденная ошибка при создании видео. Пожалуйста, попробуйте позже."
        logging.exception(f"Непредвиденная ошибка в heygen_generate_video_job: {e}")
        
        # Для сетевых ошибок и ошибок сервера - ретраи
        if hasattr(_ctx, "job_try") and "Retry" in globals():
            # Если доступна Retry, используем ее для сетевых ошибок
            # Проверяем, является ли это сетевой ошибкой (например, aiohttp.ClientError)
            if isinstance(e, (aiohttp.ClientError, asyncio.TimeoutError)) or (
                hasattr(e, "status_code") and 500 <= getattr(e, "status_code") <= 599
            ):
                # Для сетевых ошибок пробуем повторить
                raise Retry(defer=_ctx["job_try"] * 5)
        
        return {"error": True, "message": error_message, "code": "general_error", "details": str(e)}


async def zapcap_edit_video_job(
    _ctx, avatar_video_url: str, subtitle_template_id: str
) -> str:

    processor = ZapcapProcessor(os.getenv("ZAPCAP_API_KEY"))

    try:
        download_url, transcript, duration = await processor.process_video(
            avatar_video_url,
            upload_type="url",
            broll_percent=30,
            template_id=subtitle_template_id,
        )
    except httpx.HTTPStatusError as e:
        # if there is an error due to network or zapcap status - we retry
        if 500 <= e.response.status_code <= 600:
            raise Retry(defer=_ctx["job_try"] * 5)

    return download_url


async def generate_music_job(_ctx, script: str) -> str:
    openai_interactor = OpenAIInteractions()
    generator = MusicGenerator(os.getenv("AIML_API_KEY"))

    try:
        prompt_for_music_gen = await openai_interactor.agenerate_prompt_for_music(
            script=script
        )
    except httpx.HTTPStatusError as e:
        # if there is an error due to network or openai status - we retry
        if 500 <= e.response.status_code <= 600:
            raise Retry(defer=_ctx["job_try"] * 5)

    try:
        audio_url = await generator.generate_music(
            prompt_for_music_gen, steps=300, seconds_total=30
        )
    except httpx.HTTPStatusError as e:
        # if there is an error due to network or AIML status - we retry
        if 500 <= e.response.status_code <= 600:
            raise Retry(defer=_ctx["job_try"] * 5)

    return audio_url


async def check_payment_status_job(ctx, user_id, chat_id, order_id, credits_amount: int):
    """
    Фоновая задача для проверки статуса платежа
    """
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            response = await client.post(
                f"{WEBHOOK_BASE_URL}/api/payments/status?order_id={order_id}",
                headers={"accept": "application/json"},
                content="",
            )

            if response.status_code == 200:
                data = response.json()
                status = data.get("status")

                if status == "completed":

                    add_credits_response = await client.post(
                        f"{WEBHOOK_BASE_URL}/api/users/{user_id}/credits/add",
                        params={"credits": credits_amount, "update_purchase_time": "true"}
                    )

                    logging.debug(f"\n\nWE ARE ADDING {credits_amount} CREDITS HERE\n\n")

                    if add_credits_response.status_code == 200:
                        
                        success_message = Text(
                                Bold("✅ Оплата успешно прошла!"),
                                "\n\n",
                                f"🎉 Вам начислено {credits_amount} кредитов.",
                                "\n\n",
                                "📊 Подробную информацию об использовании, остатке и других деталях можно посмотреть по команде /profile"
                            ).as_markdown()
                            
                        bot, dp = await get_bot()
                        await bot.send_message(chat_id=chat_id, text=success_message, parse_mode=ParseMode.MARKDOWN_V2)
                        return True  # Возвращаем True, чтобы остановить проверку

            return False  # Продолжаем проверку

        except Exception as e:
            logging.error(f"Ошибка при проверке статуса платежа: {e}")
            return False


class WorkerSettings:
    redis_settings = RedisSettings(host="redis", port=6379)
    functions = [
        process_openai_call_job,
        heygen_generate_video_job,
        zapcap_edit_video_job,
        generate_music_job,
        check_payment_status_job,
    ]
    job_timeout = 1200

# processor = HeygenProcessor(api_key=os.getenv("HEYGEN_API_KEY"))
#     config = VideoGenerationConfig(
#         content=state_data["user_script"],
#         voice_id=state_data["avatar"]["voice_id"],
#         avatar_id=state_data["avatar"]["avatar_id"],
#         dimensions=(720, 1280),
#         speed=1.0,
#     )
#     try:
#         video_url = await processor.generate_video(config)
#         logging.info("Generated video URL: '{}'.".format(video_url))
#         print(f"Generated video URL: {video_url}")

#         await callback.message.answer(
#             Text(Bold("Ваша ссылка:"), "\n\n", Url(video_url)).as_markdown()
#         )

#         await waiting_message.delete()
