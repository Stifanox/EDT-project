"""Nawigacja między widokami (P0, kontrakt).

Otwieranie dokumentu z dowolnego widoku: `open_document(doc_id)`.
Widok dokumentu odczytuje wybór przez `selected_document_id()`.
"""

from __future__ import annotations

import streamlit as st

PAGE_HOME = "app.py"
PAGE_DOCUMENTS = "pages/1_Baza_dokumentow.py"
PAGE_SEARCH = "pages/2_Wyszukiwarka.py"
PAGE_ENTITIES = "pages/3_Encje_NER.py"
PAGE_STATS = "pages/4_Statystyki.py"
PAGE_DOCUMENT = "pages/5_Dokument.py"

_DOC_KEY = "selected_doc_id"
_HIGHLIGHT_KEY = "highlight_terms"


def open_document(doc_id: str, highlight_terms: list[str] | None = None) -> None:
    """Przejdź do widoku szczegółów dokumentu (opcjonalnie z podświetleniem termów zapytania)."""
    st.session_state[_DOC_KEY] = doc_id
    st.session_state[_HIGHLIGHT_KEY] = highlight_terms or []
    st.switch_page(PAGE_DOCUMENT)


def selected_document_id() -> str | None:
    return st.session_state.get(_DOC_KEY) or st.query_params.get("doc")


def selected_highlight_terms() -> list[str]:
    return list(st.session_state.get(_HIGHLIGHT_KEY, []))


def set_selected_document(doc_id: str | None) -> None:
    st.session_state[_DOC_KEY] = doc_id
