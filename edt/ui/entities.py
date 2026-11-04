"""Wizualizacja encji (właściciel: O3; wersja bazowa z P0, rozbudowa w N3).

Kontrakt używany przez widok dokumentu (O1, D5):
  * `entities_html(text, mentions, extra_spans=()) -> str`
  * `entity_legend_html(labels=None) -> str`
"""

from __future__ import annotations

import html
from collections.abc import Iterable

from edt.models import EntityMention, EntityType
from edt.ui.components import highlight_html

ENTITY_COLORS: dict[EntityType, str] = {
    EntityType.PERSON: "#ffadad",
    EntityType.ORG: "#a0c4ff",
    EntityType.LOC: "#caffbf",
    EntityType.DATE: "#ffd6a5",
    EntityType.TIME: "#fdffb6",
    EntityType.EVENT: "#bdb2ff",
    EntityType.PRODUCT: "#9bf6ff",
    EntityType.MONEY: "#d4f0c0",
    EntityType.QUANTITY: "#e0e0e0",
    EntityType.MISC: "#ffc6ff",
}


def entity_style(label: EntityType) -> str:
    return (
        f"background:{ENTITY_COLORS.get(label, '#eeeeee')};color:#1a1a1a;"
        "padding:0 3px;border-radius:4px"
    )


def entities_html(
    text: str,
    mentions: Iterable[EntityMention],
    extra_spans: Iterable[tuple[int, int, str]] = (),
) -> str:
    """Cały tekst dokumentu z wyróżnionymi encjami.
    `extra_spans` – dodatkowe podświetlenia (np. termy zapytania) w formacie highlight_html."""
    # TODO(N3): etykieta typu przy encji (np. tooltip/indeks górny), filtr typów
    spans = [(m.start, m.end, entity_style(m.label)) for m in mentions]
    return highlight_html(text, [*spans, *extra_spans])


def entity_legend_html(labels: Iterable[EntityType] | None = None) -> str:
    labels = list(labels) if labels is not None else list(EntityType)
    items = [
        f'<span style="{entity_style(lbl)};margin-right:6px">{html.escape(lbl.label_pl)}</span>'
        for lbl in labels
    ]
    return " ".join(items)
