"""Odczyt plików TXT/PDF -> czysty tekst + metadane (etap D1).

Kontrakt: `parse_file(filename, data) -> ParsedFile` lub wyjątek `IngestError`
z komunikatem nadającym się do pokazania w GUI.
"""

from __future__ import annotations

import codecs
import io
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from edt.config import SUPPORTED_EXTENSIONS
from edt.ingest.cleaning import clean_pdf_pages, looks_multicolumn
from edt.models import SourceType
from edt.textproc import normalize_text

logger = logging.getLogger(__name__)
# pypdf jest bardzo „gadatliwy” przy wadliwych PDF
logging.getLogger("pypdf").setLevel(logging.ERROR)


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
    if not data:
        raise IngestError(f"Plik {filename} jest pusty.")
    parsed = parse_txt(data) if ext == ".txt" else parse_pdf(data)
    if not parsed.text.strip():
        raise IngestError(f"Plik {filename} nie zawiera tekstu.")
    return parsed


# --------------------------------------------------------------------------- #
# TXT
# --------------------------------------------------------------------------- #
_PL_CHARS = frozenset("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
# Znaki typowe dla odczytu polskiego tekstu w złym kodowaniu (cp1250 <-> iso-8859-2).
_MOJIBAKE = frozenset("±¶¼¡¦¬¥šŠťŤľĽ�")


def _decoding_score(text: str) -> int:
    """Wyższy = bardziej prawdopodobnie poprawne kodowanie polskiego tekstu."""
    bad = sum(c in _MOJIBAKE or "\x80" <= c <= "\x9f" for c in text)
    return sum(c in _PL_CHARS for c in text) - 3 * bad


def decode_text(data: bytes) -> tuple[str, str]:
    """Bajty -> (tekst, nazwa kodowania).

    Kolejność: BOM UTF-16/UTF-8 → ścisłe UTF-8 → lepsze z cp1250 / iso-8859-2
    (ocena po polskich znakach i typowych „krzakach”) → charset-normalizer.
    """
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16"), "utf-16"
    try:
        encoding = "utf-8-sig" if data.startswith(codecs.BOM_UTF8) else "utf-8"
        return data.decode("utf-8-sig"), encoding
    except UnicodeDecodeError:
        pass

    candidates: list[tuple[int, str, str]] = []
    for enc in ("cp1250", "iso-8859-2"):
        try:
            text = data.decode(enc)
        except UnicodeDecodeError:
            continue
        candidates.append((_decoding_score(text), enc, text))
    if candidates:
        score, enc, text = max(candidates, key=lambda c: c[0])  # remis -> cp1250 (pierwszy)
        if score >= 0:
            return text, enc

    from charset_normalizer import from_bytes

    best = from_bytes(data).best()
    if best is not None:
        return str(best), best.encoding
    return data.decode("utf-8", errors="replace"), "utf-8 (z zamianą znaków)"


def parse_txt(data: bytes) -> ParsedFile:
    text, encoding = decode_text(data)
    return ParsedFile(normalize_text(text), SourceType.TXT, metadata={"encoding": encoding})


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #
def _pdf_metadata(reader: Any) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    try:
        info = reader.metadata
    except Exception:  # uszkodzony słownik /Info nie może blokować importu
        logger.debug("Nie udało się odczytać metadanych PDF", exc_info=True)
        return meta
    if not info:
        return meta
    for key, attr in (("title", "title"), ("author", "author"), ("subject", "subject"),
                      ("creator", "creator"), ("producer", "producer")):
        try:
            value = getattr(info, attr)
        except Exception:
            continue
        if value and str(value).strip():
            meta[key] = str(value).strip()
    try:
        created = info.creation_date
    except Exception:
        created = None
    if isinstance(created, datetime):
        meta["created"] = created.isoformat()
    return meta


def _extract_page(page: Any) -> str:
    """Tryb `layout` (zachowuje odstępy między akapitami); dla stron wielokolumnowych
    lub przy błędzie – zwykły tryb pypdf. Wadliwa strona => pusty tekst."""
    try:
        text = page.extract_text(extraction_mode="layout") or ""
        if text.strip() and not looks_multicolumn(text):
            return text
    except Exception:
        logger.debug("Tryb layout nie zadziałał – używam zwykłego", exc_info=True)
    try:
        return page.extract_text() or ""
    except Exception:  # jedna wadliwa strona nie przekreśla dokumentu
        logger.warning("Nie udało się odczytać strony PDF", exc_info=True)
        return ""


def parse_pdf(data: bytes) -> ParsedFile:
    from pypdf import PdfReader
    from pypdf.errors import DependencyError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                decrypted = reader.decrypt("")  # PDF z samym hasłem właściciela da się czytać
            except (DependencyError, NotImplementedError) as exc:
                raise IngestError(f"Nieobsługiwany typ szyfrowania PDF: {exc}") from exc
            if not decrypted:
                raise IngestError("Plik PDF jest zabezpieczony hasłem – nie można odczytać treści.")
        page_texts = [_extract_page(page) for page in reader.pages]
    except IngestError:
        raise
    except Exception as exc:
        raise IngestError(f"Nie udało się odczytać pliku PDF (plik uszkodzony?): {exc}") from exc

    num_pages = len(page_texts)
    if num_pages == 0:
        raise IngestError("Plik PDF nie zawiera żadnych stron.")
    empty_pages = sum(not t.strip() for t in page_texts)
    if empty_pages == num_pages:
        raise IngestError(
            "PDF nie zawiera warstwy tekstowej (prawdopodobnie skan) – OCR nie jest obsługiwany."
        )

    metadata = _pdf_metadata(reader)
    if empty_pages:
        metadata["pages_without_text"] = empty_pages
    return ParsedFile(clean_pdf_pages(page_texts), SourceType.PDF, num_pages, metadata)
