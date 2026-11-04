"""Testy integracyjne fasady AppServices (działają na zaślepkach i na prawdziwych modułach)."""

from __future__ import annotations

from edt.services import build_services
from edt.textproc import detect_language, make_snippet


def test_ingest_search_delete_flow():
    s = build_services(load_samples=False)
    res = s.ingest_file("a.txt", b"Kot siedzi na macie w Krakowie od 1999 roku.")
    assert res.ok and res.document.language == "pl"

    dup = s.ingest_file("b.txt", b"Kot siedzi na macie w Krakowie od 1999 roku.")
    assert not dup.ok and dup.duplicate_of is not None

    assert s.ingest_file("c.docx", b"x").error

    doc_id = res.document.id
    assert all(results for results in s.search_all("kot").values())
    assert doc_id in s.entities.doc_ids_with()

    assert s.delete_document(doc_id)
    assert s.repository.count() == 0
    assert all(not results for results in s.search_all("kot").values())
    assert s.entities.mentions(doc_id) == []


def test_samples_load():
    s = build_services(load_samples=True)
    assert s.repository.count() >= 8
    langs = {d.language for d in s.repository.list()}
    assert langs == {"pl", "en"}


def test_detect_language():
    assert detect_language("To jest dokument napisany po polsku, który ma kilka słów.") == "pl"
    assert detect_language("This is a document written in English with some words.") == "en"
    assert detect_language("") == "unknown"


def test_snippet_highlights_point_at_terms():
    text = "Ala ma kota. " * 50 + "Tutaj jest samochód elektryczny. " + "Koniec. " * 50
    snippet, hl = make_snippet(text, ["samochód"])
    assert hl and all(snippet[s:e].lower() == "samochód" for s, e in hl)
