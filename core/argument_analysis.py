"""Argument structure analysis.

Local part: cue-word heuristics. They detect *signals* of claims, explanations and so on; they do not
understand meaning and will miss implicit reasoning. Every label is a hint for the author to check.
LLM part: optional structured analysis, labelled as a model estimate and validated before display.
"""
from __future__ import annotations

import re

from providers.base import LLMProvider, ProviderResponseError, extract_json
from utils.text_processing import content_words, jaccard, split_paragraphs, split_sentences

CUES = {
    "claim": ["argue", "argues", "this essay", "this report", "this paper", "i contend", "it is clear that", "should", "must",
              "is essential", "is important", "is crucial", "is necessary", "demonstrates that", "thesis", "key point", "central"],
    "explanation": ["because", "since", "this is because", "due to", "as a result of", "which means", "in other words", "this means",
                    "this is why", "owing to", "so that", "by "],
    "example": ["for example", "for instance", "such as", "e.g.", "to illustrate", "consider "],
    "evidence": ["according to", "found that", "study", "studies", "survey", "data", "research", "report shows", "statistics", "evidence", "percent", "%"],
    "qualification": ["may", "might", "could", "to some extent", "in some cases", "perhaps", "limited", "unless", "depends", "partly", "arguably", "tend to"],
    "counterargument": ["however", "on the other hand", "critics", "some argue", "others argue", "nevertheless", "in contrast", "conversely", "although", "despite"],
    "implication": ["therefore", "thus", "consequently", "as a result", "this suggests", "this implies", "it follows", "hence", "for this reason", "this indicates"],
}
CITATION = re.compile(r"\([A-Z][A-Za-z\-\u2019' ]+(?:,| and | & | et al\.?)[^()]*?\d{4}[a-z]?[^()]*\)|\[\d+(?:[,\u2013\-]\s*\d+)*\]")
UNCITED_EVIDENCE = re.compile(r"\b(\d+(?:\.\d+)?\s?%|\d{2,}|studies (?:show|suggest|indicate)|research (?:shows|suggests|indicates)|experts (?:say|agree)|it is well known)\b", re.I)
TRANSITION_START = re.compile(r"^(however|moreover|furthermore|in addition|therefore|thus|consequently|similarly|in contrast|first|second|finally|"
                              r"overall|in conclusion|for example|as a result|on the other hand|nevertheless|additionally|meanwhile|next|then)\b", re.I)


def _has(low: str, cue: str) -> bool:
    return re.search(r"(?<![\w])" + re.escape(cue.strip()) + (r"" if cue.endswith(" ") else r"(?![\w])"), low) is not None


def label_sentence(sentence: str) -> list[str]:
    low = sentence.lower()
    labels = [lab for lab, cues in CUES.items() if any(_has(low, c) for c in cues)]
    if CITATION.search(sentence) and "evidence" not in labels:
        labels.append("evidence")
    return labels


