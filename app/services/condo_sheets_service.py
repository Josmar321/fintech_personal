import re
from datetime import datetime

import gspread
import structlog

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
    apt_match = re.search(r"(?<!\d)(\d{2,3})(?!\d)", mensaje)
    if not apt_match:
        logger.warning("condo_no_apt_number", mensaje=mensaje)
        return (False, "Manual verification required")

    apt_number = apt_match.group(1)

    sheet = _get_sheet()
    if sheet is None:
        return (False, "Manual verification required")

    target_month = fecha_operacion.month - 1
    if target_month == 0:
        target_month = 12
    month_name = MONTH_NAMES.get(target_month)
    if not month_name:
        logger.error("condo_invalid_month", month=target_month)
        return (False, "Manual verification required")

    try:
        ws = sheet.worksheet(month_name)
    except gspread.exceptions.WorksheetNotFound:
        logger.warning("condo_worksheet_not_found", month=month_name)
        return (False, "Worksheet for this month not found")

    all_rows = ws.get_all_values()
    for row_idx in range(6, len(all_rows)):
        row = all_rows[row_idx]
        dpto = str(row[1]).strip() if len(row) > 1 else ""
        if not dpto:
            continue

        dpto_digits = re.search(r"(\d+)", dpto)
        if not dpto_digits:
            continue

        if dpto_digits.group(1) != apt_number:
            continue

        raw_amount = str(row[6]) if len(row) > 6 else ""
        cleaned = raw_amount.replace("S/.", "").replace("s/.", "").replace(" ", "").strip()
        if not cleaned:
            logger.warning("condo_empty_amount", dpto=dpto, row=row_idx + 1)
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

        ws.update_cell(row_idx + 1, pagado_col, "Depositó")
        logger.info("condo_payment_registered", dpto=dpto, monto=monto, month=month_name)
        return (True, "Success")

    logger.warning("condo_dpto_not_found", apt=apt_number)
    return (False, "Manual verification required")


_APT_RE = re.compile(r"(?<!\d)(\d{2,3})(?!\d)")


def register_condo_payment(
    origen: str, monto: float, mensaje: str, fecha_operacion: datetime
) -> tuple[bool, str]:
    apt_match = _APT_RE.search(mensaje)
    if not apt_match:
        logger.warning("condo_no_apt_number", mensaje=mensaje)
        return (False, "Manual verification required")

    apt_number = apt_match.group(1)

    sheet = _get_sheet()
    if sheet is None:
        return (False, "Manual verification required")

    target_month = fecha_operacion.month - 1
    if target_month == 0:
        target_month = 12
    month_name = MONTH_NAMES.get(target_month)
    if not month_name:
        logger.error("condo_invalid_month", month=target_month)
        return (False, "Manual verification required")

    try:
        ws = sheet.worksheet(month_name)
    except gspread.exceptions.WorksheetNotFound:
        logger.warning("condo_worksheet_not_found", month=month_name)
        return (False, "Worksheet for this month not found")

    all_rows = ws.get_all_values()
    for row_idx in range(6, len(all_rows)):
        row = all_rows[row_idx]
        dpto = str(row[1]).strip() if len(row) > 1 else ""

        if not dpto:
            continue

        dpto_digits = re.search(r"(\d+)", dpto)
        if not dpto_digits:
            continue

        if dpto_digits.group(1) != apt_number:
            continue

        raw_amount = str(row[6]) if len(row) > 6 else ""
        cleaned = raw_amount.replace("S/.", "").replace("s/.", "").replace(" ", "").strip()
        if not cleaned:
            logger.warning("condo_empty_amount", dpto=dpto, row=row_idx + 1)
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

        ws.update_cell(row_idx + 1, pagado_col, "Depositó")
        logger.info("condo_yape_payment_registered", dpto=dpto, monto=monto, month=month_name)
        return (True, "Success")

    logger.warning("condo_dpto_not_found", apt=apt_number)
    return (False, "Manual verification required")


