"""Czyszczenie tekstu wyciągniętego z PDF (etap D1).

`pypdf` zwraca tekst strona po stronie, linia po linii, tak jak był złożony na stronie.
Tutaj odtwarzamy tekst ciągły:
  1. usunięcie powtarzających się nagłówków/stopek i numerów stron,
  2. sklejenie słów przeniesionych z dywizem na końcu linii (także między stronami),
  3. sklejenie linii w akapity: puste linie z trybu `layout` (odstęp pionowy),
     a pomocniczo heurystyka „krótka ostatnia linia + koniec zdania”.
"""

from __future__ import annotations

import math
import re
import statistics
from collections import Counter

from edt.textproc import normalize_text

_LIGATURES = str.maketrans(
    {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}
)
_PAGE_NUMBER_RE = re.compile(
    r"^\s*(?:(?:strona|str\.|page|p\.)\s*)?[-–]?\s*\d{1,4}\s*[-–]?"
    r"(?:\s*(?:/|z|of)\s*\d{1,4})?\s*$",
    re.IGNORECASE,
)
_SENTENCE_END = tuple(".!?:;…\"”»)")
_EDGE_LINES = 2  # ile linii z góry/dołu strony traktujemy jako potencjalny nagłówek/stopkę


def _edge_key(line: str) -> str:
    """Klucz porównania nagłówków/stopek: cyfry zamienione na '#', np. 'Strona 3' -> 'strona #'."""
    return re.sub(r"\d+", "#", line.strip().lower())


def split_page_lines(page_text: str) -> list[str]:
    """Linie strony bez białych znaków na brzegach. Puste linie ZOSTAJĄ – w trybie `layout`
    pypdf oznaczają odstęp pionowy, czyli zwykle granicę akapitu."""
    text = page_text.translate(_LIGATURES).replace("\u00ad", "")
    return [line.strip() for line in text.splitlines()]


def _trim_blank(lines: list[str]) -> list[str]:
    start, end = 0, len(lines)
    while start < end and not lines[start]:
        start += 1
    while end > start and not lines[end - 1]:
        end -= 1
    return lines[start:end]


def remove_headers_footers(pages: list[list[str]]) -> list[list[str]]:
    """Usuwa numery stron oraz linie powtarzające się na brzegach większości stron."""
    pages = [_trim_blank(p) for p in pages]
    n = len(pages)
    repeated: set[str] = set()
    if n >= 2:
        counts: Counter[str] = Counter()
        for lines in pages:
            content = [x for x in lines if x]
            counts.update({_edge_key(x) for x in content[:_EDGE_LINES] + content[-_EDGE_LINES:]})
        threshold = max(2, math.ceil(0.6 * n))
        repeated = {k for k, c in counts.items() if c >= threshold}

    def is_edge_noise(line: str) -> bool:
        return _edge_key(line) in repeated or bool(_PAGE_NUMBER_RE.match(line))

    cleaned = []
    for lines in pages:
        for _ in range(_EDGE_LINES):
            if lines and is_edge_noise(lines[0]):
                lines = _trim_blank(lines[1:])
        for _ in range(_EDGE_LINES):
            if lines and is_edge_noise(lines[-1]):
                lines = _trim_blank(lines[:-1])
        cleaned.append(lines)
    return cleaned


def looks_multicolumn(page_text: str) -> bool:
    """Czy tekst z trybu `layout` wygląda na wielokolumnowy (duże przerwy w środku linii)."""
    lines = [x.strip() for x in page_text.splitlines() if x.strip()]
    if len(lines) < 5:
        return False
    gapped = sum(bool(re.search(r"\S {6,}\S", x)) for x in lines)
    return gapped / len(lines) > 0.3


def _starts_new_block(first_char: str) -> bool:
    return first_char.isupper() or first_char.isdigit() or first_char in "•-–—*(\"„«"


def join_lines(lines: list[str]) -> str:
    """Skleja linie w akapity i usuwa przeniesienia wyrazów.

    Pusta linia zawsze kończy akapit. Poza tym nowy akapit zaczyna się, gdy poprzednia
    linia jest wyraźnie krótsza od typowej
    i kończy zdanie (albo jest bardzo krótka, np. tytuł), a następna linia zaczyna się
    wielką literą, cyfrą lub punktorem (zapas dla PDF bez odstępów między akapitami).
    """
    if not lines:
        return ""
    lengths = [len(x.strip()) for x in lines if x.strip()]
    typical = statistics.median(lengths) if lengths else 0

    paragraphs: list[str] = []
    current = ""
    prev = ""
    for raw in lines:
        line = raw.strip()
        if not line:
            if current:
                paragraphs.append(current)
            current, prev = "", ""
            continue
        if not current:
            current = line
        elif current.endswith("-") and len(current) > 1 and current[-2].isalpha():
            # przeniesienie: "elektro-" + "mobilność" -> "elektromobilność";
            # "Skłodowska-" + "Curie" -> "Skłodowska-Curie" (wielka litera => łącznik zostaje)
            current = (current[:-1] if line[0].islower() else current) + line
        elif _starts_new_block(line[0]) and (
            (prev.endswith(_SENTENCE_END) and len(prev) < 0.8 * typical)
            or len(prev) < 0.6 * typical
        ):
            paragraphs.append(current)
            current = line
        else:
            current += " " + line
        prev = line
    if current:
        paragraphs.append(current)
    return "\n\n".join(paragraphs)


def clean_pdf_pages(page_texts: list[str]) -> str:
    """Pełne czyszczenie: teksty stron -> tekst dokumentu (akapity oddzielone pustą linią)."""
    pages = remove_headers_footers([split_page_lines(p) for p in page_texts])
    # strony łączymy bez pustej linii – akapit może przechodzić na kolejną stronę
    lines = [line for page in pages for line in page]
    return normalize_text(join_lines(lines))