def analyse_argument(text: str) -> dict:
    paragraphs = split_paragraphs(text)
    result_pars, all_sents, flags = [], [], []
    for pi, p in enumerate(paragraphs, 1):
        sents = split_sentences(p)
        labelled = [{"paragraph": pi, "sentence": s, "labels": label_sentence(s)} for s in sents]
        all_sents.extend(labelled)
        present = {l for ls in labelled for l in ls["labels"]}
        counts = {k: sum(1 for ls in labelled if k in ls["labels"]) for k in CUES}
        support = present & {"explanation", "example", "evidence"}
        if "claim" in present and not support and len(sents) >= 1:
            flags.append({"paragraph": pi, "type": "claim_without_visible_support",
                          "note": "A claim cue appears but no explanation, example or evidence cue. Check whether support is actually missing or just phrased without a cue word.",
                          "needs_author_input": True})
        if len(sents) == 1 and ("claim" in present or "implication" in present):
            flags.append({"paragraph": pi, "type": "single_sentence_paragraph",
                          "note": "One-sentence paragraph carrying a claim. Optional: consider whether it needs development. Short paragraphs are sometimes a deliberate choice.",
                          "needs_author_input": False})
        for ls in labelled:
            if UNCITED_EVIDENCE.search(ls["sentence"]) and not CITATION.search(ls["sentence"]):
                flags.append({"paragraph": pi, "type": "possible_unsupported_evidence_claim", "sentence": ls["sentence"][:200],
                              "note": "Statistic or appeal to research without a visible citation. Add a source you have actually read, or soften the claim. Do not invent one.",
                              "needs_author_input": True})
        result_pars.append({"paragraph": pi, "sentences": len(sents), "components": sorted(present), "counts": counts})

    # repetition: similar content-word sets between sentences
    sets = [(i, set(content_words(s["sentence"]))) for i, s in enumerate(all_sents)]
    for a in range(len(sets)):
        for b in range(a + 1, len(sets)):
            if len(sets[a][1]) >= 4 and len(sets[b][1]) >= 4 and jaccard(sets[a][1], sets[b][1]) >= 0.6:
                flags.append({"paragraph": all_sents[sets[b][0]]["paragraph"], "type": "possible_repetition",
                              "sentence": all_sents[sets[b][0]]["sentence"][:200],
                              "note": "Very similar wording to an earlier sentence. Repetition is sometimes intentional emphasis; remove only if it adds nothing.",
                              "needs_author_input": False})
    # continuity
    cont = []
    for a, b in zip(sets, sets[1:]):
        if a[1] and b[1]:
            cont.append(jaccard(a[1], b[1]))
    par_sets = [set(content_words(p)) for p in paragraphs]
    for i in range(1, len(paragraphs)):
        first = split_sentences(paragraphs[i])[0] if paragraphs[i] else ""
        if jaccard(par_sets[i - 1], par_sets[i]) < 0.04 and not TRANSITION_START.match(first):
            flags.append({"paragraph": i + 1, "type": "possible_abrupt_shift",
                          "note": "Little shared vocabulary with the previous paragraph and no opening transition. The link may be clear to you but not to a reader.",
                          "needs_author_input": False})
    totals = {k: sum(1 for s in all_sents if k in s["labels"]) for k in CUES}
    return {
        "method": "local cue-word heuristics (observations about wording, not understanding)",
        "paragraphs": result_pars, "sentences": all_sents, "flags": flags, "totals": totals,
        "unlabelled_sentences": sum(1 for s in all_sents if not s["labels"]),
        "topic_continuity_mean_adjacent_sentences": round(sum(cont) / len(cont), 3) if cont else None,
        "claim_to_support_ratio": (round(totals["claim"] / max(1, totals["explanation"] + totals["example"] + totals["evidence"]), 2) if all_sents else None),
    }


# ---------- optional LLM analysis ----------
LLM_FIELDS = {"main_claim": str, "supporting_explanation": str, "reasoning_link": str, "evidence_present": list, "missing_support": list,
              "qualifications_and_counterarguments": list, "implications": list, "repetition_without_value": list,
              "underexplained_ideas": list, "needs_information_from_author": list}

SYSTEM = ("You analyse the argument structure of a student's or professional's draft. Report only what is in the text. "
          "Never invent evidence, quotations, citations or data. If something is absent, say it is absent. "
          "Return JSON only, no commentary.")


def build_analysis_prompt(text: str) -> str:
    keys = ", ".join(f'"{k}": {"string" if t is str else "list of strings"}' for k, t in LLM_FIELDS.items())
    return ("Analyse the draft between the markers. Distinguish genuinely missing argument components from optional stylistic choices; "
            "do not recommend lengthening for its own sake.\nReturn a JSON object with keys: " + keys +
            "\n<<<DRAFT\n" + text + "\nDRAFT>>>")


def validate_llm_analysis(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ProviderResponseError("The model did not return a JSON object.")
    out = {}
    for k, t in LLM_FIELDS.items():
        v = data.get(k, "" if t is str else [])
        if t is str:
            out[k] = v if isinstance(v, str) else str(v)
        else:
            out[k] = [str(x) for x in v] if isinstance(v, list) else ([str(v)] if v else [])
    if not any(out.values()):
        raise ProviderResponseError("The model response was empty.")
    return out


def llm_analyse_argument(provider: LLMProvider, text: str) -> dict:
    resp = provider.generate(SYSTEM, build_analysis_prompt(text), json_mode=True)
    return validate_llm_analysis(extract_json(resp.text))
