"""Widok: Wyszukiwarka (właściciel: O2, etapy S5–S6). Wersja szkieletowa z P0."""

import streamlit as st

from edt.ui import nav
from edt.ui.components import snippet_html
from edt.ui.state import get_services

st.set_page_config(page_title="Wyszukiwarka", page_icon="🔎", layout="wide")
services = get_services()

st.title("🔎 Wyszukiwarka")
st.info("Szkielet z P0 – porównanie rankingów i filtr encji w etapach **S5/S6**.", icon="🚧")

query = st.text_input("Zapytanie", placeholder="np. samochody elektryczne")
if query:
    results = services.search_all(query)
    cols = st.columns(len(results))
    for col, (name, items) in zip(cols, results.items(), strict=False):
        with col:
            st.subheader(services.engines[name].label)
            if not items:
                st.caption("Brak wyników")
            for r in items:
                st.markdown(f"**{r.rank}. {r.doc_name}** · `{r.score:.3f}`")
                st.markdown(snippet_html(r.snippet, r.snippet_highlights), unsafe_allow_html=True)
                if st.button("Otwórz", key=f"{name}-{r.doc_id}"):
                    nav.open_document(r.doc_id, highlight_terms=query.split())
