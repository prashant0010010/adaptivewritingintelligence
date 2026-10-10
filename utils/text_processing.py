"""Basic text utilities: sentence/paragraph splitting, tokenisation, diffs."""
from __future__ import annotations

import difflib
import html
import re

_ABBREV = ["e.g.", "i.e.", "et al.", "etc.", "vs.", "Dr.", "Mr.", "Mrs.", "Ms.", "Prof.", "Fig.", "No.", "cf.", "approx.", "St."]
_PLACE = "\u0001"
_WORD = re.compile(r"[^\W\d_]+(?:['\u2019\-][^\W\d_]+)*", re.UNICODE)

STOPWORDS = set("""a about above after again all also am an and any are as at be because been before being below between both but by
can could did do does doing down during each few for from further had has have having he her here hers him his how i if in into is it its
just me more most my no nor not of off on once only or other our out over own same she should so some such than that the their them then
there these they this those through to too under until up very was we were what when where which while who whom why will with would you your""".split())


def normalise_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text.replace("\r\n", "\n")) if p.strip()]


def split_sentences(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    t = " ".join(text.split())
    for a in _ABBREV:
        t = t.replace(a, a.replace(".", _PLACE))
    t = re.sub(r"\b([A-Z])\.", lambda m: m.group(1) + _PLACE, t)  # initials
    t = re.sub(r"(\d)\.(\d)", lambda m: m.group(1) + _PLACE + m.group(2), t)  # decimals
    parts = re.split(r"(?<=[.!?])[\"'\u201d\u2019)\]]*\s+(?=[\"'\u201c(\[]?[A-Z0-9])", t)
    return [p.replace(_PLACE, ".").strip() for p in parts if p.strip()]


def words(text: str) -> list[str]:
    return _WORD.findall(text)


def content_words(text: str) -> list[str]:
    return [w.lower() for w in words(text) if w.lower() not in STOPWORDS and len(w) > 2]


def word_count(text: str) -> int:
    return len(words(text))


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def diff_html(original: str, revised: str) -> str:
    """Word-level diff as HTML (deletions struck red, insertions green). Input is escaped."""
    a, b = original.split(), revised.split()
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            out.append(html.escape(" ".join(a[i1:i2])))
        else:
            if i2 > i1:
                out.append(f"<del style='background:#fdd;color:#900'>{html.escape(' '.join(a[i1:i2]))}</del>")
            if j2 > j1:
                out.append(f"<ins style='background:#dfd;color:#060;text-decoration:none'>{html.escape(' '.join(b[j1:j2]))}</ins>")
    return "<div style='line-height:1.7'>" + " ".join(out) + "</div>"


def change_summary(original: str, revised: str) -> dict:
    wo, wr = word_count(original), word_count(revised)
    a, b = original.split(), revised.split()
    added = removed = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            removed += i2 - i1
        if tag in ("replace", "insert"):
            added += j2 - j1
    return {
        "words_original": wo, "words_revised": wr, "word_difference": wr - wo,
        "percent_change": round(100 * (wr - wo) / wo, 1) if wo else None,
        "words_added": added, "words_removed": removed,
        "sentences_original": len(split_sentences(original)), "sentences_revised": len(split_sentences(revised)),
        "text_similarity_ratio": round(difflib.SequenceMatcher(None, a, b, autojunk=False).ratio(), 3),
    }
