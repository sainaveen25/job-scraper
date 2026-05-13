"""
tests/automation/test_ai_provider_store.py
==========================================
Unit tests for UserAIProviderStore — BYOK key storage security.
"""
from __future__ import annotations

import os
import json
import pytest

from automation.ai.provider_store import UserAIProviderStore

SECRET = "test-encryption-secret-32bytes!!"
USER_A = "user_aaa111"
USER_B = "user_bbb222"


@pytest.fixture(autouse=True)
def env_secret(monkeypatch):
    monkeypatch.setenv("AI_KEY_ENCRYPTION_SECRET", SECRET)
    # Reset lru_cache so monkeypatched env vars take effect
    from automation.ai import config as ai_config
    ai_config.get_ai_config.cache_clear()
    yield
    ai_config.get_ai_config.cache_clear()


@pytest.fixture()
def store(tmp_path):
    return UserAIProviderStore(store_dir=tmp_path / "providers")


class TestSaveAndRetrieve:
    def test_save_returns_setting_without_plaintext(self, store):
        setting = store.save(USER_A, "gemini", "AIzaSyD_fake_key_abc123")
        assert setting.provider == "gemini"
        assert setting.key_last4.endswith("123") or "****" in setting.key_last4
        # encrypted_api_key must not equal the plaintext
        assert setting.encrypted_api_key != "AIzaSyD_fake_key_abc123"
        assert "AIzaSyD_fake_key_abc123" not in setting.encrypted_api_key

    def test_save_and_decrypt_roundtrip(self, store):
        plaintext = "sk-proj-test1234567890"
        store.save(USER_A, "openai", plaintext)
        recovered = store.get_decrypted_key(USER_A, "openai")
        assert recovered == plaintext

    def test_list_for_user_excludes_encrypted_key(self, store):
        store.save(USER_A, "gemini", "AIzaSyD_realkey_shouldbenever_returned")
        providers = store.list_for_user(USER_A)
        assert len(providers) == 1
        row = providers[0]
        assert "encrypted_api_key" not in row
        assert "AIzaSyD" not in json.dumps(row)

    def test_list_for_user_includes_masked_key(self, store):
        store.save(USER_A, "anthropic", "sk-ant-fakekeyabc")
        providers = store.list_for_user(USER_A)
        row = providers[0]
        assert "key_last4" in row
        assert "****" in row["key_last4"]

    def test_multiple_providers_stored_separately(self, store):
        store.save(USER_A, "gemini", "gemini-key-111")
        store.save(USER_A, "openai", "openai-key-222")
        providers = store.list_for_user(USER_A)
        assert len(providers) == 2
        names = {p["provider"] for p in providers}
        assert names == {"gemini", "openai"}

    def test_user_isolation(self, store):
        store.save(USER_A, "groq", "groq-key-user-a")
        store.save(USER_B, "groq", "groq-key-user-b")
        key_a = store.get_decrypted_key(USER_A, "groq")
        key_b = store.get_decrypted_key(USER_B, "groq")
        assert key_a == "groq-key-user-a"
        assert key_b == "groq-key-user-b"
        assert key_a != key_b


class TestDelete:
    def test_delete_removes_provider(self, store):
        store.save(USER_A, "gemini", "some-key")
        assert store.delete(USER_A, "gemini") is True
        assert store.get(USER_A, "gemini") is None

    def test_delete_nonexistent_returns_false(self, store):
        assert store.delete(USER_A, "openai") is False

    def test_delete_only_removes_target_provider(self, store):
        store.save(USER_A, "gemini", "key-1")
        store.save(USER_A, "openai", "key-2")
        store.delete(USER_A, "gemini")
        providers = store.list_for_user(USER_A)
        assert len(providers) == 1
        assert providers[0]["provider"] == "openai"


class TestFeatureFlags:
    def test_is_enabled_for_resume_tailor_default_true(self, store):
        store.save(USER_A, "gemini", "key")
        setting = store.get(USER_A, "gemini")
        assert setting.is_enabled_for("resume_tailor") is True

    def test_is_enabled_for_disabled_when_flag_false(self, store):
        store.save(USER_A, "gemini", "key", use_for_resume_tailoring=False)
        setting = store.get(USER_A, "gemini")
        assert setting.is_enabled_for("resume_tailor") is False

    def test_is_enabled_for_returns_false_when_globally_disabled(self, store):
        store.save(USER_A, "gemini", "key", enabled=False)
        setting = store.get(USER_A, "gemini")
        assert setting.is_enabled_for("resume_tailor") is False

    def test_get_enabled_for_feature_returns_correct_setting(self, store):
        store.save(USER_A, "gemini", "key", use_for_ats_analysis=True)
        result = store.get_enabled_for_feature(USER_A, "ats_analysis")
        assert result is not None
        assert result.provider == "gemini"

    def test_get_enabled_for_feature_none_when_none_configured(self, store):
        result = store.get_enabled_for_feature(USER_A, "resume_tailor")
        assert result is None


class TestInvalidProvider:
    def test_unsupported_provider_raises(self, store):
        with pytest.raises(ValueError, match="Unsupported provider"):
            store.save(USER_A, "unknown_provider_xyz", "some-key")


class TestNoPlaintextInStorage:
    def test_storage_file_contains_no_plaintext_key(self, store, tmp_path):
        plaintext = "sk-super-secret-this-must-not-appear-in-file"
        store.save(USER_A, "openai", plaintext)
        # Read raw storage file
        all_text = ""
        for f in (tmp_path / "providers").rglob("*.json"):
            all_text += f.read_text(encoding="utf-8")
        assert plaintext not in all_text
        assert "super-secret" not in all_text
