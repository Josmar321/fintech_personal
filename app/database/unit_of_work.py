from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import async_session_factory
from app.database.repositories.user_repository import UserRepository


class UnitOfWork:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._user_repo: UserRepository | None = None

    @property
    def users(self) -> UserRepository:
        if self._user_repo is None:
            self._user_repo = UserRepository(self.session)
        return self._user_repo

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()


@asynccontextmanager
async def get_uow() -> AsyncGenerator[UnitOfWork, None]:
    async with async_session_factory() as session:
        uow = UnitOfWork(session)
        try:
            yield uow
            await uow.commit()
        except Exception:
            await uow.rollback()
            raise
