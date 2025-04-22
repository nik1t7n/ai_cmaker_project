import urllib.parse
from aiogram.utils.formatting import Text

GREETING_TEXT = Text(
    "👋 Привет! Этот бот поможет тебе создавать рилсы без съёмок, монтажа и долгой подготовки.\n\n"
    "🚀 Попробуй демо-версию, чтобы увидеть возможности сервиса в действии! У вас есть 3 бесплатные демо-генерации!\n\n"
    "📝 Прочитай коротенькую инструкцию о том, что представляет из себя бот\n\n"
    "💎 Или знакомься с нашими тарифами, чтобы выбрать подходящий план для регулярного создания контента."
).as_markdown()

WEBHOOK_BASE_URL = "http://webhook:8000"

BOT_URL = "https://t.me/ai_cmaker_bot"


predefined_message = "Здравствуйте!) я хочу создать своего ИИ Аватара для автоматического создания коротких видео 😎🔥"
predefined_message = urllib.parse.quote(predefined_message) 
chat_username = "Airrrro"
TELEGRAM_LINK_INDIVIDUAL = f"https://t.me/{chat_username}?start&text={predefined_message}"
