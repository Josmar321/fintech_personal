from datetime import datetime
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import BaseRepository
from app.database.models.email_source import EmailSource


class EmailSourceRepository(BaseRepository[EmailSource]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(EmailSource, session)

    async def get_active_sources(self) -> Sequence[EmailSource]:
        stmt = select(EmailSource).where(EmailSource.is_active == True)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_last_sync_date(
        self, source_id: int, last_sync_date: datetime
    ) -> None:
        stmt = (
            update(EmailSource)
            .where(EmailSource.id == source_id)
            .values(last_sync_date=last_sync_date)
        )
        await self.session.execute(stmt)
