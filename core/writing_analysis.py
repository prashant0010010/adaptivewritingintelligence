"""Deterministic, local feature extraction. Nothing here calls an external service.

Every measure is an observation about the supplied text only. None of them proves authorship,
ability or intent, and short samples give unstable values (see LIMITATIONS in docs).
"""
from __future__ import annotations

import math
import re
import statistics
from collections import Counter

from utils.text_processing import STOPWORDS, split_paragraphs, split_sentences, words

MIN_SENTENCES_FOR_SD = 5
MIN_WORDS_FOR_MATTR = 50

TRANSITIONS = {
    "addition": ["in addition", "moreover", "furthermore", "also", "additionally", "besides", "similarly", "likewise"],
    "contrast": ["however", "but", "in contrast", "on the other hand", "yet", "whereas", "nevertheless", "nonetheless", "conversely", "instead"],
    "concession": ["although", "even though", "despite", "in spite of", "admittedly", "while", "granted"],
    "cause_result": ["therefore", "thus", "consequently", "as a result", "hence", "because", "since", "so that", "for this reason", "accordingly"],
    "example": ["for example", "for instance", "such as", "e.g.", "to illustrate", "in particular"],
    "sequence": ["first", "second", "third", "next", "then", "finally", "subsequently", "meanwhile", "initially"],
    "summary": ["in conclusion", "in summary", "overall", "to summarise", "to summarize", "in short", "ultimately"],
}
HEDGES = ["may", "might", "could", "suggests", "suggest", "appears", "appear", "seems", "seem", "likely", "perhaps", "possibly",
          "probably", "tends to", "tend to", "somewhat", "arguably", "potentially", "to some extent"]
BOOSTERS = ["clearly", "definitely", "certainly", "undoubtedly", "obviously", "always", "never", "must", "demonstrates", "proves"]
SUBORDINATORS = ["because", "although", "though", "while", "whereas", "since", "unless", "if", "when", "which", "that", "who"]
FUNCTION_WORDS = ["the", "of", "and", "to", "in", "a", "is", "that", "it", "for", "as", "with", "on", "this", "by", "be", "are", "or", "not", "which"]
PUNCT = {"comma": ",", "semicolon": ";", "colon": ":", "question_mark": "?", "exclamation_mark": "!", "open_paren": "(",
         "em_dash": "\u2014", "en_dash": "\u2013", "hyphen": "-", "double_quote": '"', "ellipsis": "\u2026"}


def _phrase_count(text_lower: str, phrase: str) -> int:
    return len(re.findall(r"(?<![\w])" + re.escape(phrase) + r"(?![\w])", text_lower))


def _sd(values: list[float]) -> float | None:
    return round(statistics.pstdev(values), 2) if len(values) >= MIN_SENTENCES_FOR_SD else None


def mattr(tokens: list[str], window: int = 50) -> float | None:
    """Moving-average type-token ratio. Less sensitive to length than plain TTR."""
    if len(tokens) < MIN_WORDS_FOR_MATTR:
        return None
    window = min(window, len(tokens))
    ratios = [len(set(tokens[i:i + window])) / window for i in range(len(tokens) - window + 1)]
    return round(sum(ratios) / len(ratios), 3)


def analyse_text(text: str) -> dict:
    text = text or ""
    toks = words(text)
    low = [t.lower() for t in toks]
    low_text = text.lower()
    sents = split_sentences(text)
    paras = split_paragraphs(text)
    n_words = len(toks)
    per_1000 = (1000 / n_words) if n_words else 0
    per_100 = (100 / n_words) if n_words else 0

    sent_lens = [len(words(s)) for s in sents]
    para_lens = [len(words(p)) for p in paras]
    feats: dict = {
        "char_count": len(text), "word_count": n_words, "sentence_count": len(sents), "paragraph_count": len(paras),
        "reliable": n_words >= 200,
        "mean_sentence_length": round(statistics.mean(sent_lens), 2) if sent_lens else None,
        "median_sentence_length": statistics.median(sent_lens) if sent_lens else None,
        "sentence_length_sd": _sd(sent_lens),
        "min_sentence_length": min(sent_lens) if sent_lens else None,
        "max_sentence_length": max(sent_lens) if sent_lens else None,
        "mean_paragraph_length": round(statistics.mean(para_lens), 1) if para_lens else None,
        "paragraph_length_sd": round(statistics.pstdev(para_lens), 1) if len(para_lens) >= 3 else None,
    }
    bins = {"1-10": 0, "11-20": 0, "21-30": 0, "31+": 0}
    for L in sent_lens:
        bins["1-10" if L <= 10 else "11-20" if L <= 20 else "21-30" if L <= 30 else "31+"] += 1
    feats["sentence_length_bins"] = bins

    feats["type_token_ratio"] = round(len(set(low)) / n_words, 3) if n_words else None
    feats["mattr_50"] = mattr(low)
    fw = Counter(w for w in low if w in FUNCTION_WORDS)
    feats["function_words_per_1000"] = {w: round(fw[w] * per_1000, 1) for w in FUNCTION_WORDS}
    feats["punctuation_per_1000_words"] = {k: round(text.count(ch) * per_1000, 1) for k, ch in PUNCT.items()}

    for name, bank in (("hedging", HEDGES), ("boosters", BOOSTERS)):
        c = sum(_phrase_count(low_text, p) for p in bank)
        feats[f"{name}_per_100_words"] = round(c * per_100, 2)
    sub = sum(_phrase_count(low_text, p) for p in SUBORDINATORS)
    feats["subordinators_per_sentence"] = round(sub / len(sents), 2) if sents else None
    feats["commas_per_sentence"] = round(text.count(",") / len(sents), 2) if sents else None

    trans_counts, trans_detail = {}, Counter()
    for cat, bank in TRANSITIONS.items():
        total = 0
        for p in bank:
            c = _phrase_count(low_text, p)
            if c:
                trans_detail[p] += c
                total += c
        trans_counts[cat] = total
    feats["transition_counts"] = trans_counts
    feats["transitions_per_100_words"] = round(sum(trans_counts.values()) * per_100, 2)
    feats["top_transitions"] = trans_detail.most_common(8)

    openers = Counter(re.sub(r"\W", "", s.split()[0]).lower() for s in sents if s.split())
    feats["top_sentence_openers"] = openers.most_common(8)

    def ngrams(n):
        grams = Counter()
        for i in range(len(low) - n + 1):
            g = low[i:i + n]
            if all(w in STOPWORDS for w in g) or g[0] in STOPWORDS and g[-1] in STOPWORDS:
                continue
            grams[" ".join(g)] += 1
        return [(g, c) for g, c in grams.most_common(10) if c >= 2]

    feats["top_bigrams"], feats["top_trigrams"] = ngrams(2), ngrams(3)
    content = [w for w in low if w not in STOPWORDS and len(w) > 3]
    feats["repeated_content_words"] = [(w, c) for w, c in Counter(content).most_common(10) if c >= 3]
    feats["flesch_reading_ease_approx"] = flesch(text)
    return feats


