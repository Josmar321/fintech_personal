from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin
from app.domain.enums import TransactionType, TransactionSource

if TYPE_CHECKING:
    from .user import User
    from .account import Account
    from .category import Category


class Transaction(Base, TimestampMixin):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)

    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="MXN", server_default="MXN")
    type: Mapped[TransactionType] = mapped_column(String(20), nullable=False)

    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    is_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[TransactionSource] = mapped_column(String(20), nullable=False, default="manual", server_default="manual")
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="transactions")
    account: Mapped["Account"] = relationship(back_populates="transactions")
    category: Mapped["Category | None"] = relationship(back_populates="transactions")
