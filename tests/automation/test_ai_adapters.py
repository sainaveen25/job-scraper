"""
tests/automation/test_ai_adapters.py
=====================================
Unit tests for all AI provider adapters.

All tests use responses.mock / unittest.mock to intercept HTTP calls.
No real API keys or network connections needed.
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from automation.ai.adapters.base import AIErrorCode


def _mock_requests_post(status_code: int, json_body: dict) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_body
    return mock_resp


def _mock_requests_get(status_code: int) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    return mock_resp


FAKE_KEY = "fake-key-for-test"

# ---------------------------------------------------------------------------
# Gemini adapter
# ---------------------------------------------------------------------------

class TestGeminiAdapter:
    @pytest.fixture()
    def adapter(self):
        from automation.ai.adapters.gemini import GeminiAdapter
        return GeminiAdapter(default_api_key=FAKE_KEY, default_model="gemini-2.0-flash-lite")

    def test_successful_generation(self, adapter):
        body = {"candidates": [{"content": {"parts": [{"text": "Hello from Gemini!"}]}}], "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5}}
        with patch("requests.post", return_value=_mock_requests_post(200, body)):
            resp = adapter.generate("Say hello")
        assert resp.success is True
        assert resp.output == "Hello from Gemini!"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 5

    def test_401_maps_to_invalid_api_key(self, adapter):
        with patch("requests.post", return_value=_mock_requests_post(401, {})):
            resp = adapter.generate("test")
        assert resp.error_code == AIErrorCode.INVALID_API_KEY
        assert resp.success is False

    def test_429_maps_to_rate_limited(self, adapter):
        with patch("requests.post", return_value=_mock_requests_post(429, {})):
            resp = adapter.generate("test")
        assert resp.error_code == AIErrorCode.RATE_LIMITED
        assert resp.retryable is True

    def test_empty_response_body(self, adapter):
        body = {"candidates": [{"content": {"parts": [{"text": ""}]}}]}
        with patch("requests.post", return_value=_mock_requests_post(200, body)):
            resp = adapter.generate("test")
        assert resp.error_code == AIErrorCode.EMPTY_RESPONSE

    def test_key_not_in_logs_on_failure(self, adapter, caplog):
        with caplog.at_level(logging.DEBUG), \
             patch("requests.post", return_value=_mock_requests_post(401, {})):
            adapter.generate("test", api_key=FAKE_KEY)
        assert FAKE_KEY not in "\n".join(caplog.messages)


# ---------------------------------------------------------------------------
# OpenAI adapter
# ---------------------------------------------------------------------------

class TestOpenAIAdapter:
    @pytest.fixture()
    def adapter(self):
        from automation.ai.adapters.openai import OpenAIAdapter
        return OpenAIAdapter(default_api_key=FAKE_KEY, default_model="gpt-4o-mini")

    def test_successful_generation(self, adapter):
        body = {"choices": [{"message": {"content": "Hello from OpenAI!"}}], "usage": {"prompt_tokens": 8, "completion_tokens": 4}}
        with patch("requests.post", return_value=_mock_requests_post(200, body)):
            resp = adapter.generate("Say hello")
        assert resp.success is True
        assert resp.output == "Hello from OpenAI!"
        assert resp.input_tokens == 8
        assert resp.output_tokens == 4

    def test_403_maps_to_invalid_api_key(self, adapter):
        with patch("requests.post", return_value=_mock_requests_post(403, {})):
            resp = adapter.generate("test")
        assert resp.error_code == AIErrorCode.INVALID_API_KEY

    def test_429_maps_to_rate_limited_and_retryable(self, adapter):
        with patch("requests.post", return_value=_mock_requests_post(429, {})):
            resp = adapter.generate("test")
        assert resp.error_code == AIErrorCode.RATE_LIMITED
        assert resp.retryable is True

    def test_502_maps_to_provider_unavailable(self, adapter):
        with patch("requests.post", return_value=_mock_requests_post(502, {})):
            resp = adapter.generate("test")
        assert resp.error_code == AIErrorCode.PROVIDER_UNAVAILABLE

    def test_validate_key_true_on_200(self, adapter):
        with patch("requests.get", return_value=_mock_requests_get(200)):
            assert adapter.validate_key(FAKE_KEY) is True

    def test_validate_key_false_on_401(self, adapter):
        with patch("requests.get", return_value=_mock_requests_get(401)):
            assert adapter.validate_key(FAKE_KEY) is False

    def test_key_not_in_logs(self, adapter, caplog):
        with caplog.at_level(logging.DEBUG), \
             patch("requests.post", return_value=_mock_requests_post(403, {})):
            adapter.generate("test", api_key=FAKE_KEY)
        assert FAKE_KEY not in "\n".join(caplog.messages)


# ---------------------------------------------------------------------------
# Anthropic adapter
# ---------------------------------------------------------------------------

class TestAnthropicAdapter:
    @pytest.fixture()
    def adapter(self):
        from automation.ai.adapters.anthropic import AnthropicAdapter
        return AnthropicAdapter(default_api_key=FAKE_KEY, default_model="claude-haiku-4-5")

    def test_successful_generation(self, adapter):
        body = {"content": [{"text": "Hello from Claude!"}], "usage": {"input_tokens": 12, "output_tokens": 6}}
        with patch("requests.post", return_value=_mock_requests_post(200, body)):
            resp = adapter.generate("Say hello")
        assert resp.success is True
        assert resp.output == "Hello from Claude!"
        assert resp.input_tokens == 12
        assert resp.output_tokens == 6

    def test_401_maps_to_invalid_api_key(self, adapter):
        with patch("requests.post", return_value=_mock_requests_post(401, {})):
            resp = adapter.generate("test")
        assert resp.error_code == AIErrorCode.INVALID_API_KEY

    def test_429_maps_to_rate_limited(self, adapter):
        with patch("requests.post", return_value=_mock_requests_post(429, {})):
            resp = adapter.generate("test")
        assert resp.error_code == AIErrorCode.RATE_LIMITED


# ---------------------------------------------------------------------------
# Groq adapter
# ---------------------------------------------------------------------------

class TestGroqAdapter:
    @pytest.fixture()
    def adapter(self):
        from automation.ai.adapters.groq import GroqAdapter
        return GroqAdapter(default_api_key=FAKE_KEY, default_model="llama-3.3-70b-versatile")

    def test_successful_generation(self, adapter):
        body = {"choices": [{"message": {"content": "Hello from Groq!"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 3}}
        with patch("requests.post", return_value=_mock_requests_post(200, body)):
            resp = adapter.generate("Say hello")
        assert resp.success is True
        assert resp.output == "Hello from Groq!"

    def test_429_maps_to_rate_limited(self, adapter):
        with patch("requests.post", return_value=_mock_requests_post(429, {})):
            resp = adapter.generate("test")
        assert resp.error_code == AIErrorCode.RATE_LIMITED
        assert resp.retryable is True


# ---------------------------------------------------------------------------
# OpenRouter adapter
# ---------------------------------------------------------------------------

class TestOpenRouterAdapter:
    @pytest.fixture()
    def adapter(self):
        from automation.ai.adapters.openrouter import OpenRouterAdapter
        return OpenRouterAdapter(default_api_key=FAKE_KEY, default_model="openai/gpt-4o-mini")

    def test_successful_generation(self, adapter):
        body = {"choices": [{"message": {"content": "Hello from OpenRouter!"}}], "usage": {"prompt_tokens": 7, "completion_tokens": 3}}
        with patch("requests.post", return_value=_mock_requests_post(200, body)):
            resp = adapter.generate("Say hello")
        assert resp.success is True
        assert resp.output == "Hello from OpenRouter!"

    def test_missing_model_returns_error(self):
        from automation.ai.adapters.openrouter import OpenRouterAdapter
        adapter = OpenRouterAdapter(default_api_key=FAKE_KEY, default_model="")
        resp = adapter.generate("test")
        assert resp.error_code == AIErrorCode.MODEL_NOT_AVAILABLE

    def test_401_maps_to_invalid_api_key(self, adapter):
        with patch("requests.post", return_value=_mock_requests_post(401, {})):
            resp = adapter.generate("test")
        assert resp.error_code == AIErrorCode.INVALID_API_KEY


# ---------------------------------------------------------------------------
# AIResponse.to_dict contract
# ---------------------------------------------------------------------------

class TestAIResponseContract:
    def test_to_dict_success_shape(self):
        from automation.ai.adapters.base import AIResponse
        resp = AIResponse(
            success=True, output="result", provider_used="gemini",
            model_used="gemini-2.0-flash-lite", used_byok=True,
            input_tokens=100, output_tokens=50
        )
        d = resp.to_dict()
        assert d["success"] is True
        assert d["output"] == "result"
        assert d["providerUsed"] == "gemini"
        assert d["modelUsed"] == "gemini-2.0-flash-lite"
        assert d["usedByok"] is True
        assert d["usage"]["inputTokens"] == 100
        assert d["usage"]["outputTokens"] == 50
        assert d["errorCode"] is None

    def test_to_dict_error_shape(self):
        from automation.ai.adapters.base import AIResponse
        resp = AIResponse(
            success=False, output=None, provider_used="openai",
            model_used="gpt-4o-mini", used_byok=False,
            error_code="rate_limited", user_message="Rate limit hit.",
            retryable=True
        )
        d = resp.to_dict()
        assert d["success"] is False
        assert d["errorCode"] == "rate_limited"
        assert d["retryable"] is True
        assert d["output"] is None
