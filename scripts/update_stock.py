#!/usr/bin/env python3
"""Actualiza el stock desde el archivo configurado (CSV/Excel)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import STOCK_FILE, STOCK_DB_PATH
from stock.repository import StockRepository


def main() -> int:
    repo = StockRepository(STOCK_DB_PATH)
    repo.init_schema()
    n = repo.update_from_file(STOCK_FILE)
    print(f"Stock actualizado: {n} vehículos desde {STOCK_FILE}")
    return 0 if n >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
