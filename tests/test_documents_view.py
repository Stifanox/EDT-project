"""Testy etapu D4: widok „Baza dokumentów” (logika + przepływy w AppTest)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from edt import config
from edt.models import SourceType
from edt.ui.documents_view import (
    documents_frame,
    filter_documents,
    format_size,
    selected_documents,
)

from .conftest import make_doc

ROOT = Path(__file__).resolve().parent.parent
TABLE_KEY = "docs-table-0"


@pytest.fixture
def docs():
    return [
        make_doc("a", "Tekst polski o Krakowie i Wiśle.", "Raport_Krakow.txt"),
        replace(make_doc("b", "English text about the Vistula river.", "vistula.pdf"),
                source_type=SourceType.PDF, num_pages=3),
        make_doc("c", "Kolejny polski tekst o Toruniu.", "torun.txt"),
    ]


# --------------------------------------------------------------------------- #
# Logika (bez Streamlit)
# --------------------------------------------------------------------------- #
def test_filter_documents(docs):
    assert [d.id for d in filter_documents(docs)] == ["a", "b", "c"]
    assert [d.id for d in filter_documents(docs, "  krakow ")] == ["a"]       # bez wielkości liter
    assert [d.id for d in filter_documents(docs, source_types=["pdf"])] == ["b"]
    assert [d.id for d in filter_documents(docs, languages=["pl"])] == ["a", "c"]
    assert filter_documents(docs, "torun", ["pdf"]) == []
    assert [d.id for d in filter_documents(docs, source_types=[SourceType.TXT])] == ["a", "c"]


def test_documents_frame(docs):
    frame = documents_frame(docs, entity_count=lambda doc_id: {"a": 2}.get(doc_id, 0))
    assert list(frame["Nazwa"]) == ["Raport_Krakow.txt", "vistula.pdf", "torun.txt"]
    assert list(frame["Typ"]) == ["TXT", "PDF", "TXT"]
    assert list(frame["Język"]) == ["polski", "angielski", "polski"]
    assert frame["Strony"].isna().tolist() == [True, False, True]
    assert frame.loc[0, "Encje"] == 2 and frame.loc[0, "Słowa"] == docs[0].num_words
    assert documents_frame([]).empty


def test_selected_documents_ignores_out_of_range(docs):
    assert [d.id for d in selected_documents(docs, [2, 0, 7])] == ["c", "a"]


@pytest.mark.parametrize(("size", "text"), [(0, "0 B"), (937, "937 B"), (2048, "2.0 KB"),
                                            (5 * 1024**2, "5.0 MB")])
def test_format_size(size, text):
    assert format_size(size) == text


# --------------------------------------------------------------------------- #
# Przepływy GUI (AppTest)
# --------------------------------------------------------------------------- #
@pytest.fixture
def page(monkeypatch):
    monkeypatch.setattr(config, "LOAD_SAMPLES_IF_EMPTY", True)
    from edt.ui.state import get_services

    get_services.clear()  # świeże AppServices na bazie tymczasowej tego testu
    # start od app.py (jak w prawdziwej aplikacji), żeby st.switch_page znajdował strony
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.run()
    at.switch_page("pages/1_Baza_dokumentow.py").run()
    assert not at.exception
    return at


def _button(at, label):
    return next(b for b in at.button if b.label == label)


def _select(at, rows):
    at.session_state[TABLE_KEY] = {"selection": {"rows": rows, "columns": [], "cells": []}}
    at.run()


def test_table_and_filters(page):
    assert len(page.dataframe[0].value) == 12
    page.text_input(key="name-filter").input("kopernik").run()
    assert list(page.dataframe[0].value["Nazwa"]) == ["pl_07_mikolaj_kopernik.pdf"]
    page.text_input(key="name-filter").input("").run()
    page.multiselect(key="type-filter").select("pdf").run()
    page.multiselect(key="lang-filter").select("en").run()
    assert list(page.dataframe[0].value["Nazwa"]) == ["en_05_vistula_river.pdf"]
    assert any(c.value.startswith("Wyświetlono 1 z 12") for c in page.caption)


def test_buttons_depend_on_selection(page):
    assert _button(page, "📄 Otwórz").disabled and _button(page, "🗑️ Usuń (0)").disabled
    _select(page, [0, 1])
    assert _button(page, "📄 Otwórz").disabled            # otwieramy tylko jeden
    assert not _button(page, "🗑️ Usuń (2)").disabled
    _select(page, [3])
    assert not _button(page, "📄 Otwórz").disabled


def test_delete_with_confirmation(page):
    from edt.ui.state import get_services

    names = list(page.dataframe[0].value["Nazwa"][:2])
    _select(page, [0, 1])
    _button(page, "🗑️ Usuń (2)").click().run()
    assert any(names[0] in m.value for m in page.markdown)   # dialog z listą
    _button(page, "Usuń").click().run()

    assert not page.exception
    assert len(page.dataframe[0].value) == 10
    assert not set(names) & set(page.dataframe[0].value["Nazwa"])
    assert any("Usunięto 2" in s.value for s in page.success)
    services = get_services()
    assert services.repository.count() == 10 and len(services.files.doc_ids()) == 10


def test_delete_cancel_keeps_documents(page):
    _select(page, [0])
    _button(page, "🗑️ Usuń (1)").click().run()
    _button(page, "Anuluj").click().run()
    assert len(page.dataframe[0].value) == 12


def test_open_document_navigates(page):
    _select(page, [11])
    _button(page, "📄 Otwórz").click().run()
    assert not page.exception
    assert page.session_state["selected_doc_id"]


def test_rebuild_indexes_button(page):
    _button(page, "🔄 Przebuduj indeksy").click().run()
    assert any("Indeksy przebudowane" in s.value for s in page.success)


def test_ingest_report_is_rendered_readably(page):
    """Upload nie jest wspierany przez AppTest – raport podajemy przez session_state,
    a sam `ingest_many` testuje tests/test_pipeline.py."""
    from edt.ui.state import get_services

    services = get_services()
    report = services.ingest_many([
        ("nowy.txt", "Zupełnie nowy dokument o Gdańsku.".encode()),
        ("kopia.txt", (ROOT / "data" / "sample" / "pl_01_samochody_elektryczne.txt").read_bytes()),
        ("zly.docx", b"PK"),
    ])
    page.session_state["last_report"] = report
    page.run()
    assert any(w.value.startswith("Dodano: 1 · duplikaty: 1 · błędy: 1") for w in page.warning)
    assert any("kopia.txt" in i.value and "pl_01_samochody" in i.value for i in page.info)
    assert any("zly.docx" in e.value and "Nieobsługiwany format" in e.value for e in page.error)
    assert len(page.dataframe[0].value) == 13

    _button(page, "Ukryj raport").click().run()
    assert not page.warning and not page.error
