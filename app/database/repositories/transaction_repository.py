from datetime import datetime
from decimal import Decimal
from typing import Any, Sequence

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import BaseRepository
from app.database.models.transaction import Transaction


class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Transaction, session)

    async def get_by_user_id_and_id(
        self, user_id: int, transaction_id: int
    ) -> Transaction | None:
        stmt = select(Transaction).where(
            Transaction.user_id == user_id, Transaction.id == transaction_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_existing_pairs(
        self,
        user_id: int,
        min_date: datetime,
        max_date: datetime,
        amount: Decimal,
    ) -> set[tuple[str, str]]:
        stmt = select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.date >= min_date,
            Transaction.date <= max_date,
            Transaction.amount == amount,
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return {(r.date.strftime("%Y-%m-%d"), str(r.amount)) for r in rows}

    async def bulk_create_from_dicts(
        self, items: list[dict[str, Any]]
    ) -> Sequence[Transaction]:
        transactions = [Transaction(**item) for item in items]
        self.session.add_all(transactions)
        await self.session.flush()
        return transactions
