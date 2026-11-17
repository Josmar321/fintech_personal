from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User
    from .category import Category


class KeywordMapping(Base, TimestampMixin):
    __tablename__ = "keyword_mappings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    keyword: Mapped[str] = mapped_column(String(100), nullable=False)
    category_name: Mapped[str] = mapped_column(String(100), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="keyword_mappings")
    category: Mapped["Category | None"] = relationship()
