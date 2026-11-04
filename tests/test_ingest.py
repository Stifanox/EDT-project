"""Testy etapu D1: parsowanie TXT/PDF i czyszczenie tekstu."""

from __future__ import annotations

import codecs
from pathlib import Path

import pytest

from edt.ingest import IngestError, parse_file
from edt.ingest.cleaning import clean_pdf_pages, join_lines, looks_multicolumn
from edt.ingest.parsers import decode_text
from edt.models import SourceType
from edt.sample_data import iter_sample_files
from edt.textproc import detect_language

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "pdf"
SAMPLE_PDFS = ["pl_07_mikolaj_kopernik.pdf", "en_05_vistula_river.pdf"]

PL_TEXT = "Zażółć gęślą jaźń. ĄĆĘŁŃÓŚŹŻ - Łódź, Kraków, Gdańsk, źdźbło, świerszcz."


# --------------------------------------------------------------------------- #
# TXT
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("raw", "expected_encoding"),
    [
        (PL_TEXT.encode("utf-8"), "utf-8"),
        (codecs.BOM_UTF8 + PL_TEXT.encode("utf-8"), "utf-8-sig"),
        (PL_TEXT.encode("utf-16"), "utf-16"),
        (PL_TEXT.encode("cp1250"), "cp1250"),
        (PL_TEXT.encode("iso-8859-2"), "iso-8859-2"),
    ],
    ids=["utf8", "utf8-bom", "utf16", "cp1250", "iso-8859-2"],
)
def test_txt_encodings(raw, expected_encoding):
    text, encoding = decode_text(raw)
    assert text == PL_TEXT
    assert encoding == expected_encoding
    parsed = parse_file("a.txt", raw)
    assert parsed.text == PL_TEXT and parsed.source_type is SourceType.TXT
    assert parsed.metadata["encoding"] == expected_encoding


def test_txt_normalizes_whitespace():
    parsed = parse_file("a.txt", b"  Linia 1\r\nLinia   2\r\n\r\n\r\n\r\nAkapit 2  ")
    assert parsed.text == "Linia 1\nLinia 2\n\nAkapit 2"


@pytest.mark.parametrize(
    ("name", "data", "fragment"),
    [
        ("pusty.txt", b"", "pusty"),
        ("spacje.txt", b"   \n\n  ", "nie zawiera tekstu"),
        ("plik.docx", b"abc", "Nieobsługiwany format"),
        ("bez_rozszerzenia", b"abc", "brak rozszerzenia"),
    ],
)
def test_ingest_errors_txt(name, data, fragment):
    with pytest.raises(IngestError, match=fragment):
        parse_file(name, data)


# --------------------------------------------------------------------------- #
# PDF
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", SAMPLE_PDFS)
def test_pdf_text_matches_source_exactly(name):
    """Ekstrakcja + czyszczenie odtwarza tekst źródłowy 1:1: bez nagłówków/stopek,
    z usuniętymi przeniesieniami i zachowanymi akapitami."""
    parsed = parse_file(name, (ROOT / "data" / "sample" / name).read_bytes())
    expected = (FIXTURES / name.replace(".pdf", ".expected.txt")).read_text("utf-8").strip()
    assert parsed.text == expected
    assert parsed.source_type is SourceType.PDF


def test_pdf_metadata_and_pages():
    parsed = parse_file("k.pdf", (ROOT / "data" / "sample" / SAMPLE_PDFS[0]).read_bytes())
    assert parsed.num_pages == 3
    assert parsed.metadata["title"] == "Mikołaj Kopernik i przewrót heliocentryczny"
    assert parsed.metadata["author"] == "Zespół EDT"
    assert parsed.metadata["created"].startswith("2026-11-04")
    assert "Strona" not in parsed.text and "Materiały przykładowe" not in parsed.text


def test_pdf_owner_password_only_is_readable():
    parsed = parse_file("o.pdf", (FIXTURES / "owner_only.pdf").read_bytes())
    assert "Zażółć gęślą jaźń" in parsed.text


