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


async def process_callback_query(callback_query, db_session) -> None:
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    message_id = callback_query.message.message_id

    if data.startswith("cat:"):
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
        await edit_message_text(chat_id, message_id, new_text, reply_markup={})
        await answer_callback_query(callback_query.id)
        return

    if data.startswith("confirm:") or data.startswith("skip:"):
        action, tx_id_str = data.split(":", 1)
        try:
            tx_id = int(tx_id_str)
        except ValueError:
            await answer_callback_query(callback_query.id)
            return

        tx_repo = TransactionRepository(db_session)
        txn = await tx_repo.get(tx_id)
        if not txn:
            await edit_message_text(chat_id, message_id, "❌ Transacción no encontrada", reply_markup={})
            await answer_callback_query(callback_query.id)
            return

        if action == "confirm":
            raw = txn.raw_data or {}
            mensaje = str(raw.get("Mensaje", "") or "")
            monto = float(raw.get("Monto", 0) or 0)
            target_month = txn.date.month - 1
            mensaje_lower = mensaje.lower()

            from app.services.condo_sheets_service import CondoSheetsService
            condo_sheets_service = CondoSheetsService()

            condominio_cat = await _get_or_create_condominio_category(txn.user_id, db_session)

            is_common = any(kw in mensaje_lower for kw in condo_sheets_service._COMMON_AREA_ROWS)

            if is_common:
                ok, sheet_msg = condo_sheets_service.confirm_common_area_payment(mensaje, monto, target_month)
            else:
                m = condo_sheets_service._APT_RE.search(mensaje)
                if not m:
                    _pending_input[chat_id] = {
                        "action": "awaiting_apt",
                        "tx_id": tx_id,
                        "monto": monto,
                        "target_month": target_month,
                        "user_id": txn.user_id,
                    }
                    await edit_message_text(
                        chat_id, message_id,
                        f"✏️ S/.{monto:.2f} - Escribe el número de dpto (ej: 203):",
                        reply_markup={},
                    )
                    await answer_callback_query(callback_query.id)
                    return
                apt = m.group(1)
                ok, sheet_msg = condo_sheets_service.confirm_condo_payment(apt, monto, target_month)

            if ok:
                await tx_repo.update(tx_id, category_id=condominio_cat.id, status=TransactionStatus.CATEGORIZED.value)
                await edit_message_text(chat_id, message_id, f"✅ S/.{monto:.2f} registrado en sheet + Condominio", reply_markup={})
            else:
                await edit_message_text(chat_id, message_id, f"❌ {sheet_msg}", reply_markup={})

        elif action == "skip":
            await tx_repo.update(tx_id, category_id=1227, status=TransactionStatus.CATEGORIZED.value)
            await edit_message_text(chat_id, message_id, "✅ Ingreso registrado: S/.{monto:.2f}".format(monto=txn.amount), reply_markup={})

        await answer_callback_query(callback_query.id)
        return

    if data.startswith("validated:"):
        await _handle_condo_validation_callback(callback_query, db_session)
        return

    logger.warning("unknown_callback_data", data=data)


async def _get_or_create_condominio_category(user_id: int, db_session) -> int:
    from app.db.repositories.category_repo import CategoryRepository
    cat_repo = CategoryRepository(db_session)
    category = await cat_repo.get_by_type_and_parent("condo", None)
    if category:
        return category.id
    from app.db.models.category import Category as CatModel
    new_cat = CatModel(name="Condominio", type="condo", parent_id=None)
    cat_repo.create(new_cat)
    await db_session.flush()
    return new_cat.id


async def _handle_condo_validation_callback(callback_query, db_session) -> None:
    """Maneja la respuesta Sí/No de validación condominio desde Telegram."""
    data = callback_query.data
    parts = data.split(":", 2)
    if len(parts) != 3:
        return

    action, tx_id_str, approved_str = parts
    try:
        tx_id = int(tx_id_str)
        approved = approved_str.lower() == "yes"
    except ValueError:
        return

    chat_id = callback_query.message.chat.id
    tx_repo = TransactionRepository(db_session)
    txn = await tx_repo.get(tx_id)
    if not txn:
        return

    if approved:
        raw = txn.raw_data or {}
        mensaje = str(raw.get("Mensaje", "") or "")
        monto = float(raw.get("Monto", 0) or 0)
        target_month = txn.date.month - 1

        condominio_cat = await _get_or_create_condominio_category(txn.user_id, db_session)
        from app.services.condo_sheets_service import CondoSheetsService
        condo_sheets_service = CondoSheetsService()
        ok, sheet_msg = condo_sheets_service.confirm_condo_payment(mensaje, monto, target_month)

        if ok:
            await tx_repo.update(tx_id, category_id=condominio_cat.id, status=TransactionStatus.CATEGORIZED.value)
            await edit_message_text(
                chat_id, message_id,
                f"✅ S/.{txn.amount:.2f} registrado en sheet como pago de condominio",
                reply_markup={}
            )
        else:
            await edit_message_text(
                chat_id, message_id,
                f"❌ {sheet_msg}",
                reply_markup={}
            )
    else:
        await tx_repo.update(tx_id, status=TransactionStatus.PENDING_CATEGORY.value)
        await edit_message_text(
            chat_id, message_id,
            "👤 Movido a gastos personales - elegí una categoría",
            reply_markup={}
        )

    return


