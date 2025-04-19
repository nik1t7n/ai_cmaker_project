import asyncio
import logging
import json
from typing import List, Dict, Optional

from arq_jobs import WorkerSettings 
from dotenv import load_dotenv

from arq import create_pool
from arq.connections import RedisSettings

# Загрузка переменных окружения
load_dotenv()

# Ключ для хранения истории в Redis
HISTORY_KEY = "video_script:history"

# Системный промпт, который всегда используется
SYSTEM_PROMPT = """
Ты профессиональный автор текстов для видеороликов. Твоя задача - создать ТОЛЬКО текст для озвучивания на тему, которую я предоставлю.

ВАЖНО: Пиши ИСКЛЮЧИТЕЛЬНО текст для озвучки, который будет зачитан диктором слово в слово.

НЕ ВКЛЮЧАЙ в ответ:
- Названия сцен или их описания (например, "[Сцена: Бесси на лугу]")
- Технические указания (например, "[ЧАСТЬ 1: 0:31-2:00]") 
- Имена говорящих (например, "Нарратор:", "Бесси:")
- Инструкции по тону (например, "с теплым голосом")
- Любые теги форматирования (**, *, _)
- Любые метаданные, заголовки или описания видео
- Указания на типы планов, музыку, эффекты

Твой ответ должен быть ТОЛЬКО тем текстом, который будет непосредственно произнесен при озвучивании видео - как единый, связный монолог.

ПРИМЕР ПРАВИЛЬНОГО ОТВЕТА:
Добро пожаловать в мир, где дружба и смелость встречаются на каждом шагу. Сегодня 
мы расскажем вам историю о корове по имени Бесси. Она не просто обычная корова, а 
настоящая героиня нашего времени! Бесси живет на ферме, где растет любимая трава и 
звучит смех детей. Она дружелюбная, игривая и всегда готова помочь своим друзьям. 
Но у Бесси есть особая мечта - увидеть мир за пределами фермы...
...
"""


# ============================ CLIENT: VIDEO SCRIPT GENERATOR ============================

class VideoScriptGenerator:
    """
    Сервис для генерации и уточнения видео-сценариев, адаптированный для Telegram-бота.
    Работает через ARQ и хранит историю в Redis.
    """
    def __init__(self, redis_pool: Optional[object] = None):
        self.logger = logging.getLogger(__name__)
        self.redis_pool = redis_pool  # Ожидается объект, возвращённый create_pool()
        self.system_prompt = SYSTEM_PROMPT

    async def init_redis(self):
        if self.redis_pool is None:
            self.redis_pool = await create_pool(WorkerSettings.redis_settings)
        self.logger.info("Redis pool инициализирован.")

    async def reset_history(self):
        history = {
            "system": self.system_prompt,
            "scenario": None,
            "feedback": None
        }
        await self.redis_pool.set(HISTORY_KEY, json.dumps(history))
        self.logger.info("История сценария сброшена.")

    async def load_history(self) -> Dict[str, Optional[str]]:
        raw = await self.redis_pool.get(HISTORY_KEY)
        if raw:
            return json.loads(raw)
        return {"system": self.system_prompt, "scenario": None, "feedback": None}

    async def update_history(self, scenario: Optional[str] = None, feedback: Optional[str] = None):
        history = await self.load_history()
        if scenario is not None:
            history["scenario"] = scenario
            if history["feedback"] is None:
                history["feedback"] = None
        if feedback is not None:
            history["feedback"] = feedback
        await self.redis_pool.set(HISTORY_KEY, json.dumps(history))
        self.logger.info("История обновлена.")

    async def _enqueue_openai_job(self, messages: List[Dict[str, str]]) -> Optional[str]:
        job = await self.redis_pool.enqueue_job("process_openai_call_job", messages, _defer_by=0)
        if job is None:
            raise RuntimeError("Job was not enqueued; possible duplicate job id?")
        return await job.result(timeout=180)

    async def generate_script(self, concept: str) -> str:
        await self.init_redis()
        await self.reset_history()
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"Create a video script for the following concept: {concept}"}
        ]
        self.logger.info("Отправляем задачу на генерацию сценария.")
        try:
            script = await self._enqueue_openai_job(messages)
            await self.update_history(scenario=script)
            return script
        except asyncio.TimeoutError:
            self.logger.error("Timeout waiting for script generation")
            return "Произошла ошибка при генерации сценария. Пожалуйста, попробуйте снова с более коротким описанием."

    async def refine_script(self, feedback: str) -> str:
        await self.init_redis()
        history = await self.load_history()
        if history.get("scenario") is None:
            raise ValueError("Сценарий не был сгенерирован. Сначала вызовите generate_script().")
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "assistant", "content": history["scenario"]},
            {"role": "user", "content": (
                "Вот сценарий, который предоставил юзер:\n\n"
                f"{history['scenario']}\n\n"
                "ТЕПЕРЬ ТВОЯ ЗАДАЧА СОСТОИТ В ТОМ, ЧТОБЫ ПЕРЕПИСАТЬ СЦЕНАРИЙ ЮЗЕРА "
                "ТОЧЬ В ТОЧЬ СЛЕДУЯ ИНСТРУКЦИЯМ, КОТОРЫЕ Я ТЕБЕ ПРЕДОСТАВИЛ НИЖЕ! "
                "ТОЧНО СЛЕДУЙ ТОМУ, ЧТО НАПИСАНО, ОСНОВЫВАЙСЯ НА ПРЕДЫДУЩЕМ СЦЕНАРИИ\n\n"
                "ИНСТРУКЦИИ:\n\n"
                f"{feedback}"
            )},
        ]
        
        self.logger.debug("\n\n\n------------------\n\n\n")
        self.logger.debug(f"previous scenario:\n\n{ history['scenario']}\n\n")
        self.logger.debug(f"feedback: {feedback}")
        
        await self.update_history(feedback=feedback)
        self.logger.info("Отправляем задачу на уточнение сценария.")
        refined_script = await self._enqueue_openai_job(messages)
        await self.update_history(scenario=refined_script)
        
        self.logger.debug(f"\n\nREFINED SCRIPT:\n {refined_script}")
        
        return refined_script
