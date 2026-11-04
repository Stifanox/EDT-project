"""Dostęp do przykładowego korpusu z data/sample (testy, demo, pierwsze uruchomienie)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from edt.config import SAMPLE_DIR, SUPPORTED_EXTENSIONS


def iter_sample_files(directory: Path = SAMPLE_DIR) -> Iterator[tuple[str, bytes]]:
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path.name, path.read_bytes()
