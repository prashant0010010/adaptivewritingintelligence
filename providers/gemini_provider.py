"""Google Gemini provider using the google-genai SDK (`pip install google-genai`).

SDK usage verified against google-genai 2.x: genai.Client(api_key=..., http_options=types.HttpOptions(timeout=<ms>))
and client.models.generate_content(model=..., contents=..., config=types.GenerateContentConfig(...)).
Model names and quotas change; the model comes from GEMINI_MODEL in .env.
"""
from __future__ import annotations

import logging
import time

from providers.base import (LLMProvider, LLMResponse, ProviderError, ProviderNotConfigured, ProviderRateLimited,
                            ProviderResponseError, ProviderTimeout)

log = logging.getLogger("awi.gemini")


class GeminiProvider(LLMProvider):
    name = "gemini"
    sends_data_externally = True

    def __init__(self, api_key: str, model: str, timeout: int = 60, max_retries: int = 2, _client=None, _sleep=time.sleep):
        self.api_key, self.model = (api_key or "").strip(), model
        self.timeout, self.max_retries, self._client, self._sleep = timeout, max_retries, _client, _sleep

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise ProviderNotConfigured("No Gemini API key is set. Add GEMINI_API_KEY to your .env file, or use local-only mode.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ProviderNotConfigured("The google-genai package is not installed. Run: pip install -r requirements.txt") from exc
        self._client = genai.Client(api_key=self.api_key, http_options=types.HttpOptions(timeout=int(self.timeout * 1000)))
        return self._client

    def _classify(self, exc: Exception) -> tuple[ProviderError, bool]:
        code = getattr(exc, "code", None)
        name = type(exc).__name__.lower()
        if "timeout" in name or "timed out" in str(exc).lower():
            return ProviderTimeout(f"The request timed out after {self.timeout}s."), True
        if code == 429:
            return ProviderRateLimited("Rate limit or quota reached. Wait a moment, or check your plan and quota."), True
        if isinstance(code, int) and code >= 500:
            return ProviderError(f"The provider had a temporary server error ({code})."), True
        if code in (400, 401, 403):
            return ProviderError(f"The provider rejected the request ({code}). Check the API key, model name and permissions."), False
        if code == 404:
            return ProviderError("Model not found. Check GEMINI_MODEL in .env against Google's current model list."), False
        return ProviderError(f"The provider request failed ({type(exc).__name__})."), False

    def generate(self, system: str, prompt: str, json_mode: bool = False) -> LLMResponse:
        client = self._get_client()
        try:
            from google.genai import types
            cfg = types.GenerateContentConfig(system_instruction=system, temperature=0.4,
                                              response_mime_type="application/json" if json_mode else None)
        except ImportError:
            cfg = None
        started, last = time.time(), None
        for attempt in range(self.max_retries + 1):
            try:
                resp = client.models.generate_content(model=self.model, contents=prompt, config=cfg)
                text = getattr(resp, "text", None)
                if not text or not str(text).strip():
                    raise ProviderResponseError("The model returned no text (it may have been blocked or empty).")
                return LLMResponse(str(text), self.name, self.model, round(time.time() - started, 2))
            except ProviderResponseError:
                raise
            except ProviderNotConfigured:
                raise
            except Exception as exc:  # SDK exceptions vary by version; classify defensively
                err, retry = self._classify(exc)
                last = err
                log.warning("Gemini call failed (attempt %d): %s", attempt + 1, type(exc).__name__)
                if retry and attempt < self.max_retries:
                    self._sleep(min(2 ** attempt * 1.5, 10))
                    continue
                raise err from None
        raise last or ProviderError("Request failed.")
