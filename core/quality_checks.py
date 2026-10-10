"""Deterministic quality checks comparing a revision with its original.

These checks flag things to inspect. No score here proves that meaning was preserved.
Status values: pass (nothing flagged), warn (inspect this), info (context only).
"""
from __future__ import annotations

import re
from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from core.argument_analysis import CITATION
from core.writing_analysis import analyse_text, style_distance
from utils.text_processing import content_words, jaccard, split_sentences, word_count

QUOTE = re.compile(r"[\"\u201c]([^\"\u201d]{12,}?)[\"\u201d]")
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*(?:\s?%)?")
PLACEHOLDER = re.compile(r"\[[A-Z][A-Z ]+:[^\]]*\]")
CAPITALISED = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}(?:\s[A-Z][a-z]{2,})*\b")


def _norm_cite(c: str) -> str:
    return re.sub(r"\s+", " ", c.strip().lower())


def _check(name, status, detail, **extra):
    return {"name": name, "status": status, "detail": detail, **extra}


def run_quality_checks(original: str, revised: str, mode: str = "clarity", profile_text: str = "") -> dict:
    checks, metrics = [], {}
    o_words, r_words = word_count(original), word_count(revised)
    metrics["words_original"], metrics["words_revised"] = o_words, r_words

    # citations
    oc = {_norm_cite(c.group(0)) for c in CITATION.finditer(original)}
    rc = {_norm_cite(c.group(0)) for c in CITATION.finditer(revised)}
    missing, added = sorted(oc - rc), sorted(rc - oc)
    metrics["citations_missing"], metrics["citations_added"] = len(missing), len(added)
    checks.append(_check("Citation integrity", "warn" if missing or added else "pass",
                         ("Missing from revision: " + "; ".join(missing) + ". " if missing else "") +
                         ("New citations not in original (possible fabrication): " + "; ".join(added) if added else "") or "All in-text citations preserved, none added."))

    # quotations
    oq = [q.strip() for q in QUOTE.findall(original)]
    lost = [q for q in oq if q not in revised]
    newq = [q.strip() for q in QUOTE.findall(revised) if q.strip() not in original]
    metrics["quotes_altered_or_missing"] = len(lost)
    checks.append(_check("Quotation integrity", "warn" if lost or newq else "pass",
                         (f"{len(lost)} original quotation(s) changed or missing. " if lost else "") +
                         (f"{len(newq)} quotation(s) appear that were not in the original. " if newq else "") or "Quotations preserved verbatim."))

    # numbers
    on, rn = Counter(NUMBER.findall(original)), Counter(NUMBER.findall(revised))
    n_missing, n_added = sorted((on - rn).elements()), sorted((rn - on).elements())
    metrics["numbers_added"], metrics["numbers_missing"] = len(n_added), len(n_missing)
    checks.append(_check("Numbers and statistics", "warn" if n_added or n_missing else "pass",
                         (f"Added: {', '.join(n_added)}. " if n_added else "") + (f"Missing: {', '.join(n_missing)}." if n_missing else "") or "Numbers unchanged."))

    # key-term retention (prefix match tolerates inflection)
    key_terms = {w for w in content_words(original) if len(w) >= 5}
    rev_stems = {w[:5] for w in content_words(revised)}
    if key_terms:
        kept = sum(1 for w in key_terms if w[:5] in rev_stems)
        ratio = kept / len(key_terms)
        metrics["key_term_retention"] = round(ratio, 2)
        lost_terms = sorted(w for w in key_terms if w[:5] not in rev_stems)[:12]
        low = ratio < (0.5 if mode in ("elaborate", "diagnose") else 0.7)
        checks.append(_check("Key-term retention", "warn" if low and mode != "diagnose" else "pass",
                             f"{kept} of {len(key_terms)} distinctive words from the original still appear (or an inflection does)."
                             + (f" Not found: {', '.join(lost_terms)}." if lost_terms else "")))
    # named entities
    names_o = set(CAPITALISED.findall(original))
    names_missing = sorted(n for n in names_o if n not in revised)
    checks.append(_check("Names and capitalised terms", "warn" if names_missing else "pass",
                         ("Not found in revision: " + ", ".join(names_missing[:10])) if names_missing else "Capitalised names preserved."))

    # possible unsupported additions: revised sentences with little overlap with original
    orig_set = set(content_words(original))
    novel = []
    for s in split_sentences(revised):
        sset = set(content_words(s))
        if PLACEHOLDER.search(s) or len(sset) < 4:
            continue
        if len(sset & orig_set) / len(sset) < 0.4:
            novel.append(s[:160])
    metrics["possibly_new_sentences"] = len(novel)
    checks.append(_check("Possible unsupported additions", "warn" if novel and mode != "diagnose" else "pass",
                         ("Sentences with little vocabulary from the original (check they add no new facts): " + " | ".join(novel[:3])) if novel else "No sentence stands out as new content. This is a vocabulary-overlap heuristic and can miss added claims."))

    # placeholders
    ph = PLACEHOLDER.findall(revised)
    metrics["placeholders"] = len(ph)
    if ph:
        checks.append(_check("Placeholders to complete", "info", f"{len(ph)} visible placeholder(s) need information from you."))

    # length
    ratio = (r_words / o_words) if o_words else None
    metrics["length_ratio"] = round(ratio, 2) if ratio else None
    if ratio is not None and mode != "diagnose":
        limits = {"minimal_edit": (0.85, 1.15), "clarity": (0.6, 1.4), "reduce_repetition": (0.4, 1.05), "elaborate": (1.0, 2.5)}.get(mode, (0.6, 1.6))
        out = ratio < limits[0] or ratio > limits[1]
        checks.append(_check("Length vs objective", "warn" if out else "pass", f"Revision is {ratio:.2f}x the original length (expected roughly {limits[0]}-{limits[1]}x for this mode)."))

    # repetition
    def rep(t):
        toks = [w.lower() for w in re.findall(r"[A-Za-z']+", t)]
        tri = Counter(zip(toks, toks[1:], toks[2:]))
        return sum(c - 1 for c in tri.values() if c > 1)
    ro, rr = rep(original), rep(revised)
    metrics["repeated_trigrams_original"], metrics["repeated_trigrams_revised"] = ro, rr
    checks.append(_check("Repetition", "warn" if rr > ro + 1 else "pass", f"Repeated three-word sequences: original {ro}, revision {rr}."))

    # readability
    a, b = analyse_text(original), analyse_text(revised)
    metrics["flesch_original"], metrics["flesch_revised"] = a["flesch_reading_ease_approx"], b["flesch_reading_ease_approx"]
    metrics["mean_sentence_length_original"], metrics["mean_sentence_length_revised"] = a["mean_sentence_length"], b["mean_sentence_length"]
    checks.append(_check("Readability (approximate, English)", "info",
                         f"Mean sentence length {a['mean_sentence_length']} -> {b['mean_sentence_length']}; Flesch approx. {a['flesch_reading_ease_approx']} -> {b['flesch_reading_ease_approx']}. Lower Flesch is not automatically worse for academic writing."))

    # weak overall similarity signal
    try:
        vec = TfidfVectorizer().fit([original, revised])
        sim = float(cosine_similarity(vec.transform([original]), vec.transform([revised]))[0][0])
        metrics["tfidf_cosine"] = round(sim, 3)
        checks.append(_check("Vocabulary overlap (weak signal)", "info", f"TF-IDF cosine {sim:.2f}. High overlap does not prove the meaning is preserved, and low overlap does not prove it changed."))
    except ValueError:
        pass

    # style distance to profile
    if profile_text.strip():
        d_o, d_r = style_distance(original, profile_text), style_distance(revised, profile_text)
        if d_o and d_r:
            metrics["style_distance_original"], metrics["style_distance_revised"] = d_o["mean"], d_r["mean"]
            closer = d_r["mean"] < d_o["mean"]
            checks.append(_check("Closeness to your sample statistics", "info",
                                 f"Coarse distance (sentence lengths and function words) {d_o['mean']} -> {d_r['mean']} ({'closer' if closer else 'not closer'}). This does not establish that it sounds like you."))
        else:
            checks.append(_check("Closeness to your sample statistics", "info", "Not enough text in the profile or draft (about 100+ words each) for this comparison."))

    return {"checks": checks, "metrics": metrics, "warnings": sum(1 for c in checks if c["status"] == "warn"),
            "note": "Checks flag items to inspect. They do not prove meaning preservation or quality."}
