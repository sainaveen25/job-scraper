"""
automation/ai/adapters/gemini.py
==================================
Google Gemini adapter using the REST generateContent API.

Default model:  APPLYMATE_GEMINI_MODEL env var  (gemini-2.0-flash-lite)
Endpoint:       https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
Auth:           ?key=<api_key>  (query param)
"""
from __future__ import annotations

import logging

import requests

from automation.ai.adapters.base import (
    AIAdapter,
    AIErrorCode,
    AIResponse,
    error_response,
    http_status_to_error_code,
)
from automation.ai.config import get_ai_config

logger = logging.getLogger(__name__)

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiAdapter(AIAdapter):
    provider_name = "gemini"

    def __init__(self, default_api_key: str = "", default_model: str = "") -> None:
        cfg = get_ai_config()
        self._default_key = default_api_key or cfg.applymate_gemini_api_key
        self._default_model = default_model or cfg.gemini_model
        self._timeout = cfg.request_timeout_seconds

    def generate(self, prompt: str, *, model: str | None = None, api_key: str | None = None) -> AIResponse:
        used_model = model or self._default_model
        used_key = api_key or self._default_key
        used_byok = bool(api_key)

        if not used_key:
            return error_response(self.provider_name, used_model, AIErrorCode.INVALID_API_KEY, used_byok=used_byok)

        url = f"{_BASE_URL}/{used_model}:generateContent"
        body = {"contents": [{"parts": [{"text": prompt}]}]}

        try:
            resp = requests.post(
                url,
                params={"key": used_key},
                json=body,
                timeout=self._timeout,
            )
        except requests.Timeout:
            return error_response(self.provider_name, used_model, AIErrorCode.PROVIDER_UNAVAILABLE, used_byok=used_byok, retryable=True)
        except requests.RequestException as exc:
            logger.warning("Gemini request failed: %s", type(exc).__name__)
            return error_response(self.provider_name, used_model, AIErrorCode.PROVIDER_UNAVAILABLE, used_byok=used_byok, retryable=True)

        if resp.status_code != 200:
            code = http_status_to_error_code(resp.status_code)
            retryable = code in (AIErrorCode.RATE_LIMITED, AIErrorCode.PROVIDER_UNAVAILABLE)
            return error_response(self.provider_name, used_model, code, used_byok=used_byok, retryable=retryable)

        try:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, ValueError):
            return error_response(self.provider_name, used_model, AIErrorCode.EMPTY_RESPONSE, used_byok=used_byok)

        if not text or not text.strip():
            return error_response(self.provider_name, used_model, AIErrorCode.EMPTY_RESPONSE, used_byok=used_byok)

        usage_meta = data.get("usageMetadata") or {}
        return AIResponse(
            success=True,
            output=text.strip(),
            provider_used=self.provider_name,
            model_used=used_model,
            used_byok=used_byok,
            input_tokens=usage_meta.get("promptTokenCount"),
            output_tokens=usage_meta.get("candidatesTokenCount"),
        )

    def validate_key(self, api_key: str) -> bool:
        """Send a minimal prompt to test the key.  Returns True on success."""
        resp = self.generate("Say OK", model=self._default_model, api_key=api_key)
        return resp.success or resp.error_code not in (AIErrorCode.INVALID_API_KEY,)
