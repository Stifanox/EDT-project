"""Stan aplikacji Streamlit (P0). Jedna instancja `AppServices` na proces serwera."""

from __future__ import annotations

import streamlit as st

from edt.services import AppServices, build_services


@st.cache_resource(show_spinner="Ładowanie bazy dokumentów i indeksów…")
def _cached_services() -> AppServices:
    return build_services()


def get_services() -> AppServices:
    """Wspólne `AppServices` + dogonienie zmian w bazie zrobionych przez inny proces
    (np. import z CLI, D6). Gdy nic się nie zmieniło, koszt to jedno zapytanie o listę id."""
    services = _cached_services()
    services.sync_with_repository()
    return services


get_services.clear = _cached_services.clear  # type: ignore[attr-defined]  # dla testów
