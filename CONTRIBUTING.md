# Praca z gitem

Model: **każdy na swoim branchu**, bez obowiązkowego review. `main` zawsze musi się uruchamiać
i przechodzić `pytest -m "not slow"`.

## Branche

| Branch | Kto |
|--------|-----|
| `main` | stabilna wersja, scalamy tylko ukończone etapy |
| `dev/o1`, `dev/o2`, `dev/o3` | robocze branche osób |

## Codzienna praca

```bash
git checkout dev/o2
git pull                       # własne zmiany z innego komputera
git merge origin/main          # pobierz ukończone etapy innych (rób to często!)
# ... praca ...
git add -A && git commit -m "[S3] Add TF-IDF vectorizer with cosine ranking"
git push
```

## Ukończenie etapu → `main`

```bash
git fetch && git merge origin/main     # najpierw scal main do siebie i rozwiąż konflikty u siebie
pytest -m "not slow"                   # musi przejść
git checkout main && git pull
git merge --no-ff dev/o2 -m "[S3] Merge TF-IDF search"
git push
git checkout dev/o2
```

Możesz też zrobić Pull Request na GitHubie i zmergować go samodzielnie. Dzięki temu łatwiej
później prześledzić historię.

## Commity

- **Wiadomości commitów piszemy po angielsku**, w trybie rozkazującym (`Add …`, `Fix …`, `Update …`), np. `[D1] Add PDF text extraction with page count`.
- Prefiks z ID etapu: `[D1]`, `[S4]`, `[N2]`, `[X1]`; zmiany ogólne: `[docs]`, `[infra]`.
- Zmiana pliku wspólnego (kontraktu): osobny commit z prefiksem `[contract]` i wpis w `PROGRESS.md`.

## Konflikty w PROGRESS.md

Każda osoba edytuje tylko **swoją sekcję** tabeli i dopisuje wiersze na **końcu** dziennika.
Jeśli mimo to pojawi się konflikt, zachowaj obie wersje wierszy.

## Pierwsza publikacja na GitHubie (jednorazowo, O1)

```bash
git init -b main
git add -A && git commit -m "[P0] Add project foundation: contracts, stubs, GUI skeleton, docs"
git remote add origin git@github.com:<org>/<repo>.git
git push -u origin main
for b in dev/o1 dev/o2 dev/o3; do git branch $b && git push -u origin $b; done
```