def batch_match_condo_payments(
    transactions: list[dict],
) -> list[tuple[bool, str]]:
    """
    Lee cada hoja de mes una sola vez, matchea todas las transacciones
    en memoria, escribe "Depositó" en batch.
    Retorna lista de (ok, msg) paralela a transactions.
    """
    if not transactions:
        return []

    from collections import defaultdict

    month_groups: dict[int, list[int]] = defaultdict(list)
    for i, tx in enumerate(transactions):
        fecha = tx.get("_fecha")
        if not fecha:
            continue
        tm = fecha.month - 1
        if tm == 0:
            tm = 12
        month_groups[tm].append(i)

    sheet = _get_sheet()
    if sheet is None:
        msg = "Google Sheets not configured"
        return [(False, msg)] * len(transactions)

    results: list[tuple[bool, str] | None] = [None] * len(transactions)

    for target_month, indices in month_groups.items():
        month_name = MONTH_NAMES.get(target_month)
        if not month_name:
            for i in indices:
                results[i] = (False, "Invalid month")
            continue

        try:
            ws = sheet.worksheet(month_name)
        except gspread.exceptions.WorksheetNotFound:
            for i in indices:
                results[i] = (False, f"Worksheet {month_name} not found")
            continue

        all_rows = ws.get_all_values()
        pagado_col = _find_column(ws, "¿PAGÓ?")
        if not pagado_col:
            for i in indices:
                results[i] = (False, "Missing ¿PAGÓ? column")
            continue

        updates: list[tuple[int, int, str]] = []  # (row_idx_1based, col, value)

        for i in indices:
            tx = transactions[i]
            mensaje = str(tx.get("Mensaje", ""))
            apt_match = _APT_RE.search(mensaje)
            if not apt_match:
                results[i] = (False, "Manual verification required")
                continue

            apt_number = apt_match.group(1)
            found = False
            for row_idx in range(6, len(all_rows)):
                row = all_rows[row_idx]
                dpto = str(row[1]).strip() if len(row) > 1 else ""
                if not dpto:
                    continue
                dpto_digits = re.search(r"(\d+)", dpto)
                if not dpto_digits:
                    continue
                if dpto_digits.group(1) != apt_number:
                    continue

                monto = float(tx.get("Monto", 0))
                raw_amount = str(row[6]) if len(row) > 6 else ""
                cleaned = raw_amount.replace("S/.", "").replace("s/.", "").replace(" ", "").strip()
                if not cleaned:
                    break
                try:
                    sheet_amount = float(cleaned)
                except ValueError:
                    break

                if round(sheet_amount, 2) != round(monto, 2):
                    results[i] = (False, "Amount mismatch")
                    found = True
                    break

                already_paid = str(row[pagado_col - 1]).strip() if len(row) > pagado_col - 1 else ""
                if already_paid.lower() == "depositó":
                    results[i] = (True, "Already paid")
                    found = True
                    break

                updates.append((row_idx + 1, pagado_col, "Depositó"))
                results[i] = (True, "Success")
                found = True
                logger.info("condo_batch_match", dpto=dpto, monto=monto, month=month_name)
                break

            if not found:
                results[i] = (False, "Manual verification required")

        if updates:
            batch_data = [{"range": f"{chr(64 + col)}{row}", "values": [[val]]} for row, col, val in updates]
            ws.batch_update(batch_data)

    return [(r if r else (False, "Unknown error")) for r in results]


