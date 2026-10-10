"""Revision planning, prompt construction, generation and response validation."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from core.profile_learning import preference_guidance
from providers.base import LLMProvider, ProviderResponseError, extract_json

MODES = {
    "clarity": ("Preserve meaning, improve clarity", "Improve clarity and readability. Keep every claim and its order."),
    "flow": ("Improve logical flow", "Improve the logical order and connections between sentences without adding new claims."),
    "elaborate": ("Strengthen explanation and elaboration", "Develop ideas that are stated but under-explained, using ONLY information in the draft. Where support is missing, insert a visible placeholder like [ADD EVIDENCE: what is needed] instead of inventing it."),
    "transitions": ("Improve transitions", "Improve transitions between sentences and paragraphs only. Change little else."),
    "academic": ("Improve academic precision", "Make wording more precise and appropriately formal. Do not add citations or claims; keep the author's hedging level unless it is clearly inaccurate."),
    "reduce_repetition": ("Reduce unnecessary repetition", "Remove repetition that adds nothing. Keep deliberate emphasis. Do not shorten beyond that."),
    "match_style": ("Match the selected profile's approved style", "Revise so it reads like the author's approved examples and stated preferences, without changing the meaning."),
    "diagnose": ("Identify weaknesses without rewriting", "Do NOT rewrite. Return findings only (findings_only). Leave revised_text empty."),
    "minimal_edit": ("Minimal edit", "Fix only errors and clearly awkward phrasing. Change as little as possible."),
}
REWRITING_MODES = [m for m in MODES if m != "diagnose"]
# Learned preferences that conflict with a mode's goal.
CONFLICTS = {("elaborate", "length", "shorter"), ("reduce_repetition", "length", "longer"), ("minimal_edit", "length", "longer"),
             ("elaborate", "sentence_length", "shorter")}

SYSTEM = ("You are a careful writing editor working for the author, whose draft is the source of truth. Rules: "
          "(1) Never invent facts, quotations, citations, statistics, names or evidence. "
          "(2) Keep every in-text citation and every quotation exactly as written. "
          "(3) Preserve the author's meaning, claims and level of certainty. "
          "(4) If support is needed but absent, add a visible placeholder in square brackets rather than making it up, and list it in questions_for_author. "
          "(5) Do not lengthen text unless the objective requires it. "
          "(6) Reply with JSON only: {\"revised_text\": string, \"changes\": [{\"change\": string, \"reason\": string}], "
          "\"placeholders\": [string], \"questions_for_author\": [string], \"findings\": [string]}.")


@dataclass
class RevisionContext:
    onboarding: dict = field(default_factory=dict)
    preferences: dict = field(default_factory=dict)   # key -> value (learned or user)
    avoid_phrases: list = field(default_factory=list)
    examples: list = field(default_factory=list)       # approved only, already truncated


@dataclass
class RevisionResult:
    revised_text: str
    changes: list
    placeholders: list
    questions: list
    findings: list
    runtime_seconds: float
    provider: str
    prompt_chars: int


def plan_revision(mode: str, preferences: dict, use_preferences: bool = True) -> dict:
    if mode not in MODES:
        raise ValueError(f"Unknown revision mode: {mode}")
    conflicts = []
    if use_preferences:
        for key, val in preferences.items():
            if (mode, key, val) in CONFLICTS:
                conflicts.append(f"Your learned preference '{key}: {val}' conflicts with the requested mode '{MODES[mode][0]}'. "
                                 f"The requested mode takes priority for this run; untick 'apply my preferences' to ignore the preference entirely.")
    steps = [MODES[mode][1]]
    if use_preferences and preferences:
        steps += preference_guidance(preferences)
    return {"mode": mode, "label": MODES[mode][0], "steps": steps, "conflicts": conflicts,
            "preferences_applied": dict(preferences) if use_preferences else {}}


def build_prompt(draft: str, genre: str, mode: str, ctx: RevisionContext, use_preferences: bool = True) -> str:
    parts = [f"Genre: {genre}", f"Objective: {MODES[mode][1]}"]
    if use_preferences:
        if ctx.onboarding:
            parts.append("Author's stated preferences:\n" + "\n".join(f"- {k}: {v}" for k, v in ctx.onboarding.items()))
        guidance = preference_guidance(ctx.preferences)
        if guidance:
            parts.append("Learned from the author's feedback (observed tendencies, not rules):\n" + "\n".join(f"- {g}" for g in guidance))
        if ctx.avoid_phrases:
            parts.append("Phrases the author wants avoided: " + "; ".join(ctx.avoid_phrases))
        if ctx.examples:
            parts.append("Approved examples of the author's writing (for tone and structure only; do not copy content):\n"
                         + "\n".join(f"[{i}] {e['text']}" for i, e in enumerate(ctx.examples, 1)))
    parts.append("Draft to revise:\n<<<DRAFT\n" + draft + "\nDRAFT>>>")
    return "\n\n".join(parts)


def parse_revision_response(raw: str, mode: str) -> dict:
    data = extract_json(raw)
    revised = data.get("revised_text", "")
    if not isinstance(revised, str):
        raise ProviderResponseError("The model returned a malformed 'revised_text'.")
    if mode != "diagnose" and not revised.strip():
        raise ProviderResponseError("The model returned an empty revision.")

    def lst(key):
        v = data.get(key, [])
        return v if isinstance(v, list) else ([v] if v else [])

    changes = []
    for c in lst("changes"):
        changes.append({"change": str(c.get("change", "")), "reason": str(c.get("reason", ""))} if isinstance(c, dict) else {"change": str(c), "reason": ""})
    return {"revised_text": revised.strip(), "changes": changes, "placeholders": [str(x) for x in lst("placeholders")],
            "questions": [str(x) for x in lst("questions_for_author")], "findings": [str(x) for x in lst("findings")]}


def generate_revision(provider: LLMProvider, draft: str, genre: str, mode: str, ctx: RevisionContext | None = None,
                      use_preferences: bool = True) -> RevisionResult:
    if not draft or not draft.strip():
        raise ValueError("Draft is empty.")
    ctx = ctx or RevisionContext()
    prompt = build_prompt(draft, genre, mode, ctx, use_preferences)
    started = time.time()
    resp = provider.generate(SYSTEM, prompt, json_mode=True)
    parsed = parse_revision_response(resp.text, mode)
    return RevisionResult(parsed["revised_text"], parsed["changes"], parsed["placeholders"], parsed["questions"], parsed["findings"],
                          round(time.time() - started, 3), provider.name, len(prompt) + len(SYSTEM))
