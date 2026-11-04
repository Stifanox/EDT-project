"""Logika i komponenty widoków dokumentów (właściciel: O1; D4, D5).

Funkcje `filter_documents`, `documents_frame`, `format_size` nie zależą od Streamlit,
więc da się je testować jednostkowo. Funkcje `render_*` rysują elementy GUI.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable

import pandas as pd

from edt.models import Document, SourceType

LANGUAGE_LABELS: dict[str, str] = {"pl": "polski", "en": "angielski", "unknown": "nieznany"}

COLUMNS = ["Nazwa", "Typ", "Język", "Strony", "Słowa", "Znaki", "Rozmiar [KB]", "Encje", "Dodano"]


def format_size(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB"):
        if value < 1024 or unit == "MB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"  # pragma: no cover - nieosiągalne


def language_label(code: str) -> str:
    return LANGUAGE_LABELS.get(code, code)


def filter_documents(
    docs: Iterable[Document],
    name_query: str = "",
    source_types: Collection[SourceType | str] | None = None,
    languages: Collection[str] | None = None,
) -> list[Document]:
    """Filtr listy dokumentów. Puste / None kryterium = bez ograniczenia.
    `name_query` – podciąg nazwy, bez rozróżniania wielkości liter."""
    q = name_query.strip().casefold()
    types = {SourceType(t) for t in source_types} if source_types else None
    langs = set(languages) if languages else None
    return [
        d for d in docs
        if (not q or q in d.name.casefold())
        and (types is None or d.source_type in types)
        and (langs is None or d.language in langs)
    ]


def documents_frame(
    docs: Iterable[Document],
    entity_count: Callable[[str], int] | None = None,
) -> pd.DataFrame:
    """Tabela dokumentów do `st.dataframe`. Wiersz i = docs[i] (kolejność zachowana)."""
    rows = [
        {
            "Nazwa": d.name,
            "Typ": d.source_type.value.upper(),
            "Język": language_label(d.language),
            "Strony": d.num_pages,
            "Słowa": d.num_words,
            "Znaki": d.num_chars,
            "Rozmiar [KB]": round(d.size_bytes / 1024, 1),  # liczba => poprawne sortowanie
            "Encje": entity_count(d.id) if entity_count else None,
            "Dodano": d.added_at.astimezone().replace(tzinfo=None),
        }
        for d in docs
    ]
    frame = pd.DataFrame(rows, columns=COLUMNS)
    return frame.astype({"Strony": "Int64", "Encje": "Int64"})


def selected_documents(docs: list[Document], row_positions: Iterable[int]) -> list[Document]:
    """Zaznaczone wiersze `st.dataframe` (pozycje w oryginalnej ramce) -> dokumenty."""
    return [docs[i] for i in row_positions if 0 <= i < len(docs)]


# --------------------------------------------------------------------------- #
# Streamlit
# --------------------------------------------------------------------------- #
def table_column_config() -> dict:
    import streamlit as st

    return {
        "Nazwa": st.column_config.TextColumn(width="large"),
        "Strony": st.column_config.NumberColumn(format="%d"),
        "Słowa": st.column_config.NumberColumn(format="%d"),
        "Znaki": st.column_config.NumberColumn(format="%d"),
        "Rozmiar [KB]": st.column_config.NumberColumn(format="%.1f"),
        "Encje": st.column_config.NumberColumn(format="%d", help="Liczba wystąpień encji"),
        "Dodano": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm"),
    }


def render_ingest_report(report) -> None:
    """Czytelne podsumowanie importu (`edt.services.IngestReport`)."""
    import streamlit as st

    if report.added and not report.errors:
        st.success(report.summary(), icon="✅")
    elif report.added:
        st.warning(report.summary(), icon="⚠️")
    else:
        st.error(report.summary(), icon="❌")
    for r in report.duplicates:
        st.info(f"**{r.filename}** – pominięto: ten sam plik jest już w bazie jako "
                f"„{r.duplicate_of.name}”.", icon="♻️")
    for r in report.errors:
        st.error(f"**{r.filename}** – {r.error}", icon="❌")
    for warning in report.warnings:
        st.warning(warning, icon="⚠️")
