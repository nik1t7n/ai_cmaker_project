from aiogram import types, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.utils.formatting import Text
from bot.constants import GREETING_TEXT
from bot.keyboards.keyboards import get_greeting_inline_keyboard, get_script_method_inline_keyboard
from bot.states import VideoCreation


router = Router()


@router.callback_query(lambda c: c.data == "back:start")
async def handle_back_to_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    greeting_text = GREETING_TEXT

    keyboard = get_greeting_inline_keyboard()
    await callback.message.answer(greeting_text, reply_markup=keyboard, parse_mode=ParseMode.MARKDOWN_V2)
    await callback.message.edit_reply_markup(
        parse_mode=ParseMode.MARKDOWN_V2, reply_markup=None
    )


@router.callback_query(lambda c: c.data == "back:choosing_script_method") 
async def handle_back_to_script_method(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    text = Text(
        "Выберите способ создания сценария:\n",
    ).as_markdown()
    script_method_keyboard = get_script_method_inline_keyboard()

    await callback.message.answer(
        text=text,
        reply_markup=script_method_keyboard,
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    await callback.message.edit_text(
        text=Text("Без проблем, давайте заново!").as_markdown(),
        parse_mode=ParseMode.MARKDOWN_V2, reply_markup=None
    )
    await state.set_state(VideoCreation.choosing_script_method)


