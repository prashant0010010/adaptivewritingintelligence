import pandas as pd
import streamlit as st

from ui.common import Ctx, MODE_GEMINI


def render(ctx: Ctx):
    st.header("Dashboard")
    s = ctx.settings
    if s.gemini_configured:
        st.success(f"Gemini API key found (model: {s.gemini_model}). It is used only when you choose Gemini mode and agree to each send.")
    else:
        st.info("No Gemini API key configured. Local analysis, samples, profiles and reports work. Revision and LLM analysis need a key, or the offline demo provider.")
    if ctx.profile_id is None:
        st.warning("No profile yet. Open **Profiles** to create one.")
        return
    c = ctx.repo.counts(ctx.profile_id)
    st.subheader(f"Profile: {ctx.profile['name']}")
    cols = st.columns(4)
    cols[0].metric("Writing samples", c["samples"])
    cols[1].metric("Approved examples", c["approved_examples"])
    cols[2].metric("Feedback decisions", c["feedback"])
    cols[3].metric("Writing sessions", c["drafts"])
    v = ctx.repo.latest_preference_version(ctx.profile_id)
    st.caption(f"Preference profile version: {v if v else 'none yet (no learned or set preferences)'}. "
               f"{c['samples_in_learning']} of {c['samples']} samples are included in profile analysis.")
    st.subheader("Recent writing sessions")
    drafts = ctx.repo.list_drafts(ctx.profile_id, 8)
    if drafts:
        st.dataframe(pd.DataFrame([{"Title": d["title"], "Genre": d["genre"], "Created": d["created_at"][:16]} for d in drafts]), hide_index=True, use_container_width=True)
    else:
        st.write("None yet.")
    st.subheader("What is available")
    st.markdown("- **Local, always on:** sample library, feature analysis, cue-based argument analysis, quality checks, feedback learning, reports\n"
                "- **Needs a language model:** revisions and the model-based argument analysis (labelled as estimates)\n"
                f"- **Data location:** `{s.data_dir}` (nothing is uploaded unless you consent per request)")
