"""Punkt wejścia: `streamlit run app.py`."""

import streamlit as st

from edt.ui import nav
from edt.ui.state import get_services

st.set_page_config(page_title="EDT – eksploracja dokumentów", page_icon="📚", layout="wide")

services = get_services()

st.title("📚 EDT – eksploracja dokumentów tekstowych")
st.caption("Baza dokumentów · wyszukiwanie: słowa kluczowe / TF-IDF / semantyczne · NER")

c1, c2, c3 = st.columns(3)
c1.metric("Dokumenty", services.repository.count())
c2.metric("Metody wyszukiwania", len(services.engines))
c3.metric("Unikalne encje", len(services.entities.entity_stats()))

st.page_link(nav.PAGE_DOCUMENTS, label="Baza dokumentów", icon="📁")
st.page_link(nav.PAGE_SEARCH, label="Wyszukiwarka", icon="🔎")
st.page_link(nav.PAGE_ENTITIES, label="Encje NER", icon="🏷️")
st.page_link(nav.PAGE_STATS, label="Statystyki", icon="📊")
