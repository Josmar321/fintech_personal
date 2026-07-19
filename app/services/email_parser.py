import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from email.message import Message

import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger()

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


@dataclass
class ParsedTransaction:
    amount: Decimal
    date: datetime
    description: str
    raw_data: dict = field(default_factory=dict)


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
    email_date_str = msg.get("Date", "")
    email_date = datetime.now(timezone.utc)

    if email_date_str:
        from email.utils import parsedate_to_datetime
        try:
            parsed = parsedate_to_datetime(email_date_str)
            if parsed:
                email_date = parsed
        except Exception:
            pass

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
        },
    )
