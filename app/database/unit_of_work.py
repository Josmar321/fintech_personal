from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import async_session_factory
from app.database.repositories.account_repository import AccountRepository
from app.database.repositories.category_repository import CategoryRepository
from app.database.repositories.email_source_repository import EmailSourceRepository
from app.database.repositories.transaction_repository import TransactionRepository
from app.database.repositories.user_repository import UserRepository


class UnitOfWork:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._user_repo: UserRepository | None = None
        self._account_repo: AccountRepository | None = None
        self._category_repo: CategoryRepository | None = None
        self._transaction_repo: TransactionRepository | None = None
        self._email_source_repo: EmailSourceRepository | None = None

    @property
    def users(self) -> UserRepository:
        if self._user_repo is None:
            self._user_repo = UserRepository(self.session)
        return self._user_repo

    @property
    def accounts(self) -> AccountRepository:
        if self._account_repo is None:
            self._account_repo = AccountRepository(self.session)
        return self._account_repo

    @property
    def categories(self) -> CategoryRepository:
        if self._category_repo is None:
            self._category_repo = CategoryRepository(self.session)
        return self._category_repo

    @property
    def transactions(self) -> TransactionRepository:
        if self._transaction_repo is None:
            self._transaction_repo = TransactionRepository(self.session)
        return self._transaction_repo

    @property
    def email_sources(self) -> EmailSourceRepository:
        if self._email_source_repo is None:
            self._email_source_repo = EmailSourceRepository(self.session)
        return self._email_source_repo

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
