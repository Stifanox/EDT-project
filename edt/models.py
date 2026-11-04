"""Wspólne modele danych – KONTRAKT między modułami.

⚠️ Plik zamrożony po etapie P0. Dozwolone są tylko zmiany wstecznie zgodne
(np. nowe pole z wartością domyślną) i każdą trzeba wpisać do
PROGRESS.md -> "Dziennik decyzji". Szczegóły: docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


# --------------------------------------------------------------------------- #
# Dokumenty
# --------------------------------------------------------------------------- #
class SourceType(StrEnum):
    TXT = "txt"
    PDF = "pdf"


@dataclass(frozen=True, slots=True)
class Document:
    """Dokument w bazie. `text` to już oczyszczona treść (po parsowaniu).

    Offsety znakowe (np. w EntityMention) zawsze odnoszą się do `text`.
    """

    id: str
    name: str                      # nazwa pliku wyświetlana w GUI
    text: str
    source_type: SourceType
    language: str = "unknown"      # "pl" | "en" | "unknown"
    added_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    size_bytes: int = 0            # rozmiar oryginalnego pliku
    num_pages: int | None = None   # tylko PDF
    content_hash: str = ""         # sha256 oryginalnych bajtów (deduplikacja)
    metadata: dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def num_chars(self) -> int:
        return len(self.text)

    @property
    def num_words(self) -> int:
        return len(self.text.split())


def compute_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def new_document_id() -> str:
    return uuid.uuid4().hex


# --------------------------------------------------------------------------- #
# Wyszukiwanie
# --------------------------------------------------------------------------- #
class SearchMethod(StrEnum):
    KEYWORD = "keyword"
    TFIDF = "tfidf"
    SEMANTIC = "semantic"


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Jeden wynik wyszukiwania. Lista wyników jest posortowana malejąco po `score`,
    a `rank` numerowany od 1."""

    doc_id: str
    doc_name: str
    score: float
    rank: int
    method: str                                        # SearchMethod lub inna nazwa silnika
    snippet: str = ""                                  # fragment tekstu związany z zapytaniem
    snippet_highlights: tuple[tuple[int, int], ...] = ()   # (start, end) w obrębie `snippet`
    details: dict[str, Any] = field(default_factory=dict, compare=False)  # np. dopasowane termy


# --------------------------------------------------------------------------- #
# NER
# --------------------------------------------------------------------------- #
class EntityType(StrEnum):
    """Wspólny (kanoniczny) zestaw typów encji – niezależny od modelu/języka.
    Mapowanie etykiet spaCy -> EntityType robi etap N1."""

    PERSON = "PERSON"
    ORG = "ORG"
    LOC = "LOC"
    DATE = "DATE"
    TIME = "TIME"
    EVENT = "EVENT"
    PRODUCT = "PRODUCT"
    MONEY = "MONEY"
    QUANTITY = "QUANTITY"
    MISC = "MISC"

    @property
    def label_pl(self) -> str:
        return _ENTITY_LABELS_PL[self]


_ENTITY_LABELS_PL: dict[EntityType, str] = {
    EntityType.PERSON: "Osoba",
    EntityType.ORG: "Organizacja",
    EntityType.LOC: "Lokalizacja",
    EntityType.DATE: "Data / okres",
    EntityType.TIME: "Czas",
    EntityType.EVENT: "Wydarzenie",
    EntityType.PRODUCT: "Produkt",
    EntityType.MONEY: "Kwota",
    EntityType.QUANTITY: "Liczba / ilość",
    EntityType.MISC: "Inne",
}


@dataclass(frozen=True, slots=True)
class EntityMention:
    """Pojedyncze wystąpienie encji w dokumencie."""

    doc_id: str
    text: str             # forma z tekstu, np. "Marii Skłodowskiej-Curie"
    label: EntityType
    start: int            # offset znakowy w Document.text
    end: int
    normalized: str = ""  # klucz grupowania (np. lemat, lowercase); pusty => text.lower()
    raw_label: str = ""   # oryginalna etykieta modelu, np. "persName" / "GPE"

    @property
    def key(self) -> str:
        return self.normalized or self.text.lower()


@dataclass(frozen=True, slots=True)
class EntityStat:
    """Zagregowana encja w całym korpusie (lista encji, top-N, wyszukiwanie encji)."""

    key: str              # EntityMention.key
    text: str             # najczęstsza forma powierzchniowa (do wyświetlania)
    label: EntityType
    mention_count: int
    doc_count: int
