# Architektura i kontrakty

## Idea: równoległa praca dzięki kontraktom i zaślepkom

Etap **P0** dostarczył wspólne typy danych (`edt/models.py`), interfejsy (`edt/interfaces.py`),
fasadę (`edt/services.py`) oraz **działające zaślepki** każdego modułu. Dzięki temu:

- aplikacja uruchamia się od pierwszego dnia (`streamlit run app.py`) i ma dane (`data/sample/`);
- każda osoba podmienia **swoją** zaślepkę na prawdziwą implementację, nie czekając na innych;
- testy kontraktowe (`tests/contracts/`) gwarantują, że po podmianie reszta dalej działa.

| Zaślepka (P0) | Zastępuje ją | Etap |
|---------------|--------------|------|
| `InMemoryDocumentRepository` | `SqliteDocumentRepository` | D2 (O1) |
| `parse_pdf` → błąd „nie zaimplementowano” | parser PDF | D1 (O1) |
| `SubstringSearchEngine` ×3 | `KeywordSearchEngine`, `TfidfSearchEngine`, `SemanticSearchEngine` | S2–S4 (O2) |
| `RegexEntityExtractor` | `SpacyEntityExtractor` | N1 (O3) |
| `InMemoryEntityIndex` | `SqliteEntityIndex` (opcjonalnie zostaje in-memory) | N2 (O3) |
| proste `entities_html` | rozbudowane wyróżnianie z etykietami | N3 (O3) |
| szkielety stron `pages/*` | pełne widoki | D4, D5, S6, N4, N5, N6 |

## Przepływ danych

```
               ┌───────────── AppServices (edt/services.py) ─────────────┐
 upload ──▶ ingest_file(name, bytes)                                      │
            │  parse_file() ─▶ Document ─▶ repository.add()               │
            │                         └──▶ for indexer in indexers:       │
            │                                 indexer.add_document(doc)   │
            │        indexers = [*engines.values(), entities]             │
            │                                                             │
 zapytanie ─▶ search_all(query, top_k, doc_filter)                        │
            │     └─▶ {name: engine.search(...) -> list[SearchResult]}    │
            │                                                             │
 filtr encji ─▶ entities.doc_ids_with(key, label) ─▶ doc_filter ─────────┘
```

Przy starcie: `build_services()` → jeśli baza pusta, wczytuje `data/sample/`; w przeciwnym razie
`rebuild_indexes()` (wszystkie indeksery dostają `repository.list()`).
Instancja jest cache'owana w procesie Streamlit przez `edt/ui/state.get_services()`.

## Kontrakty (skrót – źródłem prawdy jest kod)

### `Document` (`edt/models.py`)
`id, name, text, source_type, language ("pl"|"en"|"unknown"), added_at, size_bytes, num_pages,
content_hash, metadata` + właściwości `num_chars`, `num_words`. `text` jest już znormalizowany,
a wszystkie offsety odnoszą się do niego.

### `SearchEngine.search(query, top_k=10, doc_filter=None) -> list[SearchResult]`
- maks. `top_k` wyników, malejąco po `score`, `rank` 1..n, `method == engine.name`;
- tylko `score > 0`; puste zapytanie → `[]`;
- `doc_filter=None` → bez filtra; `set()` → `[]`;
- `snippet` = fragment związany z zapytaniem, `snippet_highlights` = zakresy w snippecie;
- `details` = dowolne dane diagnostyczne (np. dopasowane termy, najlepszy fragment, wagi TF-IDF).
  Widok porównawczy może je pokazywać.

Wyniki różnych metod **nie są porównywalne liczbowo** (BM25 vs cosine). Porównujemy rankingi (S5),
ewentualnie wyniki znormalizowane do [0, 1] tylko w warstwie prezentacji.

### `EntityIndex`
- `mentions(doc_id)` → encje dokumentu (po `start`), do wyróżniania w widoku dokumentu;
- `mentions_of(key, label)` → wszystkie wystąpienia encji, do pokazania fragmentów kontekstu;
- `entity_stats(query, label, limit)` → agregaty (lista encji, wyszukiwarka encji, top-N);
- `doc_ids_with(key, label)` → zbiór dokumentów, używany jako filtr wyszukiwania.

`key` encji = `normalized` (np. lemat lub lowercase), dzięki czemu „Warszawie” i „Warszawa”
mogą się zgrupować (jeśli N1 wypełni `normalized` lematem).

### `EntityType`
`PERSON, ORG, LOC, DATE, TIME, EVENT, PRODUCT, MONEY, QUANTITY, MISC` (+ `label_pl` do GUI).
Sugerowane mapowanie (N1):

| spaCy PL (`pl_core_news`) | spaCy EN (`en_core_web`) | EntityType |
|---|---|---|
| persName | PERSON | PERSON |
| orgName | ORG, NORP* | ORG |
| placeName, geogName | GPE, LOC, FAC | LOC |
| date | DATE | DATE |
| time | TIME | TIME |
| – | EVENT | EVENT |
| – | PRODUCT, WORK_OF_ART | PRODUCT |
| – | MONEY | MONEY |
| – | QUANTITY, PERCENT, CARDINAL*, ORDINAL* | QUANTITY |
| – | LAW, LANGUAGE, inne | MISC |

\* do decyzji O3 (np. pomijać CARDINAL/ORDINAL jako szum).

### Nawigacja (`edt/ui/nav.py`)
`open_document(doc_id, highlight_terms=None)` zapisuje wybór w `st.session_state` i przełącza
na `pages/5_Dokument.py`. Widok dokumentu czyta `selected_document_id()` i `selected_highlight_terms()`.

### SQLite (`edt/db.py`)
Jedna baza `data/edt.db`. Każdy moduł ma **własne tabele** (`documents` = O1, `entities` = O3)
i tworzy je przez `ensure_schema()`. Nie łączymy tabel między modułami w SQL; dane innych
modułów pobieramy przez interfejsy.

## Mapa zależności między etapami

```
P0 ──┬─▶ D1 ─▶ D3 ◀─ D2           D4 ~D3    D5 ~N3
     │                            (O1)
     ├─▶ S1 ─▶ S2 ─┐
     │      └▶ S3 ─┼─▶ S5 ─▶ S6 ~N2     S7 ~S2..S4
     │         S4 ─┘          (O2)
     │
     └─▶ N1 ─▶ N2 ─▶ N4, N5    N3    N6 ~N2
                            (O3)

X1 (integracja) ◀─ wszystkie ;  X2 (raport/demo) ◀─ X1
```
`─▶` zależność twarda, `~` miękka (można pracować na zaślepce i podmienić później).
**Między osobami nie ma zależności twardych** – wszystkie styki są pokryte zaślepkami z P0.
