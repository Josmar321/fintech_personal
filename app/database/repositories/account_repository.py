from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.account import Account
from app.database.repositories.base import BaseRepository


class AccountRepository(BaseRepository[Account]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Account)

    async def get_by_user_id(
        self, user_id: int, *, skip: int = 0, limit: int = 100
    ) -> list[Account]:
        result = await self.session.execute(
            select(Account)
            .where(Account.user_id == user_id)
            .order_by(Account.id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_user_id_and_id(
        self, user_id: int, account_id: int
    ) -> Account | None:
        result = await self.session.execute(
            select(Account).where(
                Account.id == account_id, Account.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def delete_user_scoped(self, user_id: int, account_id: int) -> bool:
        account = await self.get_by_user_id_and_id(user_id, account_id)
        if not account:
            return False
        await self.session.delete(account)
        await self.session.flush()
        return True
