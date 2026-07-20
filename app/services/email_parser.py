import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from email.message import Message

import pandas as pd
import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger()

# ── Generic patterns ──────────────────────────────────────────────

AMOUNT_KEYWORDS = [
    "total", "amount", "charged", "monto", "cargo", "cobro",
    "compra", "purchase", "payment", "pago", "transaction",
]

MERCHANT_PATTERNS = [
    re.compile(r"(?:establecimiento|comercio|merchant|establishment)\s*:?\s*(.+?)(?:\n|$)", re.IGNORECASE),
    re.compile(r"(?:en|at|via)\s+([A-Z][A-Za-z0-9\s.]+?)(?:\n|,|\.|$)", re.IGNORECASE),
]

SUBJECT_PREFIXES = [
    "Notificación de cargo", "Cargo", "Compra en", "Compra de",
    "Purchase", "Payment", "Transaction", "Notification",
    "Notificación",
]

# ── BBVA-specific patterns ────────────────────────────────────────

BBVA_MONTO = re.compile(
    r"(?:monto|total|cargo)\s*:?\s*\$?\s*([\d,]+\.\d{2})",
    re.IGNORECASE,
)
BBVA_FECHA = re.compile(
    r"(?:fecha|fechatrx)\s*:?\s*(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE,
)
BBVA_COMERCIO = re.compile(
    r"(?:comercio|establecimiento|merchant)\s*:?\s*(.+?)(?:\n|$)",
    re.IGNORECASE,
)

# ── Yape column name normalisation ────────────────────────────────

YAPE_COL_ALIASES = {
    "fecha": "fecha",
    "date": "fecha",
    "fecha_de_operacion": "fecha",
    "operation_date": "fecha",
    "fecha_de_aplicacion": "fecha_aplicacion",
    "monto": "monto",
    "amount": "monto",
    "importe": "monto",
    "descripcion": "descripcion",
    "description": "descripcion",
    "detalle": "descripcion",
    "tipo": "tipo",
    "type": "tipo",
    "ingreso/egreso": "tipo",
    "origen": "origen",
    "destino": "destino",
    "destination": "destino",
    "mensaje": "mensaje",
    "message": "mensaje",
    "motivo": "mensaje",
}

YAPE_INCOME_ALIASES = {"te_pago", "te pagó", "recibido", "income", "ingreso", "pago_recibido"}


@dataclass
class ParsedTransaction:
    amount: Decimal
    date: datetime
    description: str
    type: str = "expense"
    mensaje: str | None = None
    origen: str | None = None
    raw_data: dict = field(default_factory=dict)


# ── Generic helpers ───────────────────────────────────────────────