def confirm_condo_payment(
    apt_number: str, monto: float, target_month: int
) -> tuple[bool, str]:
    if target_month < 1:
        target_month = 12

    sheet = _get_sheet()
    if sheet is None:
        return (False, "Google Sheets not configured")

    month_name = MONTH_NAMES.get(target_month)
    if not month_name:
        return (False, "Invalid month")

    try:
        ws = sheet.worksheet(month_name)
    except gspread.exceptions.WorksheetNotFound:
        return (False, f"Worksheet {month_name} not found")

    all_rows = ws.get_all_values()
    pagado_col = _find_column(ws, "¿PAGÓ?")
    dpto_col = _find_column(ws, "Departamento")
    monto_col = _find_column(ws, "Monto")
    if not pagado_col:
        return (False, "Missing ¿PAGÓ? column")
    if not dpto_col:
        return (False, "Missing Departamento column")

    for row_idx in range(6, len(all_rows)):
        row = all_rows[row_idx]
        dpto = str(row[dpto_col - 1]).strip() if len(row) > dpto_col - 1 else ""
        if not dpto:
            continue
        dpto_digits = re.search(r"(\d+)", dpto)
        if not dpto_digits:
            continue
        if dpto_digits.group(1) != apt_number:
            continue

        already = str(row[pagado_col - 1]).strip() if len(row) > pagado_col - 1 else ""
        if already.lower() == "depositó":
            return (True, "Already paid")

        ws.update_cell(row_idx + 1, pagado_col, "Depositó")
        logger.info("condo_confirm_paid", dpto=apt_number, monto=monto, month=month_name)
        return (True, "Updated")

    next_row = len(all_rows) + 1
    ws.update_cell(next_row, dpto_col, apt_number)
    if monto_col:
        ws.update_cell(next_row, monto_col, f"S/.{monto:.2f}")
    ws.update_cell(next_row, pagado_col, "Depositó")
    logger.info("condo_confirm_new_row", dpto=apt_number, monto=monto, month=month_name)
    return (True, "Added new row")


_COMMON_AREA_ROWS: dict[str, str] = {
    "riego": "RIEGO DE PARQUE Y JARDINES",
    "jardin": "RIEGO DE PARQUE Y JARDINES",
    "jardines": "RIEGO DE PARQUE Y JARDINES",
    "parque": "RIEGO DE PARQUE Y JARDINES",
}

_COMMON_AREA_NAME_COL = 3


def confirm_common_area_payment(
    mensaje: str, monto: float, target_month: int
) -> tuple[bool, str]:
    if target_month < 1:
        target_month = 12

    mensaje_lower = mensaje.lower()
    area_name = None
    for kw, name in _COMMON_AREA_ROWS.items():
        if kw in mensaje_lower:
            area_name = name
            break

    if not area_name:
        return (False, "No common area keyword found in message")

    sheet = _get_sheet()
    if sheet is None:
        return (False, "Google Sheets not configured")

    month_name = MONTH_NAMES.get(target_month)
    if not month_name:
        return (False, "Invalid month")

    try:
        ws = sheet.worksheet(month_name)
    except gspread.exceptions.WorksheetNotFound:
        return (False, f"Worksheet {month_name} not found")

    all_rows = ws.get_all_values()
    pagado_col = _find_column(ws, "¿PAGÓ?")
    monto_col = _find_column(ws, "Monto")
    if not pagado_col:
        return (False, "Missing ¿PAGÓ? column")

    for row_idx in range(6, len(all_rows)):
        row = all_rows[row_idx]
        cell = str(row[_COMMON_AREA_NAME_COL - 1]).strip() if len(row) > _COMMON_AREA_NAME_COL - 1 else ""
        if cell != area_name:
            continue

        already = str(row[pagado_col - 1]).strip() if len(row) > pagado_col - 1 else ""
        if already.lower() == "depositó":
            return (True, "Already paid")

        ws.update_cell(row_idx + 1, pagado_col, "Depositó")
        if monto_col:
            ws.update_cell(row_idx + 1, monto_col, f"S/.{monto:.2f}")
        logger.info("condo_common_area_paid", area=area_name, monto=monto, month=month_name)
        return (True, f"Updated {area_name}")

    return (False, f"Row '{area_name}' not found in sheet for {month_name}")


def _get_sheet():
    if not settings.GOOGLE_SHEETS_CREDENTIALS_PATH or not settings.CONDO_SHEET_ID:
        logger.error("google_sheets_not_configured")
        return None

    client = gspread.service_account(filename=settings.GOOGLE_SHEETS_CREDENTIALS_PATH)
    return client.open_by_key(settings.CONDO_SHEET_ID)


def _find_column(ws, name: str) -> int | None:
    headers = ws.row_values(6)
    for i, h in enumerate(headers, start=1):
        if h.strip() == name.strip():
            return i
    return None
