"""Narzędzie wiersza poleceń (etap D6).

    python -m edt.cli import <folder|plik.zip|plik.txt|plik.pdf> [...] [--no-recursive]
    python -m edt.cli list
    python -m edt.cli export-documents documents.csv
    python -m edt.cli export-entities entities.csv|.json [--aggregated] [--doc ID]
    python -m edt.cli rebuild

Działa na tej samej bazie co aplikacja (`config.DB_PATH`). Uruchomiona aplikacja
zauważy zmiany przy następnym odświeżeniu strony (`AppServices.sync_with_repository`).
Kod wyjścia: 0 – OK, 1 – część plików nie została wczytana, 2 – błąd wywołania.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from edt.exporting import documents_csv, entities_export
from edt.ingest import IngestError
from edt.ingest.sources import FileBatch, folder_batch, zip_batch
from edt.services import AppServices, build_services


def _batches(paths: Sequence[str], recursive: bool) -> list[FileBatch]:
    batches = []
    for raw in paths:
        p = Path(raw).expanduser()
        if p.is_dir():
            batches.append(folder_batch(p, recursive))
        elif p.suffix.lower() == ".zip":
            batches.append(zip_batch(p.read_bytes()))
        elif p.is_file():
            batches.append(FileBatch([p.name], iter([(p.name, p.read_bytes())])))
        else:
            raise IngestError(f"Nie znaleziono: {p}")
    return batches


def cmd_import(services: AppServices, args: argparse.Namespace) -> int:
    exit_code = 0
    for batch in _batches(args.paths, not args.no_recursive):
        for name in batch.skipped:
            print(f"  pominięto: {name}")

        def progress(i: int, n: int, name: str) -> None:
            print(f"  [{i}/{n}] {name}", flush=True)

        report = services.ingest_many(batch, on_progress=None if args.quiet else progress)
        for r in [*report.duplicates, *report.errors]:
            print(f"  ! {r.filename}: {r.error}")
        for w in report.warnings:
            print(f"  ! {w}")
        print(report.summary())
        if report.errors:
            exit_code = 1
    return exit_code


def cmd_list(services: AppServices, args: argparse.Namespace) -> int:
    for d in services.repository.list():
        pages = f"{d.num_pages} str." if d.num_pages else ""
        print(f"{d.id}  {d.source_type.value:3}  {d.language:7}  {d.num_words:>7} słów  "
              f"{pages:>7}  {d.name}")
    print(f"Razem: {services.repository.count()} dokumentów")
    return 0


def cmd_export_documents(services: AppServices, args: argparse.Namespace) -> int:
    data = documents_csv(services.repository.list(),
                         lambda doc_id: len(services.entities.mentions(doc_id)))
    Path(args.output).write_bytes(data)
    print(f"Zapisano {services.repository.count()} dokumentów do {args.output}")
    return 0


def cmd_export_entities(services: AppServices, args: argparse.Namespace) -> int:
    fmt = Path(args.output).suffix.lower().lstrip(".")
    if fmt not in ("csv", "json"):
        print("Plik wyjściowy musi mieć rozszerzenie .csv lub .json", file=sys.stderr)
        return 2
    if args.doc:
        doc = services.repository.get(args.doc)
        if doc is None:
            print(f"Nie ma dokumentu o id {args.doc}", file=sys.stderr)
            return 2
        docs = [doc]
    else:
        docs = services.repository.list()
    Path(args.output).write_bytes(entities_export(docs, services.entities, fmt, args.aggregated))
    print(f"Zapisano encje do {args.output}")
    return 0


def cmd_rebuild(services: AppServices, args: argparse.Namespace) -> int:
    failures = services.rebuild_indexes()
    for f in failures:
        print(f"  ! {f.indexer}: {f.error}")
    print("Indeksy przebudowane" + (" z błędami" if failures else ""))
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m edt.cli", description="EDT – baza dokumentów")
    parser.add_argument("-v", "--verbose", action="store_true", help="logi na stderr")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("import", help="wczytaj pliki / foldery / archiwa ZIP")
    p.add_argument("paths", nargs="+")
    p.add_argument("--no-recursive", action="store_true", help="bez podfolderów")
    p.add_argument("-q", "--quiet", action="store_true", help="bez postępu dla każdego pliku")
    p.set_defaults(func=cmd_import)

    sub.add_parser("list", help="lista dokumentów").set_defaults(func=cmd_list)

    p = sub.add_parser("export-documents", help="lista dokumentów z metadanymi do CSV")
    p.add_argument("output")
    p.set_defaults(func=cmd_export_documents)

    p = sub.add_parser("export-entities", help="encje do CSV/JSON")
    p.add_argument("output")
    p.add_argument("--aggregated", action="store_true", help="zestawienie zamiast wystąpień")
    p.add_argument("--doc", help="tylko jeden dokument (id)")
    p.set_defaults(func=cmd_export_entities)

    sub.add_parser("rebuild", help="przebuduj indeksy").set_defaults(func=cmd_rebuild)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    services = build_services(load_samples=False)
    try:
        return args.func(services, args)
    except IngestError as exc:
        print(f"Błąd: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
