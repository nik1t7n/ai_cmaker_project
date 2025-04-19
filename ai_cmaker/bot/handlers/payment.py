import asyncio
import logging
import os
import re
import tempfile
import uuid
from datetime import datetime, timedelta

import httpx
import yaml
from aiogram import F, Router, types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InputMediaVideo, URLInputFile
from aiogram.utils.formatting import Bold, Italic, Text, Url, as_marked_list
from aiogram.utils.keyboard import InlineKeyboardBuilder
from arq import create_pool
from openai import OpenAI

from arq_jobs import WorkerSettings
from bot.constants import WEBHOOK_BASE_URL
from bot.init import get_bot
from bot.keyboards.keyboards import (
    get_back_to_choosing_script_keyboard,
    get_payment_confirmation_inline_keyboard,
    get_script_method_inline_keyboard,
    get_subtitle_styles_inline_keyboard,
)
from bot.schemas import PackageType
from bot.states import PaymentForm, VideoCreation

bot, dp = asyncio.run(get_bot())
router = Router()


async def start_payment_checker(
    bot, user_id, chat_id, order_id, credits_amount: int, state: FSMContext
):
    """
    Запускает фоновую задачу для проверки статуса платежа
    """
    redis_pool = await create_pool(WorkerSettings.redis_settings)

    # Время начала проверки
    start_time = datetime.now()
    # Конечное время (15 минут)
    end_time = start_time + timedelta(minutes=15)

    # Проверяем статус каждые 10 секунд в течение указанных минут
    logging.debug("\n\nLAUNCH CHECK_PAYMENT_JOB ")
    while datetime.now() < end_time:
        job = await redis_pool.enqueue_job(
            "check_payment_status_job",
            user_id,
            chat_id,
            order_id,
            credits_amount,
        )

        # Ждем результат выполнения задачи
        result = await job.result()

        # Если платеж успешно завершен, прекращаем проверку
        if result:
            logging.debug("\n\nWE GOT RESULT - MUST CLOSE\n\n")
            await redis_pool.close()
            return  # <-- Эта строка работает правильно, но может быть проблема с асинхронным выполнением

        logging.debug("\n\nSTILL NO RESULT\n\n")
        # Ждем указанных секунд перед следующей проверкой
        await asyncio.sleep(10)

    # Если по истечении указанных минут платеж не прошел, отправляем сообщение "КОНЕЦ"
    error_msg = Text(
        Bold("Произошла какая то ошибка или вы не успели выполнить оплату!"),
        "\n\n",
        "Пожалуйста, попробуйте совершить оплату заново",
    ).as_markdown()
    await bot.send_message(chat_id=chat_id, text=error_msg, parse_mode=ParseMode.MARKDOWN_V2)
    await state.set_state(PaymentForm.confirmation)
    await redis_pool.close()


def normalize_phone(raw_phone: str) -> str | None:
    # Удаляем всё, кроме цифр
    digits = re.sub(r"\D", "", raw_phone)

    # Словарь с кодами стран и длиной номера без кода
    country_codes = {
        "996": {"name": "Кыргызстан", "length": 9},  # +996 XXX XXX XXX
        "7": {"name": "Россия/Казахстан", "length": 10},  # +7 XXX XXX XX XX
        "998": {"name": "Узбекистан", "length": 9},  # +998 XX XXX XX XX
        "375": {"name": "Беларусь", "length": 9},  # +375 XX XXX XX XX
    }

    # Определяем страну по коду
    country_code = None
    country_name = None

    for code, info in country_codes.items():
        if digits.startswith(code):
            country_code = code
            country_name = info["name"]
            expected_length = info["length"]
            digits_without_code = digits[len(code) :]
            break

    # Если номер начинается с 0, считаем что это местный формат для Кыргызстана
    if digits.startswith("0") and country_code is None:
        country_code = "996"
        country_name = "Кыргызстан"
        expected_length = country_codes[country_code]["length"]
        digits_without_code = digits[1:]  # Убираем ведущий 0

    # Если код страны не определен, возвращаем None
    if country_code is None:
        return None

    # Проверяем длину номера без кода страны
    if len(digits_without_code) == expected_length:
        return f"+{country_code}{digits_without_code}"  # Возвращаем в международном формате
    else:
        return None


