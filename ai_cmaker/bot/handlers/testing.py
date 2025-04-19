from aiogram import Router, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InputMediaVideo, URLInputFile
from aiogram.utils.formatting import Bold, Text, Url, Italic
from bot.init import get_bot 
import yaml
from bot.keyboards.keyboards import get_subtitle_styles_inline_keyboard 
import asyncio 


bot, dp = asyncio.run(get_bot())
router = Router()

@router.message(Command("test_send_gif"))
async def cmd_test_gif(message: types.Message, state: FSMContext):
    state_data = await state.get_data()
    chat_id = state_data["chat_id"]

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

    await bot.send_media_group(chat_id=chat_id, media=gifs)
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN_V2,
    )



