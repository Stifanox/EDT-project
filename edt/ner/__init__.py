"""Rozpoznawanie encji nazwanych (właściciel: O3)."""

from edt.ner.memory_index import InMemoryEntityIndex
from edt.ner.stub import RegexEntityExtractor

__all__ = ["InMemoryEntityIndex", "RegexEntityExtractor"]
