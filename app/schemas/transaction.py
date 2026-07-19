from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.domain.enums import TransactionType, TransactionSource


class TransactionBase(BaseModel):
    account_id: int
    category_id: int | None = None
    description: str = Field(min_length=1, max_length=500)
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    type: TransactionType
    currency: str = Field(default="MXN", min_length=3, max_length=3)
    date: datetime
    is_recurring: bool = False
    is_flagged: bool = False
    notes: str | None = Field(max_length=2000, default=None)
    source: TransactionSource = TransactionSource.MANUAL


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    account_id: int | None = None
    category_id: int | None = None
    description: str | None = Field(min_length=1, max_length=500, default=None)
    amount: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    type: TransactionType | None = None
    currency: str | None = Field(min_length=3, max_length=3, default=None)
    date: datetime | None = None
    is_recurring: bool | None = None
    is_flagged: bool | None = None
    notes: str | None = Field(max_length=2000, default=None)
    source: TransactionSource | None = None


class TransactionRead(TransactionBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
