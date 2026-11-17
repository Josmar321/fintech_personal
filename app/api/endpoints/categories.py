from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user, get_db
from app.database.models.user import User
from app.database.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.services.category_service import seed_default_categories

router = APIRouter()


@router.get("/", response_model=list[CategoryRead])
async def list_categories(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = CategoryRepository(db)
    return await repo.get_by_user_id(current_user.id, skip=skip, limit=limit)


@router.post("/", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = CategoryRepository(db)
    if data.parent_id:
        parent = await repo.get_by_user_id_and_id(current_user.id, data.parent_id)
        if not parent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent category not found")
    return await repo.create(user_id=current_user.id, **data.model_dump())


@router.get("/tree", response_model=list[CategoryRead])
async def get_category_tree(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = CategoryRepository(db)
    roots = await repo.get_root_categories(current_user.id)
    result = []
    for root in roots:
        node = CategoryRead.model_validate(root)
        children = await repo.get_children(root.id)
        node.child_count = len(children)
        result.append(node)
    return result


@router.get("/{category_id}", response_model=CategoryRead)
async def get_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = CategoryRepository(db)
    category = await repo.get_by_user_id_and_id(current_user.id, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


@router.patch("/{category_id}", response_model=CategoryRead)
async def update_category(
    category_id: int,
    data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = CategoryRepository(db)
    category = await repo.get_by_user_id_and_id(current_user.id, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return await repo.update(category.id, **data.model_dump(exclude_unset=True))


@router.post("/seed")
async def seed_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await seed_default_categories(current_user.id, db)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = CategoryRepository(db)
    deleted = await repo.delete_user_scoped(current_user.id, category_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
