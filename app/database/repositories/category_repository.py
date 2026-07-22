from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.category import Category
from app.database.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Category)

    async def get_by_user_id(
        self, user_id: int, *, skip: int = 0, limit: int = 100
    ) -> list[Category]:
        result = await self.session.execute(
            select(Category)
            .where(Category.user_id == user_id)
            .order_by(Category.id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_user_id_and_id(
        self, user_id: int, category_id: int
    ) -> Category | None:
        result = await self.session.execute(
            select(Category).where(
                Category.id == category_id, Category.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def get_root_categories(self, user_id: int) -> list[Category]:
        result = await self.session.execute(
            select(Category).where(
                Category.user_id == user_id, Category.parent_id.is_(None)
            )
        )
        return list(result.scalars().all())

    async def get_children(self, category_id: int) -> list[Category]:
        result = await self.session.execute(
            select(Category).where(Category.parent_id == category_id)
        )
        return list(result.scalars().all())

    async def delete_user_scoped(self, user_id: int, category_id: int) -> bool:
        category = await self.get_by_user_id_and_id(user_id, category_id)
        if not category:
            return False
        await self.session.delete(category)
        await self.session.flush()
        return True
