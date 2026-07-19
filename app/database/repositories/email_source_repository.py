from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.email_source import EmailSource
from app.database.repositories.base import BaseRepository


class EmailSourceRepository(BaseRepository[EmailSource]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, EmailSource)

    async def get_active_sources(self) -> list[EmailSource]:
        result = await self.session.execute(
            select(EmailSource).where(EmailSource.is_active == True)
        )
        return list(result.scalars().all())
