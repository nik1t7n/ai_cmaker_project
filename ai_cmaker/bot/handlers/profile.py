import logging
from datetime import datetime

import httpx
from aiogram import Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.formatting import Bold, Text
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.constants import WEBHOOK_BASE_URL

router = Router()


@router.message(Command("profile"))
async def cmd_profile(message: types.Message, state: FSMContext):
    state_data = await state.get_data()

    user_id = state_data.get("user_id")
    if not user_id:
        user_id = message.from_user.id
        await state.update_data(user_id=user_id)

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(f"{WEBHOOK_BASE_URL}/api/users/{user_id}")

        # if somehow user does not exists
        # it is possible only if he pressed /profile command before /start
        if response.status_code == 404:
            warning_msg = Text(
                Bold(
                    "Извините, но перед началом работы с ботом - вам следует активировать его, использовав команду /start"
                )
            ).as_markdown()
            await message.answer(text=warning_msg, parse_mode=ParseMode.MARKDOWN_V2)
        if response.status_code == 200:
            data = response.json()
            credits_left = data.get("credits_left", 0)
            credits_expire_date_str = data.get("credits_expire_date")

            # Формируем сообщение для профиля пользователя

            # Обрабатываем дату истечения
            if credits_expire_date_str:
                try:
                    # Парсим дату истечения
                    credits_expire_date = datetime.fromisoformat(
                        credits_expire_date_str.replace("Z", "+00:00")
                    )
                    current_date = datetime.now()

                    # Форматируем дату истечения в читаемом виде
                    formatted_expire_date = credits_expire_date.strftime(
                        "%d %B %Y года"
                    )
                    formatted_expire_date = (
                        formatted_expire_date.replace("January", "января")
                        .replace("February", "февраля")
                        .replace("March", "марта")
                        .replace("April", "апреля")
                        .replace("May", "мая")
                        .replace("June", "июня")
                        .replace("July", "июля")
                        .replace("August", "августа")
                        .replace("September", "сентября")
                        .replace("October", "октября")
                        .replace("November", "ноября")
                        .replace("December", "декабря")
                    )

                    # Проверяем, истекла ли подписка
                    if current_date > credits_expire_date:
                        # Подписка истекла
                        profile_text = Text(
                            Bold("📊 Ваш профиль"),
                            "\n\n",
                            Bold("🔴 Ваша подписка истекла"),
                            "\n",
                            f"Дата истечения: {formatted_expire_date}",
                            "\n",
                            Bold("Доступные кредиты: 0"),
                        )
                        credits_left = 0
                    else:
                        # Подписка активна, вычисляем оставшиеся дни
                        days_left = (credits_expire_date - current_date).days
                        profile_text = Text(
                            Bold("📊 Ваш профиль"),
                            "\n\n",
                            Bold("🟢 Ваша подписка активна"),
                            "\n\n",
                            f"Дата истечения: {formatted_expire_date}",
                            "\n\n",
                            Bold(f"Осталось дней: {days_left}"),
                            "\n",
                            Bold(f"Доступные кредиты: {credits_left}"),
                        )

                except (ValueError, TypeError):
                    # Если возникла ошибка при обработке даты
                    profile_text = Text(
                        "⚠️ Информация о сроке действия подписки недоступна",
                        "\n",
                        Bold(f"Доступные кредиты: {credits_left}"),
                    )
            else:
                # Если дата истечения не указана
                profile_text = Text(
                    "⚠️ У вас нет активной подписки",
                )

            # Создаем клавиатуру с кнопкой покупки, если подписка истекла или кредитов мало
            builder = None
            builder = InlineKeyboardBuilder()
            builder.row(
                types.InlineKeyboardButton(
                    text="💳 Пополнить кредиты", callback_data="pricing"
                )
            )

            # Отправляем сообщение
            await message.answer(
                profile_text.as_markdown(),
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=builder.as_markup() if builder else None,
            )
        else:
            # Если запрос не удался
            error_text = Text(
                Bold("❌ Не удалось получить информацию о профиле"),
                "\n\n",
                "Пожалуйста, попробуйте позже или обратитесь в поддержку.",
            )
            await message.answer(
                error_text.as_markdown(), parse_mode=ParseMode.MARKDOWN_V2
            )
