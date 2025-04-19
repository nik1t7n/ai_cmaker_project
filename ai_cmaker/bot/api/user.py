from datetime import datetime, timezone
import logging

import httpx
from aiogram import types
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

from bot.constants import WEBHOOK_BASE_URL


async def create_user(
    message: types.Message, state: FSMContext, error_msg: str
):
    async with httpx.AsyncClient() as client:
        try:
            state_data = await state.get_data()
            user_id = state_data["user_id"]
            payload = {"user_id": user_id}
            response = await client.post(f"{WEBHOOK_BASE_URL}/api/users", json=payload)

            if response.status_code == 201:
                logging.info("User has been successfully created!")
                await state.update_data(user_id=user_id)
            elif response.status_code == 409:
                logging.debug(
                    "You are trying to create already existing user. Passing further"
                )
                pass  # because we have already registered this user
            else:
                logging.warning(
                    f"Unexpected server answer during user creation.\n"
                    f"Status: {response.status_code}\n"
                    f"Details: {response.text}"
                )
                await message.answer(
                    error_msg, parse_mode=ParseMode.MARKDOWN_V2
                )
        except httpx.RequestError as exc:
            logging.critical("Critical error during user creation", f"Details: {exc}")
            raise Exception(f"Error during regitering user: {exc}")


async def add_credits(
    message: types.Message, state: FSMContext, credits_amount: int
):
    state_data = await state.get_data()
    user_id = state_data["user_id"]

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            add_credits_response = await client.post(
                f"{WEBHOOK_BASE_URL}/api/users/{user_id}/credits/add",
                params={"credits": credits_amount, "update_purchase_time": "true"}
            )

            if add_credits_response.status_code == 200:
                return True 
            else:
                logging.error(
                        f"Unexpected error during credits adding",
                        f"Status code: {add_credits_response.status_code}",
                        f"Details: {add_credits_response.text}"
                    )
                
        except Exception as e:
            logging.critical(f"Error during adding credits: {e}")
            raise Exception(f"Error during adding credits: {e}")


async def check_user_credits(user_id: int):
    async with httpx.AsyncClient(timeout=10) as client:

        response = await client.get(f"{WEBHOOK_BASE_URL}/api/users/{user_id}")

        if response.status_code == 200:
            data = response.json()
            credits_left = data.get("credits_left")

            # "credits_expire_date": "2025-05-12T03:38:54.650742",
            credits_expire_date = datetime.fromisoformat(data.get("credits_expire_date"))
            current_date = datetime.now()

            if credits_left <= 0 or current_date > credits_expire_date: 
                return False 

        else:
            return False 

    return True
