import pandas as pd
import streamlit as st

from config.settings import GENRES
from core.writing_analysis import analyse_text, build_genre_profile, style_distance
from database.db import DatabaseError
from ui.common import Ctx, require_profile


def render(ctx: Ctx):
    st.header("Writing profile laboratory")
    if not require_profile(ctx):
        return
    genre = st.selectbox("Genre profile", GENRES, key="lab_genre")
    samples = ctx.repo.list_samples(ctx.profile_id, genre=genre, learning_only=True)
    gp = build_genre_profile(samples)
    if not samples:
        st.info(f"No learning-eligible samples in '{genre}'. Add samples on the Writing samples page. Genres are analysed separately on purpose.")
    else:
        f = gp["features"]
        st.markdown(f"**Observed from {gp['sample_count']} sample(s), {gp['word_count']:,} words.** Evidence level: **{gp['evidence_level']}** "
                    "(a label from amount of text and number of samples, not a probability).")
        if gp["evidence_level"] in ("very limited", "limited"):
            st.warning("Small amounts of text give unstable measurements. Treat the numbers below as rough.")
        c = st.columns(4)
        c[0].metric("Mean sentence length", f["mean_sentence_length"])
        c[1].metric("Sentence length SD", f["sentence_length_sd"] if f["sentence_length_sd"] is not None else "n/a (under 5 sentences)")
        c[2].metric("Vocabulary diversity (MATTR-50)", f["mattr_50"] if f["mattr_50"] is not None else "n/a (under 50 words)")
        c[3].metric("Mean paragraph length", f["mean_paragraph_length"])
        st.caption("MATTR averages the type-token ratio over 50-word windows, which reduces (but does not remove) sensitivity to sample length.")
        l, r = st.columns(2)
        l.write("Sentence length distribution")
        l.bar_chart(pd.Series(f["sentence_length_bins"]))
        r.write("Transitions by function (count)")
        r.bar_chart(pd.Series(f["transition_counts"]))
        c2 = st.columns(3)
        c2[0].metric("Transitions per 100 words", f["transitions_per_100_words"])
        c2[1].metric("Hedging per 100 words", f["hedging_per_100_words"])
        c2[2].metric("Subordinators per sentence", f["subordinators_per_sentence"])
        with st.expander("Punctuation per 1000 words and function words"):
            st.dataframe(pd.DataFrame({"punctuation": f["punctuation_per_1000_words"]}).T, use_container_width=True)
            st.dataframe(pd.DataFrame({"function words": f["function_words_per_1000"]}).T, use_container_width=True)
        with st.expander("Phrases, openers and repeated vocabulary"):
            st.write("Top transitions:", f["top_transitions"])
            st.write("Common sentence openers:", f["top_sentence_openers"])
            st.write("Frequent bigrams:", f["top_bigrams"])
            st.write("Frequent trigrams:", f["top_trigrams"])
            st.write("Repeated content words:", f["repeated_content_words"])
        if gp["stability"]:
            with st.expander("Stability across samples"):
                st.dataframe(pd.DataFrame(gp["stability"]).T)
                st.caption("A large spread between samples means this feature may depend on topic or occasion rather than being a stable habit.")
        if st.button("Save this analysis snapshot"):
            ctx.repo.save_genre_profile(ctx.profile_id, genre, f, gp["sample_count"], gp["word_count"])
            st.success("Saved.")
        st.subheader("Compare a draft with these samples")
        draft = st.text_area("Draft text", height=140, key="lab_draft")
        if st.button("Compare"):
            d = style_distance(draft, "\n\n".join(s["text"] for s in samples))
            if not d:
                st.warning("Both the draft and the samples need roughly 100+ words.")
            else:
                st.write(d)
                st.caption("Jensen-Shannon distance (0 identical, 1 very different) on sentence-length and function-word distributions only. "
                           "It does not establish authorship or that a draft sounds like you.")
    st.subheader("Approved style examples")
    st.caption("Short passages you consider typical of how you want to sound. Only approved examples are used in prompts; rejected ones never are.")
    for e in ctx.repo.list_examples(ctx.profile_id, "approved"):
        c1, c2 = st.columns([8, 1])
        c1.write(f"[{e['genre']}] {e['text'][:220]}{'...' if len(e['text']) > 220 else ''}")
        if c2.button("Delete", key=f"dex_{e['id']}"):
            ctx.repo.delete_example(ctx.profile_id, e["id"])
            st.rerun()
    with st.form("add_example", clear_on_submit=True):
        ex_text = st.text_area("Add an approved example passage")
        if st.form_submit_button("Add example"):
            try:
                ctx.repo.add_example(ctx.profile_id, genre, ex_text, "approved")
                st.rerun()
            except DatabaseError as e:
                st.error(str(e))
