import asyncio
from aiogram import types
import logging


async def animate(
    message: str, stop_animation: asyncio.Event, waiting_message: types.Message
):
    animation_symbols = ["⏳", "⌛"]
    while not stop_animation.is_set():
        for symbol in animation_symbols:
            await asyncio.sleep(1.5)
            try:
                await waiting_message.edit_text(f"{symbol} {message}")
            except Exception as e:
                logging.warning(f"Ошибка при обновлении анимации: {e}")
                break
