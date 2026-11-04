"""Przechowywanie oryginałów wgranych plików (etap D2).

Plik dokumentu leży w `<root>/<doc_id><ext>`, np. `data/files/3f2a….pdf`.
Używane przez `AppServices` (zapis przy imporcie, usuwanie razem z dokumentem)
i widok dokumentu D5 (pobranie oryginału).
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from collections.abc import Collection
from pathlib import Path

logger = logging.getLogger(__name__)

_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")


def _check_id(doc_id: str) -> str:
    """Chroni przed path traversal (np. doc_id = '../../etc/passwd')."""
    if not _SAFE_ID.fullmatch(doc_id):
        raise ValueError(f"Niepoprawny identyfikator dokumentu: {doc_id!r}")
    return doc_id


class FileStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def save(self, doc_id: str, filename: str, data: bytes) -> Path:
        """Zapis atomowy (plik tymczasowy + rename). Zwraca ścieżkę zapisanego pliku."""
        _check_id(doc_id)
        self.delete(doc_id)  # inny plik tego samego dokumentu (np. inne rozszerzenie)
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / f"{doc_id}{Path(filename).suffix.lower()}"
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return target

    def path(self, doc_id: str) -> Path | None:
        _check_id(doc_id)
        if not self.root.is_dir():
            return None
        return next((p for p in self.root.glob(f"{doc_id}.*") if p.is_file()), None)

    def read(self, doc_id: str) -> bytes | None:
        p = self.path(doc_id)
        return p.read_bytes() if p else None

    def delete(self, doc_id: str) -> bool:
        p = self.path(doc_id)
        if p is None:
            return False
        p.unlink(missing_ok=True)
        return True

    def doc_ids(self) -> set[str]:
        if not self.root.is_dir():
            return set()
        return {p.name.split(".", 1)[0] for p in self.root.iterdir()
                if p.is_file() and not p.name.startswith(".")}

    def prune(self, keep: Collection[str]) -> int:
        """Usuwa pliki osierocone (bez dokumentu w bazie) i resztki zapisów tymczasowych."""
        keep = set(keep)
        removed = 0
        if not self.root.is_dir():
            return 0
        for p in self.root.iterdir():
            if not p.is_file():
                continue
            if p.name.startswith(".tmp-") or p.name.split(".", 1)[0] not in keep:
                p.unlink(missing_ok=True)
                removed += 1
        if removed:
            logger.info("Usunięto %d osieroconych plików z %s", removed, self.root)
        return removed
