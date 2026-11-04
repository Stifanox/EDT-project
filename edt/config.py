"""Globalna konfiguracja aplikacji (ścieżki, nazwy modeli, stałe).

Plik współdzielony – zmiany zgłaszaj w PROGRESS.md -> "Dziennik decyzji".
Wartości można nadpisać zmiennymi środowiskowymi (przydatne w testach).
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("EDT_DATA_DIR", ROOT_DIR / "data"))

SAMPLE_DIR = ROOT_DIR / "data" / "sample"   # przykładowy korpus (w repo)
FILES_DIR = DATA_DIR / "files"              # oryginały wgranych plików (poza repo)
CACHE_DIR = DATA_DIR / "cache"              # cache indeksów / embeddingów (poza repo)
DB_PATH = Path(os.environ.get("EDT_DB_PATH", DATA_DIR / "edt.db"))

SUPPORTED_EXTENSIONS: tuple[str, ...] = (".txt", ".pdf")
SUPPORTED_LANGUAGES: tuple[str, ...] = ("pl", "en")

# Gdy baza jest pusta przy starcie, wczytaj korpus z data/sample.
LOAD_SAMPLES_IF_EMPTY = os.environ.get("EDT_LOAD_SAMPLES", "1") == "1"

DEFAULT_TOP_K = 10
SNIPPET_WIDTH = 240

# Wyszukiwanie semantyczne (etap S4) – model wielojęzyczny (pl + en).
SEMANTIC_MODEL_NAME = os.environ.get(
    "EDT_SEMANTIC_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)

# NER (etap N1) – modele spaCy per język.
SPACY_MODELS: dict[str, str] = {
    "pl": os.environ.get("EDT_SPACY_PL", "pl_core_news_md"),
    "en": os.environ.get("EDT_SPACY_EN", "en_core_web_md"),
}
