from datetime import date

import streamlit as st

from config.settings import GENRES
from database.db import DatabaseError
from database.models import SAMPLE_STATUSES
from ui.common import Ctx, require_profile
from utils.document_parser import ExtractionError, extract_text
from utils.text_processing import normalise_whitespace, word_count


def render(ctx: Ctx):
    st.header("Writing samples")
    if not require_profile(ctx):
        return
    st.caption("Samples stay in your local database. They are never sent anywhere by this page.")
    t1, t2 = st.tabs(["Add a sample", "Library"])
    with t1:
        src = st.radio("Source", ["Paste text", "Upload file (TXT, DOCX, PDF)"], horizontal=True)
        key = "sample_text"
        if src.startswith("Upload"):
            up = st.file_uploader("Choose a file", type=["txt", "docx", "pdf"])
            if up is not None and st.session_state.get("_last_upload") != (up.name, up.size):
                try:
                    ex = extract_text(up.name, up.getvalue(), ctx.settings.max_upload_mb)
                    st.session_state[key] = ex.text
                    st.session_state["_extract_warnings"] = ex.warnings
                    st.session_state["_last_upload"] = (up.name, up.size)
                    st.session_state["_sample_title"] = up.name.rsplit(".", 1)[0]
                except ExtractionError as e:
                    st.error(str(e))
                    st.session_state[key] = ""
            for w in st.session_state.get("_extract_warnings", []):
                st.warning(w)
        text = st.text_area("Text (preview and correct extraction mistakes here before saving)", key=key, height=260)
        c1, c2, c3 = st.columns(3)
        title = c1.text_input("Title", value=st.session_state.get("_sample_title", ""))
        genre = c2.selectbox("Genre", GENRES)
        status = c3.selectbox("Representativeness", SAMPLE_STATUSES)
        d = st.date_input("Date written", value=date.today())
        notes = st.text_input("Notes (optional)")
        include = st.checkbox("Include in profile learning", value=True)
        st.caption(f"{word_count(text)} words")
        if st.button("Save sample", type="primary"):
            clean = normalise_whitespace(text)
            if word_count(clean) < 20:
                st.error("Too short to save (under 20 words). Nothing was stored.")
            elif len(clean) > ctx.settings.max_input_chars:
                st.error(f"Too long (limit {ctx.settings.max_input_chars:,} characters). Split it into sections.")
            else:
                try:
                    ctx.repo.add_sample(ctx.profile_id, title, genre, clean, "upload" if src.startswith("Upload") else "paste", status, include, notes, d.isoformat())
                    st.success("Sample saved.")
                    for k in ("_last_upload", "_extract_warnings", "_sample_title"):
                        st.session_state.pop(k, None)
                except DatabaseError as e:
                    st.error(str(e))
    with t2:
        samples = ctx.repo.list_samples(ctx.profile_id)
        if not samples:
            st.write("No samples yet.")
        for s in samples:
            with st.expander(f"{s['title']}  |  {s['genre']}  |  {word_count(s['text'])} words  |  {s['status']}" + ("" if s["include_in_learning"] else "  |  excluded")):
                st.text(s["text"][:1500] + (" ..." if len(s["text"]) > 1500 else ""))
                c1, c2, c3 = st.columns(3)
                new_status = c1.selectbox("Status", SAMPLE_STATUSES, index=SAMPLE_STATUSES.index(s["status"]), key=f"st_{s['id']}")
                inc = c2.checkbox("Include in learning", value=bool(s["include_in_learning"]), key=f"inc_{s['id']}")
                if c3.button("Save changes", key=f"sv_{s['id']}"):
                    ctx.repo.update_sample(ctx.profile_id, s["id"], status=new_status, include_in_learning=int(inc))
                    st.rerun()
                if st.checkbox("Confirm delete", key=f"cd_{s['id']}") and st.button("Delete sample", key=f"del_{s['id']}"):
                    ctx.repo.delete_sample(ctx.profile_id, s["id"])
                    st.rerun()
