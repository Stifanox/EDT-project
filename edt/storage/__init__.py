"""Przechowywanie dokumentów (właściciel: O1)."""

from edt.storage.errors import DuplicateDocumentError
from edt.storage.files import FileStore
from edt.storage.memory import InMemoryDocumentRepository
from edt.storage.sqlite_repo import SqliteDocumentRepository

__all__ = [
    "DuplicateDocumentError",
    "FileStore",
    "InMemoryDocumentRepository",
    "SqliteDocumentRepository",
]
