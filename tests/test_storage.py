"""Testy etapu D2: trwałe repozytorium SQLite i przechowywanie oryginałów plików."""

from __future__ import annotations

import threading
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from edt import config
from edt.db import connect
from edt.models import SourceType
from edt.services import build_services
from edt.storage import FileStore, SqliteDocumentRepository

from .conftest import make_doc

ROOT = Path(__file__).resolve().parent.parent
KOPERNIK_PDF = ROOT / "data" / "sample" / "pl_07_mikolaj_kopernik.pdf"


# --------------------------------------------------------------------------- #
# SqliteDocumentRepository
# --------------------------------------------------------------------------- #
def test_data_survives_new_connection(tmp_path):
    db = tmp_path / "edt.db"
    doc = replace(
        make_doc("abc", "Zażółć gęślą jaźń – test trwałości."),
        source_type=SourceType.PDF,
        num_pages=3,
        added_at=datetime(2026, 11, 4, 15, 30, 12, 345678, tzinfo=UTC),
        metadata={"title": "Tytuł „cudzysłów”", "author": "Zespół EDT", "pages_without_text": 1},
    )
    repo = SqliteDocumentRepository(connect(db))
    repo.add(doc)
    repo.conn.close()

    got = SqliteDocumentRepository(connect(db)).get("abc")
    assert got == doc                      # wszystkie pola porównywane w dataclass
    assert got.metadata == doc.metadata    # metadata ma compare=False – sprawdzamy osobno
    assert got.added_at.tzinfo is not None


def test_list_order_is_insertion_order_for_equal_timestamps():
    repo = SqliteDocumentRepository(connect(":memory:"))
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(5):
        repo.add(replace(make_doc(f"d{i}", f"tekst {i}"), added_at=ts))
    assert [d.id for d in repo.list()] == [f"d{i}" for i in range(5)]


def test_schema_is_idempotent(tmp_path):
    db = tmp_path / "edt.db"
    SqliteDocumentRepository(connect(db)).add(make_doc("x", "raz"))
    repo = SqliteDocumentRepository(connect(db))  # ponowne ensure_schema nie kasuje danych
    assert repo.count() == 1


def test_concurrent_writes_from_threads(tmp_path):
    repo = SqliteDocumentRepository(connect(tmp_path / "edt.db"))
    errors: list[BaseException] = []

    def worker(n: int) -> None:
        try:
            for i in range(20):
                repo.add(make_doc(f"t{n}-{i}", f"wątek {n} dokument {i}"))
                repo.list()
        except BaseException as exc:  # pragma: no cover - raportujemy niżej
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert repo.count() == 80


# --------------------------------------------------------------------------- #
# FileStore
# --------------------------------------------------------------------------- #
def test_file_store_roundtrip(tmp_path):
    store = FileStore(tmp_path / "files")
    assert store.path("abc") is None and store.read("abc") is None
    p = store.save("abc", "Raport.PDF", b"%PDF-data")
    assert p.name == "abc.pdf" and store.read("abc") == b"%PDF-data"
    store.save("abc", "raport.txt", b"txt")  # nadpisanie innym rozszerzeniem
    assert store.path("abc").name == "abc.txt" and len(list(store.root.iterdir())) == 1
    assert store.delete("abc") is True and store.delete("abc") is False


def test_file_store_prune(tmp_path):
    store = FileStore(tmp_path)
    for doc_id in ("keep", "orphan"):
        store.save(doc_id, "a.txt", b"x")
    (tmp_path / ".tmp-leftover").write_bytes(b"x")
    assert store.prune({"keep"}) == 2
    assert store.doc_ids() == {"keep"}


@pytest.mark.parametrize("bad_id", ["../secret", "a/b", "", "x" * 200, "a.b"])
def test_file_store_rejects_unsafe_ids(tmp_path, bad_id):
    with pytest.raises(ValueError):
        FileStore(tmp_path).save(bad_id, "a.txt", b"x")


# --------------------------------------------------------------------------- #
# Integracja z AppServices
# --------------------------------------------------------------------------- #
def test_services_store_original_and_delete_everything():
    s = build_services(load_samples=False)
    data = KOPERNIK_PDF.read_bytes()
    doc = s.ingest_file(KOPERNIK_PDF.name, data).document
    assert doc is not None
    assert s.original_path(doc.id).read_bytes() == data
    assert config.DB_PATH.exists()

    assert s.delete_document(doc.id)
    assert s.original_path(doc.id) is None
    assert s.repository.get(doc.id) is None
    assert s.entities.mentions(doc.id) == []
    assert list(config.FILES_DIR.iterdir()) == []


def test_restart_keeps_documents_and_rebuilds_indexes():
    first = build_services(load_samples=True)
    n = first.repository.count()
    assert n == 12
    first.repository.conn.close()

    second = build_services(load_samples=True)  # baza niepusta => bez ponownego importu
    assert second.repository.count() == n
    assert second.search("keyword", "heliocentryczny")
    assert second.entities.entity_stats()
    assert all(second.original_path(d.id) for d in second.repository.list())


def test_startup_prunes_orphan_files():
    config.FILES_DIR.mkdir(parents=True)
    (config.FILES_DIR / "deadbeef.txt").write_bytes(b"sierota")
    build_services(load_samples=False)
    assert not (config.FILES_DIR / "deadbeef.txt").exists()


def test_tests_do_not_touch_real_data_dir():
    assert config.DB_PATH != ROOT / "data" / "edt.db"
    assert ROOT not in config.FILES_DIR.parents
