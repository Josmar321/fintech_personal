from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.keyword_mapping import KeywordMapping
from app.database.repositories.base import BaseRepository


class KeywordMappingRepository(BaseRepository[KeywordMapping]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, KeywordMapping)

    async def get_by_user_id_and_keyword(
        self, user_id: int, keyword: str
    ) -> KeywordMapping | None:
        stmt = select(KeywordMapping).where(
            KeywordMapping.user_id == user_id,
            KeywordMapping.keyword == keyword,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
