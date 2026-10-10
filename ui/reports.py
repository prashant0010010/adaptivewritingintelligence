import pandas as pd
import streamlit as st

from config.settings import GENRES
from core.evaluation import DEFAULT_METHODS, SYNTHETIC_CASES, run_evaluation
from core.profile_learning import active_preferences
from core.revision_engine import RevisionContext
from database.db import backup_db
from providers.base import ProviderError
from ui.common import Ctx, consent_gate, get_provider, require_profile
from utils.export import build_report_markdown, markdown_to_docx_bytes, markdown_to_text


def render(ctx: Ctx):
    st.header("Reports, evaluation and data")
    if not require_profile(ctx):
        return
    t1, t2, t3 = st.tabs(["Report", "Evaluation", "Data and backup"])
    with t1:
        md = build_report_markdown(ctx.repo, ctx.profile_id)
        st.caption("Observed measurements, stated preferences and learned estimates are labelled separately.")
        st.markdown(md)
        c = st.columns(3)
        name = ctx.profile["name"].replace(" ", "_")
        c[0].download_button("Download Markdown", md, f"report_{name}.md", "text/markdown")
        c[1].download_button("Download TXT", markdown_to_text(md), f"report_{name}.txt", "text/plain")
        try:
            c[2].download_button("Download DOCX", markdown_to_docx_bytes(md), f"report_{name}.docx",
                                 "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        except Exception as e:  # python-docx problem should not break the page
            c[2].write(f"DOCX export unavailable: {e}")
    with t2:
        _evaluation(ctx)
    with t3:
        st.write(f"Data folder: `{ctx.settings.data_dir}`")
        st.write(f"Database: `{ctx.settings.db_path}`  |  Backups: `{ctx.settings.backup_dir}`  |  Logs: `{ctx.settings.log_dir}` (no user text is logged)")
        if st.button("Create a database backup now"):
            path = backup_db(ctx.settings.db_path, ctx.settings.backup_dir)
            st.success(f"Backup written to {path}")
        st.caption("Restoring: close the app, then follow the README section 'Back up and reset'.")


def _evaluation(ctx: Ctx):
    st.warning("Built-in cases are synthetic demonstrations. With the demo provider they only check that the pipeline runs. "
               "Results are not evidence that this app beats any other tool. To compare tools fairly, give each the same text, the same objective "
               "and the same instructions, then inspect the outputs yourself.")
    with st.expander("Add your own benchmark case (only text you have permission to use)"):
        with st.form("bench", clear_on_submit=True):
            t = st.text_input("Title")
            g = st.selectbox("Genre", GENRES, key="bench_genre")
            tx = st.text_area("Text")
            if st.form_submit_button("Add case") and t.strip() and tx.strip():
                ctx.repo.add_benchmark_case(ctx.profile_id, t, g, tx)
                st.rerun()
        for c in ctx.repo.list_benchmark_cases(ctx.profile_id):
            a, b = st.columns([6, 1])
            a.write(c["title"])
            if b.button("Delete", key=f"bc_{c['id']}"):
                ctx.repo.delete_benchmark_case(ctx.profile_id, c["id"])
                st.rerun()
    cases = list(SYNTHETIC_CASES) + [{"title": c["title"], "genre": c["genre"], "text": c["text"]} for c in ctx.repo.list_benchmark_cases(ctx.profile_id)]
    chosen = st.multiselect("Cases", [c["title"] for c in cases], default=[c["title"] for c in cases][:3])
    cases = [c for c in cases if c["title"] in chosen]
    provider = get_provider(ctx)
    n_calls = sum(1 for m in DEFAULT_METHODS if m[1]) * len(cases)
    ok = consent_gate(provider, f"{len(cases)} case text(s) in {n_calls} requests", sum(len(c["text"]) for c in cases) * max(1, n_calls // max(1, len(cases))), "consent_eval")
    if st.button("Run evaluation", disabled=not (ok and cases)):
        genre = cases[0]["genre"]
        ctx_r = RevisionContext(ctx.repo.get_onboarding(ctx.profile_id), active_preferences(ctx.repo, ctx.profile_id, genre),
                                [a["phrase"] for a in ctx.repo.list_avoid_phrases(ctx.profile_id)], [])
        profile_text = "\n\n".join(s["text"] for s in ctx.repo.list_samples(ctx.profile_id, learning_only=True))
        rows = run_evaluation(provider, cases, DEFAULT_METHODS, ctx_r, profile_text)
        st.session_state["eval_rows"] = rows
    rows = st.session_state.get("eval_rows")
    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, hide_index=True, use_container_width=True)
        st.caption("Columns are deterministic checks (see docs/ARCHITECTURE.md). 'warnings' counts items to inspect, not errors. Add your own ratings on the revision page for user-judged similarity and satisfaction.")
        if st.button("Save results to reports"):
            cols = [c for c in df.columns if c != "error"]
            md = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n" + "\n".join("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows)
            md += f"\n\nProvider: {provider.name if provider else 'none'}. Synthetic or user-supplied cases; not evidence of general quality."
            ctx.repo.save_report(ctx.profile_id, "evaluation", "Evaluation run", md)
            st.success("Saved.")
