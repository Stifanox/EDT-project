"""Widok: Statystyki korpusu (właściciel: O3, etap N6). Wersja szkieletowa z P0."""

import streamlit as st

from edt.ui.state import get_services

st.set_page_config(page_title="Statystyki", page_icon="📊", layout="wide")
services = get_services()

st.title("📊 Statystyki")
st.info("Szkielet z P0 – wykresy i statystyki w etapie **N6**.", icon="🚧")

docs = services.repository.list()
c1, c2, c3 = st.columns(3)
c1.metric("Dokumenty", len(docs))
c2.metric("Łącznie słów", sum(d.num_words for d in docs))
c3.metric("Śr. długość (słowa)", round(sum(d.num_words for d in docs) / len(docs)) if docs else 0)
