from typing import Any, Dict, List, Optional, Union
from uuid import UUID
import logging
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from src.repositories.transaction import TransactionRepository
from src.schemas import (
    TransactionCreate,
    TransactionStatus,
    TransactionUpdate,
    PackageType,
)
from src.models import Transaction


class TransactionService:
    def __init__(self, transaction_repository: TransactionRepository):
        self.transaction_repository = transaction_repository
        self.logger = logging.getLogger(__name__)

    async def create_transaction(
        self, transaction_create: TransactionCreate
    ) -> Transaction:
        """
        Create a new transaction with error handling.

        Args:
            transaction_create: Transaction creation data including package_type

        Returns:
            Transaction: Created transaction object

        Raises:
            ValueError: If transaction creation fails due to validation errors
            Exception: If transaction creation fails due to database errors
        """
        try:
            # Проверка наличия package_type
            if transaction_create.package_type is None:
                raise ValueError("package_type is required")

            return await self.transaction_repository.create_transaction(
                transaction_create
            )
        except IntegrityError as e:
            self.logger.error(f"IntegrityError while creating transaction: {e}")
            if "payment_id" in str(e) and "duplicate key" in str(e):
                raise ValueError(
                    f"Transaction with payment_id {transaction_create.payment_id} already exists"
                )
            elif "order_id" in str(e) and "duplicate key" in str(e):
                raise ValueError(
                    f"Transaction with order_id {transaction_create.order_id} already exists"
                )
            elif "user_id" in str(e) and "foreign key" in str(e):
                raise ValueError(
                    f"User with id {transaction_create.user_id} does not exist"
                )
            raise ValueError(f"Database integrity error: {e}")
        except SQLAlchemyError as e:
            self.logger.error(f"Database error while creating transaction: {e}")
            raise Exception(f"Database error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error while creating transaction: {e}")
            raise Exception(f"Failed to create transaction: {e}")

    async def update_transaction(
        self, transaction_id: UUID, update_data: TransactionUpdate
    ) -> Transaction:
        """
        Update an existing transaction with error handling.

        Args:
            transaction_id: UUID of the transaction to update
            update_data: Validated update data

        Returns:
            Transaction: Updated transaction

        Raises:
            ValueError: If transaction not found or validation errors
            Exception: If update fails due to database errors
        """
        try:
            transaction = await self.transaction_repository.update_transaction(
                transaction_id, update_data
            )
            if not transaction:
                raise ValueError(f"Transaction with ID {transaction_id} not found")
            return transaction
        except ValueError as e:
            # Re-raise ValueError for not found case
            self.logger.warning(f"Transaction update error: {e}")
            raise
        except IntegrityError as e:
            self.logger.error(f"IntegrityError while updating transaction: {e}")
            raise ValueError(f"Database integrity error: {e}")
        except SQLAlchemyError as e:
            self.logger.error(f"Database error while updating transaction: {e}")
            raise Exception(f"Database error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error while updating transaction: {e}")
            raise Exception(f"Failed to update transaction: {e}")

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
        Get transactions with filtering and pagination, with error handling.

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
            include_deleted: Whether to include soft deleted transactions

        Returns:
            Dictionary with transactions and pagination metadata

        Raises:
            ValueError: If invalid parameters are provided
            Exception: If query fails due to database errors
        """
        try:
            # Validate parameters
            if page < 1:
                raise ValueError("Page number must be at least 1")
            if page_size < 1:
                raise ValueError("Page size must be at least 1")
            if sort_order.lower() not in ["asc", "desc"]:
                raise ValueError("Sort order must be 'asc' or 'desc'")

            # Proceed with repository call
            return await self.transaction_repository.get_transactions(
                order_id=order_id,
                user_id=user_id,
                payment_id=payment_id,
                status=status,
                package_type=package_type,
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_order=sort_order,
                include_deleted=include_deleted,
            )
        except ValueError as e:
            # Re-raise validation errors
            self.logger.warning(f"Invalid parameter in get_transactions: {e}")
            raise
        except SQLAlchemyError as e:
            self.logger.error(f"Database error while getting transactions: {e}")
            raise Exception(f"Database error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error while getting transactions: {e}")
            raise Exception(f"Failed to get transactions: {e}")

    async def get_transaction(
        self,
        transaction_id: Optional[UUID] = None,
        order_id: Optional[str] = None,
        payment_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Transaction:
        """
        Get a single transaction by various identifiers, with error handling.

        Args:
            transaction_id: Transaction UUID
            order_id: Order ID
            payment_id: Payment ID
            include_deleted: Whether to include soft deleted transactions

        Returns:
            Transaction object

        Raises:
            ValueError: If transaction not found or no identifier provided
            Exception: If query fails due to database errors
        """
        try:
            # Validate that at least one identifier is provided
            if not any([transaction_id, order_id, payment_id]):
                raise ValueError(
                    "At least one of transaction_id, order_id, or payment_id must be provided"
                )

            transaction = await self.transaction_repository.get_transaction(
                transaction_id=transaction_id,
                order_id=order_id,
                payment_id=payment_id,
                include_deleted=include_deleted,
            )

            if not transaction:
                # Construct error message based on provided parameters
                search_params = []
                if transaction_id:
                    search_params.append(f"ID={transaction_id}")
                if order_id:
                    search_params.append(f"order_id={order_id}")
                if payment_id:
                    search_params.append(f"payment_id={payment_id}")

                raise ValueError(
                    f"Transaction not found with {' and '.join(search_params)}"
                )

            return transaction

        except ValueError as e:
            # Re-raise validation and not found errors
            self.logger.warning(f"Transaction get error: {e}")
            raise
        except SQLAlchemyError as e:
            self.logger.error(f"Database error while getting transaction: {e}")
            raise Exception(f"Database error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error while getting transaction: {e}")
            raise Exception(f"Failed to get transaction: {e}")

    async def delete_transaction(self, transaction_id: UUID) -> bool:
        """
        Soft delete a transaction by ID with error handling.

        Args:
            transaction_id: UUID of the transaction to soft delete

        Returns:
            bool: True if transaction was marked as deleted

        Raises:
            ValueError: If transaction not found
            Exception: If deletion fails due to database errors
        """
        try:
            result = await self.transaction_repository.delete_transaction(
                transaction_id
            )
            if not result:
                raise ValueError(f"Transaction with ID {transaction_id} not found")

            self.logger.info(f"Soft deleted transaction {transaction_id}")
            return True
        except ValueError as e:
            self.logger.warning(f"Transaction deletion error: {e}")
            raise
        except SQLAlchemyError as e:
            self.logger.error(f"Database error while deleting transaction: {e}")
            raise Exception(f"Database error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error while deleting transaction: {e}")
            raise Exception(f"Failed to delete transaction: {e}")

    async def restore_transaction(self, transaction_id: UUID) -> Transaction:
        """
        Restore a soft-deleted transaction with error handling.

        Args:
            transaction_id: UUID of the transaction to restore

        Returns:
            Transaction: Restored transaction

        Raises:
            ValueError: If transaction not found
            Exception: If restoration fails due to database errors
        """
        try:
            # Get transaction including deleted ones
            transaction = await self.get_transaction(
                transaction_id=transaction_id, include_deleted=True
            )

            if not transaction:
                raise ValueError(f"Transaction with ID {transaction_id} not found")

            # Create update data to restore
            update_data = TransactionUpdate()
            update_data.is_deleted = False

            return await self.transaction_repository.update_transaction(
                transaction_id, update_data
            )

        except ValueError as e:
            self.logger.warning(f"Transaction restoration error: {e}")
            raise
        except SQLAlchemyError as e:
            self.logger.error(f"Database error while restoring transaction: {e}")
            raise Exception(f"Database error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error while restoring transaction: {e}")
            raise Exception(f"Failed to restore transaction: {e}")
