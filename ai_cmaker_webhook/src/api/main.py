from fastapi import APIRouter
from src.api import webhook, user, payment 

api_router = APIRouter()
api_router.include_router(webhook.router, tags=["Webhook"], prefix="")
api_router.include_router(user.router, tags=["User"], prefix="/api/users")
api_router.include_router(payment.router, tags=["Payment"], prefix="/api")
# api_router.include_router(user_router, tags=["User"], prefix="/user")
# api_router.include_router(video_router, tags=["Video"], prefix="/video")
