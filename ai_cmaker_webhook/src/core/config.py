import os
from dotenv import load_dotenv

load_dotenv()


SUBSCRIPTION_DURATION = 28  # days
BOT_LINK = "https://t.me/ai_cmaker_bot"

async def get_package_amounts():
    return {
        "10": {
            "name": "Small Pack",
            "price": 1050,
            "description": "User have bought 10 videos with price 1050 soms"
        },
        "30": {
            "name": "Medium Pack",
            "price": 3900,
            "description": "User have bought 30 videos with price 3900 soms"
        },
        "50": {
            "name": "Large Pack",
            "price": 6100,
            "description": "User have bought 50 videos with price 6100 soms"
        },
        "100": {
            "name": "Premium Pack",
            "price": 11750,
            "description": "User have bought 100 videos with price 11750 soms"
        }
    }

database_url = os.getenv("DATABASE_URL")
