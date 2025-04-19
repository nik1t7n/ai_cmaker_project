from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.schemas import (
    PackageType,
    TransactionCreate,
    TransactionStatus,
    TransactionUpdate,
)
from src.models import Transaction


class TransactionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_transaction(
        self, transaction_create: TransactionCreate
    ) -> Transaction:
        """
        Create a new transaction in the database
        
        Args:
            transaction_create: Transaction creation data including package_type
            
        Returns:
            Transaction: Created transaction
        """
        new_transaction = Transaction(
            user_id=transaction_create.user_id,
            amount=transaction_create.amount,
            status=transaction_create.status,
            payment_id=transaction_create.payment_id,
            order_id=transaction_create.order_id,
            package_type=transaction_create.package_type,
        )

        self.db.add(new_transaction)
        await self.db.commit()
        await self.db.refresh(new_transaction)

        return new_transaction

    async def get_transaction(
        self,
        transaction_id: Optional[UUID] = None,
        order_id: Optional[str] = None,
        payment_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Optional[Transaction]:
        """
        Get a single transaction by ID, order_id, or payment_id.
        At least one identifier must be provided.
        """
        conditions = []
        
        # Добавляем условие is_deleted только если не include_deleted
        if not include_deleted:
            conditions.append(Transaction.is_deleted == False)
        
        # Добавляем только те идентификаторы, которые были предоставлены
        id_conditions = []
        if transaction_id:
            id_conditions.append(Transaction.transaction_id == transaction_id)
        if order_id:
            id_conditions.append(Transaction.order_id == order_id)
        if payment_id:
            id_conditions.append(Transaction.payment_id == payment_id)
        
        # Если предоставлено несколько идентификаторов, объединяем их через AND
        # Если предоставлен только один идентификатор, просто используем его
        if len(id_conditions) > 0:
            conditions.append(and_(*id_conditions))
        
        # Собираем все условия через AND
        query = select(Transaction).where(and_(*conditions))
        
        # Выполняем запрос
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def update_transaction(
        self, transaction_id: UUID, update_data: TransactionUpdate
    ) -> Optional[Transaction]:
        """
        Update an existing transaction in the database.

        Args:
            transaction_id: UUID of the transaction to update
            update_data: Validated update data

        Returns:
            Updated transaction or None if not found
        """
        # Запрос для получения транзакции по ID
        transaction = await self.get_transaction(transaction_id=transaction_id)

        if not transaction:
            return None

        # Обновляем поля, которые присутствуют в update_data
        # и не None (с помощью exclude_unset=True)
        update_dict = update_data.model_dump(exclude_unset=True)

        for key, value in update_dict.items():
            setattr(transaction, key, value)

        # Сохраняем изменения
        await self.db.commit()
        await self.db.refresh(transaction)

        return transaction

    async def get_transactions(
        self,
        order_id: Optional[str] = None,
        user_id: Optional[int] = None,
        payment_id: Optional[str] = None,
        status: Optional[Union[TransactionStatus, List[TransactionStatus]]] = None,
        package_type: Optional[PackageType] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        include_deleted: bool = False,
    ) -> Dict[str, Any]:
        """
        Get transactions with filtering and pagination.

        Args:
            order_id: Filter by order_id
            user_id: Filter by user_id
            payment_id: Filter by payment_id
            status: Filter by status (single value or list)
            package_type: Filter by package type
            page: Page number (starting from 1)
            page_size: Number of items per page
            sort_by: Field to sort by
            sort_order: Sort direction ('asc' or 'desc')
            include_deleted: Whether to include soft-deleted transactions

        Returns:
            Dictionary with transactions and pagination metadata
        """
        # Начинаем строить запрос
        query = select(Transaction)

        # Применяем фильтры, если они предоставлены
        filters = []

        # Добавляем фильтр is_deleted только если не include_deleted
        if not include_deleted:
            filters.append(Transaction.is_deleted == False)

        if order_id:
            filters.append(Transaction.order_id == order_id)

        if user_id:
            filters.append(Transaction.user_id == user_id)

        if payment_id:
            filters.append(Transaction.payment_id == payment_id)
            
        if package_type:
            filters.append(Transaction.package_type == package_type)

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

        value = await self.db.scalar(count_query)
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
        result = await self.db.execute(query)
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

    async def delete_transaction(self, transaction_id: UUID) -> bool:
        """
        Soft delete a transaction by ID.
        
        Args:
            transaction_id: UUID of the transaction to delete
            
        Returns:
            bool: True if successfully deleted, False if not found
        """
        # Используем include_deleted=True, чтобы находить даже уже удаленные транзакции
        transaction = await self.get_transaction(
            transaction_id=transaction_id,
            include_deleted=False
        )

        if transaction is None:
            return False
            
        transaction.is_deleted = True
        # deleted_at будет установлен автоматически через @validates в модели

        await self.db.commit()
        await self.db.refresh(transaction)

        return True

    async def restore_transaction(self, transaction_id: UUID) -> Optional[Transaction]:
        """
        Restore a soft-deleted transaction.
        
        Args:
            transaction_id: UUID of the transaction to restore
            
        Returns:
            Transaction: Restored transaction or None if not found
        """
        # Используем include_deleted=True, чтобы находить удаленные транзакции
        transaction = await self.get_transaction(
            transaction_id=transaction_id,
            include_deleted=True
        )

        if transaction is None:
            return None
            
        # Если транзакция не была удалена, просто возвращаем ее
        if not transaction.is_deleted:
            return transaction

        transaction.is_deleted = False
        # deleted_at будет сброшен автоматически через @validates в модели

        await self.db.commit()
        await self.db.refresh(transaction)

        return transaction
