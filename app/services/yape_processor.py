import math
from datetime import datetime
from typing import Any

import pandas as pd

_REQUIRED_COLS = [
    "Tipo de Transacción",
    "Origen",
    "Destino",
    "Monto",
    "Mensaje",
    "Fecha de operación",
]

_CONDO_KEYWORDS = ["dpto", "agua", "mantenimiento", "consumo", "condominio"]
_ADMIN_INCOME_KEYWORDS = ["servicio", "medición", "lectura", "servicios"]


def read_yape_excel(file_path: str) -> pd.DataFrame:
    df = pd.read_excel(file_path, header=None)
    df.columns = _REQUIRED_COLS
    df = df[1:]  # Skip the original header row that is now data
    df.dropna(subset=_REQUIRED_COLS, how="all", inplace=True)
    df = df.dropna(how="all")
    return df


def _matches_condo(row: dict[str, Any]) -> bool:
    txn_type = str(row.get("Tipo de Transacción", ""))
    if txn_type.strip() != "TE PAGÓ":
        return False

    mensaje = str(row.get("Mensaje", "")).lower()
    if any(kw in mensaje for kw in _CONDO_KEYWORDS):
        return True

    return False


def _clean(val: Any) -> Any:
    if isinstance(val, float) and math.isnan(val):
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.isoformat()
    return val


def route_transactions(df: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    condo_transactions: list[dict[str, Any]] = []
    personal_transactions: list[dict[str, Any]] = []

    for _, row in df.iterrows():
        record = {k: _clean(v) for k, v in row.to_dict().items()}
        if _matches_condo(record):
            condo_transactions.append(record)
        else:
            personal_transactions.append(record)

    return condo_transactions, personal_transactions
