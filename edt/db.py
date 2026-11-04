"""Wspólne połączenie SQLite (P0).

Jedna baza `data/edt.db`, ale **każdy moduł jest właścicielem własnych tabel**:
  * O1 (D2): `documents`
  * O3 (N2): `entities`
  * O2 (S4, opcjonalnie): cache embeddingów – raczej w plikach w data/cache/

Moduł tworzy swoje tabele przez `ensure_schema(conn, DDL)` (CREATE TABLE IF NOT EXISTS).
Nie modyfikuj tabel innych modułów – czytaj dane przez interfejsy z edt/interfaces.py.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from edt.config import DB_PATH


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Połączenie gotowe do użycia w Streamlit (wiele wątków) i w testach (":memory:")."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if str(path) != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def ensure_schema(conn: sqlite3.Connection, ddl: str) -> None:
    """Wykonuje skrypt DDL (powinien używać IF NOT EXISTS)."""
    with conn:
        conn.executescript(ddl)
