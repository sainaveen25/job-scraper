"""
automation/ai/crypto.py
========================
Server-side encryption / decryption for user BYOK API keys.

Uses ``cryptography.fernet`` (AES-128-CBC + HMAC-SHA256) which is a
transitive dependency of Scrapling.  Keys are derived from the
``AI_KEY_ENCRYPTION_SECRET`` env variable and are NEVER logged or
returned to the client.

Public API
----------
encrypt_api_key(plaintext, secret) -> str   # ciphertext string (safe to store in DB)
decrypt_api_key(ciphertext, secret) -> str   # original key, server-side only
mask_key(plaintext) -> str                   # "****<last4>"
"""
from __future__ import annotations

import base64
import hashlib
import logging

logger = logging.getLogger(__name__)


class KeyEncryptionError(Exception):
    """Raised when encryption or decryption fails.  Message is safe to log."""


def _derive_fernet_key(secret: str) -> bytes:
    """Derive a 32-byte key from *secret* and base64url-encode it for Fernet."""
    # SHA-256 of the secret gives us exactly 32 bytes.
    raw = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(raw)


def encrypt_api_key(plaintext: str, secret: str) -> str:
    """
    Encrypt *plaintext* using Fernet (AES-128-CBC + HMAC-SHA256).

    The *secret* must be a non-empty string.  The returned ciphertext is a
    URL-safe base64 string safe to store in any text column.

    Raises:
        KeyEncryptionError: if encryption fails for any reason.
    """
    if not plaintext:
        raise KeyEncryptionError("Cannot encrypt an empty API key.")
    if not secret:
        raise KeyEncryptionError(
            "AI_KEY_ENCRYPTION_SECRET is not set.  "
            "Set this env variable to enable BYOK key storage."
        )
    try:
        from cryptography.fernet import Fernet

        fernet_key = _derive_fernet_key(secret)
        f = Fernet(fernet_key)
        token = f.encrypt(plaintext.encode("utf-8"))
        return token.decode("ascii")
    except ImportError:
        raise KeyEncryptionError(
            "The 'cryptography' package is required for BYOK key storage."
        )
    except Exception as exc:
        # Log only the type, not the message — which might contain key material.
        logger.error("encrypt_api_key failed: %s", type(exc).__name__)
        raise KeyEncryptionError("Failed to encrypt API key.") from exc


def decrypt_api_key(ciphertext: str, secret: str) -> str:
    """
    Decrypt *ciphertext* using the same Fernet key derived from *secret*.

    This must only be called server-side.  The result is NEVER returned
    to the client or stored in logs.

    Raises:
        KeyEncryptionError: if decryption fails (wrong secret, tampered data, etc.)
    """
    if not ciphertext:
        raise KeyEncryptionError("Cannot decrypt an empty ciphertext.")
    if not secret:
        raise KeyEncryptionError(
            "AI_KEY_ENCRYPTION_SECRET is not set.  Cannot decrypt API key."
        )
    try:
        from cryptography.fernet import Fernet, InvalidToken

        fernet_key = _derive_fernet_key(secret)
        f = Fernet(fernet_key)
        plaintext = f.decrypt(ciphertext.encode("ascii"))
        return plaintext.decode("utf-8")
    except ImportError:
        raise KeyEncryptionError(
            "The 'cryptography' package is required for BYOK key decryption."
        )
    except Exception:
        # Do NOT log the exception message — it may contain key material.
        logger.warning("decrypt_api_key: decryption failed (wrong secret or tampered data)")
        raise KeyEncryptionError(
            "Failed to decrypt API key.  The encryption secret may have changed."
        )


def mask_key(plaintext: str) -> str:
    """
    Return a masked version of *plaintext* showing only the last 4 characters.

    Examples::

        mask_key("sk-abc123xyz")  # "****xyz"  (shows last 4: "xyz" + 4 stars)
        mask_key("ab")            # "****"

    This is safe to return to the frontend and to log.
    """
    if not plaintext:
        return "****"
    last4 = plaintext[-4:] if len(plaintext) >= 4 else plaintext
    return f"****{last4}"
