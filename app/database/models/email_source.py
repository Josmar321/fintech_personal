from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from .account import Account
    from .user import User


class EmailSource(Base, TimestampMixin):
    __tablename__ = "email_sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id"), nullable=True
    )
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    imap_host: Mapped[str] = mapped_column(String(255), nullable=False)
    imap_port: Mapped[int] = mapped_column(
        Integer, nullable=False, default=993, server_default="993"
    )
    email_address: Mapped[str] = mapped_column(String(255), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    folder: Mapped[str] = mapped_column(
        String(100), nullable=False, default="INBOX", server_default="INBOX"
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_sync_date: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, comment="High-water mark for Yape Excel rows"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )

    user: Mapped["User"] = relationship(back_populates="email_sources")
    account: Mapped["Account | None"] = relationship()
