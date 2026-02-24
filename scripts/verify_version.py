#!/usr/bin/env python3
"""Verifica que el campo 'version' se extraiga bien: CSV -> parser -> DB -> search_stock."""
from __future__ import annotations

import sys
from pathlib import Path

# Permitir importar desde la raíz del proyecto
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    from config import STOCK_FILE, STOCK_DB_PATH
    from stock.parser import parse_stock_file
    from stock.repository import StockRepository
    from agent.tools import search_stock

    print("=== 1. Parser (CSV -> registros) ===\n")
    records = parse_stock_file(STOCK_FILE)
    if not records:
        print("ERROR: No se obtuvieron registros del CSV.")
        return
    with_version = sum(1 for r in records if (r.get("version") or "").strip())
    with_year = sum(1 for r in records if r.get("año") is not None and r.get("año") > 0)
    print(f"Total registros: {len(records)}")
    print(f"Con 'version' no vacía: {with_version}")
    print(f"Con 'año' válido: {with_year}")
    # Muestra 3 ejemplos con version y año
    samples = [r for r in records if (r.get("version") or "").strip()][:3]
    for i, r in enumerate(samples, 1):
        print(f"  Ejemplo {i}: {r.get('marca')} {r.get('modelo')} -> version = {repr(r.get('version'))}, año = {r.get('año')}")
    if with_version < len(records) * 0.9:
        print("\n  ⚠ Revisar: muchas filas sin version en el CSV o en el mapeo de columnas.")
    if with_year < len(records) * 0.9:
        print("  ⚠ Revisar: muchas filas sin año (columna 'Año' en CSV puede tener encoding roto).")

    print("\n=== 2. Base de datos (después de update_from_file) ===\n")
    repo = StockRepository(STOCK_DB_PATH)
    repo.init_schema()
    # Recargar desde CSV para estar seguros
    n = repo.update_from_file(STOCK_FILE)
    print(f"Registros cargados en DB: {n}")
    rows = repo.search(limit=5)
    with_ver_db = sum(1 for r in rows if (r.get("version") or "").strip())
    print(f"De los primeros 5 en búsqueda, con 'version' no vacía: {with_ver_db}/5")
    for i, r in enumerate(rows[:3], 1):
        print(f"  Fila {i}: version = {repr(r.get('version'))} | {r.get('marca')} {r.get('modelo')}")
    # Conteo global en DB
    with repo._conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM vehiculos").fetchone()[0]
        with_ver = conn.execute(
            "SELECT COUNT(*) FROM vehiculos WHERE TRIM(COALESCE(version,'')) != ''"
        ).fetchone()[0]
        with_ano = conn.execute(
            "SELECT COUNT(*) FROM vehiculos WHERE año IS NOT NULL AND año > 0"
        ).fetchone()[0]
    print(f"En toda la DB: {with_ver}/{total} con version no vacía, {with_ano}/{total} con año válido.")
    if with_ver < total * 0.9:
        print("  ⚠ Revisar: columna 'version' en INSERT o en el parser.")
    if with_ano < total * 0.9:
        print("  ⚠ Revisar: columna 'año' en INSERT o en el parser.")

    print("\n=== 3. Herramienta search_stock (texto que ve el agente) ===\n")
    out = search_stock.invoke({"limit": 3, "order_by_precio": "asc"})
    print("Primeras líneas de la respuesta:")
    for line in out.split("\n")[:10]:
        print(f"  {line}")
    # Comprobar que aparece "Versión:" con contenido
    if "| Versión:" in out:
        count = out.count("| Versión:")
        print(f"\n  OK: La respuesta contiene '| Versión:' {count} vez/veces.")
    else:
        print("\n  ⚠ La respuesta NO contiene '| Versión:'. Revisar agent/tools.py.")
    if "(N/A)" in out:
        print("  ⚠ Hay '(N/A)' en la respuesta (revisar si es año o versión).")
    if "Versión:" in out and "(N/A)" not in out.split("Versión:")[0]:
        print("  OK: Versión presente y año no mostrado como N/A en las líneas con versión.")

    print("\n=== Resumen ===\n")
    ok = (
        with_version >= len(records) * 0.9
        and with_year >= len(records) * 0.9
        and with_ver >= total * 0.9
        and with_ano >= total * 0.9
        and "| Versión:" in out
    )
    if ok:
        print("Versión y año se extraen correctamente en todo el flujo.")
    else:
        print("Revisar algún paso del flujo (parser, DB o formato de search_stock).")


if __name__ == "__main__":
    main()
