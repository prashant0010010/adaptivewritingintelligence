"""Shared UI helpers: app context, provider selection, consent gate."""
from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from config.settings import Settings
from database.repository import Repository
from providers.base import LLMProvider
from providers.gemini_provider import GeminiProvider
from providers.mock_provider import MockProvider

MODE_LOCAL = "Local only (no language model)"
MODE_GEMINI = "Gemini API (sends selected text to Google)"
MODE_DEMO = "Demo provider (offline, rule-based, not a real model)"


@dataclass
class Ctx:
    settings: Settings
    repo: Repository
    profile_id: int | None
    profile: dict | None


def available_modes(settings: Settings) -> list[str]:
    modes = [MODE_LOCAL, MODE_DEMO]
    if settings.gemini_configured:
        modes.insert(1, MODE_GEMINI)
    return modes


def get_provider(ctx: Ctx) -> LLMProvider | None:
    mode = st.session_state.get("llm_mode", MODE_LOCAL)
    if mode == MODE_GEMINI and ctx.settings.gemini_configured:
        return GeminiProvider(ctx.settings.gemini_api_key, ctx.settings.gemini_model, ctx.settings.request_timeout, ctx.settings.max_retries)
    if mode == MODE_DEMO:
        return MockProvider()
    return None


def require_profile(ctx: Ctx) -> bool:
    if ctx.profile_id is None:
        st.info("Create or select a profile first (Profiles page).")
        return False
    return True


def consent_gate(provider: LLMProvider | None, what: str, n_chars: int, key: str) -> bool:
    """Returns True when the action may proceed. External providers need a fresh, explicit tick."""
    if provider is None:
        st.warning("No language model is active. Choose a mode in the sidebar (Gemini needs GEMINI_API_KEY in .env). Local analysis still works.")
        return False
    if not provider.sends_data_externally:
        st.caption("Demo provider: nothing leaves your computer.")
        return True
    return st.checkbox(f"I agree to send {what} (about {n_chars:,} characters) to {provider.name.title()} for this request. "
                       "It is processed under the provider's current terms and is not sent automatically.", key=key)
