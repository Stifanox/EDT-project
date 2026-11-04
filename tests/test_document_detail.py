"""Testy etapu D5: widok szczegółów dokumentu (logika + przepływy w AppTest)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from edt import config
from edt.models import EntityMention, EntityType, SourceType
from edt.ui.components import QUERY_HIGHLIGHT_STYLE
from edt.ui.documents_view import (
    document_entity_table,
    document_metadata_rows,
    mentions_in_section,
    section_of,
    spans_in_section,
    split_into_sections,
)

from .conftest import make_doc

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- #
# Logika
# --------------------------------------------------------------------------- #
def test_split_short_text_is_one_section():
    assert split_into_sections("krótki tekst", 100) == [(0, 12)]
    assert split_into_sections("", 100) == [(0, 0)]


def test_split_long_text_on_paragraphs():
    text = "\n\n".join(f"Akapit {i} " + "słowo " * 30 for i in range(50))
    sections = split_into_sections(text, 1000)
    assert len(sections) > 1
    assert sections[0][0] == 0 and sections[-1][1] == len(text)
    assert all(a[1] == b[0] for a, b in zip(sections, sections[1:], strict=False))  # bez przerw
    assert all(e - s <= 1000 for s, e in sections)
    assert all(text[s:e].startswith("Akapit") for s, e in sections)  # cięcie na akapicie


def test_split_without_separators_cuts_hard():
    sections = split_into_sections("x" * 2500, 1000)
    assert sections == [(0, 1000), (1000, 2000), (2000, 2500)]


def test_section_of():
    sections = [(0, 10), (10, 20), (20, 25)]
    assert [section_of(sections, o) for o in (0, 9, 10, 24, 99)] == [0, 0, 1, 2, 0]


def test_mentions_and_spans_in_section():
    m = [EntityMention("d", "Kraków", EntityType.LOC, 5, 11),
         EntityMention("d", "Toruń", EntityType.LOC, 18, 23),   # przecina granicę 20
         EntityMention("d", "Gdańsk", EntityType.LOC, 25, 31)]
    shifted = mentions_in_section(m, 0, 20)
    assert [(x.text, x.start, x.end) for x in shifted] == [("Kraków", 5, 11)]
    assert [(x.start, x.end) for x in mentions_in_section(m, 20, 40)] == [(5, 11)]
    assert spans_in_section([(1, 3), (19, 22), (25, 27)], 20, 40) == [(5, 7)]


def test_metadata_rows_include_pdf_metadata():
    doc = replace(make_doc("abc", "Tekst."), source_type=SourceType.PDF, num_pages=3,
                  metadata={"title": "Kopernik", "author": "Zespół EDT", "custom": 1})
    rows = dict(document_metadata_rows(doc))
    assert rows["Typ"] == "PDF" and rows["Liczba stron"] == "3"
    assert rows["Tytuł (PDF)"] == "Kopernik" and rows["Autor (PDF)"] == "Zespół EDT"
    assert rows["custom"] == "1" and rows["Identyfikator"] == "abc"


def test_entity_table_groups_and_sorts():
    m = [EntityMention("d", "Warszawie", EntityType.LOC, 0, 9, normalized="warszawa"),
         EntityMention("d", "Warszawa", EntityType.LOC, 20, 28, normalized="warszawa"),
         EntityMention("d", "Warszawa", EntityType.LOC, 40, 48, normalized="warszawa"),
         EntityMention("d", "1867", EntityType.DATE, 50, 54)]
    table = document_entity_table(m)
    assert list(table["Encja"]) == ["Warszawa", "1867"]
    assert list(table["Wystąpienia"]) == [3, 1]
    assert list(table["Typ"]) == ["Lokalizacja", "Data / okres"]
    assert list(table["key"]) == ["warszawa", "1867"] and list(table["label"]) == ["LOC", "DATE"]
    assert document_entity_table([]).empty


# --------------------------------------------------------------------------- #
# Przepływy GUI
# --------------------------------------------------------------------------- #
@pytest.fixture
def services(monkeypatch):
    monkeypatch.setattr(config, "LOAD_SAMPLES_IF_EMPTY", True)
    from edt.ui.state import get_services

    get_services.clear()
    return get_services()


def open_doc(doc_id: str | None = None, terms: list[str] | None = None) -> AppTest:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    if doc_id:
        at.session_state["selected_doc_id"] = doc_id
        at.session_state["highlight_terms"] = terms or []
    at.switch_page("pages/5_Dokument.py").run()
    assert not at.exception, at.exception
    return at


def doc_by_name(services, name):
    return next(d for d in services.repository.list() if d.name == name)


def content_html(at) -> str:
    return next(m.value for m in at.markdown if "<mark" in m.value or "<br>" in m.value)


def test_shows_selected_document_with_metadata(services):
    doc = doc_by_name(services, "pl_07_mikolaj_kopernik.pdf")
    at = open_doc(doc.id)
    assert at.title[0].value == "📄 pl_07_mikolaj_kopernik.pdf"
    assert dict((m.label, m.value) for m in at.metric)["Strony"] == "3"
    meta = at.table[0].value
    assert "Mikołaj Kopernik i przewrót heliocentryczny" in meta.to_string()
    labels = {b.label for b in at.get("download_button")}
    assert {"⬇️ Pobierz oryginał", "⬇️ Pobierz wyodrębniony tekst"} <= labels


def test_entities_highlighted_and_filterable(services):
    doc = doc_by_name(services, "pl_02_sklodowska_curie.txt")
    n_mentions = len(services.entities.mentions(doc.id))
    at = open_doc(doc.id)
    assert content_html(at).count("<mark") == n_mentions > 0
    at.multiselect[0].set_value([EntityType.DATE]).run()
    n_dates = sum(m.label is EntityType.DATE for m in services.entities.mentions(doc.id))
    assert content_html(at).count("<mark") == n_dates


def test_query_terms_from_search_are_highlighted(services):
    doc = doc_by_name(services, "pl_01_samochody_elektryczne.txt")
    at = open_doc(doc.id, terms=["stacje", "ładowania"])
    assert at.text_input[0].value == "stacje ładowania"
    html = content_html(at)
    assert QUERY_HIGHLIGHT_STYLE in html
    assert any("dopasowań fraz: <b>" in m.value for m in at.markdown)


def test_long_document_is_split_into_sections(services):
    paragraphs = [f"Akapit numer {i}. " + "Tekst wypełniający dokument. " * 40 for i in range(80)]
    paragraphs[-1] += "Szukany Unikat na samym końcu."
    doc = services.ingest_file("dlugi.txt", "\n\n".join(paragraphs).encode()).document
    assert doc.num_chars > 60_000

    at = open_doc(doc.id, terms=["Unikat"])
    slider = at.select_slider[0]
    assert len(slider.options) >= 4
    assert slider.value == len(slider.options) - 1      # sekcja z pierwszym dopasowaniem
    assert "Unikat" in content_html(at)
    at.select_slider[0].set_value(0).run()
    assert "Akapit numer 0." in content_html(at)


def test_entity_table_navigates_to_entities_view(services):
    doc = doc_by_name(services, "pl_02_sklodowska_curie.txt")
    at = open_doc(doc.id)
    at.session_state[f"entities-{doc.id}"] = {"selection": {"rows": [0], "columns": [],
                                                            "cells": []}}
    at.run()
    next(b for b in at.button if b.label.startswith("🏷️ Pokaż")).click().run()
    assert not at.exception
    selected = at.session_state["selected_entity"]
    assert doc.id in services.entities.doc_ids_with(selected["key"], EntityType(selected["label"]))


def test_delete_document_redirects_to_library(services):
    doc = doc_by_name(services, "en_02_paris_agreement.txt")
    at = open_doc(doc.id)
    next(b for b in at.button if b.label == "🗑️ Usuń dokument").click().run()
    next(b for b in at.button if b.label == "Usuń").click().run()
    assert not at.exception
    assert services.repository.get(doc.id) is None and services.original_path(doc.id) is None
    assert at.title[0].value == "📁 Baza dokumentów"
    assert any("Usunięto dokument" in s.value for s in at.success)


def test_missing_original_disables_download(services):
    doc = doc_by_name(services, "en_03_ai_healthcare.txt")
    services.files.delete(doc.id)
    at = open_doc(doc.id)
    assert "⬇️ Pobierz oryginał" not in {b.label for b in at.get("download_button")}
    assert next(b for b in at.button if b.label == "⬇️ Pobierz oryginał").disabled


def test_unknown_document_falls_back_with_warning(services):
    at = open_doc("nie-ma-takiego")
    assert any("nie istnieje" in w.value for w in at.warning)
    assert at.title[0].value.startswith("📄 ")


def test_empty_database(monkeypatch):
    monkeypatch.setattr(config, "LOAD_SAMPLES_IF_EMPTY", False)
    from edt.ui.state import get_services

    get_services.clear()
    at = open_doc()
    assert any("pusta" in i.value for i in at.info)
