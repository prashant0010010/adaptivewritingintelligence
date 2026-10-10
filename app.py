"""Adaptive Writing Intelligence: Streamlit entry point.  Run:  streamlit run app.py"""
import streamlit as st

from config.settings import get_settings
from database.db import DatabaseError, init_db
from database.repository import Repository
from ui import dashboard, history, profile_lab, profiles, reports, samples, writing_lab
from ui.common import Ctx, available_modes, MODE_LOCAL
from utils.logging_config import setup_logging

PAGES = {
    "Dashboard": dashboard,
    "Profiles": profiles,
    "Writing samples": samples,
    "Profile laboratory": profile_lab,
    "Reasoning and revision": writing_lab,
    "History": history,
    "Reports and evaluation": reports,
}


def main():
    st.set_page_config(page_title="Adaptive Writing Intelligence", layout="wide")
    settings = get_settings()
    try:
        settings.ensure_dirs()
        setup_logging(settings.log_dir)
        init_db(settings.db_path)
    except (DatabaseError, OSError) as exc:
        st.error(f"The application could not start its local storage: {exc}")
        st.stop()
    repo = Repository(settings.db_path)

    st.sidebar.title("Adaptive Writing Intelligence")
    profs = repo.list_profiles()
    pid = st.session_state.get("profile_id")
    if profs:
        ids = [p["id"] for p in profs]
        if pid not in ids:
            pid = ids[0]
        pid = st.sidebar.selectbox("Active profile", ids, index=ids.index(pid), format_func=lambda i: next(p["name"] for p in profs if p["id"] == i))
        st.session_state["profile_id"] = pid
    else:
        pid = None
        st.sidebar.info("No profile yet.")
    modes = available_modes(settings)
    if st.session_state.get("llm_mode") not in modes:
        st.session_state["llm_mode"] = MODE_LOCAL
    st.sidebar.radio("Language model mode", modes, key="llm_mode")
    if not settings.gemini_configured:
        st.sidebar.caption("Gemini unavailable: no GEMINI_API_KEY in .env.")
    page = st.sidebar.radio("Go to", list(PAGES))
    ctx = Ctx(settings, repo, pid, repo.get_profile(pid) if pid else None)
    try:
        PAGES[page].render(ctx)
    except DatabaseError as exc:
        st.error(str(exc))


main()
