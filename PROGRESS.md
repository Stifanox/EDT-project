# PROGRESS – stan realizacji projektu

> Plik dla ludzi i agentów AI. Zasady aktualizacji: [`AGENTS.md`](AGENTS.md) §6–7.
> Każda osoba edytuje **tylko swoją sekcję**; do dziennika dopisujemy wiersze **na końcu**.

**Statusy:** `⬜ TODO` · `🟦 IN_PROGRESS` · `✅ DONE` · `⛔ BLOCKED` · `🔁 REWORK`
**Zależności:** `!ID` twarda · `~ID` miękka (można zacząć na zaślepce z P0)
**Postęp:** odhaczone / wszystkie kryteria akceptacji w `docs/tasks/<ID>.md`

## Podsumowanie

| Osoba | Zakres | Etapy ukończone |
|-------|--------|-----------------|
| O1 | Fundament, dokumenty, widoki Baza/Dokument | 3 / 7 |
| O2 | Wyszukiwanie i porównanie rankingów | 0 / 7 |
| O3 | NER, encje, statystyki | 0 / 6 |
| Wszyscy | Integracja, raport | 0 / 2 |

**Kolejność:** P0 jest jedynym etapem blokującym, a po jego merge do `main` wszystkie trzy osoby
pracują równolegle. Kolejność wewnątrz sekcji jest zalecana. Szczegóły: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#mapa-zależności-między-etapami).

---

## P0 – Fundament (O1) · BLOKUJĄCY

| ID | Etap | Status | Postęp | Zależności | Uwagi |
|----|------|--------|--------|------------|-------|
| [P0](docs/tasks/P0.md) | Fundament: kontrakty, zaślepki, szkielet GUI, korpus, testy kontraktowe, dokumentacja | ✅ DONE | 12/12 | – | 2026-11-04 · po merge do `main` startują wszyscy |

## O1 – Dokumenty (właściciel: O1)

| ID | Etap | Status | Postęp | Zależności | Uwagi |
|----|------|--------|--------|------------|-------|
| [D1](docs/tasks/D1.md) | Parsowanie TXT/PDF i przetwarzanie wstępne | ✅ DONE | 7/7 | !P0 | 2026-11-04 · korpus ma teraz 2 PDF-y |
| [D2](docs/tasks/D2.md) | Repozytorium SQLite + przechowywanie plików | ✅ DONE | 6/6 | !P0 | 2026-11-04 · dokumenty trwałe w `data/edt.db` |
| [D3](docs/tasks/D3.md) | Pipeline wczytywania (masowy import, postęp, błędy, start) | ⬜ TODO | 0/6 | !D1, !D2 | |
| [D4](docs/tasks/D4.md) | Widok „Baza dokumentów” | ⬜ TODO | 0/7 | !P0, ~D3 | |
| [D5](docs/tasks/D5.md) | Widok „Szczegóły dokumentu” | ⬜ TODO | 0/7 | !P0, ~N3 | |
| [D6](docs/tasks/D6.md) | (opcjonalnie) Import folderu, eksport, filtry metadanych | ⬜ TODO | 0/4 | ~D4 | |

## O2 – Wyszukiwanie (właściciel: O2)

| ID | Etap | Status | Postęp | Zależności | Uwagi |
|----|------|--------|--------|------------|-------|
| [S1](docs/tasks/S1.md) | Analizator tekstu do wyszukiwania (lematyzacja pl/en, stop-słowa) | ⬜ TODO | 0/5 | !P0 | |
| [S2](docs/tasks/S2.md) | Wyszukiwanie słowami kluczowymi (frazy, AND/OR, BM25) | ⬜ TODO | 0/7 | !S1 | |
| [S3](docs/tasks/S3.md) | Wyszukiwanie TF-IDF (cosine) | ⬜ TODO | 0/6 | !S1 | |
| [S4](docs/tasks/S4.md) | Wyszukiwanie semantyczne (embeddingi, chunking, cache) | ⬜ TODO | 0/7 | !P0 | |
| [S5](docs/tasks/S5.md) | Porównanie rankingów (metryki, różnice pozycji) | ⬜ TODO | 0/6 | !P0, ~S2, ~S3, ~S4 | |
| [S6](docs/tasks/S6.md) | Widok „Wyszukiwarka” (obok siebie, filtr encji) | ⬜ TODO | 0/8 | !S5, ~N2 | |
| [S7](docs/tasks/S7.md) | (opcjonalnie) Ewaluacja: zapytania testowe, P@k, nDCG | ⬜ TODO | 0/4 | ~S2, ~S3, ~S4 | |

