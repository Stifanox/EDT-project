"""Stan aplikacji Streamlit (P0). Jedna instancja `AppServices` na proces serwera."""

from __future__ import annotations

import streamlit as st

from edt.services import AppServices, build_services


@st.cache_resource(show_spinner="Ładowanie bazy dokumentów i indeksów…")
def get_services() -> AppServices:
    return build_services()
