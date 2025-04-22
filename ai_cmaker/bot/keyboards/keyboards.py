import yaml
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.constants import TELEGRAM_LINK_INDIVIDUAL


def get_greeting_inline_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру с кнопками "🚀 Полетели пробовать!" и "🏷️ Ознакомиться с тарифами"
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Пробуем!", callback_data="demo")
    builder.button(text="📝 Инструкция", callback_data="instruction")
    builder.button(text="💎 Ознакомиться с тарифами", callback_data="pricing")
    builder.adjust(2, 1)
    return builder.as_markup()


def get_after_instructions_keyboard() -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Пробуем!", callback_data="demo")
    builder.button(text="💎 Тарифы", callback_data="pricing")
    builder.button(text="❌ Вернуться на прошлый шаг", callback_data="back:start")
    builder.adjust(2, 1)
    return builder.as_markup()


def get_script_method_inline_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для выбора способа создания сценария:
    "✍️ Введу свой сценарий" и "🔮 Сгенерирую с помощью ИИ-помощника"
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Введу сам", callback_data="script_method:user")
    builder.button(text="🔮 Сгенерирую с AI", callback_data="script_method:ai")
    builder.adjust(1)
    return builder.as_markup()


def build_avatar_inline_keyboard() -> InlineKeyboardMarkup:
    """
    Создает инлайн-клавиатуру для выбора аватара.
    Каждая кнопка содержит callback_data вида "avatar:<ключ>"
    """
    builder = InlineKeyboardBuilder()
    # Определяем порядок аватаров

    with open("config.yml", "r") as f:
        config = yaml.safe_load(f)

    avatar_names = config["avatar"]["avatar_credentials"].keys()

    for name in avatar_names:
        builder.button(text=name, callback_data=f"avatar:{name}")

    builder.button(text="Вернуться к предыдущему шагу", callback_data="back:start")

    builder.adjust(3, 3, 1)
    return builder.as_markup()


def get_cancel_script_inline_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура, которая отменяет текущий выбор пользователя по написанию
    сценария и возвращает его опять к выбору (ИИ или самому)
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Вернуться к выбору", callback_data="cancel_script")
    builder.adjust(1)
    return builder.as_markup()


def get_back_to_choosing_script_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура, которая отменяет текущий выбор пользователя по написанию
    сценария и возвращает его опять к выбору (ИИ или самому)
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text="❌ Вернуться к выбору", callback_data="back:choosing_script_method"
    )
    builder.adjust(1)
    return builder.as_markup()


def get_subtitle_styles_inline_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    subtitle_styles = ["1", "2", "3", "4", "5", "6"]
    for style in subtitle_styles:
        builder.button(text=style, callback_data=f"subtitle_style:{style}")
    builder.adjust(3, 3)
    return builder.as_markup()


def get_payment_keyboard() -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()

    # Payment options
    builder.button(text="10 видео", callback_data="payment:10")
    builder.button(text="30 видео", callback_data="payment:30")
    builder.button(text="50 видео", callback_data="payment:50")
    builder.button(text="100 видео", callback_data="payment:100")
    builder.button(
        text="Индивидуальный тариф",
        callback_data="individual_tariff",
        url=TELEGRAM_LINK_INDIVIDUAL,
    )

    # Back button
    builder.button(text="❌ Вернуться на прошлый шаг", callback_data="back:start")

    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def get_after_ai_script_generation_inline_keyboard() -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Далее", callback_data="confirm_script")
    builder.button(text="✏ Редактировать сценарий", callback_data="edit_script")
    builder.adjust(2)
    return builder.as_markup()


def get_after_user_script_generation_inline_keyboard() -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Далее", callback_data="confirm_script")
    builder.button(text="✏ Редактировать сценарий", callback_data="edit_user_script")
    builder.adjust(2)
    return builder.as_markup()


def get_payment_confirmation_inline_keyboard() -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()
    builder.button(text="Да, оплатить", callback_data="confirm_payment")
    builder.button(text="Редактировать телефон", callback_data="edit_phone")
    builder.button(text="Редактировать email", callback_data="edit_email")
    builder.adjust(1, 2)
    return builder.as_markup()
