import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import httpx
import structlog

from app.config import settings
from app.database.unit_of_work import get_uow
from app.domain.enums import TransactionSource, TransactionStatus, TransactionType
from app.schemas.telegram import Message

logger = structlog.get_logger()

_TELEGRAM_API = "https://api.telegram.org/bot"

_EXPENSE_TRIGGERS = ("gast", "pag")
_INCOME_TRIGGERS = ("recib",)

_EXPENSE_PATTERN = re.compile(
    r"(?:gast[ée]|gasto|pag[uú]|pague)\s+"
    r"(\d+(?:[.,]\d{1,2})?)\s+"
    r"(?:en|de|por|para)\s+"
    r"(.+)",
    re.IGNORECASE,
)

_INCOME_PATTERN = re.compile(
    r"(?:recib[ií]|recibo)\s+"
    r"(\d+(?:[.,]\d{1,2})?)\s+"
    r"(?:de|por|para)\s+"
    r"(.+)",
    re.IGNORECASE,
)


async def _send_message(chat_id: int, text: str, parse_mode: str = "Markdown") -> bool:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("telegram_bot_token_missing")
        return False

    url = f"{_TELEGRAM_API}{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.error("telegram_send_failed", chat_id=chat_id, error=str(exc))
            return False


async def _handle_pendientes(chat_id: int, user_id: int) -> None:
    async with get_uow() as uow:
        txns = await uow.transactions.get_filtered(
            user_id=user_id,
            status=TransactionStatus.PENDING_CATEGORY,
            limit=20,
        )

    if not txns:
        await _send_message(chat_id, "✅ No hay transacciones pendientes de categorizar.")
        return

    lines = ["📋 *Transacciones pendientes:*\n"]
    for i, txn in enumerate(txns, 1):
        fecha = txn.date.strftime("%d/%m/%Y") if txn.date else "??"
        desc = txn.description[:50]
        monto = f"${txn.amount:,.2f}"
        lines.append(f"{i}. {fecha} — *{monto}*\n   _{desc}_\n")

    await _send_message(chat_id, "\n".join(lines))


async def _handle_manual_entry(chat_id: int, user_id: int, text: str) -> None:
    match = _EXPENSE_PATTERN.search(text)
    is_expense = True

    if not match:
        match = _INCOME_PATTERN.search(text)
        is_expense = False

    if not match:
        await _send_message(
            chat_id,
            "❌ No entendí. Usá formato:\n"
            "`Gasté 50 en transporte`\n"
            "`Recibí 1500 de salario`",
        )
        return

    try:
        amount = Decimal(match.group(1).replace(",", "."))
    except InvalidOperation:
        await _send_message(chat_id, "❌ No pude interpretar el monto.")
        return

    description = match.group(2).strip().capitalize()
    tx_type = TransactionType.EXPENSE if is_expense else TransactionType.INCOME

    async with get_uow() as uow:
        await uow.transactions.create(
            user_id=user_id,
            account_id=None,
            description=description,
            amount=amount,
            type=tx_type,
            currency="MXN",
            date=datetime.now(timezone.utc),
            source=TransactionSource.API,
            status=TransactionStatus.PENDING_CATEGORY,
        )

    emoji = "💸" if is_expense else "💰"
    label = "Gasto" if is_expense else "Ingreso"
    await _send_message(
        chat_id,
        f"{emoji} *Registrado!*\n"
        f"Monto: *${amount:,.2f}*\n"
        f"Concepto: _{description}_\n"
        f"Tipo: {label}",
    )


async def _handle_start(chat_id: int, user_id: int, user_name: str) -> None:
    await _send_message(
        chat_id,
        f"👋 *Bienvenido, {user_name}!*\n\n"
        "Comandos:\n"
        "`/pendientes` — Transacciones sin categorizar\n"
        "`Gasté X en Y` — Registrar gasto\n"
        "`Recibí X de Y` — Registrar ingreso\n",
    )


async def process_telegram_message(msg: Message) -> None:
    if not msg.text:
        return

    chat_id = msg.chat.id
    text = msg.text.strip()

    async with get_uow() as uow:
        user = await uow.users.get_by_telegram_chat(chat_id)

    if user is None:
        name = "Usuario"
        if msg.from_:
            name = msg.from_.first_name
        await _send_message(
            chat_id,
            f"👋 *Hola {name}!*\n\n"
            f"Tu *Chat ID* es: `{chat_id}`\n\n"
            "Para vincular tu cuenta:\n"
            "1. Iniciá sesión en la web\n"
            "2. Usá el endpoint `/api/v1/auth/link-telegram`\n"
            "   con tu token JWT y este Chat ID\n\n"
            "Una vez vinculado, podrás usar los comandos.",
        )
        return

    if text.startswith("/start"):
        await _handle_start(chat_id, user.id, user.full_name)

    elif text.startswith("/pendientes"):
        await _handle_pendientes(chat_id, user.id)

    elif text.lower().startswith(_EXPENSE_TRIGGERS) or text.lower().startswith(_INCOME_TRIGGERS):
        await _handle_manual_entry(chat_id, user.id, text)

    else:
        await _send_message(
            chat_id,
            "❓ No reconozco ese comando.\n"
            "Usá `/pendientes` o escribí `Gasté 50 en transporte`.",
        )
