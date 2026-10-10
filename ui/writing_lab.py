import json

import pandas as pd
import streamlit as st

from config.settings import GENRES
from core.argument_analysis import analyse_argument, llm_analyse_argument
from core.profile_learning import active_preferences, record_feedback
from core.quality_checks import run_quality_checks
from core.retrieval import retrieve_examples
from core.revision_engine import MODES, RevisionContext, generate_revision, plan_revision
from database.db import DatabaseError
from providers.base import ProviderError
from ui.common import Ctx, consent_gate, get_provider, require_profile
from utils.text_processing import change_summary, diff_html, normalise_whitespace, word_count

RATINGS = ["No rating", 1, 2, 3, 4, 5]


def render(ctx: Ctx):
    st.header("Reasoning and revision workspace")
    if not require_profile(ctx):
        return
    if "pending_draft" in st.session_state:
        st.session_state["rev_draft"] = st.session_state.pop("pending_draft")
    t1, t2 = st.tabs(["Reasoning analysis", "Revise"])
    with t1:
        _reasoning(ctx)
    with t2:
        _revise(ctx)


def _reasoning(ctx: Ctx):
    st.caption("Local analysis looks for wording cues (because, for example, however...). It cannot understand meaning, so treat flags as prompts to check, not verdicts.")
    text = st.text_area("Passage to analyse", height=220, key="rz_text")
    if st.button("Run local analysis", disabled=not text.strip()):
        st.session_state["rz_local"] = analyse_argument(text)
    res = st.session_state.get("rz_local")
    if res and text.strip():
        cols = st.columns(4)
        cols[0].metric("Sentences", len(res["sentences"]))
        cols[1].metric("Claim cues", res["totals"]["claim"])
        cols[2].metric("Support cues", res["totals"]["explanation"] + res["totals"]["example"] + res["totals"]["evidence"])
        cols[3].metric("Without any cue", res["unlabelled_sentences"])
        st.write("**Things to check**")
        if res["flags"]:
            st.dataframe(pd.DataFrame(res["flags"])[["paragraph", "type", "note"]], hide_index=True, use_container_width=True)
        else:
            st.write("Nothing flagged by the heuristics. That is not proof the argument is complete.")
        if any(f.get("needs_author_input") for f in res["flags"]):
            st.info("Some flags need information only you can supply (sources, data). The app will not invent it.")
        st.write("**Sentence labels (editable: correct any label that is wrong)**")
        df = pd.DataFrame([{"paragraph": s["paragraph"], "sentence": s["sentence"], "labels": ", ".join(s["labels"])} for s in res["sentences"]])
        edited = st.data_editor(df, hide_index=True, use_container_width=True, disabled=["paragraph", "sentence"], key="rz_editor")
        if st.button("Save analysis with my corrections"):
            md = "\n".join(f"- P{r.paragraph}: {r.sentence[:90]}... [{r.labels or 'no label'}]" for r in edited.itertuples())
            md += "\n\nFlags:\n" + "\n".join(f"- P{f['paragraph']} {f['type']}: {f['note']}" for f in res["flags"])
            ctx.repo.save_report(ctx.profile_id, "argument", f"Argument analysis ({word_count(text)} words, user-corrected labels)", md, {"flags": res["flags"]})
            st.success("Saved. It will appear in reports.")
    st.divider()
    st.write("**Model-based analysis (estimates)**")
    provider = get_provider(ctx)
    ok = consent_gate(provider, "this passage", len(text), "consent_rz")
    if st.button("Analyse with language model", disabled=not (ok and text.strip())):
        try:
            with st.spinner("Analysing..."):
                st.session_state["rz_llm"] = llm_analyse_argument(provider, text)
        except ProviderError as e:
            st.error(str(e))
    llm = st.session_state.get("rz_llm")
    if llm and text.strip():
        st.warning("Model estimate: may be wrong or miss implicit reasoning. Check each item against your text.")
        for k, v in llm.items():
            st.markdown(f"**{k.replace('_', ' ').capitalize()}**")
            if isinstance(v, list):
                for item in v:
                    st.write(f"- {item}")
                if not v:
                    st.write("_none reported_")
            else:
                st.write(v or "_none reported_")


