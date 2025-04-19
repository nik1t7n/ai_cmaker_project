from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.schemas import (
    UserCreate,
    UserFilterParams,
    UserUpdate,
)
from src.models import User, get_timezone_naive_now


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_including_deleted(self, telegram_id: int) -> Optional[User]:
        """
        Get user by telegram ID including soft-deleted users.
        Args:
            telegram_id: User's telegram ID
        Returns:
            User or None if not found
        """
        query = select(User).where(User.telegram_id == telegram_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def restore_user(self, user: User, user_id: int) -> User:
        """
        Delete soft-deleted user and create a fresh one with the same ID.
        Args:
            user: User to delete
            user_id: Telegram ID for new user
        Returns:
            Newly created user
        """
        # Completely delete the user from the database
        await self.db.delete(user)
        await self.db.commit()
        
        # Create a new user with the same telegram_id
        user_create = UserCreate(user_id=user_id)
        return await self.create_user(user_create)

    async def create_user(self, user_create: UserCreate) -> User:
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

        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)

        return new_user

    async def get_user(self, telegram_id: int) -> Optional[User]:
        """
        Get user by telegram ID.

        Args:
            telegram_id: User's telegram ID

        Returns:
            User or None if not found
        """
        query = select(User).where(
            User.is_deleted == False, User.telegram_id == telegram_id
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_users(
        self,
        filters: Optional[UserFilterParams] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "telegram_id",
        sort_order: str = "asc",
    ) -> Dict[str, Any]:
        """
        Get users with filtering and pagination.

        Args:
            filters: Filter parameters for users
            page: Page number (starting from 1)
            page_size: Number of items per page
            sort_by: Field to sort by
            sort_order: Sort direction ('asc' or 'desc')

        Returns:
            Dictionary with users and pagination metadata
        """
        # Базовый запрос на выборку пользователей
        query = select(User)

        # Применяем фильтры, если они предоставлены
        if filters:
            filter_conditions = []

            filter_conditions.append(User.is_deleted == False)

            if filters.is_paid is not None:
                filter_conditions.append(User.is_paid == filters.is_paid)

            if filters.min_credits is not None:
                filter_conditions.append(User.credits_left >= filters.min_credits)

            if filters.max_credits is not None:
                filter_conditions.append(User.credits_left <= filters.max_credits)

            if filters.created_after:
                filter_conditions.append(User.purchase_time >= filters.created_after)

            if filters.created_before:
                filter_conditions.append(User.purchase_time <= filters.created_before)

            if filters.credits_expire_before:
                filter_conditions.append(
                    User.credits_expire_date <= filters.credits_expire_before
                )

            if filters.telegram_ids and len(filters.telegram_ids) > 0:
                filter_conditions.append(User.telegram_id.in_(filters.telegram_ids))

            if filter_conditions:
                query = query.where(and_(*filter_conditions))

        # Запрос для подсчета общего количества записей
        count_query = select(func.count()).select_from(query.subquery())
        total_count = await self.db.scalar(count_query) or 0

        # Применяем сортировку
        if hasattr(User, sort_by):
            sort_column = getattr(User, sort_by)
            if sort_order.lower() == "desc":
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column.asc())

        # Применяем пагинацию
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Выполняем запрос
        result = await self.db.execute(query)
        users = result.scalars().all()

        # Вычисляем метаданные пагинации
        total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

        return {
            "items": users,
            "pagination": {
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "page_size": page_size,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }

    async def update_user(
        self, telegram_id: int, update_data: UserUpdate
    ) -> Optional[User]:
        """
        Update an existing user.

        Args:
            telegram_id: Telegram ID of the user to update
            update_data: User data to update

        Returns:
            Updated user or None if not found
        """
        # Проверяем, существует ли пользователь
        user = await self.get_user(telegram_id)
        if not user:
            return None

        # Формируем словарь с данными для обновления
        update_dict = update_data.model_dump(exclude_unset=True)

        # Если нет данных для обновления, возвращаем пользователя без изменений
        if not update_dict:
            return user

        # is_paid: Optional[bool] = None

        # Обновляем пользователя
        for key, value in update_dict.items():
            setattr(user, key, value)

        await self.db.commit()
        await self.db.refresh(user)

        return user

    # credits_total & credits_left & purchase_time & credits_expire_date
    # all above fields' update is going to be handled separatly
    async def add_credits(
        self, telegram_id: int, credits: int, update_purchase_time: bool = True
    ) -> Optional[User]:
        """
        Add credits to user's account and optionally update purchase time.

        Args:
            telegram_id: Telegram ID of the user
            credits: Number of credits to add
            update_purchase_time: Whether to update purchase_time field to current time

        Returns:
            Updated user or None if not found
        """
        user = await self.get_user(telegram_id)
        if not user:
            return None

        # Обновляем количество кредитов
        user.credits_total += credits
        user.credits_left += credits

        # Устанавливаем флаг оплаты
        user.is_paid = True

        # Обновляем время покупки, если требуется
        if update_purchase_time:
            current_time = get_timezone_naive_now()
            user.purchase_time = current_time
            # credits_expire_date будет обновлен автоматически через validate

        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def deduct_credits(self, telegram_id: int, credits: int) -> Optional[User]:
        """
        Deduct credits from user's account.

        Args:
            telegram_id: Telegram ID of the user
            credits: Number of credits to deduct

        Returns:
            Updated user or None if not found or not enough credits
        """
        # Атомарное обновление с проверкой достаточности кредитов
        stmt = (
            update(User)
            .where(
                and_(
                    User.is_deleted == False,
                    User.telegram_id == telegram_id,
                    User.credits_left >= credits,
                )
            )
            .values(credits_left=User.credits_left - credits)
            .returning(User)
        )

        result = await self.db.execute(stmt)
        updated_user = result.scalar_one_or_none()

        # Если пользователь не обновлен (недостаточно кредитов или не найден)
        if not updated_user:
            return None

        await self.db.commit()

        return updated_user

    async def update_usage_stats(
        self,
        telegram_id: int,
        generations: Optional[int] = None,
        prompt_tokens: Optional[int] = None,
        response_tokens: Optional[int] = None,
        video_duration: Optional[int] = None,
    ) -> Optional[User]:
        """
        Update user's usage statistics.

        Args:
            telegram_id: Telegram ID of the user
            generations: Number of generations to add
            prompt_tokens: Number of prompt tokens to add
            response_tokens: Number of response tokens to add
            video_duration: Video duration time in seconds to add

        Returns:
            Updated user or None if not found
        """
        user = await self.get_user(telegram_id)
        if not user:
            return None

        # Обновляем статистику использования
        if generations:
            user.total_generations += generations
        if prompt_tokens:
            user.total_prompt_tokens += prompt_tokens
        if response_tokens:
            user.total_response_tokens += response_tokens
        if video_duration:
            user.total_video_duration_time += video_duration

        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def set_user_data(
        self, telegram_id: int, data_key: str, data_value: Any
    ) -> Optional[User]:
        """
        Set a specific value in user's other_data JSON field.

        Args:
            telegram_id: Telegram ID of the user
            data_key: Key to set in other_data
            data_value: Value to set

        Returns:
            Updated user or None if not found
        """
        user = await self.get_user(telegram_id)
        if not user:
            return None

        # Инициализируем other_data, если оно None
        current_data = user.other_data or {}

        if hasattr(current_data, "_asdict"):
            current_data = current_data._asdict()
        elif not isinstance(current_data, dict):
            current_data = {}

        current_data[data_key] = data_value

        # Устанавливаем значение
        user.other_data = current_data

        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def delete_user(self, telegram_id: int) -> bool:
        """
        Soft delete a user by telegram ID.

        Args:
            telegram_id: Telegram ID of the user to delete

        Returns:
            True if user was deleted, False if not found
        """
        user = await self.get_user(telegram_id)
        if not user:
            return False

        user.is_deleted = True
        await self.db.commit()
        await self.db.refresh(user)

        return True
