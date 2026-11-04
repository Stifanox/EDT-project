# EDT – eksploracja dokumentów tekstowych

Aplikacja (Streamlit) do budowania bazy dokumentów TXT/PDF, wyszukiwania informacji
trzema metodami (**słowa kluczowe**, **TF-IDF**, **semantyczne**) z porównaniem rankingów
oraz automatycznego rozpoznawania encji nazwanych (**NER**) dla języka polskiego i angielskiego.

> 📋 **Stan prac:** [`PROGRESS.md`](PROGRESS.md) · 🏗️ **Architektura i kontrakty:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
> · 🤖 **Zasady dla agentów AI:** [`AGENTS.md`](AGENTS.md) · 🔀 **Praca z gitem:** [`CONTRIBUTING.md`](CONTRIBUTING.md)

## Zespół

| ID | Osoba | Branch | Zakres |
|----|-------|--------|--------|
| O1 | Mateusz | `dev/o1` | Rdzeń, baza dokumentów, parsowanie TXT/PDF, widoki *Baza dokumentów* i *Dokument* |
| O2 | Karol | `dev/o2` | Wyszukiwanie: słowa kluczowe, TF-IDF, semantyczne, porównanie rankingów, widok *Wyszukiwarka* |
| O3 | Marcin | `dev/o3` | NER (spaCy pl/en), indeks encji, widok *Encje NER*, panel top encji, *Statystyki* |

## Szybki start

```bash
python -m venv .venv && source .venv/bin/activate     # Python 3.11–3.13
pip install -r requirements-dev.txt
python -m spacy download pl_core_news_md               # potrzebne od etapu N1
python -m spacy download en_core_web_md
streamlit run app.py
```

Przy pierwszym uruchomieniu (pusta baza) aplikacja sama wczytuje przykładowy korpus z `data/sample/`
(10 krótkich tekstów PL/EN). Wyłączysz to zmienną `EDT_LOAD_SAMPLES=0`.

Model semantyczny (`paraphrase-multilingual-MiniLM-L12-v2`, ok. 470 MB) pobiera się automatycznie przy
pierwszym użyciu (etap S4).

### Testy

```bash
pytest -m "not slow"     # szybkie: kontrakty, zaślepki, GUI (obowiązkowe przed merge)
pytest                   # wszystkie, łącznie z ciężkimi modelami
```

## Struktura

```
app.py                  # strona startowa Streamlit
pages/                  # widoki: 1_Baza_dokumentow, 2_Wyszukiwarka, 3_Encje_NER, 4_Statystyki, 5_Dokument
edt/
  models.py             # KONTRAKT: Document, SearchResult, EntityMention, EntityStat, EntityType
  interfaces.py         # KONTRAKT: DocumentRepository, SearchEngine, EntityExtractor, EntityIndex
  services.py           # fasada AppServices – jedyne miejsce łączenia modułów
  config.py             # ścieżki, nazwy modeli
  textproc.py           # tokenizacja, stop-słowa, snippety, wykrywanie języka
  db.py                 # wspólne połączenie SQLite
  ingest/               # O1: parsowanie TXT/PDF
  storage/              # O1: repozytorium dokumentów
  search/               # O2: silniki wyszukiwania + porównanie rankingów
  ner/                  # O3: ekstrakcja i indeks encji
  stats/                # O3: statystyki korpusu (powstaje w N6)
  ui/                   # komponenty GUI (state, nav, components, entities, …)
data/sample/            # przykładowy korpus (w repo)
docs/tasks/             # opis każdego etapu: zakres, pliki, kryteria akceptacji
tests/contracts/        # testy kontraktów – każda implementacja musi je przejść
```

## Przykładowe zapytania do demo

| Zapytanie | Oczekiwany efekt (po S2–S4) |
|-----------|-------------|
| `samochody elektryczne` | keyword/TF-IDF znajdą `pl_01`; semantyczne także `en_01` (inny język) i `pl_06` (synonimy: „pojazdy zasilane z baterii”) |
| `pojazdy na prąd` | słowa kluczowe prawie nic, semantyczne – dokumenty o elektromobilności |
| `Nobel radioactivity` | dopasowanie między językami (`en_04` ↔ `pl_02`) |
| `sztuczna inteligencja szpital` + filtr encji typu ORG | filtrowanie wyników po encjach |
