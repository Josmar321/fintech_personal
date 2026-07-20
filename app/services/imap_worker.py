import asyncio
import imaplib
import email
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence

import structlog

from app.config import settings
from app.database.repositories.email_source_repository import EmailSourceRepository
from app.database.repositories.transaction_repository import TransactionRepository
from app.database.unit_of_work import AsyncSessionFactory
from app.services.email_parser import (
    ParsedTransaction,
    parse_bbva_email,
    parse_yape_excel,
    parse_email,
)
from app.services.telegram_service import send_message

logger = structlog.get_logger()

BATCH_SIZE = 50

BANK_STRATEGIES = {
    "BBVA": parse_bbva_email,
    "YAPE": parse_yape_excel,
}

CONDO_KEYWORDS = ["agua", "dpto", "consumo", "departamento"]


async def run_worker_loop() -> None:
    logger.info("imap_worker_started", poll_interval=settings.IMAP_POLL_INTERVAL)
    while True:
        try:
            await process_all_sources()
        except Exception:
            logger.exception("imap_worker_cycle_error")
        await asyncio.sleep(settings.IMAP_POLL_INTERVAL)


async def process_all_sources() -> None:
    async with AsyncSessionFactory() as session:
        repo = EmailSourceRepository(session)
        sources = await repo.get_active_sources()

    for source in sources:
        try:
            await process_source(source)
        except Exception:
            logger.exception("source_processing_error", source_id=source.id)


async def process_source(source) -> None:
    logger.info("processing_source", source_id=source.id, bank=source.bank_name)

    transactions = await _fetch_and_parse(source)

    if not transactions:
        logger.info("no_transactions_found", source_id=source.id)
        return

    strategy = source.bank_name.upper()

    if strategy == "YAPE":
        await _process_yape(source, transactions)
    elif strategy == "BBVA":
        await _process_single(source, transactions, parse_bbva_email)
    else:
        await _process_generic(source, transactions)


async def _process_yape(source, transactions: Sequence[ParsedTransaction]) -> None:
    # HWM filter
    last_date = source.last_sync_date
    if last_date:
        if last_date.tzinfo is None:
            last_date = last_date.replace(tzinfo=timezone.utc)
        transactions = [t for t in transactions if t.date > last_date]
        logger.info(
            "yape_hwm_filter",
            total_before=len(transactions),
            after_hwm=len(transactions),
            last_sync_date=str(last_date),
        )
        if not transactions:
            return

    max_date = max(t.date for t in transactions)
    min_date = min(t.date for t in transactions)
    max_date_naive = max_date.replace(tzinfo=None)

    async with AsyncSessionFactory() as session:
        from app.services.condo_sheets_service import register_water_payment

        tx_repo = TransactionRepository(session)
        uow = tx_repo.uow

        # Separate condo vs non-condo before any DB write
        to_create: list[dict] = []
        condo_alerts: list[ParsedTransaction] = []

        for t in transactions:
            is_condo = (
                t.type == "income"
                and t.mensaje
                and any(kw in t.mensaje.lower() for kw in CONDO_KEYWORDS)
            )

            if not is_condo:
                to_create.append(_txn_dict(source, t))
                continue

            ok, msg = await asyncio.to_thread(
                register_water_payment,
                origen=t.origen or "",
                monto=float(t.amount),
                mensaje=t.mensaje,
                fecha_operacion=t.date,
            )

            if ok:
                to_create.append(_txn_dict(source, t))
                logger.info("condo_auto_approved", amount=str(t.amount), mensaje=t.mensaje)
            else:
                condo_alerts.append(t)
                logger.warning("condo_manual_review", amount=str(t.amount), mensaje=t.mensaje)

        # Dedup against existing
        existing_pairs: set[tuple[str, str]] = set()
        if to_create:
            existing_pairs = await tx_repo.get_existing_pairs(
                user_id=source.user_id,
                min_date=min_date,
                max_date=max_date,
                amount=Decimal("0"),
            )

        final_create = [
            d for d in to_create
            if (d["date"].strftime("%Y-%m-%d"), str(d["amount"])) not in existing_pairs
        ]

        logger.info(
            "yape_batch_stats",
            raw=len(transactions),
            condo_auto=sum(1 for d in to_create if d not in final_create or True),
            deduped=len(to_create) - len(final_create),
            inserted=len(final_create),
            alerts=len(condo_alerts),
        )

        if final_create:
            await tx_repo.bulk_create_from_dicts(final_create)

        await EmailSourceRepository(session).update_last_sync_date(
            source.id, max_date_naive
        )

        await uow.commit()

    # Condo alerts (outside DB session)
    if condo_alerts:
        async with AsyncSessionFactory() as session:
            from sqlalchemy import select
            from app.database.models.user import User

            stmt = select(User.telegram_chat_id).where(User.id == source.user_id)
            result = await session.execute(stmt)
            row = result.one_or_none()
            chat_id = row[0] if row else None

        if chat_id:
            for t in condo_alerts:
                text = (
                    f"⚠️ *Pago a revisar:* {t.origen or 'Desconocido'} "
                    f"yapeó S/ {float(t.amount):.2f}. "
                    f"Mensaje: {t.mensaje}"
                )
                await send_message(chat_id, text)


