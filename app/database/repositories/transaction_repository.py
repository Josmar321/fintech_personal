from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.transaction import Transaction
from app.database.repositories.base import BaseRepository
from app.domain.enums import TransactionType


class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Transaction)

    async def get_by_user_id(
        self, user_id: int, *, skip: int = 0, limit: int = 100
    ) -> list[Transaction]:
        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_user_id_and_id(
        self, user_id: int, transaction_id: int
    ) -> Transaction | None:
        result = await self.session.execute(
            select(Transaction).where(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_filtered(
        self,
        user_id: int,
        *,
        account_id: int | None = None,
        category_id: int | None = None,
        type: TransactionType | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Transaction]:
        stmt = select(Transaction).where(Transaction.user_id == user_id)

        if account_id is not None:
            stmt = stmt.where(Transaction.account_id == account_id)
        if category_id is not None:
            stmt = stmt.where(Transaction.category_id == category_id)
        if type is not None:
            stmt = stmt.where(Transaction.type == type)
        if date_from is not None:
            stmt = stmt.where(Transaction.date >= date_from)
        if date_to is not None:
            stmt = stmt.where(Transaction.date <= date_to)

        stmt = stmt.order_by(Transaction.date.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_user_scoped(
        self, user_id: int, transaction_id: int
    ) -> bool:
        transaction = await self.get_by_user_id_and_id(user_id, transaction_id)
        if not transaction:
            return False
        await self.session.delete(transaction)
        await self.session.flush()
        return True