def _revise(ctx: Ctx):
    repo, pid = ctx.repo, ctx.profile_id
    c1, c2, c3 = st.columns([2, 2, 3])
    genre = c1.selectbox("Genre", GENRES, key="rev_genre")
    title = c2.text_input("Title", key="rev_title")
    mode = c3.selectbox("Revision mode", list(MODES), format_func=lambda m: MODES[m][0], key="rev_mode")
    draft = st.text_area("Draft, outline or idea", height=220, key="rev_draft")
    use_prefs = st.checkbox("Apply my stated and learned preferences", value=True)
    k = st.slider("Approved examples to include (most relevant first)", 0, 3, 2)
    prefs = active_preferences(repo, pid, genre)
    plan = plan_revision(mode, prefs, use_prefs)
    with st.expander("Revision plan", expanded=bool(plan["conflicts"])):
        for s in plan["steps"]:
            st.write(f"- {s}")
        for c in plan["conflicts"]:
            st.warning(c)
        if not use_prefs:
            st.caption("Preferences will not be used.")
    provider = get_provider(ctx)
    onboarding = repo.get_onboarding(pid) if use_prefs else {}
    examples = retrieve_examples(draft, repo.list_examples(pid, "approved"), genre, k) if use_prefs and draft.strip() else []
    avoid = [a["phrase"] for a in repo.list_avoid_phrases(pid)] if use_prefs else []
    rctx = RevisionContext(onboarding, prefs if use_prefs else {}, avoid, examples)
    sent = len(draft) + sum(len(e["text"]) for e in examples) + sum(len(v) for v in onboarding.values())
    st.caption(f"What would be sent: your draft, {len(examples)} approved example passage(s), and your stated preferences.")
    ok = consent_gate(provider, "this draft and the selected context", sent, "consent_rev")
    too_long = len(draft) > ctx.settings.max_input_chars
    if too_long:
        st.error(f"Draft is over the {ctx.settings.max_input_chars:,}-character limit. Revise it in sections.")
    if st.button("Generate", type="primary", disabled=not (ok and draft.strip()) or too_long):
        original = normalise_whitespace(draft)
        try:
            with st.spinner("Working..."):
                res = generate_revision(provider, original, genre, mode, rctx, use_prefs)
            profile_text = "\n\n".join(s["text"] for s in repo.list_samples(pid, genre=genre, learning_only=True))
            quality = run_quality_checks(original, res.revised_text, mode, profile_text) if res.revised_text else {}
            did = repo.create_draft(pid, title, genre, original)
            rid = repo.add_revision(pid, did, "generated", mode, res.revised_text, None,
                                    {"changes": res.changes, "placeholders": res.placeholders, "questions": res.questions, "findings": res.findings},
                                    quality, res.provider, "proposed", res.runtime_seconds)
            st.session_state["rev_state"] = {"draft_id": did, "rev_id": rid, "original": original, "genre": genre, "mode": mode, "res": res.__dict__, "quality": quality, "done": False}
        except (ProviderError, ValueError, DatabaseError) as e:
            st.error(f"Could not generate: {e}")
    state = st.session_state.get("rev_state")
    if state:
        _show_result(ctx, state)


