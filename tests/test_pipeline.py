"""Testy etapu D3: import wielu plików, odporność na błędy indekserów, logowanie."""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Sequence
from pathlib import Path

import pytest

from edt.models import Document
from edt.services import AppServices, build_services
from edt.storage import DuplicateDocumentError

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "pdf"
KOPERNIK = ROOT / "data" / "sample" / "pl_07_mikolaj_kopernik.pdf"


class FlakyIndexer:
    """Indekser, który rzuca wyjątek przy wybranych operacjach (domyślnie: zawsze)."""

    name = "flaky"

    def __init__(self, fail_on: set[str], times: int | None = None) -> None:
        self.fail_on, self.times = fail_on, times
        self.docs: dict[str, Document] = {}

    def _maybe_fail(self, action: str) -> None:
        if action in self.fail_on and (self.times is None or self.times > 0):
            if self.times is not None:
                self.times -= 1
            raise RuntimeError(f"awaria {action}")

    def rebuild(self, docs: Sequence[Document]) -> None:
        self._maybe_fail("rebuild")
        self.docs = {d.id: d for d in docs}

    def add_document(self, doc: Document) -> None:
        self._maybe_fail("add")
        self.docs[doc.id] = doc

    def remove_document(self, doc_id: str) -> None:
        self._maybe_fail("remove")
        self.docs.pop(doc_id, None)


@pytest.fixture
def services() -> AppServices:
    return build_services(load_samples=False)


def _batch() -> list[tuple[str, bytes]]:
    txt = "Dokument testowy o Toruniu i Wiśle z 2026 roku.".encode()
    return [
        ("a.txt", txt),
        (KOPERNIK.name, KOPERNIK.read_bytes()),
        ("a_kopia.txt", txt),                          # duplikat w obrębie paczki
        ("raport.docx", b"PK..."),                     # zły format
        ("zepsuty.pdf", b"%PDF-1.4 smieci"),           # uszkodzony PDF
        ("skan.pdf", (FIXTURES / "no_text.pdf").read_bytes()),
    ]


# --------------------------------------------------------------------------- #
# ingest_many
# --------------------------------------------------------------------------- #
def test_ingest_many_report_and_progress(services):
    calls: list[tuple[int, int, str]] = []
    report = services.ingest_many(_batch(), on_progress=lambda *a: calls.append(a))

    assert len(report) == 6
    assert [r.filename for r in report.added] == ["a.txt", KOPERNIK.name]
    assert [r.filename for r in report.duplicates] == ["a_kopia.txt"]
    assert report.duplicates[0].duplicate_of.name == "a.txt"
    assert [r.filename for r in report.errors] == ["raport.docx", "zepsuty.pdf", "skan.pdf"]
    assert all(r.error for r in report.errors)
    assert report.summary().startswith("Dodano: 2 · duplikaty: 1 · błędy: 3")

    assert calls == [(i, 6, name) for i, (name, _) in enumerate(_batch(), start=1)]
    assert services.repository.count() == 2
    assert all(r.seconds >= 0 for r in report) and report.seconds >= 0


def test_ingest_many_accepts_generator_and_empty(services):
    assert len(services.ingest_many(iter([]))) == 0
    report = services.ingest_many(((n, d) for n, d in _batch()[:2]))
    assert len(report.added) == 2


# --------------------------------------------------------------------------- #
# Odporność na błędy indekserów
# --------------------------------------------------------------------------- #
def test_failing_indexer_on_add_does_not_break_import(services):
    flaky = FlakyIndexer({"add"})
    services.extra_indexers.append(flaky)

    result = services.ingest_file("a.txt", "Kopernik mieszkał we Fromborku od 1510 roku.".encode())
    assert result.ok
    assert any("flaky" in w for w in result.warnings)
    doc_id = result.document.id
    assert services.repository.get(doc_id) is not None          # dokument zapisany
    assert services.search("keyword", "Kopernik")[0].doc_id == doc_id  # inne indeksy działają
    assert services.entities.mentions(doc_id)
    assert services.original_path(doc_id) is not None
    assert services.stale_indexers == {"flaky"}
    assert services.failures[-1].action == "add" and services.failures[-1].doc_id == doc_id


