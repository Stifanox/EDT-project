"""Test dymny GUI: każda strona musi się wyrenderować bez wyjątku (na korpusie przykładowym)."""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["app.py", *sorted(str(p.relative_to(ROOT)) for p in (ROOT / "pages").glob("*.py"))]


@pytest.fixture(autouse=True)
def _load_samples(monkeypatch):
    monkeypatch.setattr("edt.config.LOAD_SAMPLES_IF_EMPTY", True)


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page):
    at = AppTest.from_file(str(ROOT / page), default_timeout=60)
    at.run()
    assert not at.exception, at.exception


def test_search_page_with_query():
    at = AppTest.from_file(str(ROOT / "pages/2_Wyszukiwarka.py"), default_timeout=60)
    at.run()
    at.text_input[0].input("samochody elektryczne").run()
    assert not at.exception, at.exception
    assert any("pl_01_samochody_elektryczne" in m.value for m in at.markdown)
