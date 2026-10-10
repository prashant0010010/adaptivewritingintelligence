"""Local evaluation harness. Runs revision methods over a fixed case set and records inspectable checks.

The built-in cases are SYNTHETIC demonstrations so the project runs immediately. Results on them
(especially with the demo provider) say nothing about real-world quality or about any other tool.
"""
from __future__ import annotations

import time

from core.quality_checks import run_quality_checks
from core.revision_engine import RevisionContext, generate_revision
from providers.base import LLMProvider, ProviderError

SYNTHETIC_CASES = [
    {"title": "Synthetic: social media and study habits", "genre": "Academic report",
     "text": "Social media is very popular among university students. Basically, many students check it between lectures, and this may reduce the time they spend on focused study (Nguyen, 2021). In order to understand the effect, the report compares two groups of students. Students in the first group reported 3 hours of daily use. Therefore, universities should consider guidance on use."},
    {"title": "Synthetic: reflective note on teamwork", "genre": "Reflective writing",
     "text": "I really learned a lot from the group project. At the start I was unsure about my role, but I took notes in meetings and that helped the team stay organised. Due to the fact that deadlines were tight, we split the work. Next time I would ask for feedback earlier."},
    {"title": "Synthetic: professional update", "genre": "Professional writing",
     "text": "The migration is basically on track. We have moved 12 of 20 services and at this point in time no incidents have been reported. The remaining services are very dependent on the billing system, so they are scheduled last."},
]

DEFAULT_METHODS = [
    ("Original (no revision)", None, False),
    ("Minimal edit", "minimal_edit", False),
    ("Clarity, without profile", "clarity", False),
    ("Clarity, with profile preferences", "clarity", True),
]


def run_evaluation(provider: LLMProvider, cases: list[dict], methods=None, ctx: RevisionContext | None = None, profile_text: str = "") -> list[dict]:
    methods = methods or DEFAULT_METHODS
    rows = []
    for case in cases:
        for label, mode, use_prefs in methods:
            row = {"case": case["title"], "method": label, "error": ""}
            started = time.time()
            try:
                revised = case["text"] if mode is None else generate_revision(provider, case["text"], case["genre"], mode, ctx, use_prefs).revised_text
            except (ProviderError, ValueError) as exc:
                row["error"] = str(exc)
                rows.append(row)
                continue
            row["runtime_s"] = round(time.time() - started, 3)
            q = run_quality_checks(case["text"], revised, mode or "clarity", profile_text)
            m = q["metrics"]
            row.update({"words": m["words_revised"], "length_ratio": m.get("length_ratio"), "key_term_retention": m.get("key_term_retention"),
                        "numbers_added": m["numbers_added"], "numbers_missing": m["numbers_missing"], "citations_missing": m["citations_missing"],
                        "citations_added": m["citations_added"], "quotes_altered": m["quotes_altered_or_missing"], "possibly_new_sentences": m["possibly_new_sentences"],
                        "repeated_trigrams": m["repeated_trigrams_revised"], "flesch_approx": m["flesch_revised"], "warnings": q["warnings"]})
            rows.append(row)
    return rows
