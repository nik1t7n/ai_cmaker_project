from datetime import timedelta
from enum import Enum
import uuid
from sqlalchemy.orm import relationship, validates
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Integer,
    JSON,
    DateTime,
    Numeric,
    String,
    Uuid,
    Enum as SQLEnum,
)
from datetime import datetime, timezone
from src.core.db import Base
from src.core.config import SUBSCRIPTION_DURATION
from src.schemas import PackageType, TransactionStatus

package_type_enum = SQLEnum(
    PackageType,
    name="package_type_enum",  # Важно: уникальное имя для PostgreSQL
    create_constraint=True,
    native_enum=True,
)

transaction_status_enum = SQLEnum(
    TransactionStatus,
    name="transaction_status_enum",  # Важно: уникальное имя для PostgreSQL
    create_constraint=True,
    native_enum=True,
)


# we make here .replace(tzinfo=None) in order to make date timezone-naive
# because PostgreSQL accepts only this type of dates
def get_timezone_naive_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True)
    credits_total = Column(Integer, default=0)
    credits_left = Column(Integer, default=0)
    is_paid = Column(Boolean, default=False)

    purchase_time = Column(DateTime, nullable=True)
    credits_expire_date = Column(DateTime, nullable=True)

    total_generations = Column(Integer, default=0)
    total_prompt_tokens = Column(Integer, default=0)
    total_response_tokens = Column(Integer, default=0)
    total_video_duration_time = Column(Integer, default=0)

    other_data = Column(JSON, nullable=True)

    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    transactions = relationship("Transaction", back_populates="user")

    # automatically set 'credits_expire_date' field after user's purchase
    @validates("purchase_time")
    def set_credits_expire_date(self, key, purchase_time):
        if purchase_time:
            self.credits_expire_date = purchase_time + timedelta(
                days=SUBSCRIPTION_DURATION
            )
        return purchase_time

    # automatically changes 'is_deleted' field immediately after soft deletion
    @validates("is_deleted")
    def update_deleted_at(self, key, value):
        if value is True:
            self.deleted_at = get_timezone_naive_now()
        elif value is False:
            self.deleted_at = None
        return value

  
class Transaction(Base):
    __tablename__ = "transactions"

    transaction_id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    amount = Column(Numeric, nullable=False)
    status = Column(
        transaction_status_enum, nullable=False, default=TransactionStatus.PENDING
    )
    payment_id = Column(
        String, nullable=True
    )  # nullable=True because we add payment id after first transaction initialization
    order_id = Column(String, nullable=True)

    package_type = Column(package_type_enum, nullable=False)

    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: get_timezone_naive_now())
    updated_at = Column(
        DateTime,
        default=lambda: get_timezone_naive_now(),
        onupdate=lambda: get_timezone_naive_now(),
    )

    user = relationship("User", back_populates="transactions")

    @validates("is_deleted")
    def update_deleted_at(self, key, value):
        if value is True:
            self.deleted_at = get_timezone_naive_now() 
        elif value is False:
            self.deleted_at = None
        return value