## O3 – NER i statystyki (właściciel: O3)

| ID | Etap | Status | Postęp | Zależności | Uwagi |
|----|------|--------|--------|------------|-------|
| [N1](docs/tasks/N1.md) | Ekstraktor NER spaCy (pl + en) + mapowanie typów | ⬜ TODO | 0/7 | !P0 | |
| [N2](docs/tasks/N2.md) | Trwały indeks encji (SQLite) + zapytania | ⬜ TODO | 0/5 | !P0, ~N1 | |
| [N3](docs/tasks/N3.md) | Wyróżnianie encji w tekście (komponent) | ⬜ TODO | 0/5 | !P0 | |
| [N4](docs/tasks/N4.md) | Widok „Encje NER” | ⬜ TODO | 0/6 | !P0, ~N2 | |
| [N5](docs/tasks/N5.md) | Panel najczęstszych encji | ⬜ TODO | 0/4 | !P0, ~N1 | |
| [N6](docs/tasks/N6.md) | Statystyki korpusu (dokumenty, długości, terminy, typy encji) | ⬜ TODO | 0/6 | !P0 | |

## Wspólne – na koniec

| ID | Etap | Status | Postęp | Zależności | Uwagi |
|----|------|--------|--------|------------|-------|
| [X1](docs/tasks/X1.md) | Integracja end-to-end, wydajność, porządki | ⬜ TODO | 0/6 | !D3, !S6, !N4 | prowadzi O1 |
| [X2](docs/tasks/X2.md) | Raport / prezentacja / demo | ⬜ TODO | 0/4 | !X1 | wszyscy |

---

## Prośby do innych osób

| Data | Od | Do | Prośba | Status |
|------|----|----|--------|--------|
| | | | | |

## Dziennik decyzji i zmian kontraktów

| Data | Kto | Decyzja / zmiana |
|------|-----|------------------|
| 2026-11-04 | O1 | Stack: Python ≥3.11 + Streamlit (multipage `pages/`), SQLite, scikit-learn, sentence-transformers, spaCy. |
| 2026-11-04 | O1 | Języki dokumentów: PL + EN. Model semantyczny: `paraphrase-multilingual-MiniLM-L12-v2`. NER: `pl_core_news_md` / `en_core_web_md`, wybór po `Document.language`. |
| 2026-11-04 | O1 | Kontrakty P0: `edt/models.py`, `edt/interfaces.py`, `edt/services.py` (fabryki per osoba), `edt/ui/nav.py`. Od teraz tylko zmiany wstecznie zgodne. |
| 2026-11-04 | O1 | Git: branche `dev/o1..o3`, merge do `main` po ukończeniu etapu, bez obowiązkowego review. Commity po angielsku. |
| 2026-11-04 | O1 | [D1] Korpus `data/sample/` ma 12 plików: 10 TXT + 2 PDF (`pl_07_mikolaj_kopernik.pdf`, `en_05_vistula_river.pdf`). Fixture `sample_docs` w `tests/conftest.py` wczytuje pliki przez `parse_file` (zmiana wstecznie zgodna). |
| 2026-11-04 | O1 | [D1] Nowe zależności: `charset-normalizer` (requirements.txt), `fpdf2` (requirements-dev.txt, tylko generator PDF). `Document.metadata` dla PDF: `title`, `author`, `subject`, `creator`, `producer`, `created` (ISO), `pages_without_text`; dla TXT: `encoding`. |
| 2026-11-04 | O1 | [D2] Dokumenty trwałe w SQLite (`data/edt.db`, tabela `documents`), oryginały w `data/files/`. `AppServices` ma nowe pole `files: FileStore \| None` i metodę `original_path(doc_id)` (zmiana wstecznie zgodna). `DocumentRepository.add` rzuca `DuplicateDocumentError` przy tej samej treści pod innym `id`. |
| 2026-11-04 | O1 | [D2] **Ważne dla wszystkich:** `tests/conftest.py` ma fixture autouse `isolated_data_dir`, więc każdy test ma własne `config.DB_PATH`, `FILES_DIR` i `CACHE_DIR` w katalogu tymczasowym. W swoim kodzie czytaj te ścieżki z `config` **w chwili wywołania** (np. `connect(config.DB_PATH)`), a nie przez domyślny argument ustalany przy imporcie. |