def test_rebuild_repairs_stale_indexer(services):
    flaky = FlakyIndexer({"add"}, times=1)  # psuje się tylko raz
    services.extra_indexers.append(flaky)
    doc_id = services.ingest_file("a.txt", b"Pierwszy dokument.").document.id
    assert doc_id not in flaky.docs and services.stale_indexers == {"flaky"}

    assert services.rebuild_indexes(only_stale=True) == []
    assert doc_id in flaky.docs and services.stale_indexers == set()


def test_failing_rebuild_does_not_stop_other_indexers(services):
    services.ingest_file("a.txt", "Kopernik i Toruń.".encode())
    services.extra_indexers.insert(0, FlakyIndexer({"rebuild"}))
    keyword = services.engines["keyword"]
    keyword.rebuild([])                                   # „zgubiony” indeks
    assert services.search("keyword", "Kopernik") == []

    failures = services.rebuild_indexes()
    assert [f.indexer for f in failures] == ["flaky"]
    assert services.search("keyword", "Kopernik")         # odbudowany mimo awarii flaky
    assert "flaky" in services.stale_indexers


def test_failing_indexer_on_remove_still_deletes_everywhere(services):
    doc_id = services.ingest_file("a.txt", "Kopernik i Toruń.".encode()).document.id
    services.extra_indexers.append(FlakyIndexer({"remove"}))

    assert services.delete_document(doc_id) is True
    assert services.repository.get(doc_id) is None
    assert services.search("keyword", "Kopernik") == []
    assert services.entities.mentions(doc_id) == []
    assert services.original_path(doc_id) is None
    assert services.failures[-1].action == "remove"


def test_delete_is_idempotent_and_cleans_leftovers(services):
    doc_id = services.ingest_file("a.txt", "Kopernik i Toruń.".encode()).document.id
    services.repository.delete(doc_id)                    # rekord zniknął „bokiem”
    assert services.delete_document(doc_id) is False
    assert services.search("keyword", "Kopernik") == []   # ale indeksy i plik posprzątane
    assert services.original_path(doc_id) is None


# --------------------------------------------------------------------------- #
# Nieoczekiwane błędy parsera / bazy
# --------------------------------------------------------------------------- #
def test_unexpected_parser_error_is_reported(services, monkeypatch):
    def boom(filename, data):
        raise RuntimeError("bug w parserze")

    monkeypatch.setattr("edt.services.parse_file", boom)
    result = services.ingest_file("a.txt", b"tekst")
    assert not result.ok and "bug w parserze" in result.error
    assert services.repository.count() == 0


def test_repository_error_is_reported_and_nothing_indexed(services, monkeypatch):
    def broken_add(doc):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(services.repository, "add", broken_add)
    result = services.ingest_file("a.txt", b"Kopernik.")
    assert not result.ok and "database is locked" in result.error
    assert services.search("keyword", "Kopernik") == []
    assert services.files.doc_ids() == set()


def test_duplicate_race_is_reported_as_duplicate(services, monkeypatch):
    first = services.ingest_file("a.txt", b"Ten sam tekst.").document
    real_find = services.repository.find_by_hash
    calls = {"n": 0}

    def find_once_missing(h):  # pierwsze sprawdzenie „nie widzi” duplikatu (wyścig)
        calls["n"] += 1
        return None if calls["n"] == 1 else real_find(h)

    monkeypatch.setattr(services.repository, "find_by_hash", find_once_missing)
    result = services.ingest_file("b.txt", b"Ten sam tekst.")
    assert result.is_duplicate and result.duplicate_of.id == first.id


def test_original_save_failure_is_a_warning(services, monkeypatch):
    def no_disk(*args):
        raise OSError("brak miejsca na dysku")

    monkeypatch.setattr(services.files, "save", no_disk)
    result = services.ingest_file("a.txt", b"Tekst.")
    assert result.ok and any("brak miejsca" in w for w in result.warnings)


# --------------------------------------------------------------------------- #
# Logowanie
# --------------------------------------------------------------------------- #
def test_logging(services, caplog):
    services.extra_indexers.append(FlakyIndexer({"add"}))
    with caplog.at_level(logging.INFO, logger="edt.services"):
        services.ingest_many(_batch()[:4])
    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("Dodano a.txt") for m in messages)
    assert any("Pominięto duplikat a_kopia.txt" in m for m in messages)
    assert any("Nie wczytano raport.docx" in m for m in messages)
    assert any("Indekser flaky: błąd add" in m for m in messages)
    assert any(m.startswith("Import zakończony") for m in messages)


def test_duplicate_error_type_exported():
    assert issubclass(DuplicateDocumentError, ValueError)
