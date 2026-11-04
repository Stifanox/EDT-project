"""Logika i komponenty widoków dokumentów (właściciel: O1; D4, D5).

Funkcje logiki (filtry, tabele, metadane, podział na sekcje) nie zależą od Streamlit,
więc da się je testować jednostkowo. Funkcje `render_*` rysują elementy GUI.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import replace

import pandas as pd

from edt.models import Document, EntityMention, EntityType, SourceType

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
# Widok szczegółów dokumentu (D5)
# --------------------------------------------------------------------------- #
_PDF_META_LABELS = {
    "title": "Tytuł (PDF)", "author": "Autor (PDF)", "subject": "Temat (PDF)",
    "creator": "Program tworzący", "producer": "Producent PDF", "created": "Utworzono (PDF)",
    "pages_without_text": "Strony bez tekstu", "encoding": "Kodowanie",
}


def document_metadata_rows(doc: Document) -> list[tuple[str, str]]:
    """Metadane dokumentu jako pary (etykieta, wartość) do wyświetlenia."""
    rows = [
        ("Nazwa pliku", doc.name),
        ("Typ", doc.source_type.value.upper()),
        ("Język", language_label(doc.language)),
        ("Rozmiar pliku", format_size(doc.size_bytes)),
        ("Liczba stron", str(doc.num_pages) if doc.num_pages is not None else "–"),
        ("Liczba słów", str(doc.num_words)),
        ("Liczba znaków", str(doc.num_chars)),
        ("Dodano", doc.added_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")),
        ("Identyfikator", doc.id),
        ("SHA-256", doc.content_hash or "–"),
    ]
    for key, value in doc.metadata.items():
        rows.append((_PDF_META_LABELS.get(key, key), str(value)))
    return rows


def document_entity_table(mentions: Iterable[EntityMention]) -> pd.DataFrame:
    """Encje jednego dokumentu zgrupowane po (key, typ). Kolumny `key` i `label`
    służą do nawigacji (ukryj je w GUI). Sortowanie: liczba wystąpień malejąco."""
    forms: dict[tuple[str, str], Counter[str]] = {}
    for m in mentions:
        forms.setdefault((m.key, m.label.value), Counter())[m.text] += 1
    rows = [
        {"Encja": c.most_common(1)[0][0], "Typ": m_label, "Wystąpienia": sum(c.values()),
         "key": key, "label": m_label}
        for (key, m_label), c in forms.items()
    ]
    frame = pd.DataFrame(rows, columns=["Encja", "Typ", "Wystąpienia", "key", "label"])
    if not frame.empty:
        frame["Typ"] = [EntityType(v).label_pl for v in frame["label"]]
        frame = frame.sort_values(["Wystąpienia", "Encja"], ascending=[False, True])
    return frame.reset_index(drop=True)


def split_into_sections(text: str, max_chars: int = 20_000) -> list[tuple[int, int]]:
    """Dzieli długi tekst na sekcje (start, end) o długości <= max_chars, tnąc na granicy
    akapitu, a w ostateczności linii lub spacji. Sekcje pokrywają cały tekst bez przerw."""
    if len(text) <= max_chars:
        return [(0, len(text))]
    sections: list[tuple[int, int]] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            lower = start + max_chars // 2  # nie tniemy zbyt krótko
            for sep in ("\n\n", "\n", " "):
                cut = text.rfind(sep, lower, end)
                if cut != -1:
                    end = cut + len(sep)
                    break
        sections.append((start, end))
        start = end
    return sections


def section_of(sections: Sequence[tuple[int, int]], offset: int) -> int:
    """Indeks sekcji zawierającej dany offset (0, gdy poza zakresem)."""
    return next((i for i, (s, e) in enumerate(sections) if s <= offset < e), 0)


def mentions_in_section(
    mentions: Iterable[EntityMention], start: int, end: int
) -> list[EntityMention]:
    """Encje leżące w całości w [start, end), z offsetami przesuniętymi do początku sekcji."""
    return [replace(m, start=m.start - start, end=m.end - start)
            for m in mentions if start <= m.start and m.end <= end]


def spans_in_section(
    spans: Iterable[tuple[int, int]], start: int, end: int
) -> list[tuple[int, int]]:
    return [(s - start, e - start) for s, e in spans if start <= s and e <= end]


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
