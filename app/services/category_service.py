import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.category import Category
from app.database.repositories.keyword_mapping_repository import KeywordMappingRepository
from app.domain.enums import CategoryType
from app.domain.seed_data import CATEGORY_KEYWORDS, _SEED_CHILDREN, _SEED_PARENTS


async def auto_categorize(text_lower: str, user_id: int, db_session: AsyncSession) -> Category | None:
    matched_name = None
    max_len = -1
    for keyword, cat_name in CATEGORY_KEYWORDS.items():
        if re.search(rf'\b{re.escape(keyword)}\b', text_lower) and len(keyword) > max_len:
            matched_name = cat_name
            max_len = len(keyword)

    if matched_name:
        stmt = select(Category).where(
            Category.user_id == user_id,
            Category.name == matched_name,
            Category.is_active == True,
        )
        result = await db_session.execute(stmt)
        cat = result.scalar_one_or_none()
        if cat:
            return cat

    kw_repo = KeywordMappingRepository(db_session)
    words = set(w for w in text_lower.split() if len(w) > 1)
    for word in words:
        mapping = await kw_repo.get_by_user_id_and_keyword(user_id, word)
        if mapping and mapping.category_id:
            stmt = select(Category).where(Category.id == mapping.category_id, Category.is_active == True)
            result = await db_session.execute(stmt)
            cat = result.scalar_one_or_none()
            if cat:
                return cat

    return None


async def get_income_category(user_id: int, db_session: AsyncSession) -> Category | None:
    stmt = (
        select(Category)
        .where(
            Category.user_id == user_id,
            Category.type == CategoryType.INCOME.value,
            Category.parent_id.is_(None),
            Category.is_active == True,
        )
        .limit(1)
    )
    result = await db_session.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create_condominio_category(user_id: int, db_session: AsyncSession) -> Category:
    stmt = select(Category).where(
        Category.user_id == user_id,
        Category.name == "Condominio",
        Category.is_active == True,
    )
    result = await db_session.execute(stmt)
    cat = result.scalar_one_or_none()
    if cat:
        return cat

    cat = Category(
        user_id=user_id, name="Condominio", type=CategoryType.CONDO,
        icon="🏢", color="#636E72", parent_id=None, is_system=True,
    )
    db_session.add(cat)
    await db_session.flush()
    return cat


async def seed_default_categories(user_id: int, db_session: AsyncSession) -> dict:
    existing = await db_session.execute(select(Category).where(Category.user_id == user_id).limit(1))
    if existing.scalar_one_or_none():
        return {"msg": "Categories already exist"}

    parent_ids: dict[str, int] = {}
    for p in _SEED_PARENTS:
        cat = Category(user_id=user_id, name=p["name"], type=p["type"], icon=p["icon"], color=p.get("color"), is_system=True)
        db_session.add(cat)
        await db_session.flush()
        parent_ids[p["name"]] = cat.id

    for parent_name, children in _SEED_CHILDREN.items():
        pid = parent_ids.get(parent_name)
        if not pid:
            continue
        for child_name, icon, child_color, type_override in children:
            cat = Category(
                user_id=user_id, name=child_name, type=type_override or CategoryType.EXPENSE, icon=icon,
                color=child_color, parent_id=pid, is_system=True,
            )
            db_session.add(cat)

    await db_session.commit()
    return {"msg": f"Seeded {len(parent_ids)} parent + children categories"}
