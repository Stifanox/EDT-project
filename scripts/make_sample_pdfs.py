"""Generuje przykładowe i testowe pliki PDF (etap D1). Wynik jest commitowany do repo.

    python scripts/make_sample_pdfs.py [--font /ścieżka/DejaVuSans.ttf]

Tworzy:
  data/sample/pl_07_mikolaj_kopernik.pdf   – 3 strony, nagłówek/stopka, przeniesienia wyrazów
  data/sample/en_05_vistula_river.pdf      – 2 strony
  tests/fixtures/pdf/*.expected.txt        – tekst źródłowy (akapity) do porównania w testach
  tests/fixtures/pdf/encrypted.pdf         – hasło użytkownika => nieczytelny
  tests/fixtures/pdf/owner_only.pdf        – tylko hasło właściciela => czytelny
  tests/fixtures/pdf/no_text.pdf           – sama grafika (jak skan)

Wymaga: fpdf2 (requirements-dev.txt) i czcionki TTF z polskimi znakami.
"""

from __future__ import annotations

import argparse
import subprocess
import warnings
from datetime import UTC, datetime
from pathlib import Path

from fpdf import FPDF

warnings.filterwarnings("ignore", message="Dimensions for page format")

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "data" / "sample"
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "pdf"
FIXED_DATE = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)  # powtarzalne pliki

KOPERNIK = (
    "Mikołaj Kopernik i przewrót heliocentryczny",
    [
        "Mikołaj Kopernik urodził się 19 lutego 1473 roku w Toruniu w rodzinie kupieckiej. "
        "Po śmierci ojca opiekę nad nim przejął wuj, Łukasz Watzenrode, późniejszy biskup "
        "warmiński, który zadbał o staranne wykształcenie siostrzeńca.",
        "W latach 1491–1495 Kopernik studiował w Akademii Krakowskiej, gdzie zetknął się "
        "z astronomią i matematyką. Następnie wyjechał do Włoch: kształcił się w Bolonii "
        "i Padwie, a w 1503 roku uzyskał w Ferrarze doktorat z prawa kanonicznego. "
        "Podczas pobytu we Włoszech prowadził obserwacje nieba i zapoznał się z pracami "
        "starożytnych autorów, którzy rozważali ruch Ziemi.",
        "Po powrocie na Warmię pracował jako lekarz, administrator dóbr kapituły i kanonik "
        "we Fromborku. Zajmował się również ekonomią: w traktacie o monecie opisał zjawisko "
        "wypierania lepszego pieniądza przez gorszy, nazywane później prawem Kopernika-Greshama. "
        "W czasie wojny z zakonem krzyżackim organizował obronę zamku w Olsztynie.",
        "Główne dzieło astronoma, traktat „O obrotach sfer niebieskich”, ukazało się drukiem "
        "w Norymberdze w 1543 roku. Kopernik przedstawił w nim model heliocentryczny, "
        "w którym Ziemia i pozostałe planety krążą wokół Słońca, a Ziemia dodatkowo obraca "
        "się wokół własnej osi. Teoria ta zakwestionowała obowiązujący od starożytności "
        "geocentryczny system Ptolemeusza i stała się fundamentem nowożytnej astronomii, "
        "rozwijanej później przez Galileusza, Johannesa Keplera i Isaaca Newtona.",
        "Kopernik zmarł 24 maja 1543 roku we Fromborku. Według tradycji egzemplarz "
        "wydrukowanej księgi otrzymał tuż przed śmiercią. W 2005 roku w katedrze fromborskiej "
        "odnaleziono szczątki, które dzięki badaniom genetycznym zidentyfikowano jako należące "
        "do astronoma, a w 2010 roku pochowano je ponownie w katedrze.",
        "Imię Kopernika nosi dziś między innymi Uniwersytet Mikołaja Kopernika w Toruniu, "
        "warszawskie Centrum Nauki Kopernik oraz pierwiastek chemiczny kopernik o liczbie "
        "atomowej 112, nazwany tak przez Międzynarodową Unię Chemii Czystej i Stosowanej.",
    ],
    "Materiały przykładowe EDT – historia nauki",
    "Strona {n}",
    {"title": "Mikołaj Kopernik i przewrót heliocentryczny", "author": "Zespół EDT"},
)

VISTULA = (
    "The Vistula River",
    [
        "The Vistula is the longest river in Poland, flowing for just over one thousand "
        "kilometres from its source on Barania Góra in the Silesian Beskids to the Gdańsk "
        "Bay of the Baltic Sea. Its drainage basin covers more than half of the territory "
        "of Poland.",
        "Along its course the river passes many historic cities, including Kraków, "
        "Sandomierz, Warsaw, Płock, Toruń and Grudziądz. In Kraków it flows beneath Wawel "
        "Hill, the seat of Polish kings for centuries, while in Warsaw it separates the "
        "Old Town from the district of Praga.",
        "For hundreds of years the Vistula was a major trade route. Grain from the fertile "
        "lands of the Polish-Lithuanian Commonwealth was floated downstream to Gdańsk and "
        "shipped to Amsterdam and other ports of Western Europe, which brought great wealth "
        "to merchants and the nobility.",
        "Today large stretches of the river remain relatively natural, with sandbanks and "
        "islands that provide habitats for birds such as terns and little ringed plovers. "
        "Many sections are protected within the European Union's Natura 2000 network. "
        "Floods remain a serious risk: the catastrophic flood of May and June 2010 affected "
        "towns along the middle and lower Vistula.",
    ],
    "EDT sample materials – geography",
    "Page {n} of {{nb}}",
    {"title": "The Vistula River", "author": "EDT Team"},
)


