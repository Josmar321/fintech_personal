from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import settings
from app.schemas.telegram import TelegramUpdate
from app.services.telegram_service import process_telegram_message

router = APIRouter()


async def verify_telegram_secret(
    x_telegram_bot_api_secret_token: str | None = Header(None),
) -> None:
    expected = settings.TELEGRAM_WEBHOOK_SECRET
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TELEGRAM_WEBHOOK_SECRET not configured",
        )
    if x_telegram_bot_api_secret_token != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret token",
        )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    update: TelegramUpdate,
    _=Depends(verify_telegram_secret),
):
    if update.message:
        await process_telegram_message(update.message)
    return {"ok": True}