async def _process_single(source, transactions: Sequence[ParsedTransaction], parser) -> None:
    async with AsyncSessionFactory() as session:
        tx_repo = TransactionRepository(session)
        uow = tx_repo.uow
        parsed = transactions[0] if transactions else None
        if parsed:
            await tx_repo.create(
                user_id=source.user_id,
                account_id=source.account_id,
                amount=parsed.amount,
                type=parsed.type,
                description=parsed.description,
                date=parsed.date.replace(tzinfo=None),
                status="PENDING_CATEGORY",
            )
        await uow.commit()


async def _process_generic(source, transactions: Sequence[ParsedTransaction]) -> None:
    async with AsyncSessionFactory() as session:
        tx_repo = TransactionRepository(session)
        uow = tx_repo.uow
        for parsed in transactions:
            await tx_repo.create(
                user_id=source.user_id,
                account_id=source.account_id,
                amount=parsed.amount,
                type=parsed.type,
                description=parsed.description,
                date=parsed.date.replace(tzinfo=None),
                status="PENDING_CATEGORY",
            )
        await uow.commit()


def _txn_dict(source, t: ParsedTransaction) -> dict:
    return {
        "user_id": source.user_id,
        "account_id": source.account_id,
        "amount": t.amount,
        "type": t.type,
        "description": t.description,
        "date": t.date.replace(tzinfo=None),
        "status": "PENDING_CATEGORY",
    }


async def _fetch_and_parse(source) -> Sequence[ParsedTransaction]:
    strategy = source.bank_name.upper()

    if strategy == "YAPE":
        raw_messages = await _fetch_recent_emails(source)
        transactions = []
        for msg in raw_messages:
            parsed_list = parse_yape_excel(msg)
            transactions.extend(parsed_list)
        return transactions

    if strategy == "BBVA":
        raw_messages = await _fetch_recent_emails(source)
        transactions = []
        for msg in raw_messages:
            parsed = parse_bbva_email(msg)
            if parsed:
                transactions.append(parsed)
        return transactions

    raw_messages = await _fetch_recent_emails(source)
    transactions = []
    for msg in raw_messages:
        parsed = parse_email(msg)
        if parsed:
            transactions.append(parsed)
    return transactions


async def _fetch_recent_emails(source) -> list:
    return await asyncio.to_thread(_fetch_recent_emails_sync, source)


def _fetch_recent_emails_sync(source) -> list:
    from app.core.crypto import Encryption

    try:
        password = Encryption.decrypt(source.password_encrypted)
    except Exception:
        logger.error("decrypt_failed", source_id=source.id)
        return []

    try:
        mail = imaplib.IMAP4_SSL(source.imap_host, source.imap_port)
        mail.login(source.email_address, password)
        mail.select(source.folder)

        search_criteria = "UNSEEN" if settings.IMAP_UNSEEN_ONLY else "ALL"
        status, message_ids = mail.search(None, search_criteria)
        if status != "OK" or not message_ids[0]:
            mail.logout()
            return []

        ids = message_ids[0].split()
        ids = ids[-BATCH_SIZE:]

        messages = []
        for mid in ids:
            status, msg_data = mail.fetch(mid, "(RFC822)")
            if status != "OK":
                continue
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            messages.append(msg)

        mail.logout()
        return messages

    except Exception:
        logger.exception("imap_fetch_failed", source_id=source.id)
        return []
