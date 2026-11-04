"""Testy etapu D6: import z folderu / ZIP, eksport CSV/JSON, CLI, synchronizacja z bazą."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from edt import config
from edt.cli import main as cli
from edt.exporting import documents_csv, entities_export, mention_rows
from edt.ingest import IngestError
from edt.ingest.sources import folder_batch, zip_batch
from edt.services import build_services

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "sample"


@pytest.fixture
def folder(tmp_path) -> Path:
    root = tmp_path / "korpus"
    (root / "pod" / "glebiej").mkdir(parents=True)
    (root / ".ukryty").mkdir()
    (root / "a.txt").write_text("Dokument A o Krakowie z 1999 roku.", encoding="utf-8")
    (root / "pod" / "b.TXT").write_text("Dokument B o Gdańsku.", encoding="utf-8")
    (root / "pod" / "glebiej" / "k.pdf").write_bytes((SAMPLE / "pl_07_mikolaj_kopernik.pdf")
                                                     .read_bytes())
    (root / "notatki.docx").write_bytes(b"PK")
    (root / ".ukryty" / "c.txt").write_text("ukryty", encoding="utf-8")
    (root / ".DS_Store").write_bytes(b"x")
    return root


def make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


def read_csv(data: bytes) -> list[dict[str, str]]:
    assert data.startswith(b"\xef\xbb\xbf"), "CSV powinien mieć BOM (Excel + polskie znaki)"
    return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))


# --------------------------------------------------------------------------- #
# Źródła: folder i ZIP
# --------------------------------------------------------------------------- #
def test_folder_batch(folder):
    batch = folder_batch(folder)
    assert batch.names == ["a.txt", "b.TXT", "k.pdf"]
    assert batch.skipped == ["notatki.docx"]
    assert [name for name, _ in batch] == batch.names
    assert folder_batch(folder, recursive=False).names == ["a.txt"]


def test_folder_batch_missing(tmp_path):
    with pytest.raises(IngestError, match="nie istnieje"):
        folder_batch(tmp_path / "brak")


def test_zip_batch():
    data = make_zip({
        "korpus/a.txt": "Zażółć gęślą jaźń".encode(),
        "korpus/pod/k.pdf": (SAMPLE / "pl_07_mikolaj_kopernik.pdf").read_bytes(),
        "korpus/obraz.png": b"\x89PNG",
        "__MACOSX/korpus/._a.txt": b"x",
        "korpus/.ukryty.txt": b"x",
    })
    batch = zip_batch(data)
    assert batch.names == ["a.txt", "k.pdf"]
    assert batch.skipped == ["korpus/obraz.png"]
    items = dict(batch)
    assert items["a.txt"].decode() == "Zażółć gęślą jaźń"


def test_zip_bomb_and_corrupt():
    data = make_zip({f"f{i}.txt": b"a" * 10_000 for i in range(5)})  # świetnie się kompresuje
    with pytest.raises(IngestError, match="limit"):
        zip_batch(data, max_total=30_000)
    with pytest.raises(IngestError, match="ZIP"):
        zip_batch(b"to nie jest zip")


def test_ingest_many_uses_known_length_for_progress(folder):
    services = build_services(load_samples=False)
    calls = []
    report = services.ingest_many(folder_batch(folder), on_progress=lambda *a: calls.append(a))
    assert len(report.added) == 3
    assert [c[:2] for c in calls] == [(1, 3), (2, 3), (3, 3)]


# --------------------------------------------------------------------------- #
# Eksport
# --------------------------------------------------------------------------- #
@pytest.fixture
def services():
    return build_services(load_samples=True)


def test_documents_csv_roundtrip(services):
    docs = services.repository.list()
    rows = read_csv(documents_csv(docs, lambda i: len(services.entities.mentions(i))))
    assert [r["name"] for r in rows] == [d.name for d in docs]
    pdf = next(r for r in rows if r["name"] == "pl_07_mikolaj_kopernik.pdf")
    assert pdf["num_pages"] == "3" and pdf["source_type"] == "pdf"
    assert json.loads(pdf["metadata"])["author"] == "Zespół EDT"
    assert int(pdf["entity_mentions"]) == len(services.entities.mentions(pdf["id"]))


def test_entity_mentions_export(services):
    doc = next(d for d in services.repository.list() if d.name.startswith("pl_02"))
    rows = mention_rows([doc], services.entities)
    assert rows and all(r["doc_id"] == doc.id for r in rows)
    first = rows[0]
    assert f"[{first['text']}]" in first["context"]
    assert doc.text[first["start"]:first["end"]] == first["text"]

    csv_rows = read_csv(entities_export([doc], services.entities, "csv"))
    assert len(csv_rows) == len(rows) and csv_rows[0]["label_pl"]
    assert json.loads(entities_export([doc], services.entities, "json")) == rows


def test_entity_aggregated_export(services):
    stats = services.entities.entity_stats()
    rows = json.loads(entities_export([], services.entities, "json", aggregated=True))
    assert len(rows) == len(stats) and rows[0]["doc_count"] == stats[0].doc_count
    with pytest.raises(ValueError):
        entities_export([], services.entities, "xml")


# --------------------------------------------------------------------------- #
# Synchronizacja (np. aplikacja + CLI na tej samej bazie)
# --------------------------------------------------------------------------- #
def test_sync_with_repository_between_processes():
    app = build_services(load_samples=False)
    cli_side = build_services(load_samples=False)       # „inny proces”, ta sama baza

    doc = cli_side.ingest_file("a.txt", b"Kopernik i Frombork 1543.").document
    assert app.search("keyword", "Kopernik") == []      # aplikacja jeszcze nie wie
    assert app.sync_with_repository() == (1, 0)
    assert app.search("keyword", "Kopernik")[0].doc_id == doc.id
    assert app.entities.mentions(doc.id)

    cli_side.delete_document(doc.id)
    assert app.sync_with_repository() == (0, 1)
    assert app.search("keyword", "Kopernik") == []
    assert app.sync_with_repository() == (0, 0)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def test_cli_import_list_export(folder, tmp_path, capsys):
    assert cli(["import", str(folder), "-q"]) == 0
    out = capsys.readouterr().out
    assert "pominięto: notatki.docx" in out and "Dodano: 3" in out

    assert cli(["list"]) == 0
    assert "Razem: 3 dokumentów" in capsys.readouterr().out

    docs_csv, ent_json = tmp_path / "d.csv", tmp_path / "e.json"
    assert cli(["export-documents", str(docs_csv)]) == 0
    assert len(read_csv(docs_csv.read_bytes())) == 3
    assert cli(["export-entities", str(ent_json), "--aggregated"]) == 0
    assert json.loads(ent_json.read_text("utf-8"))


def test_cli_zip_and_errors(tmp_path, capsys):
    archive = tmp_path / "paczka.zip"
    archive.write_bytes(make_zip({"a.txt": b"Tekst A.", "zly.pdf": b"%PDF-1.4 smieci"}))
    assert cli(["import", str(archive)]) == 1                 # jeden plik z błędem
    assert "zly.pdf" in capsys.readouterr().out
    assert cli(["import", str(tmp_path / "brak")]) == 2
    assert cli(["export-entities", str(tmp_path / "e.xml")]) == 2
    assert cli(["export-entities", str(tmp_path / "e.csv"), "--doc", "nie-ma"]) == 2
    assert cli(["rebuild"]) == 0


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #
@pytest.fixture
def page(monkeypatch):
    monkeypatch.setattr(config, "LOAD_SAMPLES_IF_EMPTY", True)
    from edt.ui.state import get_services

    get_services.clear()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    at.switch_page("pages/1_Baza_dokumentow.py").run()
    assert not at.exception
    return at


def test_gui_folder_import_and_export_buttons(page, folder):
    page.text_input(key="folder-path").input(str(folder)).run()
    next(b for b in page.button if b.label == "Wczytaj folder").click().run()
    assert not page.exception
    # k.pdf to ten sam plik co pl_07 z korpusu przykładowego => duplikat
    assert any(s.value.startswith("Dodano: 2 · duplikaty: 1") for s in page.success)
    assert any("k.pdf" in i.value and "pl_07_mikolaj_kopernik" in i.value for i in page.info)
    assert any("notatki.docx" in c.value for c in page.caption)
    assert len(page.dataframe[0].value) == 14

    labels = {b.label for b in page.get("download_button")}
    assert {"📄 Lista dokumentów (CSV)", "🏷️ Wystąpienia encji (z kontekstem)",
            "📊 Zestawienie encji (korpus)"} <= labels


def test_gui_folder_errors(page, tmp_path):
    page.text_input(key="folder-path").input(str(tmp_path / "brak")).run()
    next(b for b in page.button if b.label == "Wczytaj folder").click().run()
    assert any("nie istnieje" in e.value for e in page.error)
    (tmp_path / "pusty").mkdir()
    page.text_input(key="folder-path").input(str(tmp_path / "pusty")).run()
    next(b for b in page.button if b.label == "Wczytaj folder").click().run()
    assert any("nie ma plików" in w.value for w in page.warning)


def test_app_picks_up_changes_from_other_process(page):
    """Dokument dodany przez CLI pojawia się w aplikacji po odświeżeniu strony."""
    other = build_services(load_samples=False)
    other.ingest_file("z_cli.txt", "Dokument dodany z wiersza poleceń.".encode())
    page.run()
    assert "z_cli.txt" in list(page.dataframe[0].value["Nazwa"])
