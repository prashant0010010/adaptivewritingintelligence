"""Retrieve approved example passages for a prompt (TF-IDF cosine similarity, same genre first).

Similarity of vocabulary is NOT proof of similar style. It is a cheap way to choose a few relevant
approved passages. Rejected examples are never returned.
"""
from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def retrieve_examples(query: str, examples: list[dict], genre: str | None = None, k: int = 3, max_chars: int = 700) -> list[dict]:
    pool = [e for e in examples if e.get("label") == "approved" and e.get("text", "").strip()]
    same = [e for e in pool if genre and e["genre"] == genre]
    pool = same or pool
    if not pool or not query.strip() or k <= 0:
        return []
    if len(pool) == 1:
        scores = [0.0]
    else:
        try:
            vec = TfidfVectorizer(stop_words="english").fit([query] + [e["text"] for e in pool])
            scores = cosine_similarity(vec.transform([query]), vec.transform([e["text"] for e in pool]))[0].tolist()
        except ValueError:  # empty vocabulary
            scores = [0.0] * len(pool)
    ranked = sorted(zip(scores, pool), key=lambda t: t[0], reverse=True)[:k]
    return [{**e, "score": round(s, 3), "text": e["text"][:max_chars]} for s, e in ranked]
