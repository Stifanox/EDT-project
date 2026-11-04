"""Eksport dokumentów i encji do CSV / JSON (etap D6, właściciel: O1).

CSV: UTF-8 z BOM (Excel poprawnie pokaże polskie znaki), separator przecinek.
Funkcje zwracają `bytes`, więc nadają się wprost do `st.download_button` i zapisu na dysk.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Iterable
from typing import Any

from edt.interfaces import EntityIndex
from edt.models import Document, EntityMention, EntityStat

CONTEXT_CHARS = 60

DOCUMENT_FIELDS = ["id", "name", "source_type", "language", "num_pages", "num_words",
                   "num_chars", "size_bytes", "entity_mentions", "added_at", "content_hash",
                   "metadata"]
MENTION_FIELDS = ["doc_id", "doc_name", "text", "key", "label", "label_pl", "raw_label",
                  "start", "end", "context"]
STAT_FIELDS = ["key", "text", "label", "label_pl", "mention_count", "doc_count"]


def to_csv(rows: Iterable[dict[str, Any]], fields: list[str]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def to_json(rows: Iterable[dict[str, Any]]) -> bytes:
    return json.dumps(list(rows), ensure_ascii=False, indent=2, default=str).encode("utf-8")


# --------------------------------------------------------------------------- #
# Dokumenty
# --------------------------------------------------------------------------- #
def document_rows(
    docs: Iterable[Document], entity_count: Callable[[str], int] | None = None
) -> list[dict[str, Any]]:
    return [
        {
            "id": d.id, "name": d.name, "source_type": d.source_type.value,
            "language": d.language, "num_pages": d.num_pages, "num_words": d.num_words,
            "num_chars": d.num_chars, "size_bytes": d.size_bytes,
            "entity_mentions": entity_count(d.id) if entity_count else None,
            "added_at": d.added_at.isoformat(), "content_hash": d.content_hash,
            "metadata": json.dumps(d.metadata, ensure_ascii=False, default=str),
        }
        for d in docs
    ]


def documents_csv(docs: Iterable[Document], entity_count: Callable[[str], int] | None = None
                  ) -> bytes:
    return to_csv(document_rows(docs, entity_count), DOCUMENT_FIELDS)


# --------------------------------------------------------------------------- #
# Encje
# --------------------------------------------------------------------------- #
def _context(text: str, m: EntityMention, width: int = CONTEXT_CHARS) -> str:
    left = text[max(0, m.start - width):m.start]
    right = text[m.end:m.end + width]
    return f"{left}[{text[m.start:m.end]}]{right}".replace("\n", " ")


def mention_rows(docs: Iterable[Document], entities: EntityIndex) -> list[dict[str, Any]]:
    """Wszystkie wystąpienia encji w podanych dokumentach, z fragmentem kontekstu."""
    rows = []
    for doc in docs:
        for m in entities.mentions(doc.id):
            rows.append({
                "doc_id": doc.id, "doc_name": doc.name, "text": m.text, "key": m.key,
                "label": m.label.value, "label_pl": m.label.label_pl, "raw_label": m.raw_label,
                "start": m.start, "end": m.end, "context": _context(doc.text, m),
            })
    return rows


def stat_rows(stats: Iterable[EntityStat]) -> list[dict[str, Any]]:
    return [
        {"key": s.key, "text": s.text, "label": s.label.value, "label_pl": s.label.label_pl,
         "mention_count": s.mention_count, "doc_count": s.doc_count}
        for s in stats
    ]


def entities_export(
    docs: Iterable[Document], entities: EntityIndex, fmt: str = "csv", aggregated: bool = False
) -> bytes:
    """Eksport encji: `aggregated=False` – każde wystąpienie z kontekstem,
    `aggregated=True` – zestawienie encji w korpusie (`entity_stats`).
    Zestawienie dotyczy całego korpusu, więc `docs` jest wtedy ignorowane."""
    if aggregated:
        rows, fields = stat_rows(entities.entity_stats()), STAT_FIELDS
    else:
        rows, fields = mention_rows(docs, entities), MENTION_FIELDS
    if fmt == "json":
        return to_json(rows)
    if fmt == "csv":
        return to_csv(rows, fields)
    raise ValueError(f"Nieznany format eksportu: {fmt}")
