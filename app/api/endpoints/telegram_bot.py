from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.config import settings
from app.schemas.telegram import TelegramUpdate
from app.services.telegram_service import process_callback_query, process_incoming_message

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
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_telegram_secret),
):
    if update.message and update.message.text:
        chat_id = update.message.chat.id
        text = update.message.text.strip()
        await process_incoming_message(chat_id, text, db)
        return {"ok": True}

    if update.callback_query:
        await process_callback_query(update.callback_query, db)
        return {"ok": True}

    return {"ok": True}
