from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy import URL as DBURL
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings


def _build_url(database: str | None = None) -> DBURL:
    return DBURL.create(
        "mssql+aioodbc",
        username=settings.DB_USER,
        password=settings.DB_PASS,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=database or settings.DB_NAME,
        query={
            "driver": "ODBC Driver 18 for SQL Server",
            "TrustServerCertificate": "yes",
        },
    )


engine = create_async_engine(
    _build_url(),
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def get_managed_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def ensure_database() -> None:
    master_engine = create_async_engine(
        _build_url("master"), isolation_level="AUTOCOMMIT"
    )
    try:
        async with master_engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM sys.databases WHERE name = :name"
                ),
                {"name": settings.DB_NAME},
            )
            if result.scalar() == 0:
                await conn.execute(
                    text(f"CREATE DATABASE [{settings.DB_NAME}]")
                )
    finally:
        await master_engine.dispose()


async def check_db_health() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
