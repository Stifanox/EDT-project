"""Zaślepka silnika wyszukiwania (P0).

Proste zliczanie wystąpień tokenów zapytania. Służy tylko do tego, żeby GUI
i inne moduły działały, zanim powstaną prawdziwe silniki (S2–S4).
Spełnia kontrakt `SearchEngine` – wzór dla prawdziwych implementacji.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from edt.config import DEFAULT_TOP_K
from edt.models import Document, SearchResult
from edt.textproc import make_snippet, tokenize


class SubstringSearchEngine:
    def __init__(self, name: str = "stub", label: str = "Zaślepka") -> None:
        self.name = name
        self.label = label
        self._docs: dict[str, Document] = {}

    # --- DocumentIndexer ---
    def rebuild(self, docs: Sequence[Document]) -> None:
        self._docs = {d.id: d for d in docs}

    def add_document(self, doc: Document) -> None:
        self._docs[doc.id] = doc

    def remove_document(self, doc_id: str) -> None:
        self._docs.pop(doc_id, None)

    # --- SearchEngine ---
    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        doc_filter: Collection[str] | None = None,
    ) -> list[SearchResult]:
        terms = tokenize(query, remove_stopwords=True)
        if not terms:
            return []
        scored: list[tuple[float, Document]] = []
        for doc in self._docs.values():
            if doc_filter is not None and doc.id not in doc_filter:
                continue
            tokens = tokenize(doc.text)
            score = float(sum(tokens.count(t) for t in terms))
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda x: (-x[0], x[1].name))
        results = []
        for rank, (score, doc) in enumerate(scored[:top_k], start=1):
            snippet, hl = make_snippet(doc.text, terms)
            results.append(
                SearchResult(doc.id, doc.name, score, rank, self.name, snippet, hl,
                             details={"terms": terms})
            )
        return results
