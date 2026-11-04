"""Ogólne komponenty UI (P0, współdzielone – zmiany wstecznie zgodne).

Komponenty specyficzne dla modułu trzymaj w osobnych plikach:
  * edt/ui/entities.py – encje (O3)
  * edt/ui/search_view.py – wyniki wyszukiwania (O2, tworzy S6)
  * edt/ui/documents_view.py – dokumenty (O1, tworzy D4/D5)
"""

from __future__ import annotations

import html
from collections.abc import Iterable


def highlight_html(
    text: str,
    spans: Iterable[tuple[int, int, str]],
) -> str:
    """Zamienia tekst na HTML z podświetlonymi fragmentami.

    `spans` – (start, end, style_css). Nakładające się zakresy są pomijane
    (wygrywa pierwszy wg pozycji). Tekst jest escapowany; nowe linie -> <br>.
    """
    out: list[str] = []
    pos = 0
    for start, end, style in sorted(spans, key=lambda s: (s[0], -s[1])):
        if start < pos or end <= start:
            continue
        out.append(html.escape(text[pos:start]))
        out.append(f'<mark style="{style}">{html.escape(text[start:end])}</mark>')
        pos = end
    out.append(html.escape(text[pos:]))
    return "".join(out).replace("\n", "<br>")


QUERY_HIGHLIGHT_STYLE = "background:#ffe066;padding:0 2px;border-radius:3px"


def snippet_html(snippet: str, highlights: Iterable[tuple[int, int]]) -> str:
    """Snippet wyniku wyszukiwania z podświetlonymi dopasowaniami."""
    return highlight_html(snippet, ((s, e, QUERY_HIGHLIGHT_STYLE) for s, e in highlights))
