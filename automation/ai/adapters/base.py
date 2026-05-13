"""
automation/ai/adapters/base.py
================================
Abstract base class and shared data contract for all AI provider adapters.

Every adapter must:
  - Implement ``generate(prompt, model=None) -> AIResponse``
  - Implement ``validate_key(api_key) -> bool``
  - Never log or propagate the raw API key.
  - Normalise HTTP errors to the standard ``error_code`` vocabulary.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Shared error codes (subset of ResumeErrorCode, extended for provider errors)
# ---------------------------------------------------------------------------

class AIErrorCode:
    INVALID_API_KEY = "invalid_api_key"
    RATE_LIMITED = "rate_limited"
    CREDITS_EXHAUSTED = "credits_exhausted"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    EMPTY_RESPONSE = "empty_response"
    MODEL_NOT_AVAILABLE = "model_not_available"
    UNKNOWN = "unknown"


_USER_MESSAGES: dict[str, str] = {
    AIErrorCode.INVALID_API_KEY: "The API key is invalid or has been revoked. Please check your key in Settings.",
    AIErrorCode.RATE_LIMITED: "The AI provider is rate-limiting requests. Please wait a moment and try again.",
    AIErrorCode.CREDITS_EXHAUSTED: "Your AI provider account has run out of credits. Please check your billing.",
    AIErrorCode.PROVIDER_UNAVAILABLE: "The AI provider is temporarily unavailable. Please try again in a few seconds.",
    AIErrorCode.EMPTY_RESPONSE: "The AI returned an empty response. Please try again.",
    AIErrorCode.MODEL_NOT_AVAILABLE: "The selected model is not available. Please choose a different model.",
    AIErrorCode.UNKNOWN: "An unexpected error occurred with the AI provider. Please try again.",
}


# ---------------------------------------------------------------------------
# Response contract
# ---------------------------------------------------------------------------

@dataclass
class AIResponse:
    """
    Unified response returned by all adapters and the router.

    Frontend contract:
      - Display ``user_message`` for any ``success=False`` response.
      - Use ``output`` for the generated content.
      - Show ``provider_used`` / ``model_used`` for transparency.
      - ``used_byok=True`` means the user's own key was used.
      - ``retryable=True`` means the caller can retry automatically.
      - Do NOT display ``error_code`` directly — use ``user_message``.
    """

    success: bool
    output: str | None
    provider_used: str
    model_used: str
    used_byok: bool = False
    error_code: str | None = None
    user_message: str | None = None
    retryable: bool = False
    input_tokens: int | None = None
    output_tokens: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "providerUsed": self.provider_used,
            "modelUsed": self.model_used,
            "usedByok": self.used_byok,
            "errorCode": self.error_code,
            "userMessage": self.user_message,
            "retryable": self.retryable,
            "usage": {
                "inputTokens": self.input_tokens,
                "outputTokens": self.output_tokens,
            } if (self.input_tokens is not None or self.output_tokens is not None) else None,
        }


def error_response(
    provider: str,
    model: str,
    error_code: str,
    *,
    used_byok: bool = False,
    retryable: bool = False,
) -> AIResponse:
    """Convenience constructor for a failed AIResponse."""
    return AIResponse(
        success=False,
        output=None,
        provider_used=provider,
        model_used=model,
        used_byok=used_byok,
        error_code=error_code,
        user_message=_USER_MESSAGES.get(error_code, _USER_MESSAGES[AIErrorCode.UNKNOWN]),
        retryable=retryable,
    )


def http_status_to_error_code(status_code: int) -> str:
    """Map an HTTP status code to a standard AI error code."""
    if status_code in (401, 403):
        return AIErrorCode.INVALID_API_KEY
    if status_code == 429:
        return AIErrorCode.RATE_LIMITED
    if status_code == 402:
        return AIErrorCode.CREDITS_EXHAUSTED
    if status_code in (503, 502, 504, 408, 425):
        return AIErrorCode.PROVIDER_UNAVAILABLE
    return AIErrorCode.UNKNOWN


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class AIAdapter(ABC):
    """Abstract base for all provider adapters."""

    #: Provider name string (e.g. "gemini", "openai")
    provider_name: str = "unknown"

    @abstractmethod
    def generate(self, prompt: str, *, model: str | None = None, api_key: str | None = None) -> AIResponse:
        """
        Send *prompt* to the AI and return an :class:`AIResponse`.

        Args:
            prompt:   The full prompt string.
            model:    Override the default model.
            api_key:  Override the default API key (BYOK path).

        The *api_key* must NEVER be included in any log output.
        """

    @abstractmethod
    def validate_key(self, api_key: str) -> bool:
        """
        Test whether *api_key* is a valid key for this provider.

        Returns True on success, False on invalid key.  May raise for
        network errors.  Must NEVER log the key value.
        """
