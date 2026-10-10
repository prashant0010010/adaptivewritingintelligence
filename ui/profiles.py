import streamlit as st

from config.settings import GENRES
from core.profile_learning import DIMENSIONS, aggregate, reset_learned_preference, set_user_preference
from database.db import DatabaseError
from ui.common import Ctx
from utils.export import export_preferences_json

QUESTIONS = [
    ("types", "What types of writing do you produce?", "text"),
    ("audience", "Who is your usual audience?", "text"),
    ("detail", "Direct explanations or more developed discussion?", ["", "Direct and concise", "Balanced", "Developed discussion"]),
    ("support", "How do you normally support a claim?", "text"),
    ("after_concept", "How much explanation do you want after introducing a concept?", ["", "One sentence", "A short paragraph", "Extended explanation"]),
    ("counterarguments", "How do you prefer to handle counterarguments?", "text"),
    ("feels_unlike_me", "What kinds of revisions feel unlike your own writing?", "text"),
    ("preserve", "What should the system preserve when revising your work?", "text"),
]


def render(ctx: Ctx):
    st.header("Profiles and preferences")
    st.caption("Profiles separate data inside this app. They are not a security boundary: anyone with access to this computer account can open the database file.")
    t1, t2, t3 = st.tabs(["Profiles", "Onboarding", "Preferences"])
    with t1:
        with st.form("new_profile", clear_on_submit=True):
            name = st.text_input("New profile name")
            notes = st.text_area("Notes (optional)", height=70)
            if st.form_submit_button("Create profile"):
                try:
                    pid = ctx.repo.create_profile(name, notes)
                    st.session_state["profile_id"] = pid
                    st.rerun()
                except DatabaseError as e:
                    st.error(str(e))
        for p in ctx.repo.list_profiles():
            st.write(f"**{p['name']}** (created {p['created_at'][:10]})" + ("  (active)" if p["id"] == ctx.profile_id else ""))
        if ctx.profile_id:
            with st.expander("Rename or delete the active profile"):
                new_name = st.text_input("Name", value=ctx.profile["name"], key="ren_name")
                new_notes = st.text_area("Notes", value=ctx.profile["notes"], key="ren_notes")
                if st.button("Save name and notes"):
                    try:
                        ctx.repo.rename_profile(ctx.profile_id, new_name, new_notes)
                        st.rerun()
                    except DatabaseError as e:
                        st.error(str(e))
                st.error("Deleting removes this profile's samples, drafts, revisions, feedback and preferences permanently.")
                if st.checkbox("I understand this cannot be undone", key="del_ok") and st.button("Delete profile"):
                    ctx.repo.delete_profile(ctx.profile_id)
                    st.session_state.pop("profile_id", None)
                    st.rerun()
    if ctx.profile_id is None:
        return
    with t2:
        st.write("Every question is optional. Only what you type is stored; nothing is inferred.")
        existing = ctx.repo.get_onboarding(ctx.profile_id)
        answers = {}
        with st.form("onboarding"):
            for key, label, kind in QUESTIONS:
                if kind == "text":
                    answers[key] = st.text_input(label, value=existing.get(key, ""), key=f"ob_{key}")
                else:
                    cur = existing.get(key, "")
                    answers[key] = st.selectbox(label, kind, index=kind.index(cur) if cur in kind else 0, key=f"ob_{key}")
            if st.form_submit_button("Save answers"):
                ctx.repo.save_onboarding(ctx.profile_id, answers)
                st.success("Saved. Clear a field and save to remove that answer.")
    with t3:
        genre = st.selectbox("Genre", GENRES, key="pref_genre")
        prefs = {p["key"]: p for p in ctx.repo.get_preferences(ctx.profile_id, genre)}
        stats = aggregate(ctx.repo.list_feedback(ctx.profile_id, genre))
        st.caption("Learned preferences are estimates counted from your accept/edit/reject decisions. They become active only after at least 3 informative decisions that mostly agree.")
        for dim, spec in DIMENSIONS.items():
            p, s = prefs.get(dim), stats[dim]
            cols = st.columns([3, 2, 2, 2])
            active = f"{p['value']} ({p['source']})" if p and p["value"] else "none"
            cols[0].write(f"**{dim.replace('_', ' ')}**: {spec['text']}")
            cols[1].write(f"Active: {active}")
            cols[2].write(f"Evidence: {s['informative_events']} events, agreement {s['agreement']}")
            options = ["(not set)"] + list(spec["labels"].values())
            choice = cols[3].selectbox("Set", options, key=f"set_{genre}_{dim}", label_visibility="collapsed")
            b1, b2 = st.columns(2)
            if b1.button("Apply my choice", key=f"apply_{genre}_{dim}") and choice != "(not set)":
                set_user_preference(ctx.repo, ctx.profile_id, genre, dim, choice)
                st.rerun()
            if b2.button("Reset (forget earlier feedback for this)", key=f"reset_{genre}_{dim}"):
                reset_learned_preference(ctx.repo, ctx.profile_id, genre, dim)
                st.rerun()
        st.subheader("Phrases to avoid")
        new_phrase = st.text_input("Add a phrase or behaviour to avoid", key="new_avoid")
        if st.button("Add") and new_phrase.strip():
            ctx.repo.add_avoid_phrase(ctx.profile_id, new_phrase)
            ctx.repo.snapshot_preferences(ctx.profile_id, f"Added avoid phrase: {new_phrase.strip()}")
            st.rerun()
        for a in ctx.repo.list_avoid_phrases(ctx.profile_id):
            if st.button(f"Remove: {a['phrase']}", key=f"rm_{a['id']}"):
                ctx.repo.delete_avoid_phrase(ctx.profile_id, a["phrase"])
                ctx.repo.snapshot_preferences(ctx.profile_id, f"Removed avoid phrase: {a['phrase']}")
                st.rerun()
        st.subheader("Version history")
        versions = ctx.repo.list_preference_versions(ctx.profile_id)
        for v in versions[:10]:
            c1, c2 = st.columns([5, 1])
            c1.write(f"v{v['version']} ({v['created_at'][:16]}): {v['change_note']}")
            if c2.button("Restore", key=f"rest_{v['version']}"):
                ctx.repo.restore_preference_version(ctx.profile_id, v["version"])
                st.rerun()
        if not versions:
            st.write("No changes yet.")
        st.download_button("Export preferences (JSON)", export_preferences_json(ctx.repo, ctx.profile_id), "preferences.json", "application/json")
