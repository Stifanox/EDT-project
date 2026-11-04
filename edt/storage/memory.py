"""Repozytorium dokumentów w pamięci (P0).

Używane w testach i jako domyślna implementacja do czasu etapu D2 (SQLite).
"""

from __future__ import annotations

from edt.models import Document


class InMemoryDocumentRepository:
    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}

    def add(self, doc: Document) -> None:
        self._docs[doc.id] = doc

    def get(self, doc_id: str) -> Document | None:
        return self._docs.get(doc_id)

    def list(self) -> list[Document]:
        return sorted(self._docs.values(), key=lambda d: d.added_at)

    def delete(self, doc_id: str) -> bool:
        return self._docs.pop(doc_id, None) is not None

    def find_by_hash(self, content_hash: str) -> Document | None:
        return next((d for d in self._docs.values() if d.content_hash == content_hash), None)

    def count(self) -> int:
        return len(self._docs)
