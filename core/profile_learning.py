"""Transparent preference learning from feedback.

This is NOT model training. Each feedback event stores how the revision changed four measurable
dimensions. Preferences are re-derived by counting votes, so the result can always be inspected.

Vote rule: for a dimension with change direction d in {+1,-1,0} (0 = change below threshold):
  accept  -> vote d       (the author kept a revision that moved this way)
  edit    -> vote d       (measured on the author's own edited text, which is a stronger signal)
  reject  -> vote -d      (weak: rejection may be about something else; counts as half weight)
A preference becomes active only when at least MIN_VOTES informative votes exist and the weighted
majority is at least MIN_AGREEMENT. One ambiguous action never changes the profile.
"""
from __future__ import annotations

from typing import Optional

from core.writing_analysis import analyse_text
from database.repository import Repository

MIN_VOTES = 3
MIN_AGREEMENT = 0.7
WEIGHTS = {"accept": 1.0, "edit": 1.5, "reject": 0.5}
DIMENSIONS = {
    "length": {"labels": {1: "longer", -1: "shorter"}, "threshold": 0.10, "text": "overall length"},
    "transitions": {"labels": {1: "more", -1: "fewer"}, "threshold": 1.0, "text": "explicit transition words (per 100 words)"},
    "sentence_length": {"labels": {1: "longer", -1: "shorter"}, "threshold": 0.10, "text": "average sentence length"},
    "hedging": {"labels": {1: "more", -1: "fewer"}, "threshold": 0.5, "text": "hedging words (per 100 words)"},
}
GUIDANCE = {
    ("length", "shorter"): "Keep the revision the same length as the draft or shorter.",
    ("length", "longer"): "Fuller development is welcome where the draft already supplies support.",
    ("transitions", "fewer"): "Use few explicit transition words; let ideas connect through content.",
    ("transitions", "more"): "Explicit transitions between sentences are welcome.",
    ("sentence_length", "shorter"): "Prefer shorter sentences than a typical formal rewrite.",
    ("sentence_length", "longer"): "Longer, developed sentences are acceptable.",
    ("hedging", "fewer"): "Avoid adding hedging words such as 'may' or 'perhaps' unless the draft has them.",
    ("hedging", "more"): "Appropriately qualified claims are welcome.",
}


def change_vector(original: str, revised: str) -> dict[str, float]:
    a, b = analyse_text(original), analyse_text(revised)
    wo = max(a["word_count"], 1)
    msl_a, msl_b = a["mean_sentence_length"] or 0, b["mean_sentence_length"] or 0
    return {
        "length": (b["word_count"] - a["word_count"]) / wo,
        "transitions": b["transitions_per_100_words"] - a["transitions_per_100_words"],
        "sentence_length": ((msl_b - msl_a) / msl_a) if msl_a else 0.0,
        "hedging": b["hedging_per_100_words"] - a["hedging_per_100_words"],
    }


def direction(dim: str, delta: float) -> int:
    t = DIMENSIONS[dim]["threshold"]
    return 1 if delta > t else -1 if delta < -t else 0


def aggregate(events: list[dict], reset_times: Optional[dict[str, str]] = None) -> dict[str, dict]:
    """events: feedback rows (with 'deltas', 'action', 'created_at'). Returns per-dimension stats."""
    reset_times = reset_times or {}
    out = {}
    for dim, spec in DIMENSIONS.items():
        votes = [0.0, 0.0]  # [toward +1, toward -1]
        n = 0
        for e in events:
            if e["created_at"] <= reset_times.get(dim, ""):
                continue
            if dim not in e.get("deltas", {}):
                continue
            d = direction(dim, e["deltas"][dim])
            if d == 0:
                continue
            w = WEIGHTS.get(e["action"], 0)
            sign = -d if e["action"] == "reject" else d
            votes[0 if sign == 1 else 1] += w
            n += 1
        total = votes[0] + votes[1]
        pref, agree = None, (max(votes) / total if total else 0.0)
        if n >= MIN_VOTES and agree >= MIN_AGREEMENT:
            pref = spec["labels"][1 if votes[0] > votes[1] else -1]
        out[dim] = {"votes_for_more": votes[0], "votes_for_less": votes[1], "informative_events": n,
                    "agreement": round(agree, 2), "preference": pref}
    return out


def record_feedback(repo: Repository, profile_id: int, revision_id: Optional[int], genre: str, mode: str, action: str,
                    original: str, final_text: str, reason: str = "") -> dict:
    """Store the event, then re-derive learned preferences. Returns the update summary."""
    deltas = change_vector(original, final_text) if final_text.strip() else {}
    repo.add_feedback(profile_id, revision_id, genre, mode, action, reason, deltas)
    return update_learned_preferences(repo, profile_id, genre)


def update_learned_preferences(repo: Repository, profile_id: int, genre: str) -> dict:
    events = repo.list_feedback(profile_id, genre)
    prefs = {p["key"]: p for p in repo.get_preferences(profile_id, genre)}
    reset_times = {k: p["updated_at"] for k, p in prefs.items() if p["source"] == "reset"}
    stats = aggregate(events, reset_times)
    changes = []
    for dim, s in stats.items():
        cur = prefs.get(dim)
        if cur and cur["source"] == "user":
            continue  # user-set preferences are never overridden by learning
        if s["preference"] and (not cur or cur["source"] == "reset" or cur["value"] != s["preference"]):
            repo.set_preference(profile_id, genre, dim, s["preference"], "learned", s["informative_events"])
            changes.append(f"{genre}: {dim} -> {s['preference']} (from {s['informative_events']} feedback events)")
        elif not s["preference"] and cur and cur["source"] == "learned":
            repo.delete_preference(profile_id, genre, dim)
            changes.append(f"{genre}: {dim} learned preference withdrawn (evidence no longer consistent)")
        elif cur and cur["source"] == "learned" and s["preference"] == cur["value"] and cur["evidence_n"] != s["informative_events"]:
            repo.set_preference(profile_id, genre, dim, cur["value"], "learned", s["informative_events"])
    version = None
    if changes:
        version = repo.snapshot_preferences(profile_id, "; ".join(changes))
    return {"stats": stats, "changes": changes, "version": version}


def reset_learned_preference(repo: Repository, profile_id: int, genre: str, dim: str) -> None:
    """Removes the preference and ignores feedback given before now when re-learning this dimension."""
    repo.set_preference(profile_id, genre, dim, "", "reset", 0)
    repo.snapshot_preferences(profile_id, f"Reset {genre}: {dim}")


def set_user_preference(repo: Repository, profile_id: int, genre: str, dim: str, value: str) -> None:
    valid = set(DIMENSIONS[dim]["labels"].values())
    if value not in valid:
        raise ValueError(f"{dim} must be one of {sorted(valid)}")
    repo.set_preference(profile_id, genre, dim, value, "user", 0)
    repo.snapshot_preferences(profile_id, f"User set {genre}: {dim} = {value}")


def active_preferences(repo: Repository, profile_id: int, genre: str) -> dict[str, str]:
    return {p["key"]: p["value"] for p in repo.get_preferences(profile_id, genre) if p["source"] in ("learned", "user") and p["value"]}


def preference_guidance(prefs: dict[str, str]) -> list[str]:
    return [GUIDANCE[(k, v)] for k, v in prefs.items() if (k, v) in GUIDANCE]
