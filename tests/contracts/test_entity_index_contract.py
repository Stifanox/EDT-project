"""Test kontraktu EntityIndex / EntityExtractor.

O3: dopisz swoje implementacje do INDEX_FACTORIES (N1/N2).
"""

from __future__ import annotations

import pytest

from edt.interfaces import EntityExtractor, EntityIndex
from edt.models import EntityType
from edt.ner import InMemoryEntityIndex, RegexEntityExtractor

INDEX_FACTORIES = [
    pytest.param(lambda: InMemoryEntityIndex(RegexEntityExtractor()), id="memory+regex"),
    # pytest.param(lambda: InMemoryEntityIndex(SpacyEntityExtractor()), id="memory+spacy",
    #              marks=pytest.mark.slow),
    # pytest.param(lambda: SqliteEntityIndex(connect(":memory:"), RegexEntityExtractor()),
    #              id="sqlite+regex"),
]


@pytest.fixture(params=INDEX_FACTORIES)
def index(request, sample_docs) -> EntityIndex:
    idx = request.param()
    idx.rebuild(sample_docs)
    return idx


def test_protocols(index):
    assert isinstance(index, EntityIndex)
    if hasattr(index, "extractor"):
        assert isinstance(index.extractor, EntityExtractor)


def test_mentions_offsets_match_text(index, sample_docs):
    for doc in sample_docs:
        mentions = index.mentions(doc.id)
        assert [m.start for m in mentions] == sorted(m.start for m in mentions)
        for m in mentions:
            assert m.doc_id == doc.id
            assert doc.text[m.start:m.end] == m.text
            assert isinstance(m.label, EntityType)


def test_finds_dates(index):
    assert index.entity_stats(label=EntityType.DATE), "korpus zawiera daty (np. 1867)"


def test_stats_sorted_and_consistent(index):
    stats = index.entity_stats()
    assert stats
    keys = [(-s.doc_count, -s.mention_count) for s in stats]
    assert keys == sorted(keys)
    top = stats[0]
    assert index.doc_ids_with(key=top.key, label=top.label)
    assert len(index.mentions_of(top.key, top.label)) == top.mention_count
    assert len(index.doc_ids_with(key=top.key, label=top.label)) == top.doc_count


def test_stats_limit_and_query(index):
    assert len(index.entity_stats(limit=3)) <= 3
    assert all("19" in s.key or "19" in s.text.lower() for s in index.entity_stats(query="19"))


def test_remove_document(index, sample_docs):
    doc_id = sample_docs[0].id
    index.remove_document(doc_id)
    assert index.mentions(doc_id) == []
    assert doc_id not in index.doc_ids_with()
