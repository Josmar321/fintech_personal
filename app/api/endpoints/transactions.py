from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_active_user, get_db
from app.database.models.user import User
from app.database.repositories.transaction_repository import TransactionRepository
from app.domain.enums import TransactionType
from app.schemas.transaction import TransactionCreate, TransactionRead, TransactionUpdate

router = APIRouter()


@router.get("/", response_model=list[TransactionRead])
async def list_transactions(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    account_id: int | None = None,
    category_id: int | None = None,
    type: TransactionType | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = TransactionRepository(db)
    return await repo.get_filtered(
        current_user.id,
        account_id=account_id,
        category_id=category_id,
        type=type,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )


@router.post("/", response_model=TransactionRead, status_code=201)
async def create_transaction(
    data: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = TransactionRepository(db)
    return await repo.create(user_id=current_user.id, **data.model_dump())


@router.get("/{transaction_id}", response_model=TransactionRead)
async def get_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = TransactionRepository(db)
    transaction = await repo.get_by_user_id_and_id(current_user.id, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.patch("/{transaction_id}", response_model=TransactionRead)
async def update_transaction(
    transaction_id: int,
    data: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = TransactionRepository(db)
    transaction = await repo.get_by_user_id_and_id(current_user.id, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return await repo.update(transaction.id, **data.model_dump(exclude_unset=True))


@router.delete("/{transaction_id}", status_code=204)
async def delete_transaction(
    transaction_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    repo = TransactionRepository(db)
    deleted = await repo.delete_user_scoped(current_user.id, transaction_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Transaction not found")
