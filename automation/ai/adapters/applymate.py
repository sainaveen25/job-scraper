"""
automation/ai/adapters/applymate.py
=====================================
ApplyMate managed-key adapter.

Selects the appropriate underlying adapter based on
``APPLYMATE_DEFAULT_AI_PROVIDER`` and uses ApplyMate's own API key.
This is the fallback used when a user has no BYOK provider configured.
"""
from __future__ import annotations

from automation.ai.adapters.base import AIAdapter, AIErrorCode, AIResponse, error_response
from automation.ai.config import get_ai_config


def _build_managed_adapter(provider: str) -> AIAdapter:
    """Instantiate the correct adapter for *provider* using managed keys."""
    if provider == "gemini":
        from automation.ai.adapters.gemini import GeminiAdapter
        return GeminiAdapter()
    if provider == "openai":
        from automation.ai.adapters.openai import OpenAIAdapter
        return OpenAIAdapter()
    if provider == "anthropic":
        from automation.ai.adapters.anthropic import AnthropicAdapter
        return AnthropicAdapter()
    if provider == "groq":
        from automation.ai.adapters.groq import GroqAdapter
        return GroqAdapter()
    if provider == "openrouter":
        from automation.ai.adapters.openrouter import OpenRouterAdapter
        return OpenRouterAdapter()
    raise ValueError(f"Unknown managed provider: {provider!r}")


class ApplyMateAdapter(AIAdapter):
    """
    Wraps the ApplyMate managed AI key.

    The underlying provider is determined at call time from
    ``APPLYMATE_DEFAULT_AI_PROVIDER``.  ``used_byok`` is always False.
    """

    provider_name = "applymate"

    def generate(self, prompt: str, *, model: str | None = None, api_key: str | None = None) -> AIResponse:
        cfg = get_ai_config()
        provider = cfg.default_provider

        if not cfg.managed_api_key(provider):
            return error_response(
                "applymate",
                model or cfg.default_model(provider),
                AIErrorCode.INVALID_API_KEY,
                used_byok=False,
            )

        try:
            adapter = _build_managed_adapter(provider)
        except ValueError:
            return error_response(
                "applymate",
                model or "",
                AIErrorCode.PROVIDER_UNAVAILABLE,
                used_byok=False,
            )

        # Do NOT pass api_key — the adapter uses its own managed key.
        result = adapter.generate(prompt, model=model)
        # Override provider_used to reflect "applymate" for tracking.
        result.provider_used = f"applymate/{provider}"
        return result

    def validate_key(self, api_key: str) -> bool:
        raise NotImplementedError("ApplyMate managed key validation is internal.")