class SamplePDF(FPDF):
    def __init__(self, font: Path, header_text: str, footer_fmt: str) -> None:
        super().__init__(format="A5")
        self.add_font("body", "", str(font))
        self.add_font("body", "B", str(font.with_name(font.stem + "-Bold" + font.suffix)))
        self.header_text, self.footer_fmt = header_text, footer_fmt
        self.set_margins(16, 14, 16)
        self.set_auto_page_break(True, margin=18)
        self.set_creation_date(FIXED_DATE)

    def header(self) -> None:
        self.set_font("body", "", 9)
        self.cell(0, 6, self.header_text, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(6)

    def footer(self) -> None:
        self.set_y(-13)
        self.set_font("body", "", 9)
        self.cell(0, 8, self.footer_fmt.format(n=self.page_no()), align="C")


def wrap_with_hyphenation(pdf: FPDF, text: str, width: float) -> list[str]:
    """Łamanie linii z przenoszeniem długich wyrazów (dywiz), jak w składzie książkowym."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if pdf.get_string_width(candidate) <= width:
            current = candidate
            continue
        if current and len(word) >= 8 and "-" not in word:
            for cut in range(len(word) - 3, 2, -1):
                head = word[:cut]
                if head.isalpha() and pdf.get_string_width(f"{current} {head}-") <= width:
                    lines.append(f"{current} {head}-")
                    current = word[cut:]
                    break
            else:
                lines.append(current)
                current = word
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def build_document(font: Path, spec, out: Path, font_size: float, line_h: float) -> None:
    title, paragraphs, header_text, footer_fmt, meta = spec
    pdf = SamplePDF(font, header_text, footer_fmt)
    pdf.set_title(meta["title"])
    pdf.set_author(meta["author"])
    pdf.alias_nb_pages("{nb}")
    pdf.add_page()
    pdf.set_font("body", "B", font_size + 4)
    pdf.cell(0, line_h + 4, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("body", "", font_size)
    width = pdf.w - pdf.l_margin - pdf.r_margin
    for para in paragraphs:
        for line in wrap_with_hyphenation(pdf, para, width):
            pdf.cell(0, line_h, line, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(line_h / 2)
    pdf.output(str(out))
    expected = FIXTURE_DIR / (out.stem + ".expected.txt")
    expected.write_text("\n\n".join([title, *paragraphs]) + "\n", encoding="utf-8")
    print(f"  {out.relative_to(ROOT)}  ({pdf.page_no()} str.)")


def build_fixtures(font: Path) -> None:
    def simple(text: str) -> FPDF:
        pdf = FPDF()
        pdf.add_font("body", "", str(font))
        pdf.set_creation_date(FIXED_DATE)
        pdf.add_page()
        pdf.set_font("body", "", 12)
        pdf.multi_cell(0, 8, text)
        return pdf

    pdf = simple("Tajny dokument zabezpieczony hasłem użytkownika.")
    pdf.set_encryption(owner_password="owner", user_password="secret")
    pdf.output(str(FIXTURE_DIR / "encrypted.pdf"))

    pdf = simple("Dokument z hasłem właściciela – można go czytać bez hasła. Zażółć gęślą jaźń.")
    pdf.set_encryption(owner_password="owner")
    pdf.output(str(FIXTURE_DIR / "owner_only.pdf"))

    pdf = FPDF()
    pdf.set_creation_date(FIXED_DATE)
    pdf.add_page()
    pdf.set_fill_color(200, 200, 200)
    pdf.rect(20, 20, 170, 250, style="F")  # „skan”: tylko grafika, brak warstwy tekstowej
    pdf.output(str(FIXTURE_DIR / "no_text.pdf"))

    # dwie kolumny – tryb `layout` skleiłby je w poprzek, parser musi przejść na tryb zwykły
    pdf = FPDF()
    pdf.add_font("body", "", str(font))
    pdf.set_creation_date(FIXED_DATE)
    pdf.add_page()
    pdf.set_font("body", "", 11)
    left = " ".join(["Lewa kolumna opisuje rzekę Wisłę i jej dopływy."] * 8)
    right = " ".join(["Right column describes the Baltic Sea coast."] * 8)
    for x, text in ((15, left), (110, right)):
        pdf.set_xy(x, 20)
        pdf.multi_cell(85, 6, text)
    pdf.output(str(FIXTURE_DIR / "two_columns.pdf"))
    print(f"  {FIXTURE_DIR.relative_to(ROOT)}/{{encrypted,owner_only,no_text,two_columns}}.pdf")


def find_font() -> Path:
    try:
        out = subprocess.run(["fc-match", "-f", "%{file}", "DejaVu Sans"],
                             capture_output=True, text=True, check=True).stdout.strip()
        if out.endswith("DejaVuSans.ttf"):
            return Path(out)
    except (OSError, subprocess.CalledProcessError):
        pass
    for candidate in ("/usr/share/fonts/dejavu/DejaVuSans.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(candidate).exists():
            return Path(candidate)
    raise SystemExit("Nie znaleziono DejaVuSans.ttf – podaj ścieżkę: --font /…/DejaVuSans.ttf")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--font", type=Path,
                        help="DejaVuSans.ttf (obok musi być DejaVuSans-Bold.ttf)")
    args = parser.parse_args()
    font = args.font or find_font()
    if not font.with_name(font.stem + "-Bold" + font.suffix).exists():
        raise SystemExit(f"Brak wariantu Bold obok {font}")
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Czcionka: {font}")
    build_document(font, KOPERNIK, SAMPLE_DIR / "pl_07_mikolaj_kopernik.pdf", 12, 7.5)
    build_document(font, VISTULA, SAMPLE_DIR / "en_05_vistula_river.pdf", 12, 7.5)
    build_fixtures(font)


if __name__ == "__main__":
    main()
