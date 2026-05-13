"""
automation/ai/adapters/openai.py
==================================
OpenAI chat completions adapter.

Default model:  APPLYMATE_OPENAI_MODEL env var  (gpt-4o-mini)
Endpoint:       https://api.openai.com/v1/chat/completions
Auth:           Bearer token
"""
from __future__ import annotations

import logging

import requests

from automation.ai.adapters.base import (
    AIAdapter, AIErrorCode, AIResponse, error_response, http_status_to_error_code,
)
from automation.ai.config import get_ai_config

logger = logging.getLogger(__name__)

_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
_MODELS_URL = "https://api.openai.com/v1/models"


class OpenAIAdapter(AIAdapter):
    provider_name = "openai"

    def __init__(self, default_api_key: str = "", default_model: str = "") -> None:
        cfg = get_ai_config()
        self._default_key = default_api_key or cfg.applymate_openai_api_key
        self._default_model = default_model or cfg.openai_model
        self._timeout = cfg.request_timeout_seconds

    def generate(self, prompt: str, *, model: str | None = None, api_key: str | None = None) -> AIResponse:
        used_model = model or self._default_model
        used_key = api_key or self._default_key
        used_byok = bool(api_key)

        if not used_key:
            return error_response(self.provider_name, used_model, AIErrorCode.INVALID_API_KEY, used_byok=used_byok)

        body = {
            "model": used_model,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            resp = requests.post(
                _COMPLETIONS_URL,
                headers={"Authorization": f"Bearer {used_key}", "Content-Type": "application/json"},
                json=body,
                timeout=self._timeout,
            )
        except requests.Timeout:
            return error_response(self.provider_name, used_model, AIErrorCode.PROVIDER_UNAVAILABLE, used_byok=used_byok, retryable=True)
        except requests.RequestException as exc:
            logger.warning("OpenAI request failed: %s", type(exc).__name__)
            return error_response(self.provider_name, used_model, AIErrorCode.PROVIDER_UNAVAILABLE, used_byok=used_byok, retryable=True)

        if resp.status_code != 200:
            code = http_status_to_error_code(resp.status_code)
            retryable = code in (AIErrorCode.RATE_LIMITED, AIErrorCode.PROVIDER_UNAVAILABLE)
            return error_response(self.provider_name, used_model, code, used_byok=used_byok, retryable=retryable)

        try:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError):
            return error_response(self.provider_name, used_model, AIErrorCode.EMPTY_RESPONSE, used_byok=used_byok)

        if not text or not text.strip():
            return error_response(self.provider_name, used_model, AIErrorCode.EMPTY_RESPONSE, used_byok=used_byok)

        usage = data.get("usage") or {}
        return AIResponse(
            success=True,
            output=text.strip(),
            provider_used=self.provider_name,
            model_used=used_model,
            used_byok=used_byok,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )

    def validate_key(self, api_key: str) -> bool:
        try:
            resp = requests.get(
                _MODELS_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False