def is_valid_email(email: str) -> bool:
    """
    Проверяет, является ли email корректным по базовому паттерну.
    """
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.fullmatch(pattern, email.strip()))


async def handle_any_payment(amount: str, callback: types.CallbackQuery):
    intro_text = Text(
        Bold(f"🎉 Вы выбрали тариф с {amount} генерациями! 🎉"),
        "\n\n",
        "💳 Приступим к оплате!",
        "\n\n",
        Bold("Введите, пожалуйста, свой номер телефона в одном из следующих форматов:"),
        "\n\n",
        "📱 Кыргызстан: +996 XXX XXX XXX",
        "\n",
        "📱 Россия/Казахстан: +7 XXX XXX XX XX",
        "\n",
        "📱 Узбекистан: +998 XX XXX XX XX",
        "\n",
        "📱 Беларусь: +375 XX XXX XX XX",
        "\n\n",
        "⚠️ Важно! Номер должен быть введен в международном формате с кодом страны.",
        "\n",
        "Для кыргызских номеров также допустимы форматы:",
        "\n",
        "• 996 XXX XXX XXX",
        "\n",
        "• 0XXX XXX XXX",
    ).as_markdown()
    await callback.message.answer(intro_text, parse_mode=ParseMode.MARKDOWN_V2)


async def show_confirmation(message: types.Message, state: FSMContext):
    state_data = await state.get_data()

    confirm_msg = Text(
        Bold("Прекрасно, мы почти закончили, давайте все перепроверим:"),
        "\n\n",
        f"Телефон: {state_data.get('user_phone', 'Не указан')}",
        "\n",
        f"Почта: {state_data.get('user_email', 'Не указана')}",
        "\n",
        f"Пакет: {state_data.get('package', 'Не выбран')} видео",
        "\n\n",
        "Все верно?",
    ).as_markdown()

    keyboard = get_payment_confirmation_inline_keyboard()
    await message.answer(
        confirm_msg, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard
    )
    await state.set_state(PaymentForm.confirmation)


