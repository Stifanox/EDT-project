"""Fasada aplikacji – jedyne miejsce, gdzie moduły są ze sobą łączone.

GUI korzysta WYŁĄCZNIE z `AppServices` (przez `edt.ui.state.get_services()`),
nigdy nie tworzy silników / repozytoriów samodzielnie.

Podmiana zaślepki na prawdziwą implementację = edycja JEDNEJ funkcji-fabryki:
  * `_make_repository()`   – właściciel O1 (etap D2)
  * `_make_engines()`      – właściciel O2 (etapy S2–S4)
  * `_make_entity_index()` – właściciel O3 (etapy N1–N2)
Nie edytuj fabryk innych osób – unikamy konfliktów w git.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field

from edt import config
from edt.config import DEFAULT_TOP_K
from edt.ingest import IngestError, parse_file
from edt.interfaces import DocumentIndexer, DocumentRepository, EntityIndex, SearchEngine
from edt.models import Document, SearchResult, compute_hash, new_document_id
from edt.textproc import detect_language


# --------------------------------------------------------------------------- #
# Fabryki – każda należy do jednej osoby
# --------------------------------------------------------------------------- #
def _make_repository() -> DocumentRepository:  # O1
    # TODO(D2): return SqliteDocumentRepository(connect())
    from edt.storage import InMemoryDocumentRepository

    return InMemoryDocumentRepository()


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

    @property
    def ok(self) -> bool:
        return self.document is not None


@dataclass
class AppServices:
    repository: DocumentRepository
    engines: dict[str, SearchEngine]
    entities: EntityIndex
    extra_indexers: list[DocumentIndexer] = field(default_factory=list)

    @property
    def indexers(self) -> list[DocumentIndexer]:
        return [*self.engines.values(), self.entities, *self.extra_indexers]

    # --- dokumenty -------------------------------------------------------- #
    def ingest_file(self, filename: str, data: bytes) -> IngestResult:
        """Wczytaj plik -> Document -> zapis w repozytorium -> powiadom indeksery.
        TODO(D3): obsługa postępu, zapis oryginału w data/files, lepsze metadane."""
        content_hash = compute_hash(data)
        if existing := self.repository.find_by_hash(content_hash):
            return IngestResult(filename, duplicate_of=existing,
                                error=f"Duplikat dokumentu „{existing.name}”.")
        try:
            parsed = parse_file(filename, data)
        except IngestError as exc:
            return IngestResult(filename, error=str(exc))
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
        self.add_document(doc)
        return IngestResult(filename, document=doc)

    def add_document(self, doc: Document) -> None:
        self.repository.add(doc)
        for indexer in self.indexers:
            indexer.add_document(doc)

    def delete_document(self, doc_id: str) -> bool:
        deleted = self.repository.delete(doc_id)
        if deleted:
            for indexer in self.indexers:
                indexer.remove_document(doc_id)
        return deleted

    def rebuild_indexes(self) -> None:
        docs = self.repository.list()
        for indexer in self.indexers:
            indexer.rebuild(docs)

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
    )
    if load_samples and services.repository.count() == 0:
        from edt.sample_data import iter_sample_files

        for name, data in iter_sample_files():
            services.ingest_file(name, data)
    else:
        services.rebuild_indexes()
    return services
