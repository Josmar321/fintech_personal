from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.domain.enums import AccountType


class AccountBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: AccountType
    bank_name: str | None = Field(max_length=255, default=None)
    account_number: str | None = Field(max_length=50, default=None)
    balance: Decimal = Field(default=Decimal("0"), max_digits=18, decimal_places=2)
    currency: str = Field(default="MXN", min_length=3, max_length=3)


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    name: str | None = Field(min_length=1, max_length=100, default=None)
    type: AccountType | None = None
    bank_name: str | None = Field(max_length=255, default=None)
    account_number: str | None = Field(max_length=50, default=None)
    balance: Decimal | None = Field(default=None, max_digits=18, decimal_places=2)
    currency: str | None = Field(min_length=3, max_length=3, default=None)
    is_active: bool | None = None


class AccountRead(AccountBase):
    id: int
    user_id: int
    is_active: bool
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
