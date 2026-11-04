"""Indeks encji w pamięci (P0) – implementacja `EntityIndex` dla dowolnego ekstraktora.

Etap N2 (O3) dodaje wersję trwałą (SQLite), ale ta klasa może zostać
jako implementacja testowa/referencyjna.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence

from edt.interfaces import EntityExtractor
from edt.models import Document, EntityMention, EntityStat, EntityType


class InMemoryEntityIndex:
    def __init__(self, extractor: EntityExtractor) -> None:
        self.extractor = extractor
        self._by_doc: dict[str, list[EntityMention]] = {}

    # --- DocumentIndexer ---
    def rebuild(self, docs: Sequence[Document]) -> None:
        self._by_doc = {}
        for doc in docs:
            self.add_document(doc)

    def add_document(self, doc: Document) -> None:
        self._by_doc[doc.id] = sorted(self.extractor.extract(doc), key=lambda m: m.start)

    def remove_document(self, doc_id: str) -> None:
        self._by_doc.pop(doc_id, None)

    # --- EntityIndex ---
    def mentions(self, doc_id: str) -> list[EntityMention]:
        return list(self._by_doc.get(doc_id, []))

    def _all(self, label: EntityType | None = None):
        for mentions in self._by_doc.values():
            for m in mentions:
                if label is None or m.label == label:
                    yield m

    def mentions_of(self, key: str, label: EntityType | None = None) -> list[EntityMention]:
        return [m for m in self._all(label) if m.key == key]

    def entity_stats(
        self, query: str = "", label: EntityType | None = None, limit: int | None = None
    ) -> list[EntityStat]:
        q = query.strip().lower()
        surface: dict[tuple[str, EntityType], Counter[str]] = defaultdict(Counter)
        docs: dict[tuple[str, EntityType], set[str]] = defaultdict(set)
        for m in self._all(label):
            if q and q not in m.key and q not in m.text.lower():
                continue
            k = (m.key, m.label)
            surface[k][m.text] += 1
            docs[k].add(m.doc_id)
        stats = [
            EntityStat(
                key, forms.most_common(1)[0][0], lbl, sum(forms.values()), len(docs[(key, lbl)])
            )
            for (key, lbl), forms in surface.items()
        ]
        stats.sort(key=lambda s: (-s.doc_count, -s.mention_count, s.key))
        return stats[:limit] if limit is not None else stats

    def doc_ids_with(self, key: str | None = None, label: EntityType | None = None) -> set[str]:
        return {m.doc_id for m in self._all(label) if key is None or m.key == key}
