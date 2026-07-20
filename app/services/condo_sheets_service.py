import re
from datetime import datetime

import gspread
import structlog
from google.oauth2.service_account import Credentials

from app.config import settings

logger = structlog.get_logger()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

MONTH_NAMES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Setiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


def register_water_payment(
    origen: str, monto: float, mensaje: str, fecha_operacion: datetime
) -> tuple[bool, str]:
    apt_match = re.search(r"\b(\d{2,3})\b", mensaje)
    if not apt_match:
        logger.warning("condo_no_apt_number", mensaje=mensaje)
        return (False, "Manual verification required")

    apt_number = apt_match.group(1)

    sheet = _get_sheet()
    if sheet is None:
        return (False, "Manual verification required")

    month_name = MONTH_NAMES.get(fecha_operacion.month)
    if not month_name:
        logger.error("condo_invalid_month", month=fecha_operacion.month)
        return (False, "Manual verification required")

    try:
        ws = sheet.worksheet(month_name)
    except gspread.exceptions.WorksheetNotFound:
        logger.warning("condo_worksheet_not_found", month=month_name)
        return (False, "Worksheet for this month not found")

    records = ws.get_all_records()
    for i, record in enumerate(records, start=2):
        dpto = str(record.get("DPTO", "")).strip()
        if not dpto:
            continue

        dpto_digits = re.search(r"(\d+)", dpto)
        if not dpto_digits:
            continue

        if dpto_digits.group(1) != apt_number:
            continue

        raw_amount = str(record.get("MONTO A PAGAR", "") or "")
        cleaned = raw_amount.replace("S/.", "").replace("s/.", "").replace(" ", "").strip()
        if not cleaned:
            logger.warning("condo_empty_amount", dpto=dpto, row=i)
            return (False, "Manual verification required")

        try:
            sheet_amount = float(cleaned)
        except ValueError:
            logger.error("condo_invalid_amount", raw=raw_amount, dpto=dpto)
            return (False, "Manual verification required")

        if round(sheet_amount, 2) != round(monto, 2):
            logger.warning(
                "condo_amount_mismatch", dpto=dpto, expected=sheet_amount, got=monto
            )
            return (False, "Manual verification required")

        pagado_col = _find_column(ws, "¿PAGÓ?")
        if not pagado_col:
            logger.error("condo_missing_pago_column")
            return (False, "Manual verification required")

        ws.update_cell(i, pagado_col, "Depositó")
        logger.info("condo_payment_registered", dpto=dpto, monto=monto, month=month_name)
        return (True, "Success")

    logger.warning("condo_dpto_not_found", apt=apt_number)
    return (False, "Manual verification required")


def _get_sheet():
    if not settings.GOOGLE_SHEETS_CREDENTIALS_PATH or not settings.CONDO_SHEET_ID:
        logger.error("google_sheets_not_configured")
        return None

    creds = Credentials.from_service_account_file(
        settings.GOOGLE_SHEETS_CREDENTIALS_PATH, scopes=SCOPES
    )
    client = gspread.authorize(creds)
    return client.open_by_key(settings.CONDO_SHEET_ID)


def _find_column(ws, name: str) -> int | None:
    headers = ws.row_values(1)
    for i, h in enumerate(headers, start=1):
        if h.strip() == name.strip():
            return i
    return None