def _show_result(ctx: Ctx, st_):
    repo, pid = ctx.repo, ctx.profile_id
    res, orig = st_["res"], st_["original"]
    st.divider()
    if st_["mode"] == "diagnose":
        st.write("**Findings (no rewrite requested)**")
        for f in res["findings"]:
            st.write(f"- {f}")
        for q in res["questions"]:
            st.write(f"- Question for you: {q}")
        return
    revised = res["revised_text"]
    cs = change_summary(orig, revised)
    st.write(f"**Word count:** {cs['words_original']} -> {cs['words_revised']} ({cs['word_difference']:+d}, {cs['percent_change']}%). "
             f"Added {cs['words_added']}, removed {cs['words_removed']}. Your original is stored unchanged.")
    a, b = st.columns(2)
    a.write("**Original**")
    a.text_area("orig", orig, height=240, disabled=True, label_visibility="collapsed")
    b.write("**Proposed revision (model-generated)**")
    b.text_area("rev", revised, height=240, disabled=True, label_visibility="collapsed")
    with st.expander("Highlighted changes", expanded=True):
        st.markdown(diff_html(orig, revised), unsafe_allow_html=True)
    if res["changes"]:
        st.write("**Significant changes**")
        for c in res["changes"]:
            st.write(f"- {c['change']}" + (f" ({c['reason']})" if c["reason"] else ""))
    for p in res["placeholders"]:
        st.warning(f"Placeholder to complete: {p}")
    for q in res["questions"]:
        st.info(f"Needs your input: {q}")
    q = st_["quality"]
    if q:
        st.write(f"**Quality checks** ({q['warnings']} to inspect). {q['note']}")
        icon = {"pass": "OK", "warn": "CHECK", "info": "INFO"}
        st.dataframe(pd.DataFrame([{"Status": icon[c["status"]], "Check": c["name"], "Detail": c["detail"]} for c in q["checks"]]), hide_index=True, use_container_width=True)
    st.divider()
    if st_["done"]:
        st.success("Feedback recorded. See the History page for the version chain.")
        if st.session_state.get("learn_msg"):
            st.info(st.session_state.pop("learn_msg"))
        return
    st.write("**Your decision**")
    edited = st.text_area("Edit before accepting (optional)", revised, height=200, key="fb_edit")
    reason = st.text_input("Why? (optional)", key="fb_reason")
    avoid = st.text_input("Phrase or behaviour to avoid in future (optional)", key="fb_avoid")
    r1, r2 = st.columns(2)
    style_r = r1.selectbox("How close is this to your own style?", RATINGS, key="fb_style")
    sat_r = r2.selectbox("Satisfaction", RATINGS, key="fb_sat")
    save_ex = st.checkbox("Save the final text as an approved style example", key="fb_saveex")
    save_rej = st.checkbox("If rejected, remember it as a rejected example (never used as a model)", key="fb_saverej")
    sr, sa = (None if style_r == "No rating" else int(style_r)), (None if sat_r == "No rating" else int(sat_r))
    b1, b2, b3 = st.columns(3)
    base = dict(repo=repo, profile_id=pid, revision_id=st_["rev_id"], genre=st_["genre"], mode=st_["mode"], original=orig, reason=reason)
    try:
        if b1.button("Accept as is"):
            repo.add_revision(pid, st_["draft_id"], "accepted_final", st_["mode"], revised, st_["rev_id"], status="accepted")
            repo.set_revision_status(pid, st_["rev_id"], "accepted", sr, sa)
            out = record_feedback(action="accept", final_text=revised, **base)
            _finish(ctx, st_, out, avoid, revised if save_ex else None)
        if b2.button("Accept my edited version"):
            if not edited.strip():
                st.error("The edited text is empty.")
            else:
                action = "accept" if edited.strip() == revised.strip() else "edit"
                repo.add_revision(pid, st_["draft_id"], "user_edited" if action == "edit" else "accepted_final", st_["mode"], edited, st_["rev_id"], status="accepted")
                repo.set_revision_status(pid, st_["rev_id"], "accepted", sr, sa)
                out = record_feedback(action=action, final_text=edited, **base)
                _finish(ctx, st_, out, avoid, edited if save_ex else None)
        if b3.button("Reject"):
            repo.set_revision_status(pid, st_["rev_id"], "rejected", sr, sa)
            if save_rej:
                repo.add_example(pid, st_["genre"], revised, "rejected", st_["rev_id"], reason)
            out = record_feedback(action="reject", final_text=revised, **base)
            _finish(ctx, st_, out, avoid, None)
    except DatabaseError as e:
        st.error(str(e))


def _finish(ctx: Ctx, st_, out: dict, avoid: str, example_text):
    if avoid.strip():
        ctx.repo.add_avoid_phrase(ctx.profile_id, avoid)
        ctx.repo.snapshot_preferences(ctx.profile_id, f"Added avoid phrase: {avoid.strip()}")
    if example_text:
        ctx.repo.add_example(ctx.profile_id, st_["genre"], example_text, "approved", st_["rev_id"])
    st_["done"] = True
    if out["changes"]:
        st.session_state["learn_msg"] = "Preference profile updated: " + "; ".join(out["changes"])
    st.rerun()
