"""Widok: Szczegóły dokumentu (właściciel: O1, etap D5). Wersja szkieletowa z P0."""

import streamlit as st

from edt.textproc import find_term_spans
from edt.ui import nav
from edt.ui.components import QUERY_HIGHLIGHT_STYLE
from edt.ui.entities import entities_html, entity_legend_html
from edt.ui.state import get_services

st.set_page_config(page_title="Dokument", page_icon="📄", layout="wide")
services = get_services()

docs = services.repository.list()
if not docs:
    st.warning("Baza dokumentów jest pusta.")
    st.stop()

ids = [d.id for d in docs]
current = nav.selected_document_id()
index = ids.index(current) if current in ids else 0
doc = st.selectbox("Dokument", docs, index=index, format_func=lambda d: d.name)
nav.set_selected_document(doc.id)

st.title(f"📄 {doc.name}")
st.info("Szkielet z P0 – pełny widok (metadane, lista encji, filtry) w etapie **D5**.", icon="🚧")
st.caption(f"Typ: {doc.source_type.value} · język: {doc.language} · słowa: {doc.num_words} · "
           f"znaki: {doc.num_chars}")

mentions = services.entities.mentions(doc.id)
query_spans = [(s, e, QUERY_HIGHLIGHT_STYLE)
               for s, e in find_term_spans(doc.text, nav.selected_highlight_terms())]
st.markdown(entity_legend_html({m.label for m in mentions}), unsafe_allow_html=True)
st.markdown(entities_html(doc.text, mentions, query_spans), unsafe_allow_html=True)
