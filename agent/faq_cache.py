"""Cache de preguntas frecuentes para respuestas rápidas."""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


def _conn(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(db_path)
    c.execute("""
        CREATE TABLE IF NOT EXISTS faq_cache (
            question_hash TEXT PRIMARY KEY,
            question_normalized TEXT,
            answer TEXT,
            hits INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    return c


class FAQCache:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _hash(self, text: str) -> str:
        normalized = " ".join(text.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()

    def get(self, question: str) -> str | None:
        key = self._hash(question)
        with _conn(self.db_path) as c:
            row = c.execute(
                "SELECT answer, hits FROM faq_cache WHERE question_hash = ?",
                (key,),
            ).fetchone()
            if row:
                answer, hits = row
                c.execute(
                    "UPDATE faq_cache SET hits = ?, updated_at = datetime('now') WHERE question_hash = ?",
                    (hits + 1, key),
                )
                return answer
        return None

    def set(self, question: str, answer: str) -> None:
        key = self._hash(question)
        normalized = " ".join(question.lower().split())
        with _conn(self.db_path) as c:
            c.execute(
                """
                INSERT INTO faq_cache (question_hash, question_normalized, answer, hits)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(question_hash) DO UPDATE SET
                    answer = excluded.answer,
                    hits = hits + 1,
                    updated_at = datetime('now')
                """,
                (key, normalized, answer),
            )
