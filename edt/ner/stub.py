"""Zaślepka ekstraktora NER (P0) – reguły regex, bez modeli ML.

Wykrywa: lata/daty (DATE) oraz ciągi >= 2 słów z wielkiej litery (MISC).
Daje GUI i innym modułom „jakieś” encje, zanim powstanie etap N1 (spaCy).
"""

from __future__ import annotations

import re

from edt.models import Document, EntityMention, EntityType

_MONTHS = (
    "stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|września|października|"
    "listopada|grudnia|January|February|March|April|May|June|July|August|September|"
    "October|November|December"
)
_DATE_RE = re.compile(rf"\b(?:\d{{1,2}}\s+(?:{_MONTHS})\s+)?(?:1[5-9]|20)\d{{2}}\b")
_CAP = r"[A-ZĄĆĘŁŃÓŚŹŻ][\wąćęłńóśźż\-]+"
_CAPSEQ_RE = re.compile(rf"\b{_CAP}(?:\s+{_CAP})+")


class RegexEntityExtractor:
    def extract(self, doc: Document) -> list[EntityMention]:
        mentions = [
            EntityMention(doc.id, m.group(), EntityType.DATE, m.start(), m.end(), raw_label="regex")
            for m in _DATE_RE.finditer(doc.text)
        ]
        mentions += [
            EntityMention(doc.id, m.group(), EntityType.MISC, m.start(), m.end(), raw_label="regex")
            for m in _CAPSEQ_RE.finditer(doc.text)
        ]
        return sorted(mentions, key=lambda m: m.start)
