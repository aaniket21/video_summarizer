import os

import pytest


def test_llm_provider_fallback(monkeypatch):
    from backend.app.llm import providers

    calls = []

    def fail_provider(_transcript: str, _chapters: list):
        calls.append("gemini")
        raise RuntimeError("gemini failed")

    def ok_provider(_transcript: str, _chapters: list):
        calls.append("claude")
        return {"title": "ok", "notesMarkdown": "# ok"}

    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_FALLBACKS", "claude,openai")

    monkeypatch.setattr(providers, "PROVIDERS", {
        "gemini": fail_provider,
        "claude": ok_provider,
        "openai": ok_provider,
    })

    payload = providers.generate_notes("hello", [])
    assert payload["title"] == "ok"
    assert calls == ["gemini", "claude"]


def test_llm_provider_exhausts_all(monkeypatch):
    from backend.app.llm import providers

    def fail_provider(_transcript: str, _chapters: list):
        raise RuntimeError("failed")

    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("LLM_FALLBACKS", "claude")

    monkeypatch.setattr(providers, "PROVIDERS", {
        "gemini": fail_provider,
        "claude": fail_provider,
    })

    with pytest.raises(RuntimeError, match="All providers failed"):
        providers.generate_notes("hello", [])
