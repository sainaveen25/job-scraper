"""
automation/ai/router.py
========================
Unified AI provider router for ApplyMate.

Routing logic (in priority order):
  1. If the user has an enabled BYOK provider for this feature → use it.
  2. Else if fallback=True → check managed-key limits → use ApplyMate key.
  3. Else → return an error response.

Usage::

    from automation.ai.router import ProviderRouter

    router = ProviderRouter()
    response = router.route(
        user_id="user_123",
        feature_type="resume_tailor",
        prompt="Tailor this resume...",
    )
    if response.success:
        print(response.output)
"""
from __future__ import annotations

import logging
from typing import Any

from automation.ai.adapters.base import AIAdapter, AIErrorCode, AIResponse, error_response
from automation.ai.config import get_ai_config, SUPPORTED_PROVIDERS
from automation.ai.provider_store import UserAIProviderStore
from automation.ai.usage_store import AIUsageStore, UsageLimitExceeded

logger = logging.getLogger(__name__)

# Feature type → ProviderSetting field mapping
_FEATURE_FIELD: dict[str, str] = {
    "resume_tailor": "use_for_resume_tailoring",
    "ats_analysis": "use_for_ats_analysis",
    "cover_letter": "use_for_cover_letters",
    "job_match": "use_for_job_match",
    "question_help": "use_for_question_help",
}


def _build_byok_adapter(provider: str, api_key: str, model: str) -> AIAdapter:
    """Instantiate the correct adapter with the user's BYOK key."""
    if provider == "gemini":
        from automation.ai.adapters.gemini import GeminiAdapter
        return GeminiAdapter(default_api_key=api_key, default_model=model)
    if provider == "openai":
        from automation.ai.adapters.openai import OpenAIAdapter
        return OpenAIAdapter(default_api_key=api_key, default_model=model)
    if provider == "anthropic":
        from automation.ai.adapters.anthropic import AnthropicAdapter
        return AnthropicAdapter(default_api_key=api_key, default_model=model)
    if provider == "groq":
        from automation.ai.adapters.groq import GroqAdapter
        return GroqAdapter(default_api_key=api_key, default_model=model)
    if provider == "openrouter":
        from automation.ai.adapters.openrouter import OpenRouterAdapter
        return OpenRouterAdapter(default_api_key=api_key, default_model=model)
    raise ValueError(f"Unknown provider: {provider!r}")


class ProviderRouter:
    """
    Routes AI generation requests to the correct provider.

    Dependency injection is used for both stores so they can be easily
    replaced in tests with lightweight in-memory fakes.
    """

    def __init__(
        self,
        *,
        provider_store: UserAIProviderStore | None = None,
        usage_store: AIUsageStore | None = None,
    ) -> None:
        self._provider_store = provider_store or UserAIProviderStore()
        self._usage_store = usage_store or AIUsageStore()

    def route(
        self,
        user_id: str,
        feature_type: str,
        prompt: str,
        *,
        requested_provider: str | None = None,
        requested_model: str | None = None,
        fallback: bool = True,
        user_tier: str = "free",
    ) -> AIResponse:
        """
        Route *prompt* to the best available AI provider for *feature_type*.

        Args:
            user_id:            ApplyMate user ID.
            feature_type:       One of the FEATURE_TYPES (e.g. "resume_tailor").
            prompt:             Full prompt string.
            requested_provider: Optional override (user explicitly chose a provider).
            requested_model:    Optional model override.
            fallback:           If True, fall back to managed key when no BYOK found.
            user_tier:          "free" or "paid" — controls managed key limits.

        Returns:
            An :class:`AIResponse` (always, never raises).
        """
        # --- 1. Try BYOK provider ----------------------------------------
        byok_response = self._try_byok(
            user_id=user_id,
            feature_type=feature_type,
            prompt=prompt,
            requested_provider=requested_provider,
            requested_model=requested_model,
        )
        if byok_response is not None:
            self._log(user_id, feature_type, byok_response)
            return byok_response

        # --- 2. Fall back to managed key ---------------------------------
        if not fallback:
            return error_response(
                "applymate",
                requested_model or "",
                AIErrorCode.INVALID_API_KEY,
            )

        managed_response = self._try_managed(
            user_id=user_id,
            feature_type=feature_type,
            prompt=prompt,
            requested_model=requested_model,
            user_tier=user_tier,
        )
        self._log(user_id, feature_type, managed_response)
        return managed_response

    # ------------------------------------------------------------------
    # BYOK path
    # ------------------------------------------------------------------

    def _try_byok(
        self,
        *,
        user_id: str,
        feature_type: str,
        prompt: str,
        requested_provider: str | None,
        requested_model: str | None,
    ) -> AIResponse | None:
        """Return an AIResponse from the user's BYOK provider, or None."""
        if requested_provider and requested_provider in SUPPORTED_PROVIDERS and requested_provider != "applymate":
            setting = self._provider_store.get(user_id, requested_provider)
        else:
            setting = self._provider_store.get_enabled_for_feature(user_id, feature_type)

        if not setting or not setting.is_enabled_for(feature_type):
            return None

        api_key = self._provider_store.get_decrypted_key(user_id, setting.provider)
        if not api_key:
            logger.warning(
                "BYOK key decryption failed for user=%s provider=%s — falling back",
                user_id,
                setting.provider,
            )
            return None

        model = requested_model or setting.selected_model
        try:
            adapter = _build_byok_adapter(setting.provider, api_key, model)
        except ValueError:
            return None

        # Pass api_key explicitly so adapter sets used_byok=True
        return adapter.generate(prompt, model=model, api_key=api_key)

    # ------------------------------------------------------------------
    # Managed key path
    # ------------------------------------------------------------------

    def _try_managed(
        self,
        *,
        user_id: str,
        feature_type: str,
        prompt: str,
        requested_model: str | None,
        user_tier: str,
    ) -> AIResponse:
        """Generate using ApplyMate's managed key, respecting usage limits."""
        cfg = get_ai_config()
        model = requested_model or cfg.default_model(cfg.default_provider)

        # Check usage limits for managed key
        limit = self._usage_store.check_limit(user_id, tier=user_tier)
        if not limit.allowed:
            return AIResponse(
                success=False,
                output=None,
                provider_used="applymate",
                model_used=model,
                used_byok=False,
                error_code=AIErrorCode.CREDITS_EXHAUSTED,
                user_message=limit.reason or "AI usage limit reached. Add your own AI key or upgrade.",
                retryable=False,
            )

        from automation.ai.adapters.applymate import ApplyMateAdapter
        adapter = ApplyMateAdapter()
        return adapter.generate(prompt, model=requested_model)

    # ------------------------------------------------------------------
    # Usage logging
    # ------------------------------------------------------------------

    def _log(self, user_id: str, feature_type: str, response: AIResponse) -> None:
        try:
            self._usage_store.log_event(
                user_id=user_id,
                feature_type=feature_type,
                provider=response.provider_used,
                model=response.model_used,
                used_byok=response.used_byok,
                status="ok" if response.success else "error",
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )
        except Exception:
            pass  # Usage logging is non-critical — never fail a generation for it
