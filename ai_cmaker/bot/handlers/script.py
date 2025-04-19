import asyncio
import logging
import os
import tempfile
import uuid

from aiogram import F, types, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InputMediaVideo, URLInputFile
from aiogram.utils.formatting import Bold, Text, Url, Italic
from aiogram.utils.keyboard import InlineKeyboardBuilder
from openai import OpenAI
import yaml
from bot.init import get_bot
from bot.states import VideoCreation
from bot.keyboards.keyboards import (
    get_after_ai_script_generation_inline_keyboard,
    get_after_user_script_generation_inline_keyboard,
    get_back_to_choosing_script_keyboard,
    get_script_method_inline_keyboard,
    get_subtitle_styles_inline_keyboard,
)

bot, dp = asyncio.run(get_bot())
router = Router()

### Обработчики выбора способа создания сценария ###
@router.callback_query(lambda c: c.data == "script_method:user")
async def user_script_mode_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    text = "Пожалуйста, введите текст сценария для вашего видео."

    inline_kb = get_back_to_choosing_script_keyboard()

    new_text = Text(
        Italic("Вы выбрали режим создания сценария вручную."),
        "\n\n",
        Bold("Я уверен, что вы напишите великолепный сценарий!")
    ).as_markdown()

    kb_message = await bot.send_message(callback.message.chat.id, text, reply_markup=inline_kb)
    await state.update_data(kb_message_id=kb_message.message_id) 
    await callback.message.edit_text(text=new_text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=None)
    await state.set_state(VideoCreation.user_script_input)


@router.callback_query(lambda c: c.data == "script_method:ai")
async def ai_script_mode_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    text = (
        "Вы вошли в режим создания сценария с помощью ИИ. Введите идею или инструкции для сценария.\n\n"
            "💡 Опиши концепцию видео, и я создам сценарий для тебя (отправь текст или голосовое сообщение)"
    )
    inline_kb = get_back_to_choosing_script_keyboard()
    await bot.send_message(callback.message.chat.id, text, reply_markup=inline_kb)
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.set_state(VideoCreation.ai_script_input)