_pending_input = {}

async def send_yape_summary(
    chat_id: int,
    filename: str,
    sheet_count: int,
    flagged: list[dict],
    personal_count: int,
    categorized_count: int = 0,
    pending_ids: list[int] | None = None,
    pending_personal_txs: list[dict] | None = None,
    skipped_count: int = 0,
    db_session=None,
) -> None:
    summary = (
        f"📄 Yape procesado: {filename}\n"
        f"✅ Condo en sheet: {sheet_count}\n"
        f"⚠️ Revisar: {len(flagged)}\n"
        f"👤 Personales: {personal_count}"
    )
    if skipped_count:
        summary += f"\n🔄 Saltados (duplicados): {skipped_count}"
    if categorized_count or pending_ids:
        pending = pending_ids or []
        summary += f"\n   ✅ {categorized_count} categorizados"
        if pending:
            summary += f"\n   ⚠️ {len(pending)} pendientes"
    await send_message(chat_id, summary)

    for tx in flagged:
        msg = f"⚠️ S/.{tx['amount']} - {tx['description']}"
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Condo", "callback_data": f"confirm:{tx['id']}"},
                    {"text": "❌ Personal", "callback_data": f"skip:{tx['id']}"},
                ]
            ]
        }
        await send_message(chat_id, msg, reply_markup=keyboard)

    # Transacciones que necesitan validación condominio (no tenían keywords dpto/agua etc)
    condo_validation_txs = [
        tx for tx in pending_personal_txs 
        if tx.get("needs_condo_validation")
    ]

    personal_pending_txs = [
        tx for tx in pending_personal_txs 
        if not tx.get("needs_condo_validation")
    ]

    # 1. Enviar mensajes de validación condominio con botones Sí/No
    for tx in condo_validation_txs:
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Sí es condo", "callback_data": f"validated:{tx['id']}:yes"},
                    {"text": "❌ No es condo", "callback_data": f"validated:{tx['id']}:no"},
                ]
            ]
        }
        msg = f"🔔 Yape pending validation\n💰 S/.{tx['amount']} - {tx['description']}\n¿Es pago de departamento?"
        await send_message(chat_id, msg, reply_markup=keyboard)

    # 2. Enviar mensajes de personales normales con categorización
    if personal_pending_txs and db_session:
        from app.database.repositories.user_repo import UserRepository
        user_repo = UserRepository(db_session)
        user = await user_repo.get_by_telegram_chat(chat_id)
        if user:
            for tx in personal_pending_txs:
                keyboard = await _build_category_keyboard(user.id, tx["id"], db_session)
                msg = f"👤 S/.{tx['amount']} - {tx['description']}"
                await send_message(chat_id, msg, reply_markup=keyboard or None)
                await asyncio.sleep(0.3)


async def _build_category_keyboard(user_id: int, tx_id: int, db_session) -> dict | None:
    from app.db.repositories.category_repo import CategoryRepository
    cat_repo = CategoryRepository(db_session)
    categories = await cat_repo.get_user_categories(user_id)
    if not categories:
        return None
    keyboard = {"inline_keyboard": []}
    for cat in categories:
        keyboard["inline_keyboard"].append([
            {"text": cat.name, "callback_data": f"cat:{tx_id}:{cat.id}"}
        ])
    return keyboard


async def process_incoming_message(chat_id: int, text: str, db_session) -> None:
    if text.strip() == '/start':
        await send_message(
            chat_id,
            "👋 ¡Hola Admin! Envíame tus gastos con el formato: [Monto] [Descripción] [Cuenta opcional]. Ej: 15 en taxi yape."
        )
        return

    import re
    from decimal import Decimal, InvalidOperation
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

    text_before = text[:match.start()].strip()
    text_after = text[match.end():].strip()
    description = (text_before + " " + text_after).strip() or "Sin descripción"

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

    if "yape" in text.lower():
        account_name = "Yape"
        acct_type = AccountType.CHECKING
    elif "crédito" in text.lower() or "credito" in text.lower():
        account_name = "Crédito"
        acct_type = AccountType.CREDIT_CARD
    elif "débito" in text.lower() or "debito" in text.lower():
        account_name = "Débito"
        acct_type = AccountType.CASH
    else:
        account_name = "Efectivo"
        acct_type = AccountType.CASH

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