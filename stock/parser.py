"""Parseo de archivos de stock (CSV, Excel) a registros normalizados."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

# Formato real: Sucursal, Ubicación, Comuna, Marca, Modelo, Versión, Año, Kilometraje, Placa Patente, Color Exterior, Precio Lista, Link
COLUMN_MAPPING = {
    "marca": ["marca", "brand", "make"],
    "modelo": ["modelo", "model"],
    "año": ["año", "ao", "year", "anio", "ano"],
    "precio": ["precio", "price", "precio_usd", "precio lista"],
    "kilometraje": ["kilometraje", "km", "kilometros", "mileage"],
    "transmision": ["transmision", "transmicion", "transmission", "trans"],
    "combustible": ["combustible", "fuel", "fuel_type"],
    "color": ["color", "color exterior"],
    "estado": ["estado", "condition", "condicion"],
    "id": ["id", "sku", "codigo"],
    # Columnas del formato real (stock copy.csv / stockfinal.csv)
    "sucursal": ["sucursal"],
    "ubicacion": ["ubicación", "ubicacion", "ubicacin"],
    "comuna": ["comuna"],
    "version": ["versión", "version", "versin"],
    "segmento": ["segmento"],
    "placa_patente": ["placa patente", "placa_patente", "patente"],
    "link": ["link"],
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = {}
    cols_lower = {c.lower().strip(): c for c in df.columns}
    for std_name, aliases in COLUMN_MAPPING.items():
        for alias in aliases:
            if alias in cols_lower:
                result[std_name] = df[cols_lower[alias]]
                break
    return pd.DataFrame(result) if result else pd.DataFrame()


def _coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.replace({",": "", "": None}), errors="coerce")


def parse_stock_file(path: str | Path) -> list[dict[str, Any]]:
    """Parsea CSV o Excel y devuelve lista de diccionarios normalizados."""
    path = Path(path)
    if not path.exists():
        return []
    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path, encoding="utf-8", encoding_errors="ignore")
    if df.empty:
        return []
    df = _normalize_columns(df)
    if df.empty:
        return []
    if "precio" in df.columns:
        df["precio"] = _coerce_numeric(df["precio"])
    if "año" in df.columns:
        df["año"] = _coerce_numeric(df["año"]).astype("Int64")
    if "kilometraje" in df.columns:
        df["kilometraje"] = _coerce_numeric(df["kilometraje"])
    df = df.dropna(how="all")
    return df.to_dict(orient="records")
