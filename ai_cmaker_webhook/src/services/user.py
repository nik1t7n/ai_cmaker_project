import logging
from typing import Any, Dict, List, Optional, Union
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from src.exceptions import CustomIntegrityError, CustomValidationError, ResourceAlreadyExistsError, ResourceNotFoundError, InsufficientCreditsError
from src.repositories.user import UserRepository
from src.schemas import (
    UserCreate,
    UserUpdate,
    UserFilterParams,
)
from src.models import User


class UserService:
    def __init__(self, user_repository: UserRepository):
        self.user_repository = user_repository
        self.logger = logging.getLogger(__name__)

    async def create_user(self, user_create: UserCreate) -> User:
        """
        Create a new user with error handling. If user was soft-deleted,
        restore the user instead of creating a new one.
        """
        try:
            # Сначала проверяем активного пользователя
            user = await self.user_repository.get_user(telegram_id=user_create.user_id)
            if user:
                raise ResourceAlreadyExistsError(
                    f"User with telegram_id {user_create.user_id} already exists"
                )
            
            # Затем проверяем, есть ли удаленный пользователь
            deleted_user = await self.user_repository.get_user_including_deleted(telegram_id=user_create.user_id)
            if deleted_user and deleted_user.is_deleted:
                # Если пользователь был удален, восстанавливаем его
                self.logger.info(f"Restoring soft-deleted user with telegram_id {user_create.user_id}")
                return await self.user_repository.restore_user(deleted_user, user_id=user_create.user_id)
            
            # Если пользователь не существует, создаем нового
            return await self.user_repository.create_user(user_create)
        except ResourceAlreadyExistsError:
            raise
        except IntegrityError as e:
            self.logger.error(f"IntegrityError while creating user: {e}")
            raise CustomIntegrityError(f"Database integrity error: {e}")
        except SQLAlchemyError as e:
            self.logger.error(f"Database error while creating user: {e}")
            raise Exception(f"Database error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error while creating user: {e}")
            raise Exception(f"Failed to create user: {e}")

    async def get_user(self, telegram_id: int) -> User:
        """
        Get user by telegram ID with error handling.

        Args:
            telegram_id: User's telegram ID

        Returns:
            User object

        Raises:
            ResourceNotFoundError: If user not found
            Exception: If query fails due to database errors
        """
        try:
            user = await self.user_repository.get_user(telegram_id)
            if not user:
                raise ResourceNotFoundError(f"User with telegram_id {telegram_id} not found")

            return user
        except ResourceNotFoundError as e:
            self.logger.warning(f"User get error: {e}")
            raise

        except SQLAlchemyError as e:
            self.logger.error(f"Database error while getting user: {e}")
            raise Exception(f"Database error: {e}")

        except Exception as e:
            self.logger.error(f"Unexpected error while getting user: {e}")
            raise Exception(f"Failed to get user: {e}")

    async def get_users(
        self,
        filters: Optional[UserFilterParams] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "telegram_id",
        sort_order: str = "asc",
    ) -> Dict[str, Any]:
        """
        Get users with filtering and pagination, with error handling.

        Args:
            filters: Filter parameters for users
            page: Page number (starting from 1)
            page_size: Number of items per page
            sort_by: Field to sort by
            sort_order: Sort direction ('asc' or 'desc')

        Returns:
            Dictionary with users and pagination metadata

        Raises:
            CustomValidationError: If invalid parameters are provided
            Exception: If query fails due to database errors
        """
        try:
            # Validate parameters
            if page < 1:
                raise CustomValidationError("Page number must be at least 1")
            if page_size < 1:
                raise CustomValidationError("Page size must be at least 1")
            if sort_order.lower() not in ["asc", "desc"]:
                raise CustomValidationError("Sort order must be 'asc' or 'desc'")
            if not hasattr(User, sort_by):
                raise CustomValidationError(f"Sort field '{sort_by}' does not exist on User model")

            # Proceed with repository call
            return await self.user_repository.get_users(
                filters=filters,
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_order=sort_order,
            )
        except CustomValidationError as e:
            # Re-raise validation errors
            self.logger.warning(f"Invalid parameter in get_users: {e}")
            raise
        except SQLAlchemyError as e:
            self.logger.error(f"Database error while getting users: {e}")
            raise Exception(f"Database error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error while getting users: {e}")
            raise Exception(f"Failed to get users: {e}")

    async def update_user(self, telegram_id: int, update_data: UserUpdate) -> User:
        """
        Update an existing user with error handling.

        Args:
            telegram_id: Telegram ID of the user to update
            update_data: User data to update

        Returns:
            Updated user

        Raises:
            CustomValidationError: If validation errors occur
            ResourceNotFoundError: If user not found
            CustomIntegrityError: If database integrity violation occurs
            Exception: If update fails due to database errors
        """
        try:

            user = await self.user_repository.update_user(telegram_id, update_data)
            if not user:
                raise ResourceNotFoundError(f"User with telegram_id {telegram_id} not found")
            return user
        except ResourceNotFoundError as e:
            self.logger.warning(f"User update error: {e}")
            raise
        except CustomValidationError as e:
            self.logger.warning(f"User update validation error: {e}")
            raise
        except IntegrityError as e:
            self.logger.error(f"IntegrityError while updating user: {e}")
            raise CustomIntegrityError(f"Database integrity error: {e}")
        except SQLAlchemyError as e:
            self.logger.error(f"Database error while updating user: {e}")
            raise Exception(f"Database error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error while updating user: {e}")
            raise Exception(f"Failed to update user: {e}")

    async def add_credits(
        self, telegram_id: int, credits: int, update_purchase_time: bool = True
    ) -> User:
        """
        Add credits to user's account with error handling.

        Args:
            telegram_id: Telegram ID of the user
            credits: Number of credits to add
            update_purchase_time: Whether to update purchase_time field

        Returns:
            Updated user

        Raises:
            CustomValidationError: If credits is not positive
            ResourceNotFoundError: If user not found
            Exception: If update fails due to database errors
        """
        try:
            if credits <= 0:
                raise CustomValidationError("Credits must be a positive number")

            user = await self.user_repository.add_credits(
                telegram_id, credits, update_purchase_time
            )
            if not user:
                raise ResourceNotFoundError(f"User with telegram_id {telegram_id} not found")

            self.logger.info(
                f"Added {credits} credits to user {telegram_id}. New total: {user.credits_left}"
            )
            return user
        except ResourceNotFoundError as e:
            self.logger.warning(f"Credit add error: {e}")
            raise
        except CustomValidationError as e:
            self.logger.warning(f"Credit add validation error: {e}")
            raise
        except SQLAlchemyError as e:
            self.logger.error(f"Database error while adding credits: {e}")
            raise Exception(f"Database error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error while adding credits: {e}")
            raise Exception(f"Failed to add credits: {e}")

    async def deduct_credits(self, telegram_id: int, credits: int) -> User:
        """
        Deduct credits from user's account with error handling.

        Args:
            telegram_id: Telegram ID of the user
            credits: Number of credits to deduct

        Returns:
            Updated user

        Raises:
            CustomValidationError: If credits is not positive
            ResourceNotFoundError: If user not found
            InsufficientCreditsError: If user doesn't have enough credits
            Exception: If update fails due to database errors
        """
        try:
            if credits <= 0:
                raise CustomValidationError("Credits must be a positive number")

            user = await self.user_repository.deduct_credits(telegram_id, credits)
            if not user:
                # Проверяем, существует ли пользователь
                exists = await self.user_repository.get_user(telegram_id)
                if not exists:
                    raise ResourceNotFoundError(f"User with telegram_id {telegram_id} not found")
                else:
                    raise InsufficientCreditsError(
                        f"User with telegram_id {telegram_id} does not have enough credits"
                    )

            self.logger.info(
                f"Deducted {credits} credits from user {telegram_id}. Remaining: {user.credits_left}"
            )
            return user
        except ResourceNotFoundError as e:
            self.logger.warning(f"Credit deduction error: {e}")
            raise
        except InsufficientCreditsError as e:
            self.logger.warning(f"Credit deduction error: {e}")
            raise
        except CustomValidationError as e:
            self.logger.warning(f"Credit deduction validation error: {e}")
            raise
        except SQLAlchemyError as e:
            self.logger.error(f"Database error while deducting credits: {e}")
            raise Exception(f"Database error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error while deducting credits: {e}")
            raise Exception(f"Failed to deduct credits: {e}")

    async def update_usage_stats(
        self,
        telegram_id: int,
        generations: Optional[int] = None,
        prompt_tokens: Optional[int] = None,
        response_tokens: Optional[int] = None,
        video_duration: Optional[int] = None,
    ) -> User:
        """
        Update user's usage statistics with error handling.

        Args:
            telegram_id: Telegram ID of the user
            generations: Number of generations to add (or None to skip)
            prompt_tokens: Number of prompt tokens to add (or None to skip)
            response_tokens: Number of response tokens to add (or None to skip)
            video_duration: Video duration time to add in seconds (or None to skip)

        Returns:
            Updated user

        Raises:
            CustomValidationError: If no usage statistics are provided
            ResourceNotFoundError: If user not found
            Exception: If update fails due to database errors
        """
        try:
            # Проверяем, что хоть один параметр не None
            if all(
                param is None
                for param in [
                    generations,
                    prompt_tokens,
                    response_tokens,
                    video_duration,
                ]
            ):
                raise CustomValidationError("At least one usage statistic must be provided")

            user = await self.user_repository.update_usage_stats(
                telegram_id, generations, prompt_tokens, response_tokens, video_duration
            )
            if not user:
                raise ResourceNotFoundError(f"User with telegram_id {telegram_id} not found")

            self.logger.info(f"Updated usage stats for user {telegram_id}")
            return user
        except ResourceNotFoundError as e:
            self.logger.warning(f"Usage stats update error: {e}")
            raise
        except CustomValidationError as e:
            self.logger.warning(f"Usage stats validation error: {e}")
            raise
        except SQLAlchemyError as e:
            self.logger.error(f"Database error while updating usage stats: {e}")
            raise Exception(f"Database error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error while updating usage stats: {e}")
            raise Exception(f"Failed to update usage stats: {e}")

    async def set_user_data(
        self, telegram_id: int, data_key: str, data_value: Any
    ) -> User:
        """
        Set a specific value in user's other_data JSON field with error handling.

        Args:
            telegram_id: Telegram ID of the user
            data_key: Key to set in other_data
            data_value: Value to set

        Returns:
            Updated user

        Raises:
            CustomValidationError: If data_key is empty
            ResourceNotFoundError: If user not found
            Exception: If update fails due to database errors
        """
        try:
            if not data_key:
                raise CustomValidationError("Data key cannot be empty")

            user = await self.user_repository.set_user_data(
                telegram_id, data_key, data_value
            )
            if not user:
                raise ResourceNotFoundError(f"User with telegram_id {telegram_id} not found")

            self.logger.info(f"Updated other_data[{data_key}] for user {telegram_id}")
            return user
        except ResourceNotFoundError as e:
            self.logger.warning(f"User data update error: {e}")
            raise
        except CustomValidationError as e:
            self.logger.warning(f"User data validation error: {e}")
            raise
        except SQLAlchemyError as e:
            self.logger.error(f"Database error while updating user data: {e}")
            raise Exception(f"Database error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error while updating user data: {e}")
            raise Exception(f"Failed to update user data: {e}")

    async def delete_user(self, telegram_id: int) -> bool:
        """
        Soft delete a user by telegram ID with error handling.

        Args:
            telegram_id: Telegram ID of the user to delete

        Returns:
            True if user was deleted

        Raises:
            ResourceNotFoundError: If user not found
            Exception: If deletion fails due to database errors
        """
        try:
            result = await self.user_repository.delete_user(telegram_id)
            if not result:
                raise ResourceNotFoundError(f"User with telegram_id {telegram_id} not found")

            self.logger.info(f"Deleted user {telegram_id}")
            return True
        except ResourceNotFoundError as e:
            self.logger.warning(f"User deletion error: {e}")
            raise
        except SQLAlchemyError as e:
            self.logger.error(f"Database error while deleting user: {e}")
            raise Exception(f"Database error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error while deleting user: {e}")
            raise Exception(f"Failed to delete user: {e}")

    async def get_users_by_credits_range(
        self, min_credits: int, max_credits: int, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Get users with credits in specified range.

        Args:
            min_credits: Minimum number of credits
            max_credits: Maximum number of credits
            page: Page number
            page_size: Page size

        Returns:
            Dictionary with users and pagination metadata

        Raises:
            CustomValidationError: If invalid parameters
            Exception: If query fails
        """
        try:
            if min_credits < 0 or max_credits < 0:
                raise CustomValidationError("Credits values cannot be negative")
            if min_credits > max_credits:
                raise CustomValidationError(
                    "Minimum credits cannot be greater than maximum credits"
                )

            filters = UserFilterParams(min_credits=min_credits, max_credits=max_credits)
            return await self.get_users(filters=filters, page=page, page_size=page_size)
        except CustomValidationError as e:
            self.logger.warning(f"Credits range query error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error in get_users_by_credits_range: {e}")
            raise

    async def get_paid_users(
        self, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Get users who have paid.

        Args:
            page: Page number
            page_size: Page size

        Returns:
            Dictionary with users and pagination metadata
        """
        try:
            filters = UserFilterParams(is_paid=True)
            return await self.get_users(filters=filters, page=page, page_size=page_size)
        except Exception as e:
            self.logger.error(f"Error in get_paid_users: {e}")
            raise

    async def get_users_with_credits_left(
        self, page: int = 1, page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Get users who have credits left.

        Args:
            page: Page number
            page_size: Page size

        Returns:
            Dictionary with users and pagination metadata
        """
        try:
            filters = UserFilterParams(min_credits=1)
            return await self.get_users(filters=filters, page=page, page_size=page_size)
        except Exception as e:
            self.logger.error(f"Error in get_users_with_credits_left: {e}")
            raise
