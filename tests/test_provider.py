import json

import pytest

from core.argument_analysis import llm_analyse_argument, validate_llm_analysis
from core.revision_engine import MODES, RevisionContext, build_prompt, generate_revision, parse_revision_response, plan_revision
from providers.base import ProviderError, ProviderNotConfigured, ProviderRateLimited, ProviderResponseError, ProviderTimeout, extract_json
from providers.gemini_provider import GeminiProvider
from providers.mock_provider import MockProvider
from config.settings import get_settings

DRAFT = "This is very basically a draft in order to test things."


def test_missing_api_key_does_not_crash_construction_and_raises_clear_error():
    p = GeminiProvider("", "model")
    with pytest.raises(ProviderNotConfigured):
        p.generate("s", "p")


def test_settings_repr_hides_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSECRETSECRETSECRETSECRET1234")
    assert "AIzaSECRET" not in repr(get_settings())


def test_extract_json_variants():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": 1} hope that helps') == {"a": 1}
    for bad in ["", "not json", "[1,2]", "{broken"]:
        with pytest.raises(ProviderResponseError):
            extract_json(bad)


def test_malformed_revision_responses():
    with pytest.raises(ProviderResponseError):
        parse_revision_response("nonsense", "clarity")
    with pytest.raises(ProviderResponseError):
        parse_revision_response(json.dumps({"revised_text": ""}), "clarity")
    with pytest.raises(ProviderResponseError):
        parse_revision_response(json.dumps({"revised_text": 5}), "clarity")
    assert parse_revision_response(json.dumps({"revised_text": "", "findings": ["x"]}), "diagnose")["findings"] == ["x"]


def test_generate_revision_with_mock():
    r = generate_revision(MockProvider(), DRAFT, "Essay", "minimal_edit")
    assert "in order to" not in r.revised_text and r.provider == "mock" and r.changes


def test_generate_revision_propagates_provider_errors():
    for exc in (ProviderTimeout("t"), ProviderRateLimited("r"), ProviderError("e")):
        with pytest.raises(type(exc)):
            generate_revision(MockProvider([exc]), DRAFT, "Essay", "clarity")


def test_empty_draft_rejected():
    with pytest.raises(ValueError):
        generate_revision(MockProvider(), "  ", "Essay", "clarity")


def test_prompt_contains_preferences_and_limited_examples_only():
    ctx = RevisionContext({"audience": "tutors"}, {"length": "shorter"}, ["leverage"], [{"text": "approved one"}])
    p = build_prompt(DRAFT, "Essay", "clarity", ctx)
    assert "tutors" in p and "leverage" in p and "approved one" in p and DRAFT in p
    assert "tutors" not in build_prompt(DRAFT, "Essay", "clarity", ctx, use_preferences=False)


def test_conflict_detected_between_mode_and_preference():
    assert plan_revision("elaborate", {"length": "shorter"})["conflicts"]
    assert not plan_revision("elaborate", {"length": "shorter"}, use_preferences=False)["conflicts"]
    assert set(MODES) >= {"clarity", "diagnose", "minimal_edit"}


def test_llm_analysis_validation():
    assert llm_analyse_argument(MockProvider(), "A claim here. More.")["main_claim"]
    with pytest.raises(ProviderResponseError):
        validate_llm_analysis({})
    with pytest.raises(ProviderResponseError):
        validate_llm_analysis([1])


class FakeAPIError(Exception):
    def __init__(self, code):
        self.code = code


class FakeModels:
    def __init__(self, behaviours):
        self.behaviours, self.n = behaviours, 0

    def generate_content(self, **kw):
        self.n += 1
        b = self.behaviours.pop(0)
        if isinstance(b, Exception):
            raise b
        return type("R", (), {"text": b})()


def _gem(behaviours, retries=2):
    client = type("C", (), {"models": FakeModels(behaviours)})()
    return GeminiProvider("k", "m", 5, retries, _client=client, _sleep=lambda s: None), client


def test_gemini_retries_transient_then_succeeds():
    p, c = _gem([FakeAPIError(429), FakeAPIError(503), "ok"])
    assert p.generate("s", "p").text == "ok" and c.models.n == 3


def test_gemini_rate_limit_gives_clear_error_after_retries():
    p, _ = _gem([FakeAPIError(429)] * 3)
    with pytest.raises(ProviderRateLimited):
        p.generate("s", "p")


def test_gemini_auth_error_not_retried_and_hides_key():
    client = type("C", (), {"models": FakeModels([FakeAPIError(403), "unused"])})()
    p = GeminiProvider("SECRETKEY123", "m", 5, 2, _client=client, _sleep=lambda s: None)
    with pytest.raises(ProviderError) as e:
        p.generate("s", "p")
    assert client.models.n == 1 and "SECRETKEY123" not in str(e.value)


def test_gemini_timeout_and_empty_response():
    class TimeoutError_(Exception):
        pass
    p, _ = _gem([TimeoutError_("timed out")] * 3)
    with pytest.raises(ProviderTimeout):
        p.generate("s", "p")
    p2, _ = _gem([""])
    with pytest.raises(ProviderResponseError):
        p2.generate("s", "p")
