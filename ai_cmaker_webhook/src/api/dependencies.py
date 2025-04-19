from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db
from src.repositories.transaction import TransactionRepository
from src.repositories.user import UserRepository
from src.services.transaction import TransactionService
from src.services.user import UserService


async def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db=db)


async def get_transaction_repository(
    db: AsyncSession = Depends(get_db),
) -> TransactionRepository:
    return TransactionRepository(db=db)


# services


async def get_user_service(
    user_repository: UserRepository = Depends(get_user_repository),
):
    return UserService(user_repository=user_repository)


async def get_transaction_service(
    transaction_repository: TransactionRepository = Depends(get_transaction_repository),
):
    return TransactionService(transaction_repository=transaction_repository)