@router.callback_query(lambda c: c.data == "payment:10")
async def handle_10_payment(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    await handle_any_payment("10", callback)

    await state.update_data(package=PackageType.PACK_10)
    await state.set_state(PaymentForm.waiting_for_phone)


@router.callback_query(lambda c: c.data == "payment:30")
async def handle_30_payment(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    logging.debug("\n\nSTARTING HANDLING 30 VIDEOS PAYMENT\n\n")
    await handle_any_payment("30", callback)
    logging.debug("\n\n30 VIDEOS PAYMENT HANDLED\n\n")

    await state.update_data(package=PackageType.PACK_30)
    await state.set_state(PaymentForm.waiting_for_phone)


@router.callback_query(lambda c: c.data == "payment:50")
async def handle_50_payment(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    await handle_any_payment("50", callback)

    await state.update_data(package=PackageType.PACK_50)
    await state.set_state(PaymentForm.waiting_for_phone)


@router.callback_query(lambda c: c.data == "payment:100")
async def handle_100_payment(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    await handle_any_payment("100", callback)

    await state.update_data(package=PackageType.PACK_100)
    await state.set_state(PaymentForm.waiting_for_phone)


@router.message(PaymentForm.waiting_for_phone)
async def process_user_phone(message: types.Message, state: FSMContext):

    raw_phone = message.text
    phone = normalize_phone(raw_phone=raw_phone)

    if not phone:
        error_msg = Text(
            "Пожалуйста, введите телефон в корректном формате, как указано выше)"
        ).as_markdown()
        await message.answer(error_msg, parse_mode=ParseMode.MARKDOWN_V2)
        return

    await state.update_data(user_phone=phone)

    state_data = await state.get_data()

    user_email = state_data.get("user_email")

    if user_email and user_email.strip():
        await show_confirmation(message=message, state=state)
    else:
        email_msg = Text(
            "Отлично, теперь введите свой email.",
            "\n",
            "Например: example@gmail.com",
        ).as_markdown()

        await message.answer(text=email_msg, parse_mode=ParseMode.MARKDOWN_V2)

        await state.set_state(PaymentForm.waiting_for_email)


@router.message(PaymentForm.waiting_for_email)
async def process_user_email(message: types.Message, state: FSMContext):

    email = message.text

    state_data = await state.get_data()

    if not is_valid_email(email):
        error_msg = Text(
            "Некорректный формат email. Пожалуйста, введите заново в правильном формате.",
            "\n",
            "Например: example@gmail.com",
            "\n\n",
            "Введите заново: ",
        ).as_markdown()
        await message.answer(error_msg, parse_mode=ParseMode.MARKDOWN_V2)
        return

    await state.update_data(user_email=email)

    state_data = await state.get_data()

    confirm_msg = Text(
        Bold("Прекрасно, мы почти закончили, давайте все перепроверим:"),
        "\n\n",
        f"Телефон: {state_data['user_phone']}",
        "\n",
        f"Почта: {state_data['user_email']}",
        "\n",
        f"Пакет: {state_data['package']} видео",
        "\n\n",
        "Все верно?",
    ).as_markdown()
    keyboard = get_payment_confirmation_inline_keyboard()
    await message.answer(
        confirm_msg, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=keyboard
    )
    await state.set_state(PaymentForm.confirmation)


@router.callback_query(lambda c: c.data == "edit_phone")
async def handle_edit_phone(callback: types.CallbackQuery, state: FSMContext):

    await callback.answer()

    phone_msg = Text(
        "Введите, пожалуйста, номер телефона заново:",
    ).as_markdown()

    await callback.message.answer(phone_msg, parse_mode=ParseMode.MARKDOWN_V2)

    # Переходим в состояние ввода телефона
    await state.set_state(PaymentForm.waiting_for_phone)


@router.callback_query(lambda c: c.data == "edit_email")
async def handle_edit_email(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    email_msg = Text(
        "Введите, пожалуйста, email заново:",
    ).as_markdown()

    await callback.message.answer(email_msg, parse_mode=ParseMode.MARKDOWN_V2)

    # Переходим в состояние ввода email
    await state.set_state(PaymentForm.waiting_for_email)


@router.callback_query(PaymentForm.confirmation, F.data == "confirm_payment")
async def confirm_payment(callback: types.CallbackQuery, state: FSMContext):

    state_data = await state.get_data()

    user_id = state_data["user_id"]
    package = state_data["package"]
    user_phone = state_data["user_phone"]
    user_email = state_data["user_email"]

    async with httpx.AsyncClient(timeout=10) as client:

        payload = {
            "user_id": user_id,
            "package": package,
            "user_phone": user_phone,
            "user_email": user_email,
        }

        logging.debug(f"\n\nPAYLOAD:\n\n {payload}\n\n")

        response = await client.post(f"{WEBHOOK_BASE_URL}/api/payments", json=payload)
        if response.status_code != 201:
            raise Exception("")

        logging.debug("\n\nPAYMENT CREATED\n\n")

        data = response.json()

        payment_url = data.get("payment_url")
        order_id = data.get("order_id")

        await state.update_data(order_id=order_id)

    link_msg = Text(
        Bold(
            "Ссылка на оплату закреплена в кнопке. У вас есть 15 минут на совершение платежа"
        )
    ).as_markdown()

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="Оплатить", url=payment_url))

    await callback.message.answer(
        text=link_msg,
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=builder.as_markup(),
    )

    chat_id = state_data["chat_id"]

    logging.debug("\n\nSTARTING TASK TO CHECK PAYMENTS\n")
    logging.debug(f"PAYLOAD: {user_id}\n{chat_id}\n{order_id}\n{int(package)}\n\n")
    asyncio.create_task(
        start_payment_checker(
            callback.bot, user_id, chat_id, order_id, credits_amount=int(package), state=state
        )
    )