def _syllables(word: str) -> int:
    word = word.lower()
    groups = re.findall(r"[aeiouy]+", word)
    n = len(groups)
    if word.endswith("e") and n > 1 and not word.endswith("le"):
        n -= 1
    return max(n, 1)


def flesch(text: str) -> float | None:
    """Approximate Flesch Reading Ease. English only; syllable counting is a heuristic."""
    toks, sents = words(text), split_sentences(text)
    if len(toks) < 30 or not sents:
        return None
    syl = sum(_syllables(w) for w in toks)
    return round(206.835 - 1.015 * (len(toks) / len(sents)) - 84.6 * (syl / len(toks)), 1)


# ---------- distribution comparison ----------
def js_distance(p: list[float], q: list[float]) -> float:
    """Jensen-Shannon distance (base 2, range 0..1) between two non-negative vectors."""
    sp, sq = sum(p), sum(q)
    if sp <= 0 or sq <= 0 or len(p) != len(q):
        raise ValueError("Both distributions need positive mass and equal length.")
    p, q = [x / sp for x in p], [x / sq for x in q]
    m = [(a + b) / 2 for a, b in zip(p, q)]

    def kl(a, b):
        return sum(x * math.log2(x / y) for x, y in zip(a, b) if x > 0)

    return round(math.sqrt(max(0.0, (kl(p, m) + kl(q, m)) / 2)), 4)


def style_distance(text_a: str, text_b: str) -> dict | None:
    """Compare sentence-length and function-word distributions of two texts.

    Lower means more similar on these two coarse features only. It does not establish authorship
    or that one text 'sounds like' the other. Returns None if either text is too short.
    """
    fa, fb = analyse_text(text_a), analyse_text(text_b)
    if fa["word_count"] < 100 or fb["word_count"] < 100:
        return None
    sl = js_distance([fa["sentence_length_bins"][k] + 0.5 for k in fa["sentence_length_bins"]],
                     [fb["sentence_length_bins"][k] + 0.5 for k in fb["sentence_length_bins"]])
    fwd = js_distance([fa["function_words_per_1000"][w] + 0.5 for w in FUNCTION_WORDS],
                      [fb["function_words_per_1000"][w] + 0.5 for w in FUNCTION_WORDS])
    return {"sentence_length_distance": sl, "function_word_distance": fwd, "mean": round((sl + fwd) / 2, 4)}


# ---------- profile level ----------
def evidence_level(total_words: int, n_samples: int) -> str:
    """Qualitative label, not a probability. Based only on amount of text and number of samples."""
    if total_words < 500 or n_samples < 1:
        return "very limited"
    if total_words < 2000 or n_samples < 3:
        return "limited"
    if total_words < 5000 or n_samples < 5:
        return "moderate"
    return "reasonable"


def build_genre_profile(samples: list[dict]) -> dict:
    """Combine samples (already filtered to one genre and to learning-eligible ones)."""
    if not samples:
        return {"sample_count": 0, "word_count": 0, "evidence_level": "very limited", "features": {}, "per_sample": [], "stability": {}}
    per = [analyse_text(s["text"]) for s in samples]
    combined = analyse_text("\n\n".join(s["text"] for s in samples))
    stab = {}
    for key in ("mean_sentence_length", "transitions_per_100_words", "hedging_per_100_words"):
        vals = [p[key] for p in per if p["word_count"] >= 100 and p[key] is not None]
        if len(vals) >= 2:
            stab[key] = {"mean": round(statistics.mean(vals), 2), "sd_across_samples": round(statistics.stdev(vals), 2), "n": len(vals)}
    return {"sample_count": len(samples), "word_count": combined["word_count"],
            "evidence_level": evidence_level(combined["word_count"], len(samples)),
            "features": combined, "per_sample": [{"title": s["title"], "words": p["word_count"], "mean_sentence_length": p["mean_sentence_length"]} for s, p in zip(samples, per)],
            "stability": stab}
