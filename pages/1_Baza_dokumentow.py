"""Widok: Baza dokumentów (właściciel: O1, etapy D4, D6) – dodawanie (pliki, ZIP, folder),
przeglądanie, usuwanie, eksport."""

import streamlit as st

from edt.exporting import documents_csv, entities_export
from edt.ingest import IngestError
from edt.ingest.sources import folder_batch, zip_batch
from edt.models import SourceType
from edt.ui import nav
from edt.ui.documents_view import (
    LANGUAGE_LABELS,
    documents_frame,
    filter_documents,
    render_ingest_report,
    selected_documents,
    table_column_config,
)
from edt.ui.state import get_services

st.set_page_config(page_title="Baza dokumentów", page_icon="📁", layout="wide")
services = get_services()
state = st.session_state
state.setdefault("upload_key", 0)   # zmiana klucza = wyczyszczenie uploadera
state.setdefault("table_key", 0)    # zmiana klucza = wyczyszczenie zaznaczenia w tabeli

st.title("📁 Baza dokumentów")

# --------------------------------------------------------------------------- #
# Dodawanie
# --------------------------------------------------------------------------- #
def run_import(files, skipped=()) -> None:
    """Import z paskiem postępu; raport zostaje w session_state i jest pokazywany po rerun."""
    bar = st.progress(0.0, text="Wczytywanie…")
    report = services.ingest_many(
        files, on_progress=lambda i, n, name: bar.progress(i / n, text=f"{i}/{n}: {name}")
    )
    state.last_report = report
    state.last_skipped = list(skipped)
    state.upload_key += 1
    st.rerun()


with st.expander("➕ Dodaj dokumenty", expanded=services.repository.count() == 0):
    t_files, t_zip, t_folder = st.tabs(["Pliki", "Archiwum ZIP", "Folder na dysku"])
    with t_files:
        uploaded = st.file_uploader(
            "Pliki TXT lub PDF", type=["txt", "pdf"], accept_multiple_files=True,
            key=f"uploader-{state.upload_key}",
        )
        if st.button("Wczytaj", type="primary", disabled=not uploaded):
            run_import([(f.name, f.getvalue()) for f in uploaded])
    with t_zip:
        archive = st.file_uploader("Archiwum ZIP z plikami TXT/PDF (także w podfolderach)",
                                   type=["zip"], key=f"zip-{state.upload_key}")
        if st.button("Wczytaj archiwum", type="primary", disabled=archive is None):
            try:
                batch = zip_batch(archive.getvalue())
            except IngestError as exc:
                st.error(str(exc), icon="❌")
            else:
                run_import(batch, batch.skipped)
    with t_folder:
        st.caption("Folder na komputerze, na którym działa aplikacja (praca lokalna).")
        folder = st.text_input("Ścieżka do folderu", placeholder="/home/…/dokumenty",
                               key="folder-path")
        recursive = st.checkbox("Z podfolderami", value=True, key="folder-recursive")
        if st.button("Wczytaj folder", type="primary", disabled=not folder.strip()):
            try:
                batch = folder_batch(folder.strip(), recursive)
            except IngestError as exc:
                st.error(str(exc), icon="❌")
            else:
                if len(batch) == 0:
                    st.warning("W folderze nie ma plików TXT ani PDF.", icon="📭")
                else:
                    run_import(batch, batch.skipped)

if report := state.get("last_report"):
    render_ingest_report(report)
    if skipped := state.get("last_skipped"):
        st.caption(f"Pominięto {len(skipped)} plików w nieobsługiwanym formacie: "
                   + ", ".join(skipped[:10]) + (" …" if len(skipped) > 10 else ""))
    if st.button("Ukryj raport", key="hide-report"):
        state.pop("last_report", None)
        state.pop("last_skipped", None)
        st.rerun()

if deleted_msg := state.pop("deleted_msg", None):
    st.success(deleted_msg, icon="🗑️")

# --------------------------------------------------------------------------- #
# Lista dokumentów + filtry
# --------------------------------------------------------------------------- #
all_docs = services.repository.list()
if not all_docs:
    st.info("Baza jest pusta – dodaj pliki TXT lub PDF powyżej.", icon="📭")
    st.stop()

f1, f2, f3 = st.columns([3, 1, 1])
name_query = f1.text_input("Szukaj po nazwie", placeholder="np. kopernik", key="name-filter")
types = f2.multiselect("Typ", [t.value for t in SourceType], format_func=str.upper,
                       key="type-filter")
present_langs = sorted({d.language for d in all_docs})
langs = f3.multiselect("Język", present_langs, format_func=lambda c: LANGUAGE_LABELS.get(c, c),
                       key="lang-filter")

