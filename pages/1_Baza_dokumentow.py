"""Widok: Baza dokumentów (właściciel: O1, etap D4). Wersja szkieletowa z P0."""

import pandas as pd
import streamlit as st

from edt.ui import nav
from edt.ui.state import get_services

st.set_page_config(page_title="Baza dokumentów", page_icon="📁", layout="wide")
services = get_services()

st.title("📁 Baza dokumentów")
st.info("Szkielet z P0 – pełny widok w etapie **D4**.", icon="🚧")

uploaded = st.file_uploader("Dodaj dokumenty (TXT, PDF)", type=["txt", "pdf"],
                            accept_multiple_files=True)
if uploaded and st.button("Wczytaj"):
    bar = st.progress(0.0, text="Wczytywanie…")
    report = services.ingest_many(
        ((f.name, f.getvalue()) for f in uploaded),
        on_progress=lambda i, n, name: bar.progress(i / n, text=f"{i}/{n}: {name}"),
    )
    bar.empty()
    (st.success if not report.errors else st.warning)(report.summary())
    for r in [*report.duplicates, *report.errors]:
        st.caption(f"⚠️ {r.filename}: {r.error}")
    for w in report.warnings:
        st.caption(f"⚠️ {w}")

docs = services.repository.list()
st.dataframe(
    pd.DataFrame([
        {"Nazwa": d.name, "Typ": d.source_type.value, "Język": d.language,
         "Słowa": d.num_words, "Znaki": d.num_chars,
         "Dodano": d.added_at.strftime("%Y-%m-%d %H:%M")}
        for d in docs
    ]),
    width="stretch", hide_index=True,
)

for d in docs:
    col1, col2, col3 = st.columns([6, 1, 1])
    col1.write(d.name)
    if col2.button("Otwórz", key=f"open-{d.id}"):
        nav.open_document(d.id)
    if col3.button("Usuń", key=f"del-{d.id}"):
        services.delete_document(d.id)
        st.rerun()
