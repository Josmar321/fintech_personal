from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.enums import CategoryType


class CategoryBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: CategoryType
    icon: str | None = Field(max_length=50, default=None)
    color: str | None = Field(pattern=r"^#[0-9a-fA-F]{6}$", default=None)
    parent_id: int | None = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    name: str | None = Field(min_length=1, max_length=100, default=None)
    type: CategoryType | None = None
    icon: str | None = Field(max_length=50, default=None)
    color: str | None = Field(pattern=r"^#[0-9a-fA-F]{6}$", default=None)
    parent_id: int | None = None
    is_active: bool | None = None


class CategoryRead(CategoryBase):
    id: int
    user_id: int
    is_system: bool
    is_active: bool
    child_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
