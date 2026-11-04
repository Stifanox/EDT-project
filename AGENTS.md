# AGENTS.md – zasady dla agentów AI (i ludzi)

Projekt realizują 3 osoby (O1, O2, O3) równolegle; każda może pracować z własnym agentem AI.
Ten plik mówi, jak pracować, żeby nie blokować innych i nie psuć ich kodu.

## 1. Procedura startowa (zawsze, przed pierwszą zmianą)

1. Przeczytaj [`PROGRESS.md`](PROGRESS.md), czyli aktualne statusy etapów i dziennik decyzji.
2. Ustal, **którą osobą jest użytkownik** (O1/O2/O3):
   - nazwa brancha `dev/o1`, `dev/o2`, `dev/o3` (`git branch --show-current`), lub
   - tabela *Zespół* w `README.md`, lub
   - jeśli nadal nie wiadomo, **zapytaj**.
3. Ustal etap: ten, który wskazał użytkownik, albo pierwszy etap tej osoby o statusie
   `TODO`, którego zależności twarde (`!`) są `DONE`.
4. Przeczytaj opis etapu `docs/tasks/<ID>.md` oraz [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
5. W `PROGRESS.md` zmień status etapu na `🟦 IN_PROGRESS` (tylko swój wiersz).

## 2. Własność plików (najważniejsza zasada)

| Właściciel | Pliki |
|------------|-------|
| **O1** | `edt/ingest/**`, `edt/storage/**`, `edt/exporting.py`, `edt/cli.py`, `edt/ui/documents_view.py`, `pages/1_Baza_dokumentow.py`, `pages/5_Dokument.py`, `app.py`, w `edt/services.py`: fabryki `_make_repository()`, `_make_file_store()` oraz metody dokumentowe `AppServices` (`ingest_*`, `add_document`, `delete_document`, `original_path`, `rebuild_indexes`), `tests/test_ingest*.py`, `tests/test_storage*.py`, `tests/fixtures/pdf/**`, `scripts/make_sample_pdfs.py`, `data/sample/**` |
| **O2** | `edt/search/**`, `edt/ui/search_view.py`, `pages/2_Wyszukiwarka.py`, fabryka `_make_engines()` w `edt/services.py`, `tests/test_search*.py`, lista `ENGINE_FACTORIES` w `tests/contracts/test_search_engine_contract.py` |
| **O3** | `edt/ner/**`, `edt/stats/**`, `edt/ui/entities.py`, `pages/3_Encje_NER.py`, `pages/4_Statystyki.py`, fabryka `_make_entity_index()` w `edt/services.py`, `tests/test_ner*.py`, `tests/test_stats*.py`, lista `INDEX_FACTORIES` w `tests/contracts/test_entity_index_contract.py` |
| **Wspólne (kontrakty)** | `edt/models.py`, `edt/interfaces.py`, `edt/config.py`, `edt/textproc.py`¹, `edt/db.py`, `edt/ui/components.py`, `edt/ui/nav.py`, `edt/ui/state.py`, pozostała część `edt/services.py` (np. `search_all`), `tests/conftest.py`, `PROGRESS.md` (każdy tylko swoją sekcję) |

¹ `textproc.py` rozwija O2 (etap S1), ale sygnatury istniejących funkcji muszą zostać.

- **Edytuj tylko pliki osoby, dla której pracujesz.** Potrzebujesz zmiany w cudzym pliku?
  Zapisz ją w `PROGRESS.md` → *Prośby do innych osób* i zastosuj obejście (np. lokalną funkcję pomocniczą).
- **Pliki wspólne:** wolno wprowadzać wyłącznie zmiany **wstecznie zgodne** (nowe pole z wartością
  domyślną, nowa funkcja, nowy opcjonalny parametr). Każdą taką zmianę opisz w
  `PROGRESS.md` → *Dziennik decyzji*. Zmiana niezgodna (zmiana nazwy, usunięcie, zmiana typu)
  wymaga zgody całego zespołu, więc zapytaj użytkownika i nie rób jej samodzielnie.
- Nie formatuj ani nie refaktoryzuj cudzych plików „przy okazji”.

## 3. Zasady architektury

- GUI (`pages/`, `edt/ui/`) **tylko prezentuje**. Logika przetwarzania (ranking, metryki,
  statystyki, NER) jest w `edt/search`, `edt/ner`, `edt/stats` itd. i jest testowalna bez Streamlit.
- GUI pobiera wszystko przez `get_services()` → `AppServices`. Nie tworzy silników ani repozytoriów samodzielnie.
- Nowa implementacja = klasa spełniająca Protocol z `edt/interfaces.py` + podmiana w **swojej**
  fabryce w `edt/services.py` + dopisanie do listy w teście kontraktowym.
- Ciężkie biblioteki (`spacy`, `sentence_transformers`, `torch`) importuj **leniwie** (w `__init__`
  klasy lub w funkcji), żeby reszta aplikacji i testów działała bez nich.
- Offsety znakowe (encje, podświetlenia) zawsze odnoszą się do `Document.text`.
- Wspólne typy encji: `EntityType` (mapowanie etykiet spaCy robi O3 w N1).
- Otwieranie dokumentu z dowolnego widoku: `edt.ui.nav.open_document(doc_id, highlight_terms)`.
- Filtrowanie wyników wyszukiwania po encjach: `services.entities.doc_ids_with(key, label)` →
  przekazane jako `doc_filter` do `SearchEngine.search`.

## 4. Konwencje kodu

- Python ≥ 3.11, type hints, `from __future__ import annotations`.
- Identyfikatory, nazwy w kodzie i **wiadomości commitów po angielsku**; teksty w GUI, docstringi i dokumentacja **po polsku**.
- Długość linii 100 (`ruff check .`).
- Bez nowych zależności „na zapas”. Nową zależność dopisz do `requirements.txt` w sekcji swojego
  modułu i zgłoś w *Dzienniku decyzji*.
- Dane runtime (`data/edt.db`, `data/files/`, `data/cache/`) nie trafiają do repo.

## 5. Testy

- `pytest -m "not slow"` musi przechodzić **przed każdym merge do `main`**.
- Każda implementacja interfejsu musi przejść test kontraktowy w `tests/contracts/`.
- Testy wymagające modeli ML oznacz `@pytest.mark.slow`. Testy nie mogą wymagać sieci, chyba że są `slow`.
- Do testów używaj fixture'ów `tiny_docs` / `sample_docs` z `tests/conftest.py`.
- Testy GUI (`streamlit.testing.v1.AppTest`), wzór w `tests/test_documents_view.py`:
  start od `app.py` + `at.switch_page("pages/…")` (inaczej `st.switch_page` nie znajdzie stron),
  `get_services.clear()` przed testem (świeże `AppServices`), zaznaczenie w `st.dataframe` przez
  `at.session_state[key] = {"selection": {"rows": [...], "columns": [], "cells": []}}`.
  Upload plików nie jest wspierany przez `AppTest`.
- Każdy test automatycznie dostaje tymczasowy katalog danych (fixture `isolated_data_dir`).
  Ścieżki (`config.DB_PATH`, `FILES_DIR`, `CACHE_DIR`) czytaj z `config` w chwili użycia.

## 6. Zakończenie etapu (Definition of Done)

1. Wszystkie kryteria akceptacji w `docs/tasks/<ID>.md` odhaczone (`- [x]`).
   Jeśli któregoś świadomie nie zrobiono, opisz to w sekcji *Notatki z realizacji* tego pliku.
2. `pytest -m "not slow"` przechodzi, a `streamlit run app.py` startuje bez błędów.
3. W `PROGRESS.md`: status `✅ DONE`, postęp `n/n`, data w *Uwagach*. Jeśli zmieniono kontrakt, wpis w dzienniku.
   Spójność sprawdza `tests/test_progress_consistency.py`. Aktualizuj *Postęp* także w trakcie pracy, po każdym odhaczonym kryterium.
4. Commit **po angielsku** z prefiksem etapu, np. `[S3] Add TF-IDF cosine ranking and snippets`.
5. Merge do `main` według [`CONTRIBUTING.md`](CONTRIBUTING.md).

Etap zablokowany: status `⛔ BLOCKED` + w kolumnie *Uwagi* napisz, przez co (ID etapu lub osoba).

## 7. Format statusów w PROGRESS.md

`⬜ TODO` · `🟦 IN_PROGRESS` · `✅ DONE` · `⛔ BLOCKED` · `🔁 REWORK`
Kolumna *Postęp* = `odhaczone/wszystkie` kryteria akceptacji z pliku etapu.
Zależności: `!ID` = twarda (bez niej nie da się zacząć), `~ID` = miękka (można zacząć na zaślepce).
