"""Wspólne fixture'y testów."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault("EDT_LOAD_SAMPLES", "0")  # testy nie wczytują korpusu samoczynnie
# Zabezpieczenie: nawet kod czytający config przy imporcie nie dotknie prawdziwego data/.
os.environ.setdefault("EDT_DATA_DIR", tempfile.mkdtemp(prefix="edt-tests-"))
os.environ.pop("EDT_DB_PATH", None)

from edt import config  # noqa: E402
from edt.ingest import parse_file  # noqa: E402
from edt.models import Document, SourceType, compute_hash  # noqa: E402
from edt.sample_data import iter_sample_files  # noqa: E402
from edt.textproc import detect_language, normalize_text  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Każdy test ma własną bazę SQLite, katalog oryginałów i cache."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "edt.db")
    monkeypatch.setattr(config, "FILES_DIR", tmp_path / "files")
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path / "cache")
    return tmp_path


def make_doc(
    doc_id: str, text: str, name: str | None = None, source_type: SourceType = SourceType.TXT
) -> Document:
    text = normalize_text(text)
    return Document(
        id=doc_id,
        name=name or f"{doc_id}.txt",
        text=text,
        source_type=source_type,
        language=detect_language(text),
        size_bytes=len(text.encode()),
        content_hash=compute_hash(text.encode()),
    )


@pytest.fixture
def tiny_docs() -> list[Document]:
    """Mały, w pełni kontrolowany korpus do testów jednostkowych."""
    return [
        make_doc("d1", "Kot siedzi na macie. Kot lubi mleko."),
        make_doc("d2", "Pies biega po parku w Warszawie."),
        make_doc("d3", "The cat sat on the mat in London."),
        make_doc("d4", "Samochody elektryczne i stacje ładowania w Polsce."),
    ]


@pytest.fixture(scope="session")
def sample_docs() -> list[Document]:
    """Korpus z data/sample (PL + EN, TXT + PDF) – wczytany parserem z edt.ingest."""
    docs = []
    for i, (name, data) in enumerate(iter_sample_files()):
        parsed = parse_file(name, data)
        docs.append(make_doc(f"s{i}", parsed.text, name, parsed.source_type))
    return docs
