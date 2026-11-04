"""Test kontraktu SearchEngine – KAŻDY silnik musi go przejść.

O2: dopisz fabrykę swojego silnika do ENGINE_FACTORIES (S2/S3/S4).
Silniki wymagające ciężkich modeli oznacz `pytest.param(..., marks=pytest.mark.slow)`.
"""

from __future__ import annotations

import pytest

from edt.interfaces import SearchEngine
from edt.search import SubstringSearchEngine

ENGINE_FACTORIES = [
    pytest.param(lambda: SubstringSearchEngine("stub", "Zaślepka"), id="stub"),
    # pytest.param(lambda: KeywordSearchEngine(), id="keyword"),
    # pytest.param(lambda: TfidfSearchEngine(), id="tfidf"),
    # pytest.param(lambda: SemanticSearchEngine(), id="semantic", marks=pytest.mark.slow),
]


@pytest.fixture(params=ENGINE_FACTORIES)
def engine(request, tiny_docs) -> SearchEngine:
    eng = request.param()
    eng.rebuild(tiny_docs)
    return eng


def test_implements_protocol(engine):
    assert isinstance(engine, SearchEngine)
    assert engine.name and engine.label


def test_results_sorted_and_ranked(engine):
    results = engine.search("kot", top_k=10)
    assert results, "zapytanie 'kot' powinno coś znaleźć"
    assert [r.rank for r in results] == list(range(1, len(results) + 1))
    assert all(a.score >= b.score for a, b in zip(results, results[1:], strict=False))
    assert all(r.method == engine.name and r.score > 0 for r in results)
    assert results[0].doc_id == "d1"


def test_top_k(engine):
    assert len(engine.search("kot pies cat samochody", top_k=2)) <= 2


def test_empty_query(engine):
    assert engine.search("") == []
    assert engine.search("   ") == []


def test_doc_filter(engine):
    assert all(r.doc_id in {"d2"} for r in engine.search("kot pies", doc_filter={"d2"}))
    assert engine.search("kot", doc_filter=set()) == []


def test_add_and_remove(engine, tiny_docs):
    engine.remove_document("d1")
    assert all(r.doc_id != "d1" for r in engine.search("kot"))
    engine.add_document(tiny_docs[0])
    assert any(r.doc_id == "d1" for r in engine.search("kot"))


def test_snippet_present(engine):
    r = engine.search("kot")[0]
    assert r.snippet
    for s, e in r.snippet_highlights:
        assert 0 <= s < e <= len(r.snippet)
