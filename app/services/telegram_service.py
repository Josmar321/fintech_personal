import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import httpx
import structlog
from sqlalchemy import select

from app.config import settings
from app.database.models.category import Category
from app.database.repositories.account_repository import AccountRepository
from app.database.repositories.category_repository import CategoryRepository
from app.database.repositories.transaction_repository import TransactionRepository
from app.database.repositories.user_repository import UserRepository
from app.domain.enums import AccountType, CategoryType, TransactionSource, TransactionStatus, TransactionType

logger = structlog.get_logger()

_AMOUNT_RE = re.compile(r"(\d+(?:[.,]\d{1,2})?)")

CATEGORY_KEYWORDS = {
    # 🥩 Alimentación
    "mercado": "Mercado", "despensa": "Mercado",
    "almuerzo": "Comida Fuera", "menu": "Comida Fuera", "restaurant": "Comida Fuera",
    "galletas": "Antojos", "snack": "Antojos", "cafe": "Antojos",
    # 🚌 Transporte
    "pasaje": "Transporte Diario", "bus": "Transporte Diario", "corredor": "Transporte Diario",
    "uber": "Taxis / Apps", "yango": "Taxis / Apps", "indriver": "Taxis / Apps",
    # 🏋️ Powerlifting & Salud
    "creatina": "Suplementación", "proteina": "Suplementación",
    "gym": "Gimnasio & Equipamiento", "magnesio": "Gimnasio & Equipamiento",
    "fisio": "Recuperación", "masaje": "Recuperación",
    # 💻 Tecnología & Laboratorios
    "vps": "Servidores e Infraestructura", "digitalocean": "Servidores e Infraestructura",
    "aws": "Servidores e Infraestructura",
    "openai": "Suscripciones IA & APIs", "chatgpt": "Suscripciones IA & APIs",
    "claude": "Suscripciones IA & APIs", "gemini": "Suscripciones IA & APIs",
    "ia": "Suscripciones IA & APIs", "tokens": "Suscripciones IA & APIs",
    # 🎓 Universidad & Desarrollo
    "certificacion": "Certificaciones", "examen": "Certificaciones",
    "tramite": "Trámites & Universidad", "constancia": "Trámites & Universidad",
    "tesis": "Proyectos Grupales", "grupo": "Proyectos Grupales", "juntada": "Proyectos Grupales",
    # 📱 Servicios, Ocio y Otros
    "celular": "Servicios Básicos", "internet": "Servicios Básicos", "plan": "Servicios Básicos",
    "netflix": "Entretenimiento", "spotify": "Entretenimiento",
    "cine": "Vida Social", "bar": "Vida Social", "fiesta": "Vida Social",
    "corte": "Gastos Personales", "barberia": "Gastos Personales", "ropa": "Gastos Personales",
}


async def send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> bool:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("telegram_bot_token_missing")
        return False
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.error("telegram_send_failed", chat_id=chat_id, error=str(exc))
            return False


async def edit_message_text(chat_id: int, message_id: int, text: str, reply_markup: dict | None = None) -> bool:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("telegram_bot_token_missing")
        return False
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.error("telegram_edit_failed", chat_id=chat_id, message_id=message_id, error=str(exc))
            return False


async def answer_callback_query(callback_query_id: str) -> bool:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("telegram_bot_token_missing")
        return False
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(url, json={"callback_query_id": callback_query_id})
            resp.raise_for_status()
            return True
        except httpx.HTTPError as exc:
            logger.error("telegram_answer_callback_failed", callback_query_id=callback_query_id, error=str(exc))
            return False


async def _get_or_create_account(
    repo: AccountRepository, user_id: int, name: str, acct_type: AccountType
):
    accounts = await repo.get_by_user_id(user_id, limit=50)
    existing = next((a for a in accounts if a.name == name), None)
    if existing:
        return existing
    return await repo.create(
        user_id=user_id,
        name=name,
        type=acct_type,
        currency="PEN",
        balance=Decimal("0"),
    )


async def _build_category_keyboard(user_id: int, transaction_id: int, db_session) -> dict | None:
    stmt = select(Category).where(
        Category.user_id == user_id,
        Category.type == CategoryType.EXPENSE.value,
        Category.is_active == True,
        Category.parent_id.isnot(None),
    ).order_by(Category.parent_id)
    result = await db_session.execute(stmt)
    categories = list(result.scalars().all())
    if not categories:
        return None

    rows = []
    for i in range(0, len(categories), 3):
        row_cats = categories[i:i + 3]
        rows.append([
            {
                "text": f"{cat.icon or '📁'} {cat.name}",
                "callback_data": f"cat:{transaction_id}:{cat.id}",
            }
            for cat in row_cats
        ])
    return {"inline_keyboard": rows}


