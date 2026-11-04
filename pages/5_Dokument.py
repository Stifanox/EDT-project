"""Widok: Szczegóły dokumentu (właściciel: O1, etap D5).

Metadane, treść z wyróżnionymi encjami i frazami zapytania, lista encji dokumentu,
pobieranie oryginału i usuwanie. Wejście: `nav.open_document(doc_id, highlight_terms)`.
"""

import streamlit as st

from edt.exporting import entities_export
from edt.models import EntityType, SourceType
from edt.textproc import find_term_spans
from edt.ui import nav
from edt.ui.components import QUERY_HIGHLIGHT_STYLE
from edt.ui.documents_view import (
    document_entity_table,
    document_metadata_rows,
    format_size,
    language_label,
    mentions_in_section,
    section_of,
    spans_in_section,
    split_into_sections,
)
from edt.ui.entities import entities_html, entity_legend_html
from edt.ui.state import get_services

SECTION_CHARS = 20_000  # długie dokumenty pokazujemy sekcjami (płynność przeglądarki)

st.set_page_config(page_title="Dokument", page_icon="📄", layout="wide")
services = get_services()
state = st.session_state

docs = services.repository.list()
if not docs:
    st.title("📄 Dokument")
    st.info("Baza dokumentów jest pusta.", icon="📭")
    st.page_link(nav.PAGE_DOCUMENTS, label="Przejdź do bazy dokumentów", icon="📁")
    st.stop()

# --------------------------------------------------------------------------- #
# Wybór dokumentu
# --------------------------------------------------------------------------- #
ids = [d.id for d in docs]
current = nav.selected_document_id()
if current and current not in ids:  # komunikat musi przetrwać st.rerun() poniżej
    state.doc_missing_msg = "Wybrany dokument nie istnieje już w bazie – pokazuję pierwszy z listy."
if msg := (state.pop("doc_missing_msg", None) if current in ids else state.get("doc_missing_msg")):
    st.warning(msg, icon="⚠️")
doc = st.selectbox(
    "Dokument", docs, index=ids.index(current) if current in ids else 0,
    format_func=lambda d: d.name, key=f"doc-select-{current}",
)
if doc.id != current:  # zmiana w selectboxie = nowy dokument, bez podświetleń zapytania
    nav.set_selected_document(doc.id)
    state["highlight_terms"] = []
    st.rerun()

st.title(f"📄 {doc.name}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Typ", doc.source_type.value.upper())
c2.metric("Język", language_label(doc.language))
c3.metric("Słowa", f"{doc.num_words:,}".replace(",", " "))
c4.metric("Strony" if doc.num_pages else "Rozmiar",
          doc.num_pages if doc.num_pages else format_size(doc.size_bytes))

mentions = services.entities.mentions(doc.id)
tab_text, tab_entities, tab_meta = st.tabs(
    ["📖 Treść", f"🏷️ Encje ({len(mentions)})", "ℹ️ Metadane i plik"]
)

# --------------------------------------------------------------------------- #
# Treść z wyróżnieniami
# --------------------------------------------------------------------------- #
with tab_text:
    present = sorted({m.label for m in mentions}, key=list(EntityType).index)
    o1, o2 = st.columns([3, 2])
    shown_labels = o1.multiselect(
        "Wyróżniaj typy encji", present, default=present,
        format_func=lambda t: t.label_pl, key=f"labels-{doc.id}",
    )
    terms_text = o2.text_input(
        "Podświetl frazy (oddziel przecinkami lub spacjami)",
        value=" ".join(nav.selected_highlight_terms()), key=f"terms-{doc.id}",
    )
    terms = [t for t in terms_text.replace(",", " ").split() if t]
    term_spans = find_term_spans(doc.text, terms)
    visible = [m for m in mentions if m.label in set(shown_labels)]

    sections = split_into_sections(doc.text, SECTION_CHARS)
    idx = 0
    if len(sections) > 1:
        first_hit = section_of(sections, term_spans[0][0]) if term_spans else 0
        idx = st.select_slider(
            f"Sekcja dokumentu (po ~{SECTION_CHARS // 1000} tys. znaków)",
            options=range(len(sections)), value=first_hit,
            format_func=lambda i: f"{i + 1}/{len(sections)}", key=f"section-{doc.id}-{terms_text}",
        )
    start, end = sections[idx]

    info = []
    if shown_labels:
        info.append(entity_legend_html(shown_labels))
    if terms:
        info.append(f"🔎 dopasowań fraz: <b>{len(term_spans)}</b>")
    if info:
        st.markdown(" &nbsp;·&nbsp; ".join(info), unsafe_allow_html=True)

    extra = [(s, e, QUERY_HIGHLIGHT_STYLE) for s, e in spans_in_section(term_spans, start, end)]
    with st.container(height=600, border=True):
        st.markdown(
            entities_html(doc.text[start:end], mentions_in_section(visible, start, end), extra),
            unsafe_allow_html=True,
        )

