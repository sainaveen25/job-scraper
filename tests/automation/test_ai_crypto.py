"""
tests/automation/test_ai_crypto.py
====================================
Unit tests for automation.ai.crypto — key encryption / decryption / masking.
All tests use an in-process secret; no network calls.
"""
from __future__ import annotations

import pytest

from automation.ai.crypto import (
    KeyEncryptionError,
    decrypt_api_key,
    encrypt_api_key,
    mask_key,
)

SECRET = "test-secret-for-unit-testing-only"
SECRET_2 = "different-secret-will-fail"


class TestEncryptDecryptRoundTrip:
    def test_roundtrip_gemini_key(self):
        plaintext = "AIzaSyD_fake_gemini_key_for_test"
        encrypted = encrypt_api_key(plaintext, SECRET)
        assert decrypt_api_key(encrypted, SECRET) == plaintext

    def test_roundtrip_openai_key(self):
        plaintext = "sk-proj-fakeopenaikeyfortesting1234567890"
        encrypted = encrypt_api_key(plaintext, SECRET)
        assert decrypt_api_key(encrypted, SECRET) == plaintext

    def test_roundtrip_short_key(self):
        plaintext = "abc1"
        encrypted = encrypt_api_key(plaintext, SECRET)
        assert decrypt_api_key(encrypted, SECRET) == plaintext

    def test_ciphertext_differs_from_plaintext(self):
        plaintext = "sk-secret-key"
        encrypted = encrypt_api_key(plaintext, SECRET)
        assert plaintext not in encrypted
        assert "sk-secret-key" not in encrypted

    def test_different_secret_fails_decryption(self):
        encrypted = encrypt_api_key("my-api-key", SECRET)
        with pytest.raises(KeyEncryptionError):
            decrypt_api_key(encrypted, SECRET_2)

    def test_tampered_ciphertext_fails_decryption(self):
        encrypted = encrypt_api_key("my-api-key", SECRET)
        tampered = encrypted[:-4] + "XXXX"
        with pytest.raises(KeyEncryptionError):
            decrypt_api_key(tampered, SECRET)

    def test_empty_plaintext_raises(self):
        with pytest.raises(KeyEncryptionError):
            encrypt_api_key("", SECRET)

    def test_empty_secret_raises_on_encrypt(self):
        with pytest.raises(KeyEncryptionError):
            encrypt_api_key("my-key", "")

    def test_empty_secret_raises_on_decrypt(self):
        with pytest.raises(KeyEncryptionError):
            decrypt_api_key("sometoken", "")


class TestMaskKey:
    def test_long_key_shows_last_four(self):
        masked = mask_key("sk-proj-abc123xyz789")
        assert masked.endswith("z789") or masked.endswith("789")
        assert "****" in masked
        assert "sk-proj" not in masked
        assert "abc123" not in masked

    def test_short_key_shows_last_four_or_all(self):
        masked = mask_key("ab12")
        assert "****" in masked
        assert len(masked) >= 4

    def test_empty_key_returns_stars(self):
        masked = mask_key("")
        assert masked == "****"

    def test_mask_does_not_expose_plaintext(self):
        plaintext = "sk-superlongsecretkey12345"
        masked = mask_key(plaintext)
        # Only last 4 characters should appear
        assert plaintext[:10] not in masked
        assert masked.startswith("****")
