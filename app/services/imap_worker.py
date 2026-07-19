import asyncio
import email as stdlib_email
import imaplib
from datetime import datetime, timezone
from decimal import Decimal

import structlog

from app.config import settings
from app.core.encryption import decrypt_value
from app.database.unit_of_work import get_uow
from app.domain.enums import TransactionSource, TransactionStatus, TransactionType
from app.services.email_parser import parse_email

logger = structlog.get_logger()


async def _fetch_unseen_ids(client: imaplib.IMAP4_SSL, folder: str) -> list[bytes]:
    def _search():
        client.select(folder)
        status, data = client.search(None, "UNSEEN")
        if status != "OK":
            return []
        return data[0].split() if data[0] else []

    return await asyncio.to_thread(_search)


async def _fetch_email_raw(client: imaplib.IMAP4_SSL, eid: bytes) -> bytes | None:
    def _fetch():
        status, data = client.fetch(eid, "(RFC822)")
        if status != "OK" or not data or not data[0]:
            return None
        return data[0][1]

    return await asyncio.to_thread(_fetch)


async def _connect_imap(
    host: str, port: int, user: str, password: str
) -> imaplib.IMAP4_SSL | None:
    def _connect():
        try:
            client = imaplib.IMAP4_SSL(host, port)
            client.login(user, password)
            return client
        except Exception as exc:
            logger.error("imap_connect_failed", host=host, error=str(exc))
            return None

    return await asyncio.to_thread(_connect)


async def _close_imap(client: imaplib.IMAP4_SSL) -> None:
    def _close():
        try:
            client.close()
            client.logout()
        except Exception:
            pass

    await asyncio.to_thread(_close)


def _is_duplicate(
    existing_amount: Decimal,
    existing_date: datetime,
    new_amount: Decimal,
    new_date: datetime,
) -> bool:
    return (
        existing_amount == new_amount
        and existing_date.date() == new_date.date()
    )


async def process_email_source(source) -> int:
    password = decrypt_value(source.password_encrypted)

    client = await _connect_imap(source.imap_host, source.imap_port, source.email_address, password)
    if client is None:
        return 0

    try:
        email_ids = await _fetch_unseen_ids(client, source.folder)
        if not email_ids:
            return 0

        processed = 0
        async with get_uow() as uow:
            for eid in email_ids:
                raw_bytes = await _fetch_email_raw(client, eid)
                if raw_bytes is None:
                    continue

                msg = stdlib_email.message_from_bytes(raw_bytes)
                parsed = parse_email(msg)
                if parsed is None:
                    continue

                duplicate = False
                existing_txns = await uow.transactions.get_by_user_id(source.user_id, limit=50)
                for txn in existing_txns:
                    if _is_duplicate(txn.amount, txn.date, parsed.amount, parsed.date):
                        duplicate = True
                        break

                if duplicate:
                    logger.debug("duplicate_skipped", amount=str(parsed.amount), date=str(parsed.date))
                    continue

                await uow.transactions.create(
                    user_id=source.user_id,
                    account_id=None,
                    description=parsed.description,
                    amount=parsed.amount,
                    type=TransactionType.EXPENSE,
                    currency="MXN",
                    date=parsed.date,
                    source=TransactionSource.IMAP,
                    status=TransactionStatus.PENDING_CATEGORY,
                    raw_data=parsed.raw_data,
                )
                processed += 1

                source.last_checked_at = datetime.now(timezone.utc)

            logger.info(
                "source_processed",
                source_id=source.id,
                bank=source.bank_name,
                total_unseen=len(email_ids),
                new_transactions=processed,
            )

        return processed
    finally:
        await _close_imap(client)


async def run_imap_worker() -> None:
    logger.info(
        "imap_worker_started",
        poll_interval=settings.IMAP_POLL_INTERVAL,
    )

    while True:
        try:
            async with get_uow() as uow:
                sources = await uow.email_sources.get_active_sources()
                for source in sources:
                    try:
                        await process_email_source(source)
                    except Exception as exc:
                        logger.error(
                            "source_processing_failed",
                            source_id=source.id,
                            error=str(exc),
                        )

        except asyncio.CancelledError:
            logger.info("imap_worker_cancelled")
            raise
        except Exception as exc:
            logger.error("imap_worker_cycle_failed", error=str(exc))

        await asyncio.sleep(settings.IMAP_POLL_INTERVAL)
