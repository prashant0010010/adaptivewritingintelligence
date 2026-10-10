"""Headless end-to-end run of the Streamlit app (no browser, no network, demo provider only)."""
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from pathlib import Path  # noqa: E402

from ui.common import MODE_DEMO  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "app.py")

PAGES = ["Dashboard", "Profiles", "Writing samples", "Profile laboratory", "Reasoning and revision", "History", "Reports and evaluation"]
TEXT = ("Social media is very popular among students. Basically, many students check it between lectures, and this may reduce focused study "
        "in order to save time. However, the report compares two groups of students over one term. Therefore, universities should act.")


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("AWI_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return AppTest.from_file(APP, default_timeout=60)


def goto(at, page):
    next(r for r in at.sidebar.radio if r.label == "Go to").set_value(page).run()
    return at


def test_all_pages_open_without_profile_or_key(app):
    at = app.run()
    assert not at.exception
    for p in PAGES:
        assert not goto(at, p).exception, p


def test_full_flow_with_demo_provider(app):
    at = app.run()
    from config.settings import get_settings
    from database.repository import Repository
    repo = Repository(get_settings().db_path)
    pid = repo.create_profile("Smoke")
    repo.add_sample(pid, "s1", "Academic report", TEXT * 3)
    at = app.run()
    for p in PAGES:
        assert not goto(at, p).exception, p
    next(r for r in at.sidebar.radio if r.label == "Language model mode").set_value(MODE_DEMO).run()
    goto(at, "Reasoning and revision")
    at.text_area(key="rev_draft").set_value(TEXT).run()
    next(b for b in at.button if b.label == "Generate").click().run()
    assert not at.exception
    assert repo.counts(pid)["drafts"] == 1 and repo.counts(pid)["revisions"] == 1
    next(b for b in at.button if b.label == "Accept as is").click().run()
    assert not at.exception
    c = repo.counts(pid)
    assert c["feedback"] == 1 and c["revisions"] == 2
    for p in ("History", "Reports and evaluation"):
        assert not goto(at, p).exception, p