docs = filter_documents(all_docs, name_query, types, langs)
st.caption(f"Wyświetlono {len(docs)} z {len(all_docs)} dokumentów · zaznacz wiersze, "
           "aby otworzyć lub usunąć · kliknij nagłówek, aby sortować")

event = st.dataframe(
    documents_frame(docs, lambda doc_id: len(services.entities.mentions(doc_id))),
    column_config=table_column_config(),
    hide_index=True,
    width="stretch",
    on_select="rerun",
    selection_mode="multi-row",
    key=f"docs-table-{state.table_key}",
)
selected = selected_documents(docs, event.selection.rows if event else [])


def _cancel_delete() -> None:
    state.pop("pending_delete", None)


# Stan „do usunięcia” trzymamy w session_state, a nie tylko w kliknięciu przycisku: dialog
# przetrwa wtedy każde ponowne uruchomienie skryptu, a zamknięcie (X / Esc) go czyści.
@st.dialog("Usunąć dokumenty?", on_dismiss=_cancel_delete)
def confirm_delete(doc_ids: list[str]) -> None:
    to_delete = [d for d in all_docs if d.id in set(doc_ids)]
    st.write(f"Zostanie usuniętych **{len(to_delete)}** dokumentów razem z indeksami, "
             "encjami i oryginałami plików. Tej operacji nie można cofnąć.")
    for d in to_delete[:10]:
        st.markdown(f"- {d.name}")
    if len(to_delete) > 10:
        st.caption(f"…i {len(to_delete) - 10} więcej")
    c1, c2 = st.columns(2)
    if c1.button("Usuń", type="primary", width="stretch"):
        removed = sum(services.delete_document(d.id) for d in to_delete)
        state.deleted_msg = f"Usunięto {removed} dokumentów."
        state.table_key += 1
        _cancel_delete()
        st.rerun()
    if c2.button("Anuluj", width="stretch"):
        _cancel_delete()
        st.rerun()


b1, b2, _ = st.columns([1, 1, 4])
if b1.button("📄 Otwórz", disabled=len(selected) != 1, width="stretch",
             help="Zaznacz dokładnie jeden dokument"):
    nav.open_document(selected[0].id)
if b2.button(f"🗑️ Usuń ({len(selected)})", disabled=not selected, width="stretch"):
    state.pending_delete = [d.id for d in selected]
if state.get("pending_delete"):
    confirm_delete(state.pending_delete)

# --------------------------------------------------------------------------- #
# Eksport (D6) – dane liczone dopiero po kliknięciu (download_button przyjmuje funkcję)
# --------------------------------------------------------------------------- #
with st.expander("⬇️ Eksport"):
    st.caption(f"Eksport dotyczy wyświetlonych dokumentów ({len(docs)}), z wyjątkiem "
               "zestawienia encji, które obejmuje cały korpus.")
    e1, e2, e3 = st.columns(3)
    e1.download_button(
        "📄 Lista dokumentów (CSV)",
        data=lambda: documents_csv(docs, lambda i: len(services.entities.mentions(i))),
        file_name="dokumenty.csv", mime="text/csv", width="stretch",
    )
    fmt = e2.radio("Format encji", ["csv", "json"], horizontal=True, format_func=str.upper,
                   key="entities-format")
    mime = "text/csv" if fmt == "csv" else "application/json"
    e2.download_button(
        "🏷️ Wystąpienia encji (z kontekstem)",
        data=lambda: entities_export(docs, services.entities, fmt),
        file_name=f"encje_wystapienia.{fmt}", mime=mime, width="stretch",
    )
    e3.download_button(
        "📊 Zestawienie encji (korpus)",
        data=lambda: entities_export(all_docs, services.entities, fmt, aggregated=True),
        file_name=f"encje_zestawienie.{fmt}", mime=mime, width="stretch",
    )

# --------------------------------------------------------------------------- #
# Narzędzia
# --------------------------------------------------------------------------- #
with st.expander("🛠️ Indeksy", expanded=bool(services.stale_indexers)):
    if services.stale_indexers:
        st.warning("Nieaktualne indeksy: " + ", ".join(sorted(services.stale_indexers))
                   + ". Wyniki wyszukiwania lub encje mogą być niepełne.", icon="⚠️")
    else:
        st.caption("Wszystkie indeksy są aktualne.")
    if st.button("🔄 Przebuduj indeksy"):
        with st.spinner("Przebudowa indeksów…"):
            failures = services.rebuild_indexes()
        if failures:
            for f in failures:
                st.error(f"{f.indexer}: {f.error}")
        else:
            st.success("Indeksy przebudowane.")
    if services.failures:
        st.caption("Ostatnie błędy indekserów:")
        st.dataframe(
            [{"Indeks": f.indexer, "Operacja": f.action, "Dokument": f.doc_id, "Błąd": f.error}
             for f in services.failures[-10:][::-1]],
            hide_index=True, width="stretch",
        )
