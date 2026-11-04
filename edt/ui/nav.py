"""Nawigacja między widokami (P0, kontrakt).

Otwieranie dokumentu z dowolnego widoku: `open_document(doc_id)`.
Widok dokumentu odczytuje wybór przez `selected_document_id()`.

Otwieranie encji w widoku „Encje NER” (D5 -> N4): `open_entity(key, label)`.
Widok encji odczytuje wybór przez `selected_entity()` -> (key, label) | None.
"""

from __future__ import annotations

import streamlit as st

from edt.models import EntityType

PAGE_HOME = "app.py"
PAGE_DOCUMENTS = "pages/1_Baza_dokumentow.py"
PAGE_SEARCH = "pages/2_Wyszukiwarka.py"
PAGE_ENTITIES = "pages/3_Encje_NER.py"
PAGE_STATS = "pages/4_Statystyki.py"
PAGE_DOCUMENT = "pages/5_Dokument.py"

_DOC_KEY = "selected_doc_id"
_HIGHLIGHT_KEY = "highlight_terms"
_ENTITY_KEY = "selected_entity"   # {"key": str, "label": str} – uzgodnione z O3 (N4)


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


def open_entity(key: str, label: EntityType | str) -> None:
    """Przejdź do widoku „Encje NER” z wybraną encją (`EntityMention.key` + typ)."""
    st.session_state[_ENTITY_KEY] = {"key": key, "label": str(label)}
    st.switch_page(PAGE_ENTITIES)


def selected_entity() -> tuple[str, EntityType] | None:
    value = st.session_state.get(_ENTITY_KEY)
    if not value:
        return None
    return value["key"], EntityType(value["label"])


def clear_selected_entity() -> None:
    st.session_state.pop(_ENTITY_KEY, None)
