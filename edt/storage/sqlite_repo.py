"""Repozytorium dokumentów w SQLite (etap D2) – implementacja `DocumentRepository`.

Tabela `documents` należy do O1. Inne moduły nie czytają jej bezpośrednio,
tylko przez interfejs (`edt/interfaces.py`).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from typing import Any

from edt.db import ensure_schema
from edt.models import Document, SourceType
from edt.storage.errors import DuplicateDocumentError

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    text         TEXT NOT NULL,
    source_type  TEXT NOT NULL,
    language     TEXT NOT NULL DEFAULT 'unknown',
    added_at     TEXT NOT NULL,              -- ISO 8601 ze strefą czasową
    size_bytes   INTEGER NOT NULL DEFAULT 0,
    num_pages    INTEGER,
    content_hash TEXT NOT NULL DEFAULT '',
    metadata     TEXT NOT NULL DEFAULT '{}'  -- JSON
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_documents_content_hash
    ON documents(content_hash) WHERE content_hash <> '';
CREATE INDEX IF NOT EXISTS ix_documents_added_at ON documents(added_at);
"""

_COLUMNS = ("id, name, text, source_type, language, added_at, size_bytes, num_pages, "
            "content_hash, metadata")


def _to_row(doc: Document) -> tuple[Any, ...]:
    return (
        doc.id, doc.name, doc.text, doc.source_type.value, doc.language,
        doc.added_at.isoformat(), doc.size_bytes, doc.num_pages, doc.content_hash,
        json.dumps(doc.metadata, ensure_ascii=False, default=str),
    )


def _from_row(row: sqlite3.Row) -> Document:
    return Document(
        id=row["id"],
        name=row["name"],
        text=row["text"],
        source_type=SourceType(row["source_type"]),
        language=row["language"],
        added_at=datetime.fromisoformat(row["added_at"]),
        size_bytes=row["size_bytes"],
        num_pages=row["num_pages"],
        content_hash=row["content_hash"],
        metadata=json.loads(row["metadata"] or "{}"),
    )


class SqliteDocumentRepository:
    """Bezpieczne dla wielu wątków (Streamlit): operacje serializowane blokadą."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._lock = threading.RLock()
        ensure_schema(conn, SCHEMA)

    def add(self, doc: Document) -> None:
        """Dodaje dokument; ten sam `id` => nadpisanie (jak w repozytorium w pamięci).
        Ta sama treść pod innym `id` => `DuplicateDocumentError`."""
        sql = (
            f"INSERT INTO documents ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET name=excluded.name, text=excluded.text, "
            "source_type=excluded.source_type, language=excluded.language, "
            "added_at=excluded.added_at, size_bytes=excluded.size_bytes, "
            "num_pages=excluded.num_pages, content_hash=excluded.content_hash, "
            "metadata=excluded.metadata"
        )
        with self._lock:
            try:
                with self.conn:
                    self.conn.execute(sql, _to_row(doc))
            except sqlite3.IntegrityError as exc:
                raise DuplicateDocumentError(
                    f"Dokument o tej samej treści już istnieje (hash {doc.content_hash[:12]}…)."
                ) from exc

    def get(self, doc_id: str) -> Document | None:
        with self._lock:
            row = self.conn.execute(
                f"SELECT {_COLUMNS} FROM documents WHERE id = ?", (doc_id,)
            ).fetchone()
        return _from_row(row) if row else None

    def list(self) -> list[Document]:
        with self._lock:
            rows = self.conn.execute(
                f"SELECT {_COLUMNS} FROM documents ORDER BY added_at, rowid"
            ).fetchall()
        return [_from_row(r) for r in rows]

    def delete(self, doc_id: str) -> bool:
        with self._lock, self.conn:
            return self.conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,)).rowcount > 0

    def find_by_hash(self, content_hash: str) -> Document | None:
        if not content_hash:
            return None
        with self._lock:
            row = self.conn.execute(
                f"SELECT {_COLUMNS} FROM documents WHERE content_hash = ?", (content_hash,)
            ).fetchone()
        return _from_row(row) if row else None

    def count(self) -> int:
        with self._lock:
            return self.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    def ids(self) -> set[str]:
        """Wszystkie id (poza protokołem; używane do sprzątania plików)."""
        with self._lock:
            return {r[0] for r in self.conn.execute("SELECT id FROM documents")}
