"""Odczyt plików TXT/PDF -> czysty tekst (P0: tylko TXT; PDF w etapie D1).

Kontrakt: `parse_file(filename, data) -> ParsedFile` lub wyjątek `IngestError`
z komunikatem nadającym się do pokazania w GUI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from edt.config import SUPPORTED_EXTENSIONS
from edt.models import SourceType
from edt.textproc import normalize_text


class IngestError(Exception):
    """Błąd wczytywania dokumentu (komunikat dla użytkownika)."""


@dataclass(slots=True)
class ParsedFile:
    text: str
    source_type: SourceType
    num_pages: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def parse_file(filename: str, data: bytes) -> ParsedFile:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise IngestError(f"Nieobsługiwany format pliku: {ext or '(brak rozszerzenia)'}")
    if ext == ".txt":
        parsed = parse_txt(data)
    else:
        parsed = parse_pdf(data)
    if not parsed.text.strip():
        raise IngestError(f"Plik {filename} nie zawiera tekstu.")
    return parsed


def parse_txt(data: bytes) -> ParsedFile:
    # TODO(D1): lepsze wykrywanie kodowania (np. charset-normalizer)
    for encoding in ("utf-8-sig", "cp1250", "iso-8859-2"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("utf-8", errors="replace")
        encoding = "utf-8 (z zamianą znaków)"
    return ParsedFile(normalize_text(text), SourceType.TXT, metadata={"encoding": encoding})


def parse_pdf(data: bytes) -> ParsedFile:
    # TODO(D1): implementacja (pypdf / pdfplumber), num_pages, metadane PDF.
    raise IngestError("Obsługa PDF nie jest jeszcze zaimplementowana (etap D1).")
