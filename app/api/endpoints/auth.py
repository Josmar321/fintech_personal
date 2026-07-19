from fastapi import APIRouter, Depends, HTTPException, status
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.config import settings
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.database.models.user import User
from app.database.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, RegisterResponse, TokenResponse
from app.schemas.user import UserCreate, UserRead

router = APIRouter()


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)

    existing = await repo.get_by_email(data.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = await repo.create(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
    )

    token = create_access_token({"sub": str(user.id)})

    return RegisterResponse(
        user=UserRead.model_validate(user),
        access_token=token,
        expires_in=settings.JWT_EXPIRY_MINUTES * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)

    user = await repo.get_by_email(data.email)
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token({"sub": str(user.id)})

    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRY_MINUTES * 60,
    )


@router.get("/me", response_model=UserRead)
async def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return UserRead.model_validate(current_user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    current_user: User = Depends(get_current_user),
):
    token = create_access_token({"sub": str(current_user.id)})

    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRY_MINUTES * 60,
    )