# --------------------------------------------------------------------------- #
# Encje dokumentu
# --------------------------------------------------------------------------- #
with tab_entities:
    table = document_entity_table(mentions)
    if table.empty:
        st.info("Nie wykryto encji w tym dokumencie.")
    else:
        st.caption("Zaznacz encję, aby zobaczyć ją w widoku „Encje NER” "
                   "(wszystkie dokumenty, w których występuje).")
        event = st.dataframe(
            table, hide_index=True, width="stretch", on_select="rerun",
            selection_mode="single-row", column_order=["Encja", "Typ", "Wystąpienia"],
            key=f"entities-{doc.id}",
        )
        rows = event.selection.rows if event else []
        x1, x2, x3 = st.columns([2, 1, 1])
        if x1.button("🏷️ Pokaż w widoku Encje NER", disabled=not rows):
            row = table.iloc[rows[0]]
            nav.open_entity(row["key"], row["label"])
        stem = doc.name.rsplit(".", 1)[0]
        for col, fmt in ((x2, "csv"), (x3, "json")):
            col.download_button(
                f"⬇️ Encje ({fmt.upper()})",
                data=lambda fmt=fmt: entities_export([doc], services.entities, fmt),
                file_name=f"{stem}_encje.{fmt}",
                mime="text/csv" if fmt == "csv" else "application/json", width="stretch",
            )

# --------------------------------------------------------------------------- #
# Metadane, pobieranie, usuwanie
# --------------------------------------------------------------------------- #
with tab_meta:
    st.table({label: value for label, value in document_metadata_rows(doc)})

    d1, d2, d3 = st.columns(3)
    original = services.original_path(doc.id)
    if original is not None:
        d1.download_button(
            "⬇️ Pobierz oryginał", data=original.read_bytes(), file_name=doc.name,
            mime="application/pdf" if doc.source_type is SourceType.PDF else "text/plain",
            width="stretch",
        )
    else:
        d1.button("⬇️ Pobierz oryginał", disabled=True, width="stretch",
                  help="Oryginał pliku nie jest dostępny")
    d2.download_button(
        "⬇️ Pobierz wyodrębniony tekst", data=doc.text.encode("utf-8"),
        file_name=f"{doc.name.rsplit('.', 1)[0]}.txt", mime="text/plain", width="stretch",
    )
    if d3.button("🗑️ Usuń dokument", width="stretch"):
        state.pending_delete_doc = doc.id


def _cancel_delete() -> None:
    state.pop("pending_delete_doc", None)


@st.dialog("Usunąć dokument?", on_dismiss=_cancel_delete)
def confirm_delete(doc_id: str) -> None:
    st.write(f"Dokument **{doc.name}** zostanie usunięty razem z indeksami, encjami "
             "i oryginałem pliku. Tej operacji nie można cofnąć.")
    b1, b2 = st.columns(2)
    if b1.button("Usuń", type="primary", width="stretch"):
        services.delete_document(doc_id)
        _cancel_delete()
        nav.set_selected_document(None)
        state.deleted_msg = f"Usunięto dokument „{doc.name}”."
        st.switch_page(nav.PAGE_DOCUMENTS)
    if b2.button("Anuluj", width="stretch"):
        _cancel_delete()
        st.rerun()


if state.get("pending_delete_doc") == doc.id:
    confirm_delete(doc.id)
