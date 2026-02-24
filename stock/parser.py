"""Parseo de archivos de stock (CSV, Excel) a registros normalizados."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

# Formato real: Sucursal, Ubicación, Comuna, Marca, Modelo, Versión, Año, Kilometraje, Placa Patente, Color Exterior, Precio Lista, Link
COLUMN_MAPPING = {
    "marca": ["marca", "brand", "make"],
    "modelo": ["modelo", "model"],
    "año": ["año", "ao", "aoo", "year", "anio", "ano"],  # "aoo" = columna "Año" con ñ leída como U+FFFD
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


def _normalize_col_name_for_match(name: str) -> str:
    """Normaliza nombre de columna para matching: reemplaza caracteres de encoding roto (ej. U+FFFD)."""
    s = name.lower().strip()
    # Reemplazo Unicode (ej. ó leído mal) para que "Versin" coincida con "version"/"versión"
    s = s.replace("\ufffd", "o").replace("\u00f3", "o")  # ó
    return s


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = {}
    # Clave normalizada -> nombre real de columna (para CSV con encoding roto, ej. Versin)
    cols_lower = {_normalize_col_name_for_match(c): c for c in df.columns}
    for std_name, aliases in COLUMN_MAPPING.items():
        for alias in aliases:
            alias_norm = _normalize_col_name_for_match(alias)
            if alias_norm in cols_lower:
                result[std_name] = df[cols_lower[alias_norm]]
                break
    return pd.DataFrame(result) if result else pd.DataFrame()


def _coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.replace({",": "", "": None}), errors="coerce")


def _clean_encoding_errors(s: str) -> str:
    """Reemplaza carácter de reemplazo Unicode (U+FFFD) en textos del CSV con encoding roto."""
    if not isinstance(s, str) or "\ufffd" not in s:
        return s
    # Correcciones por contexto antes del reemplazo genérico
    s = s.replace("Am\ufffdrico", "Americo").replace("AM\ufffdRICO", "AMERICO")
    s = s.replace("\ufffdu\ufffdoa", "Nunoa").replace("\ufffduñoa", "Nunoa").replace("Ñu\ufffdoa", "Nunoa")
    # Reemplazo genérico del resto de FFFD (ó, etc.)
    s = s.replace("\ufffd", "o")
    # Formas que quedan tras el genérico (ej. Ñuñoa -> ouooa)
    if "ouooa" in s or " uooa" in s:
        s = s.replace("ouooa", "Nunoa").replace(" uooa", "Nunoa")
    return s.strip()


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
    # Limpiar U+FFFD en columnas de texto (ubicación, comuna, etc. con encoding roto)
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).apply(_clean_encoding_errors)
    return df.to_dict(orient="records")