@pytest.mark.parametrize(
    ("data", "fragment"),
    [
        ((FIXTURES / "encrypted.pdf").read_bytes(), "zabezpieczony hasłem"),
        ((FIXTURES / "no_text.pdf").read_bytes(), "warstwy tekstowej"),
        (b"%PDF-1.4\nto nie jest prawdziwy pdf", "uszkodzony"),
        (b"zupelnie nie pdf", "uszkodzony"),
    ],
    ids=["encrypted", "scan", "garbage-header", "not-pdf"],
)
def test_pdf_errors(data, fragment):
    with pytest.raises(IngestError, match=fragment):
        parse_file("x.pdf", data)


def test_pdf_two_columns_not_interleaved():
    parsed = parse_file("c.pdf", (FIXTURES / "two_columns.pdf").read_bytes())
    left, right = "Lewa kolumna opisuje rzekę Wisłę i jej dopływy.", "Right column describes"
    assert parsed.text.count(left) == 8
    assert parsed.text.index(right) > parsed.text.rindex(left)


# --------------------------------------------------------------------------- #
# Czyszczenie (jednostkowo, bez PDF)
# --------------------------------------------------------------------------- #
LONG = "x" * 60


def test_dehyphenation():
    joined = join_lines(["To jest elektro-", "mobilność w mieście."])
    assert joined == "To jest elektromobilność w mieście."
    # wielka litera po dywizie => prawdziwy łącznik, zostaje
    joined = join_lines(["Maria Skłodowska-", "Curie była uczoną."])
    assert joined == "Maria Skłodowska-Curie była uczoną."


def test_paragraphs_from_blank_lines_and_short_lines():
    lines = [f"{LONG} a", f"{LONG} koniec.", "", f"{LONG} b", "krótka linia.", f"Nowy {LONG}"]
    assert join_lines(lines) == f"{LONG} a {LONG} koniec.\n\n{LONG} b krótka linia.\n\nNowy {LONG}"


def test_headers_footers_and_page_numbers_removed():
    words = ["alfa", "beta", "gamma", "delta"]
    pages = [
        f"Raport roczny 2026\n\n{LONG} {w} treść.\n\n{i}" if i % 2 else
        f"Raport roczny 2026\n{LONG} {w} treść.\nStrona {i} z 4"
        for i, w in enumerate(words, start=1)
    ]
    text = clean_pdf_pages(pages)
    assert "Raport roczny" not in text and "z 4" not in text
    assert all(f"{w} treść." in text for w in words)
    assert not any(ch.isdigit() for ch in text)  # numery stron usunięte


def test_header_on_single_page_is_kept():
    assert "Tytuł dokumentu" in clean_pdf_pages(["Tytuł dokumentu\n\nTreść."])


def test_ligatures_and_soft_hyphens():
    assert clean_pdf_pages(["ﬁrma ﬂota pro­gram"]) == "firma flota program"


def test_multicolumn_detection():
    assert looks_multicolumn("\n".join(["Lewa kolumna tekstu          Prawa kolumna"] * 6))
    assert not looks_multicolumn("\n".join(["Zwykła linia tekstu ciągłego bez przerw"] * 6))


# --------------------------------------------------------------------------- #
# Język
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name_data", list(iter_sample_files()), ids=lambda nd: nd[0])
def test_sample_language_detection(name_data):
    name, data = name_data
    assert detect_language(parse_file(name, data).text) == name[:2]


# --------------------------------------------------------------------------- #
# Integracja z fasadą
# --------------------------------------------------------------------------- #
def test_pdf_through_services():
    from edt.services import build_services

    services = build_services(load_samples=False)
    data = (ROOT / "data" / "sample" / SAMPLE_PDFS[0]).read_bytes()
    result = services.ingest_file(SAMPLE_PDFS[0], data)
    assert result.ok, result.error
    doc = result.document
    assert (doc.source_type, doc.num_pages, doc.language) == (SourceType.PDF, 3, "pl")
    assert doc.size_bytes == len(data) and doc.metadata["author"] == "Zespół EDT"
    hits = services.search("keyword", "heliocentryczny")
    assert hits and hits[0].doc_id == doc.id

    bad = services.ingest_file("skan.pdf", (FIXTURES / "no_text.pdf").read_bytes())
    assert not bad.ok and "warstwy tekstowej" in bad.error
