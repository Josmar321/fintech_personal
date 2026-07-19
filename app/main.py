from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.endpoints import accounts, auth, categories, transactions
from app.config import settings
from app.core.logging import setup_logging
from app.core.rate_limiter import RateLimitMiddleware
from app.database.connection import check_db_health, ensure_database

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    logger.info(
        "app_starting",
        name=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
    )
    try:
        await ensure_database()
        logger.info("database_initialized")
    except Exception as exc:
        logger.warning("database_init_skipped", error=str(exc))
    yield
    logger.info("app_shutting_down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware, calls=60, period=60)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(accounts.router, prefix="/api/v1/accounts", tags=["accounts"])
app.include_router(categories.router, prefix="/api/v1/categories", tags=["categories"])
app.include_router(transactions.router, prefix="/api/v1/transactions", tags=["transactions"])


@app.get("/health", tags=["system"])
async def health_check() -> JSONResponse:
    db_ok = await check_db_health()
    return JSONResponse(
        content={
            "status": "ok" if db_ok else "degraded",
            "version": settings.APP_VERSION,
            "database": "connected" if db_ok else "unavailable",
        },
        status_code=200 if db_ok else 503,
    )
