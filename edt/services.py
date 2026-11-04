"""Fasada aplikacji – jedyne miejsce, gdzie moduły są ze sobą łączone.

GUI korzysta WYŁĄCZNIE z `AppServices` (przez `edt.ui.state.get_services()`),
nigdy nie tworzy silników / repozytoriów samodzielnie.

Podmiana zaślepki na prawdziwą implementację = edycja JEDNEJ funkcji-fabryki:
  * `_make_repository()`, `_make_file_store()` – właściciel O1 (etap D2)
  * `_make_engines()`      – właściciel O2 (etapy S2–S4)
  * `_make_entity_index()` – właściciel O3 (etapy N1–N2)
Nie edytuj fabryk innych osób – unikamy konfliktów w git.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Collection, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from edt import config
from edt.config import DEFAULT_TOP_K
from edt.ingest import IngestError, parse_file
from edt.interfaces import DocumentIndexer, DocumentRepository, EntityIndex, SearchEngine
from edt.models import Document, SearchResult, compute_hash, new_document_id
from edt.storage.errors import DuplicateDocumentError
from edt.storage.files import FileStore
from edt.textproc import detect_language

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Fabryki – każda należy do jednej osoby
# --------------------------------------------------------------------------- #
def _make_repository() -> DocumentRepository:  # O1
    # config.DB_PATH czytany w chwili wywołania – testy podmieniają go na bazę tymczasową
    from edt.db import connect
    from edt.storage import SqliteDocumentRepository

    return SqliteDocumentRepository(connect(config.DB_PATH))


def _make_file_store() -> FileStore | None:  # O1
    return FileStore(config.FILES_DIR)


def _make_engines() -> dict[str, SearchEngine]:  # O2
    # TODO(S2/S3/S4): podmień zaślepki na KeywordSearchEngine / TfidfSearchEngine /
    # SemanticSearchEngine. Kolejność w słowniku = kolejność kolumn w GUI.
    from edt.search import SubstringSearchEngine

    return {
        "keyword": SubstringSearchEngine("keyword", "Słowa kluczowe (zaślepka)"),
        "tfidf": SubstringSearchEngine("tfidf", "TF-IDF (zaślepka)"),
        "semantic": SubstringSearchEngine("semantic", "Semantyczne (zaślepka)"),
    }


def _make_entity_index() -> EntityIndex:  # O3
    # TODO(N1/N2): ekstraktor spaCy + trwały indeks (SQLite)
    from edt.ner import InMemoryEntityIndex, RegexEntityExtractor

    return InMemoryEntityIndex(RegexEntityExtractor())


# --------------------------------------------------------------------------- #
# Fasada
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class IngestResult:
    filename: str
    document: Document | None = None
    duplicate_of: Document | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)  # np. indekser nie przyjął dokumentu
    seconds: float = 0.0                               # czas przetwarzania pliku

    @property
    def ok(self) -> bool:
        return self.document is not None

    @property
    def is_duplicate(self) -> bool:
        return self.duplicate_of is not None


@dataclass(slots=True)
class IngestReport:
    """Wynik importu wielu plików (D3). Iterowalny po `IngestResult`."""

    results: list[IngestResult] = field(default_factory=list)
    seconds: float = 0.0

    def __iter__(self) -> Iterator[IngestResult]:
        return iter(self.results)

    def __len__(self) -> int:
        return len(self.results)

    @property
    def added(self) -> list[IngestResult]:
        return [r for r in self.results if r.ok]

    @property
    def duplicates(self) -> list[IngestResult]:
        return [r for r in self.results if r.is_duplicate]

    @property
    def errors(self) -> list[IngestResult]:
        return [r for r in self.results if not r.ok and not r.is_duplicate]

    @property
    def warnings(self) -> list[str]:
        return [f"{r.filename}: {w}" for r in self.results for w in r.warnings]

    def summary(self) -> str:
        return (f"Dodano: {len(self.added)} · duplikaty: {len(self.duplicates)} · "
                f"błędy: {len(self.errors)} · czas: {self.seconds:.1f} s")


@dataclass(frozen=True, slots=True)
class IndexerFailure:
    """Błąd indeksera – dokument jest w bazie, ale ten indeks może być nieaktualny."""

    indexer: str
    action: str            # "add" | "remove" | "rebuild"
    doc_id: str | None
    error: str


ProgressCallback = Callable[[int, int, str], None]  # (przetworzone, wszystkie, nazwa pliku)

_MAX_FAILURES_KEPT = 200


def indexer_name(indexer: DocumentIndexer) -> str:
    return getattr(indexer, "name", None) or type(indexer).__name__


@dataclass
class AppServices:
    repository: DocumentRepository
    engines: dict[str, SearchEngine]
    entities: EntityIndex
    extra_indexers: list[DocumentIndexer] = field(default_factory=list)
    files: FileStore | None = None  # oryginały plików (None => nie przechowujemy)
    failures: list[IndexerFailure] = field(default_factory=list)  # historia błędów indekserów
    stale_indexers: set[str] = field(default_factory=set)         # wymagają rebuild_indexes()

    @property
    def indexers(self) -> list[DocumentIndexer]:
        return [*self.engines.values(), self.entities, *self.extra_indexers]

    # --- powiadamianie indekserów (odporne na błędy) ----------------------- #
    def _record_failure(self, indexer: DocumentIndexer, action: str, doc_id: str | None,
                        exc: Exception) -> IndexerFailure:
        name = indexer_name(indexer)
        failure = IndexerFailure(name, action, doc_id, f"{type(exc).__name__}: {exc}")
        logger.error("Indekser %s: błąd %s (dokument %s): %s", name, action, doc_id,
                     failure.error, exc_info=exc)
        self.failures.append(failure)
        del self.failures[:-_MAX_FAILURES_KEPT]
        self.stale_indexers.add(name)
        return failure

    def _notify(self, action: str, payload: Document | str) -> list[IndexerFailure]:
        doc_id = payload.id if isinstance(payload, Document) else payload
        failures = []
        for indexer in self.indexers:
            try:
                if action == "add":
                    indexer.add_document(payload)  # type: ignore[arg-type]
                else:
                    indexer.remove_document(doc_id)
            except Exception as exc:  # jeden indekser nie może zatrzymać pozostałych
                failures.append(self._record_failure(indexer, action, doc_id, exc))
        return failures

    # --- dokumenty -------------------------------------------------------- #
    def ingest_file(self, filename: str, data: bytes) -> IngestResult:
        """Plik -> Document -> repozytorium + oryginał -> indeksery.

        Nigdy nie rzuca wyjątku – błąd trafia do `IngestResult.error`, a problemy
        niekrytyczne (oryginał, indekser) do `IngestResult.warnings`."""
        started = time.perf_counter()
        result = self._ingest(filename, data)
        result.seconds = time.perf_counter() - started
        if result.ok:
            doc = result.document
            logger.info("Dodano %s (%s, %s, %d słów) w %.2f s", filename, doc.source_type.value,
                        doc.language, doc.num_words, result.seconds)
        elif result.is_duplicate:
            logger.info("Pominięto duplikat %s (= %s)", filename, result.duplicate_of.name)
        else:
            logger.warning("Nie wczytano %s: %s", filename, result.error)
        return result

    def _ingest(self, filename: str, data: bytes) -> IngestResult:
        content_hash = compute_hash(data)
        if existing := self.repository.find_by_hash(content_hash):
            return self._duplicate(filename, existing)
        try:
            parsed = parse_file(filename, data)
        except IngestError as exc:
            return IngestResult(filename, error=str(exc))
        except Exception as exc:  # błąd w parserze – nie wywracamy GUI
            logger.exception("Nieoczekiwany błąd parsowania %s", filename)
            return IngestResult(filename, error=f"Nieoczekiwany błąd odczytu pliku: {exc}")

        doc = Document(
            id=new_document_id(),
            name=filename,
            text=parsed.text,
            source_type=parsed.source_type,
            language=detect_language(parsed.text),
            size_bytes=len(data),
            num_pages=parsed.num_pages,
            content_hash=content_hash,
            metadata=parsed.metadata,
        )
        try:
            self.repository.add(doc)
        except DuplicateDocumentError:  # równoległy import tego samego pliku
            existing = self.repository.find_by_hash(content_hash)
            return self._duplicate(filename, existing) if existing else IngestResult(
                filename, error="Dokument o tej samej treści już istnieje.")
        except Exception as exc:
            logger.exception("Nie zapisano %s w bazie", filename)
            return IngestResult(filename, error=f"Błąd zapisu w bazie dokumentów: {exc}")

        result = IngestResult(filename, document=doc)
        if self.files is not None:
            try:
                self.files.save(doc.id, filename, data)
            except OSError as exc:  # brak oryginału nie unieważnia dokumentu
                logger.warning("Nie zapisano oryginału %s", filename, exc_info=True)
                result.warnings.append(f"Nie zapisano oryginału pliku: {exc}")
        for failure in self._notify("add", doc):
            result.warnings.append(
                f"Indeks „{failure.indexer}” nie przyjął dokumentu ({failure.error}). "
                "Użyj „Przebuduj indeksy”."
            )
        return result

    @staticmethod
    def _duplicate(filename: str, existing: Document) -> IngestResult:
        return IngestResult(filename, duplicate_of=existing,
                            error=f"Duplikat dokumentu „{existing.name}”.")

    def ingest_many(
        self,
        files: Iterable[tuple[str, bytes]],
        on_progress: ProgressCallback | None = None,
    ) -> IngestReport:
        """Import wielu plików. `on_progress(i, n, filename)` po każdym pliku (i = 1..n).
        Duplikaty w obrębie tej samej paczki też są wykrywane."""
        items = list(files)
        report = IngestReport()
        started = time.perf_counter()
        for i, (filename, data) in enumerate(items, start=1):
            report.results.append(self.ingest_file(filename, data))
            if on_progress is not None:
                on_progress(i, len(items), filename)
        report.seconds = time.perf_counter() - started
        logger.info("Import zakończony: %s", report.summary())
        return report

    def add_document(self, doc: Document) -> list[IndexerFailure]:
        """Dodaje gotowy `Document` (bez parsowania). Zwraca błędy indekserów."""
        self.repository.add(doc)
        return self._notify("add", doc)

    def delete_document(self, doc_id: str) -> bool:
        """Usuwa dokument z bazy, wszystkich indeksów i oryginał pliku.
        Sprzątanie indeksów/plików wykonuje się zawsze (idempotentnie), nawet gdy
        rekordu już nie ma w bazie. Zwraca True, jeśli rekord był w bazie."""
        deleted = self.repository.delete(doc_id)
        self._notify("remove", doc_id)
        if self.files is not None:
            try:
                self.files.delete(doc_id)
            except OSError:
                logger.warning("Nie usunięto oryginału dokumentu %s", doc_id, exc_info=True)
        if deleted:
            logger.info("Usunięto dokument %s", doc_id)
        return deleted

    def original_path(self, doc_id: str) -> Path | None:
        """Ścieżka oryginalnego pliku (do pobrania w widoku dokumentu) lub None."""
        return self.files.path(doc_id) if self.files is not None else None

    def rebuild_indexes(self, only_stale: bool = False) -> list[IndexerFailure]:
        """Pełna przebudowa indeksów z bazy (start aplikacji, przycisk „Przebuduj indeksy”).

        Każdy indekser dostaje pełną listę dokumentów i sam decyduje, co przeliczyć
        (np. cache embeddingów / encji). `only_stale=True` – tylko indeksery po błędzie."""
        started = time.perf_counter()
        docs = self.repository.list()
        failures = []
        for indexer in self.indexers:
            name = indexer_name(indexer)
            if only_stale and name not in self.stale_indexers:
                continue
            try:
                indexer.rebuild(docs)
            except Exception as exc:
                failures.append(self._record_failure(indexer, "rebuild", None, exc))
            else:
                self.stale_indexers.discard(name)
        logger.info("Przebudowano indeksy (%d dokumentów) w %.2f s, błędy: %d",
                    len(docs), time.perf_counter() - started, len(failures))
        return failures

    # --- wyszukiwanie ------------------------------------------------------ #
    def search(
        self,
        method: str,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        doc_filter: Collection[str] | None = None,
    ) -> list[SearchResult]:
        return self.engines[method].search(query, top_k=top_k, doc_filter=doc_filter)

    def search_all(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        doc_filter: Collection[str] | None = None,
    ) -> dict[str, list[SearchResult]]:
        """To samo zapytanie wszystkimi metodami – podstawa widoku porównawczego."""
        return {name: self.search(name, query, top_k, doc_filter) for name in self.engines}


def build_services(load_samples: bool | None = None) -> AppServices:
    """Składa aplikację. `load_samples=None` => wg config.LOAD_SAMPLES_IF_EMPTY."""
    if load_samples is None:
        load_samples = config.LOAD_SAMPLES_IF_EMPTY
    services = AppServices(
        repository=_make_repository(),
        engines=_make_engines(),
        entities=_make_entity_index(),
        files=_make_file_store(),
    )
    if services.files is not None:
        services.files.prune({d.id for d in services.repository.list()})
    if load_samples and services.repository.count() == 0:
        from edt.sample_data import iter_sample_files

        logger.info("Pusta baza – wczytuję korpus przykładowy")
        services.ingest_many(iter_sample_files())
    else:
        services.rebuild_indexes()
    return services
