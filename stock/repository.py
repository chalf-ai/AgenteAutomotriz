"""Repositorio de stock en SQLite con índices para búsqueda por rangos."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from stock.parser import parse_stock_file


def _get_conn(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS vehiculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_externo TEXT,
            marca TEXT,
            modelo TEXT,
            año INTEGER,
            precio REAL,
            kilometraje REAL,
            transmision TEXT,
            combustible TEXT,
            color TEXT,
            estado TEXT,
            sucursal TEXT,
            ubicacion TEXT,
            comuna TEXT,
            version TEXT,
            placa_patente TEXT,
            link TEXT,
            raw_json TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_vehiculos_precio ON vehiculos(precio);
        CREATE INDEX IF NOT EXISTS idx_vehiculos_año ON vehiculos(año);
        CREATE INDEX IF NOT EXISTS idx_vehiculos_kilometraje ON vehiculos(kilometraje);
        CREATE INDEX IF NOT EXISTS idx_vehiculos_marca ON vehiculos(marca);
        CREATE INDEX IF NOT EXISTS idx_vehiculos_marca_modelo ON vehiculos(marca, modelo);
        CREATE INDEX IF NOT EXISTS idx_vehiculos_año_precio ON vehiculos(año, precio);
    """)
    # Migrar DBs antiguas: agregar columnas nuevas si no existen
    for col in ["sucursal", "ubicacion", "comuna", "version", "placa_patente", "link"]:
        try:
            conn.execute(f"ALTER TABLE vehiculos ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass


def _str(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


class StockRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        return _get_conn(self.db_path)

    def init_schema(self) -> None:
        with self._conn() as c:
            _create_schema(c)

    def update_from_file(self, file_path: str) -> int:
        records = parse_stock_file(file_path)
        if not records:
            return 0
        with self._conn() as conn:
            _create_schema(conn)
            conn.execute("DELETE FROM vehiculos")
            for r in records:
                id_externo = str(r.get("id") or r.get("placa_patente") or "")
                conn.execute(
                    """
                    INSERT INTO vehiculos
                    (id_externo, marca, modelo, año, precio, kilometraje,
                     transmision, combustible, color, estado,
                     sucursal, ubicacion, comuna, version, placa_patente, link, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        id_externo,
                        _str(r.get("marca")),
                        _str(r.get("modelo")),
                        _int(r.get("año")),
                        _float(r.get("precio")),
                        _float(r.get("kilometraje")),
                        _str(r.get("transmision")),
                        _str(r.get("combustible")),
                        _str(r.get("color")),
                        _str(r.get("estado")),
                        _str(r.get("sucursal")),
                        _str(r.get("ubicacion")),
                        _str(r.get("comuna")),
                        _str(r.get("version")),
                        _str(r.get("placa_patente")),
                        _str(r.get("link")),
                        json.dumps(r, ensure_ascii=False),
                    ),
                )
            conn.commit()
            return len(records)

    def search(
        self,
        *,
        precio_min: float | None = None,
        precio_max: float | None = None,
        año_min: int | None = None,
        año_max: int | None = None,
        km_max: float | None = None,
        marca: str | None = None,
        modelo: str | None = None,
        limit: int = 50,
        order_by_precio: str = "asc",
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if precio_min is not None:
            conditions.append("precio >= ?")
            params.append(precio_min)
        if precio_max is not None:
            conditions.append("precio <= ?")
            params.append(precio_max)
        if año_min is not None:
            conditions.append("año >= ?")
            params.append(año_min)
        if año_max is not None:
            conditions.append("año <= ?")
            params.append(año_max)
        if km_max is not None:
            conditions.append("(kilometraje IS NULL OR kilometraje <= ?)")
            params.append(km_max)
        if marca:
            conditions.append("LOWER(marca) LIKE ?")
            params.append(f"%{marca.lower()}%")
        if modelo:
            conditions.append("LOWER(modelo) LIKE ?")
            params.append(f"%{modelo.lower()}%")
        where = " AND ".join(conditions) if conditions else "1=1"
        order = "DESC" if (order_by_precio or "").strip().lower() == "desc" else "ASC"
        params.append(limit)
        sql = f"SELECT * FROM vehiculos WHERE {where} ORDER BY precio {order} LIMIT ?"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def get_summary(self) -> dict[str, Any]:
        with self._conn() as conn:
            _create_schema(conn)
            total = conn.execute("SELECT COUNT(*) FROM vehiculos").fetchone()[0]
            if total == 0:
                return {"total": 0, "precio_min": None, "precio_max": None, "año_min": None, "año_max": None}
            row = conn.execute(
                "SELECT MIN(precio), MAX(precio), MIN(año), MAX(año) FROM vehiculos"
            ).fetchone()
        return {
            "total": total,
            "precio_min": row[0],
            "precio_max": row[1],
            "año_min": row[2],
            "año_max": row[3],
        }
