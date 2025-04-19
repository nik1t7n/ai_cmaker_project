from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.schemas import (
    TransactionCreate,
    TransactionInDB,
    TransactionStatus,
    TransactionUpdate,
    UserCreate,
)
from src.models import Transaction, User


async def create_user(user_create: UserCreate, db: AsyncSession) -> User:
    """
    Create a new user in the database.
    """

    new_user = User(
        telegram_id=user_create.user_id,
        credits_total=0,
        credits_left=0,
        is_paid=False,
        purchase_time=None,
        credits_expire_date=None,
        total_generations=0,
        total_prompt_tokens=0,
        total_response_tokens=0,
        total_video_duration_time=0,
        other_data={},
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


async def create_transaction(
    transaction_create: TransactionCreate, db: AsyncSession
) -> Transaction:
    """
    Create a new transaction in the database
    """

    new_transaction = Transaction(
        user_id=transaction_create.user_id,
        amount=transaction_create.amount,
        status=transaction_create.status,
        payment_id=transaction_create.payment_id,
        order_id=transaction_create.order_id,
    )

    db.add(new_transaction)
    await db.commit()
    await db.refresh(new_transaction)

    return new_transaction


async def update_transaction(
    db: AsyncSession, transaction_id: UUID, update_data: TransactionUpdate
) -> Optional[Transaction]:
    """
    Update an existing transaction in the database.

    Args:
        db: Database session
        transaction_id: UUID of the transaction to update
        update_data: Validated update data

    Returns:
        Updated transaction or None if not found
    """
    # Запрос для получения транзакции по ID
    query = select(Transaction).where(Transaction.transaction_id == transaction_id)
    result = await db.execute(query)
    transaction = result.scalar_one_or_none()

    if not transaction:
        return None

    # Обновляем поля, которые присутствуют в update_data
    # и не None (с помощью exclude_unset=True)
    update_dict = update_data.model_dump(exclude_unset=True)

    for key, value in update_dict.items():
        setattr(transaction, key, value)

    # Сохраняем изменения
    await db.commit()
    await db.refresh(transaction)

    return transaction


async def get_transactions(
    db: AsyncSession,
    order_id: Optional[str] = None,
    user_id: Optional[int] = None,
    payment_id: Optional[str] = None,
    status: Optional[Union[TransactionStatus, List[TransactionStatus]]] = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> Dict[str, Any]:
    """
    Get transactions with filtering and pagination.

    Args:
        db: Database session
        order_id: Filter by order_id
        user_id: Filter by user_id
        payment_id: Filter by payment_id
        status: Filter by status (single value or list)
        page: Page number (starting from 1)
        page_size: Number of items per page
        sort_by: Field to sort by
        sort_order: Sort direction ('asc' or 'desc')

    Returns:
        Dictionary with transactions and pagination metadata
    """
    # Начинаем строить запрос
    query = select(Transaction)

    # Применяем фильтры, если они предоставлены
    filters = []

    if order_id:
        filters.append(Transaction.order_id == order_id)

    if user_id:
        filters.append(Transaction.user_id == user_id)

    if payment_id:
        filters.append(Transaction.payment_id == payment_id)

    if status:
        if isinstance(status, list):
            filters.append(Transaction.status.in_(status))
        else:
            filters.append(Transaction.status == status)

    # Применяем все фильтры к запросу
    if filters:
        query = query.where(and_(*filters))

    # Получаем общее количество записей для пагинации
    count_query = select(func.count()).select_from(query.subquery())

    value = await db.scalar(count_query)
    total_count = value if value is not None else 0

    # Применяем сортировку
    if hasattr(Transaction, sort_by):
        sort_column = getattr(Transaction, sort_by)
        if sort_order.lower() == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

    # Применяем пагинацию
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Выполняем запрос
    result = await db.execute(query)
    transactions = result.scalars().all()

    # Вычисляем метаданные пагинации
    total_pages = (total_count + page_size - 1) // page_size

    return {
        "items": transactions,
        "pagination": {
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        },
    }


async def get_transaction(
    db: AsyncSession,
    transaction_id: Optional[UUID] = None,
    order_id: Optional[str] = None,
    payment_id: Optional[str] = None,
    status: Optional[TransactionStatus] = None,
) -> Optional[Transaction]:
    """
    Get a single transaction by ID, order_id, or payment_id.
    At least one identifier must be provided.

    Args:
        db: Database session
        transaction_id: Transaction UUID
        order_id: Order ID
        payment_id: Payment ID

    Returns:
        Transaction or None if not found
    """
    if not any([transaction_id, order_id, payment_id, status]):
        raise ValueError(
            "At least one of transaction_id, order_id, or payment_id, status must be provided"
        )

    # Строим условия для поиска
    conditions = []

    if transaction_id:
        conditions.append(Transaction.transaction_id == transaction_id)

    if order_id:
        conditions.append(Transaction.order_id == order_id)

    if payment_id:
        conditions.append(Transaction.payment_id == payment_id)

    if status:
        conditions.append(Transaction.status == status)

    # Используем OR между условиями
    query = select(Transaction).where(or_(*conditions))

    # Выполняем запрос
    result = await db.execute(query)
    return result.scalar_one_or_none()
