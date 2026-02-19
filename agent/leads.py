"""Registro de leads para que un ejecutivo los contacte."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def _conn(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(db_path)
    c.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            rut TEXT,
            correo TEXT,
            patente_vehiculo_vpp TEXT,
            kilometraje_vehiculo_vpp TEXT,
            notas TEXT,
            thread_id TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    return c


def register_lead(
    nombre: str,
    rut: str = "",
    correo: str = "",
    patente_vehiculo_vpp: str = "",
    kilometraje_vehiculo_vpp: str = "",
    notas: str = "",
    thread_id: str = "",
    db_path: str = "",
) -> dict[str, Any]:
    """Guarda un lead. Devuelve {ok: bool, message: str}."""
    from config import LEADS_DB_PATH
    path = db_path or LEADS_DB_PATH
    if not nombre or not nombre.strip():
        return {"ok": False, "message": "Falta el nombre."}
    try:
        with _conn(path) as c:
            try:
                c.execute("ALTER TABLE leads ADD COLUMN notas TEXT")
            except sqlite3.OperationalError:
                pass
            c.execute(
                """
                INSERT INTO leads (nombre, rut, correo, patente_vehiculo_vpp, kilometraje_vehiculo_vpp, notas, thread_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    nombre.strip(),
                    (rut or "").strip(),
                    (correo or "").strip(),
                    (patente_vehiculo_vpp or "").strip(),
                    (kilometraje_vehiculo_vpp or "").strip(),
                    (notas or "").strip(),
                    (thread_id or "").strip(),
                ),
            )
        return {"ok": True, "message": "Lead registrado correctamente."}
    except Exception as e:
        return {"ok": False, "message": str(e)}
