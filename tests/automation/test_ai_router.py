"""
tests/automation/test_ai_router.py
====================================
Unit tests for ProviderRouter — BYOK selection, managed fallback,
usage limits, and no plaintext key logging.

All HTTP calls are mocked — zero network access.
"""
from __future__ import annotations

import logging
import json
from unittest.mock import MagicMock, patch

import pytest

from automation.ai.adapters.base import AIResponse, AIErrorCode
from automation.ai.provider_store import UserAIProviderStore
from automation.ai.usage_store import AIUsageStore
from automation.ai.router import ProviderRouter

SECRET = "router-test-secret-32bytes!!!!!!"
USER = "user_router_test"


@pytest.fixture(autouse=True)
def env_secret(monkeypatch):
    monkeypatch.setenv("AI_KEY_ENCRYPTION_SECRET", SECRET)
    monkeypatch.setenv("APPLYMATE_DEFAULT_AI_PROVIDER", "gemini")
    monkeypatch.setenv("APPLYMATE_GEMINI_API_KEY", "managed-gemini-key")
    monkeypatch.setenv("APPLYMATE_GEMINI_MODEL", "gemini-2.0-flash-lite")
    from automation.ai import config as ai_config
    ai_config.get_ai_config.cache_clear()
    yield
    ai_config.get_ai_config.cache_clear()


@pytest.fixture()
def provider_store(tmp_path):
    return UserAIProviderStore(store_dir=tmp_path / "providers")


@pytest.fixture()
def usage_store(tmp_path):
    return AIUsageStore(store_dir=tmp_path / "usage")


@pytest.fixture()
def router(provider_store, usage_store):
    return ProviderRouter(provider_store=provider_store, usage_store=usage_store)


# ---------------------------------------------------------------------------
# BYOK vs managed selection
# ---------------------------------------------------------------------------

class TestByokSelection:
    def test_byok_selected_over_managed_when_configured(self, router, provider_store):
        provider_store.save(USER, "openai", "sk-user-openai-key")
        fake_resp = AIResponse(success=True, output="tailored resume text",
                               provider_used="openai", model_used="gpt-4o-mini", used_byok=True)

        with patch("automation.ai.router._build_byok_adapter") as mock_build:
            mock_adapter = MagicMock()
            mock_adapter.generate.return_value = fake_resp
            mock_build.return_value = mock_adapter

            resp = router.route(USER, "resume_tailor", "tailor this resume")

        assert resp.success is True
        assert resp.used_byok is True
        assert resp.provider_used == "openai"
        mock_build.assert_called_once()

    def test_managed_used_when_no_byok_configured(self, router):
        fake_resp = AIResponse(success=True, output="managed result",
                               provider_used="applymate/gemini", model_used="gemini-2.0-flash-lite", used_byok=False)

        with patch("automation.ai.adapters.applymate.ApplyMateAdapter.generate", return_value=fake_resp):
            resp = router.route(USER, "resume_tailor", "tailor this resume")

        assert resp.used_byok is False
        assert "gemini" in resp.provider_used

    def test_fallback_false_returns_error_when_no_byok(self, router):
        resp = router.route(USER, "resume_tailor", "tailor this resume", fallback=False)
        assert resp.success is False
        assert resp.error_code == AIErrorCode.INVALID_API_KEY


