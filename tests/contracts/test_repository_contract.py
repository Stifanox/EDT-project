"""Test kontraktu DocumentRepository.

O1: dopisz SqliteDocumentRepository do REPO_FACTORIES (D2).
"""

from __future__ import annotations

import pytest

from edt.db import connect
from edt.interfaces import DocumentRepository
from edt.storage import DuplicateDocumentError, InMemoryDocumentRepository, SqliteDocumentRepository

REPO_FACTORIES = [
    pytest.param(InMemoryDocumentRepository, id="memory"),
    pytest.param(lambda: SqliteDocumentRepository(connect(":memory:")), id="sqlite"),
]


@pytest.fixture(params=REPO_FACTORIES)
def repo(request) -> DocumentRepository:
    return request.param()


def test_crud(repo, tiny_docs):
    assert isinstance(repo, DocumentRepository)
    for d in tiny_docs:
        repo.add(d)
    assert repo.count() == len(tiny_docs)
    assert repo.get("d2") == tiny_docs[1]
    assert [d.id for d in repo.list()] == [d.id for d in tiny_docs]
    assert repo.find_by_hash(tiny_docs[2].content_hash).id == "d3"
    assert repo.delete("d2") is True
    assert repo.delete("d2") is False
    assert repo.get("d2") is None
    assert repo.count() == len(tiny_docs) - 1


def test_roundtrip_preserves_fields(repo, tiny_docs):
    doc = tiny_docs[0]
    repo.add(doc)
    got = repo.get(doc.id)
    for f in ("id", "name", "text", "source_type", "language", "size_bytes",
              "num_pages", "content_hash"):
        assert getattr(got, f) == getattr(doc, f), f


def test_same_id_overwrites(repo, tiny_docs):
    from dataclasses import replace

    repo.add(tiny_docs[0])
    repo.add(replace(tiny_docs[0], name="nowa_nazwa.txt"))
    assert repo.count() == 1 and repo.get("d1").name == "nowa_nazwa.txt"


def test_duplicate_content_rejected(repo, tiny_docs):
    from dataclasses import replace

    repo.add(tiny_docs[0])
    with pytest.raises(DuplicateDocumentError):
        repo.add(replace(tiny_docs[0], id="inne-id"))
    assert repo.count() == 1


def test_missing_and_empty(repo):
    assert repo.get("nie-ma") is None
    assert repo.delete("nie-ma") is False
    assert repo.find_by_hash("") is None
    assert repo.list() == [] and repo.count() == 0
