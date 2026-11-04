"""Widok: Encje NER (właściciel: O3, etapy N4–N5). Wersja szkieletowa z P0."""

import pandas as pd
import streamlit as st

from edt.models import EntityType
from edt.ui.state import get_services

st.set_page_config(page_title="Encje NER", page_icon="🏷️", layout="wide")
services = get_services()

st.title("🏷️ Encje NER")
st.info("Szkielet z P0 (zaślepka regex) – pełny widok w etapach **N4/N5**.", icon="🚧")

c1, c2 = st.columns([3, 1])
query = c1.text_input("Szukaj encji")
label_opt = c2.selectbox("Typ", ["(wszystkie)", *[t.value for t in EntityType]])
label = None if label_opt == "(wszystkie)" else EntityType(label_opt)

stats = services.entities.entity_stats(query=query, label=label)
st.dataframe(
    pd.DataFrame([
        {"Encja": s.text, "Typ": s.label.label_pl, "Wystąpienia": s.mention_count,
         "Dokumenty": s.doc_count}
        for s in stats
    ]),
    width="stretch", hide_index=True,
)
