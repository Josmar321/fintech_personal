from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user, get_db
from app.database.models.user import User
from app.database.repositories.account_repository import AccountRepository
from app.schemas.account import AccountCreate, AccountRead, AccountUpdate

router = APIRouter()


@router.get("/", response_model=list[AccountRead])
async def list_accounts(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = AccountRepository(db)
    return await repo.get_by_user_id(current_user.id, skip=skip, limit=limit)


@router.post("/", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(
    data: AccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = AccountRepository(db)
    return await repo.create(user_id=current_user.id, **data.model_dump())


@router.get("/{account_id}", response_model=AccountRead)
async def get_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = AccountRepository(db)
    account = await repo.get_by_user_id_and_id(current_user.id, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


@router.patch("/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: int,
    data: AccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = AccountRepository(db)
    account = await repo.get_by_user_id_and_id(current_user.id, account_id)
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return await repo.update(account.id, **data.model_dump(exclude_unset=True))


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = AccountRepository(db)
    deleted = await repo.delete_user_scoped(current_user.id, account_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
