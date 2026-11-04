"""Źródła plików do importu: folder na dysku i archiwum ZIP (etap D6).

Obie funkcje zwracają `FileBatch` – listę nazw (znaną od razu, do paska postępu)
i leniwy iterator `(nazwa, bajty)`, więc duży folder nie jest wczytywany do pamięci naraz.
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from edt.config import SUPPORTED_EXTENSIONS
from edt.ingest.parsers import IngestError

MAX_FILE_BYTES = 100 * 1024**2      # pojedynczy plik
MAX_ZIP_TOTAL_BYTES = 1024**3       # suma po rozpakowaniu (ochrona przed „zip bombą”)


@dataclass(slots=True)
class FileBatch:
    names: list[str]
    _items: Iterator[tuple[str, bytes]]
    skipped: list[str] = field(default_factory=list)  # pominięte (format, ukryte, za duże)

    def __len__(self) -> int:
        return len(self.names)

    def __iter__(self) -> Iterator[tuple[str, bytes]]:
        return self._items


def _is_hidden(parts: tuple[str, ...]) -> bool:
    return any(p.startswith(".") or p == "__MACOSX" for p in parts)


def folder_batch(folder: Path | str, recursive: bool = True) -> FileBatch:
    """Wszystkie pliki TXT/PDF z folderu (domyślnie z podfolderami), w kolejności alfabetycznej.
    Nazwa dokumentu = nazwa pliku (bez ścieżki)."""
    root = Path(folder).expanduser()
    if not root.is_dir():
        raise IngestError(f"Folder nie istnieje: {root}")
    pattern = "**/*" if recursive else "*"
    paths, skipped = [], []
    for p in sorted(root.glob(pattern)):
        if not p.is_file() or _is_hidden(p.relative_to(root).parts):
            continue
        if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            skipped.append(str(p.relative_to(root)))
        elif p.stat().st_size > MAX_FILE_BYTES:
            skipped.append(f"{p.relative_to(root)} (za duży)")
        else:
            paths.append(p)
    return FileBatch([p.name for p in paths], ((p.name, p.read_bytes()) for p in paths), skipped)


def zip_batch(data: bytes, max_total: int = MAX_ZIP_TOTAL_BYTES) -> FileBatch:
    """Pliki TXT/PDF z archiwum ZIP (także z podfolderów archiwum)."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise IngestError(f"Nieprawidłowe archiwum ZIP: {exc}") from exc

    infos, skipped, total = [], [], 0
    for info in sorted(archive.infolist(), key=lambda i: i.filename):
        path = PurePosixPath(info.filename)
        if info.is_dir() or _is_hidden(path.parts):
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            skipped.append(info.filename)
            continue
        if info.file_size > MAX_FILE_BYTES:
            skipped.append(f"{info.filename} (za duży)")
            continue
        total += info.file_size
        if total > max_total:
            raise IngestError(
                f"Archiwum po rozpakowaniu przekracza limit {max_total // 1024**2} MB."
            )
        infos.append(info)

    def items() -> Iterator[tuple[str, bytes]]:
        with archive:
            for info in infos:
                yield PurePosixPath(info.filename).name, archive.read(info)

    return FileBatch([PurePosixPath(i.filename).name for i in infos], items(), skipped)
