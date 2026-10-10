import json

import streamlit as st

from ui.common import Ctx, require_profile
from utils.text_processing import change_summary, diff_html

KIND = {"generated": "Generated revision", "user_edited": "Your edited revision", "accepted_final": "Accepted final"}


def render(ctx: Ctx):
    st.header("Comparison and version history")
    if not require_profile(ctx):
        return
    drafts = ctx.repo.list_drafts(ctx.profile_id, 100)
    if not drafts:
        st.info("No drafts yet. Generate a revision first.")
        return
    d = st.selectbox("Draft", drafts, format_func=lambda x: f"{x['title']} ({x['genre']}, {x['created_at'][:16]})")
    revs = ctx.repo.list_revisions(ctx.profile_id, d["id"])
    versions = [("Original draft", d["original_text"], "original")]
    for r in revs:
        versions.append((f"{KIND[r['kind']]} #{r['id']} [{r['status']}, mode {r['mode']}, {r['created_at'][11:16]}]", r["text"], r["kind"]))
    st.write("**Version chain**")
    for label, _, _ in versions:
        st.write(f"- {label}")
    labels = [v[0] for v in versions]
    c1, c2 = st.columns(2)
    a = c1.selectbox("Compare", labels, index=0)
    b = c2.selectbox("With", labels, index=len(labels) - 1)
    ta, tb = versions[labels.index(a)][1], versions[labels.index(b)][1]
    cs = change_summary(ta, tb)
    st.write(f"Words {cs['words_original']} -> {cs['words_revised']} ({cs['word_difference']:+d}); added {cs['words_added']}, removed {cs['words_removed']}; "
             f"sentences {cs['sentences_original']} -> {cs['sentences_revised']}.")
    st.markdown(diff_html(ta, tb), unsafe_allow_html=True)
    ql = [r for r in revs if r["text"] == tb and r["quality_json"] != "{}"]
    if ql:
        q = json.loads(ql[0]["quality_json"])
        st.caption(f"Stored quality checks for the selected version: {q.get('warnings', 0)} item(s) flagged at generation time.")
    if st.button("Restore selected 'With' version into the revision workspace"):
        st.session_state["pending_draft"] = tb
        st.success("Copied. Open the Reasoning and revision page: it is now in the draft box. Nothing was overwritten.")
    if st.checkbox("Confirm deleting this draft and its versions", key="del_draft_ok") and st.button("Delete draft"):
        ctx.repo.delete_draft(ctx.profile_id, d["id"])
        st.rerun()
