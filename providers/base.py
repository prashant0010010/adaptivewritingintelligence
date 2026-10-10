"""Replaceable language-model provider interface plus shared error types."""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass


class ProviderError(Exception):
    """Base class. Messages are safe to show to the user (never contain keys)."""


class ProviderNotConfigured(ProviderError):
    pass


class ProviderRateLimited(ProviderError):
    pass


class ProviderTimeout(ProviderError):
    pass


class ProviderResponseError(ProviderError):
    pass


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str = ""
    latency_seconds: float = 0.0


class LLMProvider(ABC):
    name = "base"
    sends_data_externally = True

    @abstractmethod
    def generate(self, system: str, prompt: str, json_mode: bool = False) -> LLMResponse:
        """Return model text. Raise a ProviderError subclass on any failure."""


def extract_json(text: str) -> dict:
    """Parse a JSON object from model output, tolerating code fences and surrounding prose."""
    if not isinstance(text, str) or not text.strip():
        raise ProviderResponseError("The model returned an empty response.")
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.I)
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        start, end = s.find("{"), s.rfind("}")
        if start == -1 or end <= start:
            raise ProviderResponseError("The model response was not valid JSON.")
        try:
            data = json.loads(s[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ProviderResponseError("The model response was not valid JSON.") from exc
    if not isinstance(data, dict):
        raise ProviderResponseError("The model response was JSON but not an object.")
    return data