async def _auto_categorize(text_lower: str, user_id: int, db_session) -> Category | None:
    matched_name = None
    max_len = -1
    for keyword, cat_name in CATEGORY_KEYWORDS.items():
        if keyword in text_lower and len(keyword) > max_len:
            matched_name = cat_name
            max_len = len(keyword)

    if matched_name is None:
        return None

    stmt = select(Category).where(
        Category.user_id == user_id,
        Category.name == matched_name,
        Category.is_active == True,
    )
    result = await db_session.execute(stmt)
    return result.scalar_one_or_none()


async def process_incoming_message(chat_id: int, text: str, db_session) -> None:
    if text.strip() == '/start':
        await send_message(
            chat_id,
            "👋 ¡Hola Admin! Envíame tus gastos con el formato: [Monto] [Descripción] [Cuenta opcional]. Ej: 15 en taxi yape."
        )
        return

    user_repo = UserRepository(db_session)
    user = await user_repo.get_by_telegram_chat(chat_id)

    if user is None:
        if settings.TELEGRAM_CHAT_ID and str(chat_id).strip() == str(settings.TELEGRAM_CHAT_ID).strip():
            user = await user_repo.create(
                email=f"telegram_{chat_id}@local",
                password_hash="<auto-registered>",
                full_name="Admin",
                telegram_chat_id=chat_id,
            )
            logger.info("admin_auto_registered", chat_id=chat_id)
        else:
            error_msg = f"❌ Acceso denegado.\nTu ID de Telegram es: '{chat_id}'\nEl ID en el .env es: '{settings.TELEGRAM_CHAT_ID}'"
            await send_message(chat_id, error_msg)
            return

    match = _AMOUNT_RE.search(text)
    if not match:
        await send_message(
            chat_id,
            "❌ No entendí el monto. Ej: `15 en taxi`",
        )
        return

    try:
        amount = Decimal(match.group(1).replace(",", "."))
    except InvalidOperation:
        await send_message(chat_id, "❌ Monto inválido.")
        return

    text_lower = text.lower()

    if "yape" in text_lower:
        account_name = "Yape"
        acct_type = AccountType.CHECKING
    elif "credito" in text_lower or "crédito" in text_lower:
        account_name = "Crédito"
        acct_type = AccountType.CREDIT_CARD
    elif "debito" in text_lower or "débito" in text_lower:
        account_name = "Débito"
        acct_type = AccountType.CHECKING
    else:
        account_name = "Efectivo"
        acct_type = AccountType.CASH

    before = text[: match.start()].strip()
    after = text[match.end() :].strip()
    description = (before + " " + after).strip() or "Sin descripción"

    account_repo = AccountRepository(db_session)
    account = await _get_or_create_account(account_repo, user.id, account_name, acct_type)

    tx_repo = TransactionRepository(db_session)
    transaction = await tx_repo.create(
        user_id=user.id,
        account_id=account.id,
        description=description,
        amount=amount,
        type=TransactionType.EXPENSE,
        currency="PEN",
        date=datetime.now(timezone.utc),
        source=TransactionSource.API,
        status=TransactionStatus.PENDING_CATEGORY,
    )

    category = await _auto_categorize(text_lower, user.id, db_session)
    if category:
        await tx_repo.update(
            transaction.id,
            category_id=category.id,
            status=TransactionStatus.CATEGORIZED.value,
        )
        icon = category.icon or "📁"
        await send_message(
            chat_id,
            f"✅ Gasto registrado: S/ {amount} en {account_name} - {description}\n{icon} Categoría: {category.name}",
        )
    else:
        keyboard = await _build_category_keyboard(user.id, transaction.id, db_session)
        msg = f"✅ Gasto registrado: S/ {amount} en {account_name} - {description}"
        if keyboard:
            msg += "\n\n📂 Elegí una categoría:"
            await send_message(chat_id, msg, reply_markup=keyboard)
        else:
            await send_message(chat_id, msg)


async def process_callback_query(callback_query, db_session) -> None:
    data = callback_query.data
    if not data or not data.startswith("cat:"):
        logger.warning("unknown_callback_data", data=data)
        return

    try:
        _, tx_id_str, cat_id_str = data.split(":")
        transaction_id = int(tx_id_str)
        category_id = int(cat_id_str)
    except (ValueError, IndexError):
        logger.warning("invalid_callback_data", data=data)
        return

    tx_repo = TransactionRepository(db_session)
    transaction = await tx_repo.get(transaction_id)
    if transaction is None:
        logger.warning("callback_transaction_not_found", transaction_id=transaction_id)
        return

    cat_repo = CategoryRepository(db_session)
    category = await cat_repo.get(category_id)
    if category is None:
        logger.warning("callback_category_not_found", category_id=category_id)
        return

    await tx_repo.update(
        transaction_id,
        category_id=category.id,
        status=TransactionStatus.CATEGORIZED.value,
    )

    icon = category.icon or "📁"
    new_text = f"✅ Gasto registrado: S/ {transaction.amount} en {transaction.description}\n{icon} Categoría: {category.name}"
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.message_id
    await edit_message_text(chat_id, message_id, new_text, reply_markup={})
    await answer_callback_query(callback_query.id)