def extract_body(msg: Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            try:
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                text = payload.decode("utf-8", errors="replace")
            except Exception:
                continue
            if ct == "text/html":
                return html_to_text(text)
            if ct == "text/plain":
                return text

    payload = msg.get_payload(decode=True)
    if payload:
        text = payload.decode("utf-8", errors="replace")
        if msg.get_content_type() == "text/html":
            return html_to_text(text)
        return text
    return ""


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def _get_email_date(msg: Message) -> datetime:
    email_date_str = msg.get("Date", "")
    if email_date_str:
        from email.utils import parsedate_to_datetime
        try:
            parsed = parsedate_to_datetime(email_date_str)
            if parsed:
                return parsed
        except Exception:
            pass
    return datetime.now(timezone.utc)


def _normalise_date(d: str | datetime) -> datetime | None:
    if isinstance(d, datetime):
        return d
    if isinstance(d, str):
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(d, fmt)
            except ValueError:
                continue
    return None


# ── BBVA parser ───────────────────────────────────────────────────

def parse_bbva_email(msg: Message) -> ParsedTransaction | None:
    subject = msg.get("Subject", "")
    email_date = _get_email_date(msg)
    body = extract_body(msg)

    if not body:
        logger.warning("bbva_empty_body", subject=subject)
        return None

    monto_match = BBVA_MONTO.search(body)
    if not monto_match:
        logger.warning("bbva_monto_not_found", subject=subject)
        return None

    try:
        amount = Decimal(monto_match.group(1).replace(",", ""))
    except InvalidOperation:
        logger.warning("bbva_monto_invalid", subject=subject)
        return None

    fecha_match = BBVA_FECHA.search(body)
    tx_date = (
        _normalise_date(fecha_match.group(1))
        if fecha_match
        else email_date
    )
    if tx_date and tx_date.tzinfo is None:
        tx_date = tx_date.replace(tzinfo=email_date.tzinfo or timezone.utc)

    comercio_match = BBVA_COMERCIO.search(body)
    description = comercio_match.group(1).strip().capitalize() if comercio_match else "Bank Charge"
    if not description or len(description) < 2:
        description = "Bank Charge"

    return ParsedTransaction(
        amount=amount,
        date=tx_date or email_date,
        description=description,
        raw_data={
            "subject": subject,
            "from": msg.get("From", ""),
            "message_id": msg.get("Message-ID", ""),
            "parser": "bbva",
        },
    )


# ── Yape Excel parser ─────────────────────────────────────────────

def _get_attachment_by_ext(msg: Message, ext: str = ".xlsx") -> bytes | None:
    if not msg.is_multipart():
        return None
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = part.get_filename()
        if filename and filename.lower().endswith(ext):
            payload = part.get_payload(decode=True)
            if payload:
                return payload
    return None


def _normalise_yape_col(name: str) -> str | None:
    key = name.strip().lower().replace(" ", "_").replace("-", "_")
    return YAPE_COL_ALIASES.get(key)


def _detect_income_from_tipo(tipo_val: str | None, row: dict, tipo_col: str | None) -> bool:
    if tipo_val:
        return tipo_val in YAPE_INCOME_ALIASES
    return False


def parse_yape_excel(msg: Message) -> list[ParsedTransaction]:
    subject = msg.get("Subject", "")
    raw = _get_attachment_by_ext(msg, ".xlsx")
    if raw is None:
        logger.warning("yape_no_xlsx", subject=subject)
        return []

    try:
        df = pd.read_excel(io.BytesIO(raw), engine="openpyxl")
    except Exception as exc:
        logger.error("yape_excel_read_failed", error=str(exc))
        return []

    if df.empty:
        return []

    col_map: dict[str, str] = {}
    for col in df.columns:
        mapped = _normalise_yape_col(str(col))
        if mapped:
            col_map[mapped] = col

    logger.info("yape_col_map", col_map=col_map, subject=subject)

    fechas = col_map.get("fecha")
    montos = col_map.get("monto")
    mensajes = col_map.get("mensaje")
    origenes = col_map.get("origen")
    destinos = col_map.get("destino")
    tipos = col_map.get("tipo")

    if not fechas or not montos:
        logger.warning("yape_missing_required_cols", subject=subject)
        return []

    email_date = _get_email_date(msg)
    results: list[ParsedTransaction] = []

    for _, row in df.iterrows():
        raw_date = row[fechas]
        raw_amount = row[montos]

        tx_date = _normalise_date(raw_date)
        if tx_date is None:
            continue
        if tx_date.tzinfo is None:
            tx_date = tx_date.replace(tzinfo=email_date.tzinfo or timezone.utc)

        try:
            amount = Decimal(str(raw_amount))
        except (InvalidOperation, ValueError):
            continue

        if amount == 0:
            continue

        # Determine type via tipo column, TE PAGÓ detection, or amount sign
        tipo_str = None
        if tipos:
            tipo_str = str(row[tipos]).strip().lower()

        is_income = _detect_income_from_tipo(tipo_str, row, tipos)
        if not is_income:
            is_income = amount > 0

        tx_type = "income" if is_income else "expense"
        if not is_income:
            amount = abs(amount)

        # Description from available columns
        description = "Yape"

        # Mensaje & Origen for condo routing
        mensaje_val = None
        origen_val = None

        if mensajes:
            raw_msg = str(row[mensajes]).strip()
            if raw_msg and raw_msg.lower() != "nan":
                mensaje_val = raw_msg
                description = raw_msg.capitalize()

        if origenes:
            raw_org = str(row[origenes]).strip()
            if raw_org and raw_org.lower() != "nan":
                origen_val = raw_org
        elif destinos:
            raw_dst = str(row[destinos]).strip()
            if raw_dst and raw_dst.lower() != "nan":
                origen_val = raw_dst

        results.append(
            ParsedTransaction(
                amount=amount,
                date=tx_date,
                description=description,
                type=tx_type,
                mensaje=mensaje_val,
                origen=origen_val,
                raw_data={
                    "subject": subject,
                    "from": msg.get("From", ""),
                    "message_id": msg.get("Message-ID", ""),
                    "parser": "yape",
                },
            )
        )

    return results


# ── Generic parser (fallback) ─────────────────────────────────────

def extract_amount(text: str) -> Decimal | None:
    lines = text.lower().split("\n")
    for line in lines:
        if any(kw in line for kw in AMOUNT_KEYWORDS):
            match = re.search(r"\$?\s*([\d,]+\.\d{2})", line)
            if match:
                try:
                    return Decimal(match.group(1).replace(",", ""))
                except InvalidOperation:
                    pass

    matches = re.findall(r"\$?\s*([\d,]+\.\d{2})", text)
    if matches:
        try:
            return Decimal(matches[0].replace(",", ""))
        except InvalidOperation:
            pass

    return None


def extract_date(text: str, email_date: datetime) -> datetime:
    tz = email_date.tzinfo or timezone.utc

    match = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
    if match:
        d, m, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            return datetime(y, m, d, tzinfo=tz)
        except ValueError:
            pass

    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            return datetime(y, m, d, tzinfo=tz)
        except ValueError:
            pass

    return email_date


def extract_description(text: str, subject: str) -> str:
    cleaned = _clean_subject(subject)
    if cleaned:
        return cleaned

    for pattern in MERCHANT_PATTERNS:
        match = pattern.search(text)
        if match:
            merchant = match.group(1).strip()
            if 2 < len(merchant) < 100:
                return merchant

    return "Bank Charge"


def _clean_subject(subject: str) -> str:
    if not subject:
        return ""
    for prefix in SUBJECT_PREFIXES:
        if subject.lower().startswith(prefix.lower()):
            rest = subject[len(prefix):].strip(": -")
            if rest:
                return rest
    return subject.strip()


def parse_email(msg: Message) -> ParsedTransaction | None:
    subject = msg.get("Subject", "")
    email_date = _get_email_date(msg)
    body = extract_body(msg)

    if not body:
        logger.warning("empty_email_body", subject=subject)
        return None

    amount = extract_amount(body)
    if amount is None:
        logger.warning("amount_not_found", subject=subject)
        return None

    tx_date = extract_date(body, email_date)
    description = extract_description(body, subject)

    return ParsedTransaction(
        amount=amount,
        date=tx_date,
        description=description,
        raw_data={
            "subject": subject,
            "from": msg.get("From", ""),
            "message_id": msg.get("Message-ID", ""),
            "parser": "generic",
        },
    )
