"""
automation/ai/provider_store.py
================================
File-based storage for per-user BYOK AI provider settings.

Each user's settings are stored in a JSON file at:
    <provider_store_dir>/<user_id>/providers.json

Security contract:
  - ``encrypted_api_key`` is NEVER returned by ``list_for_user`` or ``get_safe``.
  - ``get_decrypted_key`` is server-side only — never called from a path that
    returns data to the frontend.
  - Only ``provider``, ``key_last4``, ``selected_model``, ``enabled``,
    ``use_for_*``, ``last_tested_at``, ``last_test_status``, ``created_at``,
    ``updated_at`` are safe to return to the client.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automation.ai.crypto import KeyEncryptionError, decrypt_api_key, encrypt_api_key, mask_key
from automation.ai.config import get_ai_config, SUPPORTED_PROVIDERS


# Fields that are NEVER sent to the client.
_SENSITIVE_FIELDS = frozenset({"encrypted_api_key"})

# Feature-type → ProviderSetting field name mapping (module-level, not a dataclass field).
_FEATURE_FIELD_MAP: dict[str, str] = {
    "resume_tailor": "use_for_resume_tailoring",
    "ats_analysis": "use_for_ats_analysis",
    "cover_letter": "use_for_cover_letters",
    "job_match": "use_for_job_match",
    "question_help": "use_for_question_help",
}



@dataclass
class ProviderSetting:
    id: str
    user_id: str
    provider: str
    encrypted_api_key: str
    key_last4: str
    selected_model: str
    enabled: bool = True
    use_for_resume_tailoring: bool = True
    use_for_ats_analysis: bool = True
    use_for_cover_letters: bool = True
    use_for_job_match: bool = True
    use_for_question_help: bool = True
    last_tested_at: str | None = None
    last_test_status: str | None = None  # "ok" | "invalid_key" | "error"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_safe_dict(self) -> dict[str, Any]:
        """Return a dict safe to return to the frontend — no encrypted key."""
        d = asdict(self)
        for key in _SENSITIVE_FIELDS:
            d.pop(key, None)
        return d

    def is_enabled_for(self, feature_type: str) -> bool:
        """Return True if this provider is enabled for *feature_type*."""
        if not self.enabled:
            return False
        attr = _FEATURE_FIELD_MAP.get(feature_type)
        if attr is None:
            return False
        return bool(getattr(self, attr, False))


class UserAIProviderStore:
    """
    File-based per-user storage for BYOK provider settings.

    Each user has a single JSON file under ``store_dir/<user_id>/providers.json``.
    """

    def __init__(self, store_dir: str | Path | None = None) -> None:
        cfg = get_ai_config()
        self._dir = Path(store_dir or cfg.provider_store_dir)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _user_file(self, user_id: str) -> Path:
        return self._dir / _safe_user_id(user_id) / "providers.json"

    def _load_raw(self, user_id: str) -> dict[str, dict[str, Any]]:
        path = self._user_file(user_id)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_raw(self, user_id: str, data: dict[str, dict[str, Any]]) -> None:
        path = self._user_file(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(
        self,
        user_id: str,
        provider: str,
        plaintext_key: str,
        *,
        model: str = "",
        use_for_resume_tailoring: bool = True,
        use_for_ats_analysis: bool = True,
        use_for_cover_letters: bool = True,
        use_for_job_match: bool = True,
        use_for_question_help: bool = True,
        enabled: bool = True,
    ) -> ProviderSetting:
        """
        Encrypt *plaintext_key* and save the provider setting for *user_id*.

        The plaintext key is used only momentarily and is not retained after
        this method returns.
        """
        provider = provider.lower().strip()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider!r}.  Choose from {sorted(SUPPORTED_PROVIDERS)}.")

        cfg = get_ai_config()
        encrypted = encrypt_api_key(plaintext_key, cfg.key_encryption_secret)
        last4 = mask_key(plaintext_key)

        raw = self._load_raw(user_id)
        existing = raw.get(provider, {})
        now = datetime.now(timezone.utc).isoformat()

        setting = ProviderSetting(
            id=existing.get("id") or str(uuid.uuid4()),
            user_id=user_id,
            provider=provider,
            encrypted_api_key=encrypted,
            key_last4=last4,
            selected_model=model or cfg.default_model(provider),
            enabled=enabled,
            use_for_resume_tailoring=use_for_resume_tailoring,
            use_for_ats_analysis=use_for_ats_analysis,
            use_for_cover_letters=use_for_cover_letters,
            use_for_job_match=use_for_job_match,
            use_for_question_help=use_for_question_help,
            last_tested_at=existing.get("last_tested_at"),
            last_test_status=existing.get("last_test_status"),
            created_at=existing.get("created_at") or now,
            updated_at=now,
        )
        raw[provider] = asdict(setting)
        self._save_raw(user_id, raw)
        return setting

    def get(self, user_id: str, provider: str) -> ProviderSetting | None:
        """Return the raw (full) setting including encrypted key, or None."""
        raw = self._load_raw(user_id)
        data = raw.get(provider.lower())
        if not data:
            return None
        return _from_dict(data)

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        """
        Return safe (masked) provider settings for *user_id*.

        ``encrypted_api_key`` is NEVER included in the result.
        """
        raw = self._load_raw(user_id)
        return [_from_dict(v).to_safe_dict() for v in raw.values() if isinstance(v, dict)]

    def delete(self, user_id: str, provider: str) -> bool:
        """Delete the provider setting for *user_id*. Returns True if deleted."""
        raw = self._load_raw(user_id)
        if provider.lower() not in raw:
            return False
        del raw[provider.lower()]
        self._save_raw(user_id, raw)
        return True

    def get_decrypted_key(self, user_id: str, provider: str) -> str | None:
        """
        Return the decrypted API key for server-side use ONLY.

        This method MUST NOT be called from any code path that returns
        data to the client.
        """
        setting = self.get(user_id, provider)
        if not setting:
            return None
        cfg = get_ai_config()
        try:
            return decrypt_api_key(setting.encrypted_api_key, cfg.key_encryption_secret)
        except KeyEncryptionError:
            return None

    def update_test_status(self, user_id: str, provider: str, *, status: str) -> None:
        """Record the result of a key validation test (e.g. 'ok' or 'invalid_key')."""
        raw = self._load_raw(user_id)
        if provider.lower() not in raw:
            return
        raw[provider.lower()]["last_tested_at"] = datetime.now(timezone.utc).isoformat()
        raw[provider.lower()]["last_test_status"] = status
        raw[provider.lower()]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_raw(user_id, raw)

    def get_enabled_for_feature(self, user_id: str, feature_type: str) -> ProviderSetting | None:
        """
        Return the first enabled BYOK provider for *feature_type*, or None.

        Providers are iterated in insertion order; the first match wins.
        """
        raw = self._load_raw(user_id)
        for data in raw.values():
            if not isinstance(data, dict):
                continue
            setting = _from_dict(data)
            if setting.is_enabled_for(feature_type):
                return setting
        return None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _safe_user_id(user_id: str) -> str:
    """Sanitise user_id to prevent directory traversal."""
    return "".join(c for c in user_id if c.isalnum() or c in "-_")[:64] or "unknown"


def _from_dict(data: dict[str, Any]) -> ProviderSetting:
    # Only pass fields that are actual __init__ parameters (not class vars).
    init_fields = {f for f, fld in ProviderSetting.__dataclass_fields__.items() if fld.init}
    filtered = {k: v for k, v in data.items() if k in init_fields}
    return ProviderSetting(**filtered)