class TestUsageLimits:
    def test_managed_key_blocked_after_daily_limit(self, router, usage_store, monkeypatch):
        # Simulate having hit the daily limit
        monkeypatch.setenv("AI_FREE_TIER_DAILY_LIMIT", "2")
        from automation.ai import config as ai_config
        ai_config.get_ai_config.cache_clear()

        for _ in range(2):
            usage_store.log_event(USER, "resume_tailor", "applymate/gemini", "gemini-2.0-flash-lite",
                                  used_byok=False, status="ok")

        resp = router.route(USER, "resume_tailor", "tailor this resume")
        assert resp.success is False
        assert resp.error_code == AIErrorCode.CREDITS_EXHAUSTED
        assert resp.used_byok is False

    def test_byok_usage_does_not_count_toward_managed_limit(self, router, provider_store, usage_store, monkeypatch):
        monkeypatch.setenv("AI_FREE_TIER_DAILY_LIMIT", "1")
        from automation.ai import config as ai_config
        ai_config.get_ai_config.cache_clear()

        # Log a BYOK usage event (should NOT count toward managed limit)
        usage_store.log_event(USER, "resume_tailor", "openai", "gpt-4o-mini",
                              used_byok=True, status="ok")

        provider_store.save(USER, "openai", "sk-byok-key")
        fake_resp = AIResponse(success=True, output="ok", provider_used="openai",
                               model_used="gpt-4o-mini", used_byok=True)

        with patch("automation.ai.router._build_byok_adapter") as mock_build:
            mock_adapter = MagicMock()
            mock_adapter.generate.return_value = fake_resp
            mock_build.return_value = mock_adapter

            resp = router.route(USER, "resume_tailor", "tailor resume")

        assert resp.success is True
        assert resp.used_byok is True

    def test_usage_is_logged_after_successful_generation(self, router, usage_store):
        fake_resp = AIResponse(success=True, output="result",
                               provider_used="applymate/gemini", model_used="gemini-2.0-flash-lite",
                               used_byok=False, input_tokens=100, output_tokens=200)

        with patch("automation.ai.adapters.applymate.ApplyMateAdapter.generate", return_value=fake_resp):
            router.route(USER, "resume_tailor", "tailor")

        assert usage_store.get_daily_count(USER) == 1


class TestNoPlaintextKeyInLogs:
    def test_byok_key_not_logged(self, router, provider_store, caplog):
        secret_key = "sk-super-secret-key-must-not-appear-in-logs"
        provider_store.save(USER, "openai", secret_key)

        fake_resp = AIResponse(success=True, output="ok", provider_used="openai",
                               model_used="gpt-4o-mini", used_byok=True)

        with caplog.at_level(logging.DEBUG, logger="automation"), \
             patch("automation.ai.router._build_byok_adapter") as mock_build:
            mock_adapter = MagicMock()
            mock_adapter.generate.return_value = fake_resp
            mock_build.return_value = mock_adapter
            router.route(USER, "resume_tailor", "tailor")

        full_log = "\n".join(caplog.messages)
        assert secret_key not in full_log
        assert "super-secret" not in full_log

    def test_managed_key_not_logged(self, router, caplog, monkeypatch):
        monkeypatch.setenv("APPLYMATE_GEMINI_API_KEY", "AIzamanaged-secret-key-must-not-log")
        from automation.ai import config as ai_config
        ai_config.get_ai_config.cache_clear()

        fake_resp = AIResponse(success=True, output="ok", provider_used="applymate/gemini",
                               model_used="gemini-2.0-flash-lite", used_byok=False)

        with caplog.at_level(logging.DEBUG, logger="automation"), \
             patch("automation.ai.adapters.applymate.ApplyMateAdapter.generate", return_value=fake_resp):
            router.route(USER, "resume_tailor", "tailor")

        full_log = "\n".join(caplog.messages)
        assert "AIzamanaged-secret-key-must-not-log" not in full_log


class TestFeatureTypeRouting:
    def test_byok_respects_feature_flag_disabled(self, router, provider_store):
        """If BYOK is configured but disabled for ats_analysis, use managed fallback."""
        provider_store.save(USER, "openai", "sk-key", use_for_ats_analysis=False)

        fake_resp = AIResponse(success=True, output="ok", provider_used="applymate/gemini",
                               model_used="gemini-2.0-flash-lite", used_byok=False)
        with patch("automation.ai.adapters.applymate.ApplyMateAdapter.generate", return_value=fake_resp):
            resp = router.route(USER, "ats_analysis", "analyze this")

        assert resp.used_byok is False