### Обработка ввода пользовательского сценария (текстовое сообщение) ###
@router.message(VideoCreation.user_script_input, F.text)
async def process_user_script(message: types.Message, state: FSMContext):

    state_data = await state.get_data()
    user_script = message.text

    kb_message_id = state_data.get("kb_message_id")

    if kb_message_id:
        try:
            await bot.edit_message_reply_markup(
                chat_id=message.chat.id,
                message_id=kb_message_id,
                reply_markup=None
            )
        except Exception as e:
            # Обработка возможных ошибок (сообщение могло быть удалено и т.д.)
            print(f"Не удалось удалить клавиатуру: {e}")

    keyboard = get_after_user_script_generation_inline_keyboard()

    filename = f"script_{message.from_user.id}_{uuid.uuid4()}.txt"
    temp_dir = tempfile.mkdtemp(dir=os.getcwd())
    filepath = os.path.join(temp_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(user_script)
    
    caption = Text(
        Bold("Хотите использовать этот сценарий для создания видео?")
    ).as_markdown()  

    # Отправляем файл
    await message.answer_document(
        FSInputFile(filepath, filename="внутри_этого_файла_лежит_ваш_сценарий.txt"),
        caption=caption,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    os.remove(filepath)
    os.rmdir(temp_dir)

    await state.update_data(script=user_script)
    await state.set_state(VideoCreation.script_confirm)


### Обработка редактирования пользовательского сценария ###
@router.callback_query(lambda c: c.data == "edit_user_script")
async def edit_user_script(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Введите новый текст сценария.")

    try:
        # Пытаемся отредактировать подпись к документу
        await callback.message.edit_caption(
            caption=Text(
                Bold("Окей, понял, давайте редактировать сценарий)")
            ).as_markdown(),
            reply_markup=None,  # Убираем кнопки
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        await callback.message.answer("Введите обновленный текст сценария:")
    except Exception as e:
        await state.update_data(is_video_generating=False)
        # Если не получается отредактировать, отправляем новое сообщение
        logging.error(f"Ошибка при редактировании подписи: {e}")
        await callback.message.answer("Введите обновленный текст сценария:")

    await state.set_state(VideoCreation.user_script_input)


### Обработка ввода сценария для ИИ (текстовое сообщение) ###
@router.message(VideoCreation.ai_script_input, F.content_type.in_({"text", "voice"}))
async def process_ai_script_input(message: types.Message, state: FSMContext):

    if message.content_type == "voice":
        # Сначала сообщаем, что обрабатываем голосовое сообщение
        processing_msg = await message.answer("🎤 Обрабатываю голосовое сообщение...")

        try:
            # Получаем файл голосового сообщения
            voice_file = await bot.get_file(message.voice.file_id)
            voice_file_path = voice_file.file_path

            # Скачиваем файл
            voice_content = await bot.download_file(voice_file_path)

            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
                # Записываем содержимое в файл
                temp_file.write(voice_content.read())
                temp_file_path = temp_file.name

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            with open(temp_file_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="gpt-4o-transcribe", file=audio_file, response_format="text"
                )

            os.unlink(temp_file_path)

            # Обновляем сообщение о статусе
            await processing_msg.delete()

            # Используем транскрибированный текст как концепцию
            concept = transcription

        except Exception as e:
            logging.error(f"Ошибка при обработке голосового сообщения: {e}")
            await message.answer(
                "❌ Упс, какие то проблемки со слухом. Попробуйте отправить голосовое сообщение заново)"
            )
            return
    else:
        # Если сообщение текстовое, просто берем его текст
        concept = message.text

    state_data = await state.get_data()
    # existing_script_message_id = data.get("script_message_id")

    waiting_message = await message.answer("⏳Генерирую сценарий...")

    animation_symbols = ["⏳", "⌛"]
    for _ in range(10):
        for symbol in animation_symbols:
            await asyncio.sleep(1)
            try:
                await waiting_message.edit_text(f"{symbol} Генерирую сценарий...")
            except Exception as e:
                logging.warning(f"Ошибка при обновлении анимации: {e}")
                break

    try:
        from video_script_generator import VideoScriptGenerator

        keyboard = get_after_ai_script_generation_inline_keyboard()

        script_generator = VideoScriptGenerator()
        logging.debug(f"\n\n\nIS EDITED:\n\n{state_data.get('is_script_edited')}\n\n\n")
        if "is_script_edited" in state_data and state_data["is_script_edited"]:
            logging.debug("\n\n\nWE RUN REFINE SCRIPT\n\n\n")
            script = await script_generator.refine_script(concept)
        else:
            logging.debug("\n\n\nWE RUN GENERATE SCRIPT\n\n\n")
            script = await script_generator.generate_script(concept)
        await state.update_data(script=script)

        if waiting_message:
            try:
                await waiting_message.delete()
            except Exception as e:
                logging.warning(f"Не удалось удалить сообщение: {e}")

        filename = f"aiscript_{message.from_user.id}_{uuid.uuid4()}.txt"
        temp_dir = tempfile.mkdtemp(dir=os.getcwd())
        filepath = os.path.join(temp_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(script)
        
        caption = Text(
            Bold("Хотите использовать этот сценарий для создания видео?")
        ).as_markdown()

        # Отправляем файл
        script_message = await message.answer_document(
            document=FSInputFile(filepath, filename="внутри_этого_файла_лежит_ваш_сценарий.txt"),
            caption=caption,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN_V2,
        )

        os.remove(filepath)
        os.rmdir(temp_dir)

        await state.update_data(
            confirm_message_id=script_message.message_id, script=script
        )
        await state.set_state(VideoCreation.script_confirm)

    except asyncio.TimeoutError:
        if waiting_message:
            try:
                await waiting_message.delete()
            except Exception as e:
                logging.warning(f"Не удалось удалить сообщение waiting_message: {e}")
        await message.answer(
            "К сожалению, генерация сценария заняла слишком много времени. Пожалуйста, попробуйте еще раз с более коротким описанием."
        )
        keyboard = get_script_method_inline_keyboard()
        await message.answer("Как ты хочешь создать сценарий?", reply_markup=keyboard)
        await state.set_state(VideoCreation.choosing_script_method)

    except Exception as e:
        await state.update_data(is_video_generating=False)
        if waiting_message:
            try:
                await waiting_message.delete()
            except Exception as e:
                logging.warning(f"Не удалось удалить сообщение waiting_message: {e}")
        logging.error(f"Ошибка при генерации сценария: {e}")
        await message.answer(
            "Произошла ошибка при генерации сценария. Пожалуйста, попробуйте еще раз позже."
        )
        keyboard = get_script_method_inline_keyboard()
        await message.answer("Как ты хочешь создать сценарий?", reply_markup=keyboard)
        await state.set_state(VideoCreation.choosing_script_method)


### Обработчик редактирования сценария (ИИ) ###
@router.callback_query(lambda c: c.data == "edit_script")
async def edit_script(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    state_data = await state.get_data()
    
    try:
        # Редактируем подпись к документу
        await callback.message.edit_caption(
            caption=Text(
                Bold("Окей, понял, давайте редактировать сценарий)")
            ).as_markdown(),
            reply_markup=None,  # Убираем кнопки
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        await callback.message.answer("Введите уточненные инструкции для нового ИИ-сценария:")
        # Устанавливаем флаг редактирования
        logging.debug(f"\n\n\nУСТАНАВЛИВАЕМ ФЛАГ\n\n\n")
        await state.update_data(is_script_edited=True)
    except Exception as e:
        # Если не получается отредактировать, отправляем новое сообщение
        logging.error(f"Ошибка при редактировании подписи: {e}")
        await callback.message.answer("Введите уточненные инструкции для сценария:")
    
    # Устанавливаем состояние для ввода уточнений 
    await state.set_state(VideoCreation.ai_script_input)

@router.callback_query(lambda c: c.data == "confirm_script")
async def choose_subtitles_style(callback: types.CallbackQuery, state: FSMContext):
    state_data = await state.get_data()

    await state.update_data(is_script_edited=False)

    with open("config.yml", "r") as f:
        config = yaml.safe_load(f)

    gifs = []

    for str_number, value in config["video_editing"]["subtitle_styles"].items():
        file = FSInputFile(value["local_path"])
        gifs.append(InputMediaVideo(media=file))

    keyboard = get_subtitle_styles_inline_keyboard()

    text = Text(
        Bold("Выше представлены 6 стилей субтитров"),
        "\n\n",
        "Выберите один из них и поехали дальше)",
    ).as_markdown()

    await callback.message.edit_caption(
        caption=Text(
            Bold("Сценарий принят!"),
        ).as_markdown(),
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=None)

    await callback.message.answer_media_group(media=gifs)
    await callback.message.answer(
        text=text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN_V2,
    )


