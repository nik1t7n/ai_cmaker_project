from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import UUID4, BaseModel
from datetime import datetime 


class UserCreate(BaseModel):
    user_id: int


class PackageType(str, Enum):
    PACK_10 = "10"
    PACK_30 = "30"
    PACK_50 = "50"
    PACK_100 = "100"

class TransactionStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"



class PaymentCreate(BaseModel):
    user_id: int
    package: PackageType
    user_phone: str = "996555123456"
    user_email: str = "user@example.com"


class PaymentStatusCheck(BaseModel):
    order_id: str


# Базовая модель с общими полями
class TransactionBase(BaseModel):
    user_id: int
    amount: float
    status: TransactionStatus = TransactionStatus.PENDING
    payment_id: Optional[str] = None
    order_id: Optional[str] = None
    package_type: Optional[PackageType] = None 


# Модель для создания новой транзакции
class TransactionCreate(TransactionBase):
    pass


# Модель для обновления транзакции (все поля опциональны)
class TransactionUpdate(BaseModel):
    amount: Optional[float] = None
    status: Optional[TransactionStatus] = None
    payment_id: Optional[str] = None
    order_id: Optional[str] = None


# Полная модель транзакции (включая ID и временные метки)
class TransactionInDB(TransactionBase):
    transaction_id:UUID4
    created_at: datetime
    updated_at: datetime

    is_deleted: bool
    deleted_at: Optional[datetime] = None 


    class Config:
        orm_mode = True


# Модель для возврата клиенту (может скрывать некоторые внутренние поля)
class TransactionResponse(TransactionInDB):
    pass

# credits_total & credits_left & purchase_time & credits_expire_date 
# all above fields' update is going to be handled separatly
class UserUpdate(BaseModel):
    is_paid: Optional[bool] = None 


class UserResponse(BaseModel):
    telegram_id: int
    credits_total: int
    credits_left: int
    is_paid: bool
    purchase_time: Optional[datetime] = None
    credits_expire_date: Optional[datetime] = None
    total_generations: int
    total_prompt_tokens: int
    total_response_tokens: int
    total_video_duration_time: int
    other_data: Optional[dict] = None

    is_deleted: bool
    deleted_at: Optional[datetime] = None 

    class Config:
        from_attributes = True



class UserFilterParams(BaseModel):
    is_paid: Optional[bool] = None
    min_credits: Optional[int] = None
    max_credits: Optional[int] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    credits_expire_before: Optional[datetime] = None
    telegram_ids: Optional[List[int]] = None
    
    class Config:
        arbitrary_types_allowed = True



class UserListResponse(BaseModel):
    items: List[UserResponse]
    pagination: Dict[str, Any]

    class Config:
        arbitrary_types_allowed = True


