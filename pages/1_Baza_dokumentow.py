"""Widok: Baza dokumentów (właściciel: O1, etap D4) – dodawanie, przeglądanie, usuwanie."""

import streamlit as st

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
with st.expander("➕ Dodaj dokumenty", expanded=services.repository.count() == 0):
    uploaded = st.file_uploader(
        "Pliki TXT lub PDF", type=["txt", "pdf"], accept_multiple_files=True,
        key=f"uploader-{state.upload_key}",
    )
    if st.button("Wczytaj", type="primary", disabled=not uploaded):
        bar = st.progress(0.0, text="Wczytywanie…")
        state.last_report = services.ingest_many(
            ((f.name, f.getvalue()) for f in uploaded),
            on_progress=lambda i, n, name: bar.progress(i / n, text=f"{i}/{n}: {name}"),
        )
        state.upload_key += 1
        st.rerun()

if report := state.get("last_report"):
    render_ingest_report(report)
    if st.button("Ukryj raport", key="hide-report"):
        del state.last_report
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
name_query = f1.text_input("Szukaj po nazwie", placeholder="np. kopernik")
types = f2.multiselect("Typ", [t.value for t in SourceType], format_func=str.upper)
present_langs = sorted({d.language for d in all_docs})
langs = f3.multiselect("Język", present_langs, format_func=lambda c: LANGUAGE_LABELS.get(c, c))

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
