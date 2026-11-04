"""Podstawowe przetwarzanie tekstu współdzielone przez moduły.

Wersja P0 jest celowo prosta. Etap S1 (O2) może ją rozbudować (lematyzacja,
lepsze stop-słowa), ale **sygnatury funkcji muszą zostać zachowane**,
bo korzystają z nich też O1 (wykrywanie języka) i O3 (statystyki terminów).
"""

from __future__ import annotations

import re
import unicodedata

from edt.config import SNIPPET_WIDTH

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

STOPWORDS_PL: frozenset[str] = frozenset(
    """
    a aby ale ani albo bardzo bez bo by być był była było były będzie będą co czy
    dla do gdy gdzie go i ich im innych jak jako jakie jego jej jest jeszcze jednak
    już ją które który która kiedy lub ma mają może można na nad nie nich nim niż
    o od oraz po pod ponieważ przed przez przy się są ta tak także te tego tej tem
    to tu tych tylko tym w we więc wszystko z za ze że żeby oraz jeden jedna było
    był jestem będą także tę tam tutaj u wraz około roku lat
    """.split()
)

STOPWORDS_EN: frozenset[str] = frozenset(
    """
    a about after all also an and any are as at be been before being but by can
    could did do does for from had has have he her his how if in into is it its
    more most no not of on or other our over she so some such than that the their
    them then there these they this those through to under up was we were what
    when where which while who will with would you your
    """.split()
)

STOPWORDS: frozenset[str] = STOPWORDS_PL | STOPWORDS_EN

_PL_DIACRITICS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")


def normalize_text(text: str) -> str:
    """Normalizacja Unicode (NFC), ujednolicenie białych znaków i końców linii.
    Zachowuje podział na akapity (pusta linia)."""
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(" ", " ").replace("﻿", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def tokenize(text: str, *, lowercase: bool = True, remove_stopwords: bool = False) -> list[str]:
    """Podział na tokeny słowne (litery/cyfry)."""
    tokens = _TOKEN_RE.findall(text.lower() if lowercase else text)
    if remove_stopwords:
        tokens = [t for t in tokens if t.lower() not in STOPWORDS]
    return tokens


def content_terms(text: str) -> list[str]:
    """Tokeny „treściowe”: lowercase, bez stop-słów, bez liczb i tokenów 1-znakowych.
    Używane m.in. do statystyk „najczęstsze terminy”."""
    return [t for t in tokenize(text, remove_stopwords=True) if len(t) > 1 and not t.isdigit()]


def detect_language(text: str) -> str:
    """Heurystyczne wykrywanie języka: 'pl' | 'en' | 'unknown'.
    (Etap D1 może podmienić na bibliotekę, zachowując sygnaturę.)"""
    sample = text[:5000]
    tokens = tokenize(sample)
    if not tokens:
        return "unknown"
    pl = sum(t in STOPWORDS_PL for t in tokens) + 2 * sum(c in _PL_DIACRITICS for c in sample) / 10
    en = sum(t in STOPWORDS_EN for t in tokens)
    if pl == en == 0:
        return "unknown"
    return "pl" if pl > en else "en"


def find_term_spans(text: str, terms: list[str]) -> list[tuple[int, int]]:
    """Pozycje (start, end) wystąpień termów/fraz w tekście (case-insensitive,
    dopasowanie od początku słowa). Wynik posortowany, bez nakładania się."""
    spans: list[tuple[int, int]] = []
    for term in {t.strip() for t in terms if t and t.strip()}:
        pattern = re.compile(r"(?<!\w)" + re.escape(term), re.IGNORECASE)
        spans.extend(m.span() for m in pattern.finditer(text))
    spans.sort()
    merged: list[tuple[int, int]] = []
    for s, e in spans:
        if merged and s < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def make_snippet_at(
    text: str, start: int, end: int, width: int = SNIPPET_WIDTH
) -> tuple[str, int]:
    """Fragment tekstu o długości ~`width` wokół zakresu [start, end).
    Zwraca (snippet, offset) – offset to pozycja początku snippetu w `text`,
    potrzebna do przeliczenia podświetleń."""
    if not text:
        return "", 0
    pad = max(0, (width - (end - start)) // 2)
    s = max(0, start - pad)
    e = min(len(text), max(end + pad, s + width))
    # przesuń na granice słów
    if s > 0:
        sp = text.rfind(" ", 0, s)
        s = sp + 1 if sp != -1 and s - sp < 30 else s
    if e < len(text):
        sp = text.find(" ", e)
        e = sp if sp != -1 and sp - e < 30 else e
    snippet = text[s:e].replace("\n", " ")
    prefix = "…" if s > 0 else ""
    suffix = "…" if e < len(text) else ""
    return prefix + snippet + suffix, s - len(prefix)


def make_snippet(
    text: str, terms: list[str], width: int = SNIPPET_WIDTH
) -> tuple[str, tuple[tuple[int, int], ...]]:
    """Fragment wokół pierwszego wystąpienia któregokolwiek termu + podświetlenia
    (względem snippetu). Gdy brak dopasowań – początek tekstu bez podświetleń."""
    spans = find_term_spans(text, terms)
    if not spans:
        snippet, _ = make_snippet_at(text, 0, 0, width)
        return snippet, ()
    first_s, first_e = spans[0]
    snippet, offset = make_snippet_at(text, first_s, first_e, width)
    limit = len(snippet)
    highlights = tuple(
        (s - offset, e - offset) for s, e in spans if s - offset >= 0 and e - offset <= limit
    )
    return snippet, highlights
