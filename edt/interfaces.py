"""Interfejsy (Protocol) modułów – KONTRAKT między osobami.

⚠️ Plik zamrożony po etapie P0 (zasady zmian: jak w edt/models.py).

Każdy komponent, który musi wiedzieć o dodaniu/usunięciu dokumentu
(silniki wyszukiwania, indeks encji), implementuje `DocumentIndexer`.
`AppServices` (edt/services.py) powiadamia wszystkie indeksery.
Testy kontraktowe: tests/contracts/.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from typing import Protocol, runtime_checkable

from edt.config import DEFAULT_TOP_K
from edt.models import Document, EntityMention, EntityStat, EntityType, SearchResult


@runtime_checkable
class DocumentRepository(Protocol):
    """Trwałe przechowywanie dokumentów i metadanych (właściciel: O1)."""

    def add(self, doc: Document) -> None: ...
        # ten sam id => nadpisanie; ta sama treść (content_hash) pod innym id =>
        # edt.storage.DuplicateDocumentError
    def get(self, doc_id: str) -> Document | None: ...
    def list(self) -> list[Document]: ...                 # kolejność: od najstarszego
    def delete(self, doc_id: str) -> bool: ...            # True, jeśli usunięto
    def find_by_hash(self, content_hash: str) -> Document | None: ...
    def count(self) -> int: ...


@runtime_checkable
class DocumentIndexer(Protocol):
    """Coś, co utrzymuje indeks nad dokumentami i reaguje na zmiany w bazie."""

    def rebuild(self, docs: Sequence[Document]) -> None: ...   # pełna przebudowa
    def add_document(self, doc: Document) -> None: ...
    def remove_document(self, doc_id: str) -> None: ...


@runtime_checkable
class SearchEngine(DocumentIndexer, Protocol):
    """Metoda wyszukiwania (właściciel: O2).

    Kontrakt `search`:
      * zwraca maks. `top_k` wyników, posortowanych malejąco po `score`,
        `rank` = 1..n, `method` = `self.name`;
      * zwraca tylko dokumenty o score > 0 (brak dopasowania => brak wyniku);
      * `doc_filter=None` => bez ograniczeń; zbiór => tylko te doc_id
        (pusty zbiór => pusta lista). Służy do filtrowania po encjach;
      * puste / same białe znaki zapytanie => pusta lista (bez wyjątku).
    """

    name: str    # identyfikator, np. "keyword", "tfidf", "semantic"
    label: str   # nazwa do GUI, np. "Słowa kluczowe"

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        doc_filter: Collection[str] | None = None,
    ) -> list[SearchResult]: ...


@runtime_checkable
class EntityExtractor(Protocol):
    """Wykrywanie encji w jednym dokumencie (właściciel: O3)."""

    def extract(self, doc: Document) -> list[EntityMention]: ...


@runtime_checkable
class EntityIndex(DocumentIndexer, Protocol):
    """Przechowywanie i odpytywanie encji w korpusie (właściciel: O3).

    `key` w metodach = `EntityMention.key` / `EntityStat.key`.
    """

    def mentions(self, doc_id: str) -> list[EntityMention]: ...
        # encje jednego dokumentu, posortowane po `start`

    def mentions_of(self, key: str, label: EntityType | None = None) -> list[EntityMention]: ...
        # wszystkie wystąpienia danej encji w całym korpusie

    def entity_stats(
        self,
        query: str = "",
        label: EntityType | None = None,
        limit: int | None = None,
    ) -> list[EntityStat]: ...
        # agregaty; `query` filtruje po podciągu (case-insensitive) w key/text;
        # sortowanie: doc_count malejąco, potem mention_count malejąco

    def doc_ids_with(
        self,
        key: str | None = None,
        label: EntityType | None = None,
    ) -> set[str]: ...
        # dokumenty zawierające encję `key` i/lub dowolną encję typu `label`;
        # oba None => wszystkie dokumenty, które mają jakąkolwiek encję
