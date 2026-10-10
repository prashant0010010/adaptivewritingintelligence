"""Mock provider for tests and the offline demo.

In its default mode it performs a trivial rule-based edit so the whole pipeline can be exercised.
It is NOT a language model and its output must not be read as an example of real quality.
"""
from __future__ import annotations

import json
import re
from typing import Callable, Optional, Union

from providers.base import LLMProvider, LLMResponse, ProviderError

_FILLERS = [(r"\bin order to\b", "to"), (r"\bvery\b ", ""), (r"\breally\b ", ""), (r"\bbasically\b,? ", ""), (r"\bdue to the fact that\b", "because"),
            (r"\bat this point in time\b", "now")]


class MockProvider(LLMProvider):
    name = "mock"
    sends_data_externally = False

    def __init__(self, responses: Optional[list[Union[str, Exception, Callable]]] = None):
        self.responses = list(responses or [])
        self.calls: list[dict] = []

    def generate(self, system: str, prompt: str, json_mode: bool = False) -> LLMResponse:
        self.calls.append({"system": system, "prompt": prompt, "json_mode": json_mode})
        if self.responses:
            item = self.responses.pop(0)
            if isinstance(item, Exception):
                raise item
            text = item(prompt) if callable(item) else item
            return LLMResponse(text, self.name, "mock")
        return LLMResponse(self._default(prompt), self.name, "mock")

    @staticmethod
    def _default(prompt: str) -> str:
        m = re.search(r"<<<DRAFT\n(.*?)\nDRAFT>>>", prompt, re.S)
        if not m:
            raise ProviderError("Mock provider could not find a draft in the prompt.")
        draft = m.group(1)
        if "main_claim" in prompt:
            first = re.split(r"(?<=[.!?])\s", draft.strip())[0]
            return json.dumps({"main_claim": first, "supporting_explanation": "(demo provider: not analysed)", "reasoning_link": "",
                               "evidence_present": [], "missing_support": ["Demo provider only: no real analysis performed."],
                               "qualifications_and_counterarguments": [], "implications": [], "repetition_without_value": [],
                               "underexplained_ideas": [], "needs_information_from_author": []})
        revised = draft
        for pat, rep in _FILLERS:
            revised = re.sub(pat, rep, revised, flags=re.I)
        revised = re.sub(r"[ \t]{2,}", " ", revised)
        changes = [] if revised == draft else [{"change": "Removed filler wording", "reason": "Demo provider rule-based edit"}]
        return json.dumps({"revised_text": revised if "findings_only" not in prompt else "", "changes": changes, "placeholders": [],
                           "questions_for_author": [], "findings": ["Demo provider: rule-based filler removal only."]})
