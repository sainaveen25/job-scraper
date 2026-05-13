"""
automation/ai/config.py
========================
Central configuration for ApplyMate's AI provider system.

All values are read from environment variables so models and limits
can be updated without code changes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv


SUPPORTED_PROVIDERS = frozenset({"gemini", "openai", "anthropic", "groq", "openrouter", "applymate"})

FEATURE_TYPES = frozenset({
    "resume_tailor",
    "ats_analysis",
    "cover_letter",
    "job_match",
    "question_help",
})


@dataclass(frozen=True)
class AIConfig:
    # Encryption
    key_encryption_secret: str  # Required for BYOK; 32+ byte base64 string

    # Managed provider selection
    default_provider: str = "gemini"

    # Managed API keys (ApplyMate's own keys)
    applymate_gemini_api_key: str = ""
    applymate_openai_api_key: str = ""
    applymate_anthropic_api_key: str = ""
    applymate_groq_api_key: str = ""
    applymate_openrouter_api_key: str = ""

    # Configurable model names (no code change needed to update)
    gemini_model: str = "gemini-2.0-flash-lite"
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-haiku-4-5"
    groq_model: str = "llama-3.3-70b-versatile"
    openrouter_default_model: str = ""

    # Usage limits — free tier
    free_daily_limit: int = 10
    free_monthly_limit: int = 100

    # Usage limits — paid tier
    paid_daily_limit: int = 200
    paid_monthly_limit: int = 2000

    # Storage paths (file-based, consistent with existing project pattern)
    provider_store_dir: str = "data/ai_providers"
    usage_store_dir: str = "data/ai_usage"

    # Request timeout
    request_timeout_seconds: int = 30

    def managed_api_key(self, provider: str) -> str:
        """Return the managed API key for a given provider name."""
        mapping = {
            "gemini": self.applymate_gemini_api_key,
            "openai": self.applymate_openai_api_key,
            "anthropic": self.applymate_anthropic_api_key,
            "groq": self.applymate_groq_api_key,
            "openrouter": self.applymate_openrouter_api_key,
        }
        return mapping.get(provider, "")

    def default_model(self, provider: str) -> str:
        """Return the default model name for a given provider."""
        mapping = {
            "gemini": self.gemini_model,
            "openai": self.openai_model,
            "anthropic": self.anthropic_model,
            "groq": self.groq_model,
            "openrouter": self.openrouter_default_model,
        }
        return mapping.get(provider, "")


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except ValueError:
        return default


@lru_cache(maxsize=1)
def get_ai_config() -> AIConfig:
    load_dotenv(override=False)
    return AIConfig(
        key_encryption_secret=os.getenv("AI_KEY_ENCRYPTION_SECRET", "").strip(),
        default_provider=os.getenv("APPLYMATE_DEFAULT_AI_PROVIDER", "gemini").strip().lower(),
        applymate_gemini_api_key=os.getenv("APPLYMATE_GEMINI_API_KEY", "").strip(),
        applymate_openai_api_key=os.getenv("APPLYMATE_OPENAI_API_KEY", "").strip(),
        applymate_anthropic_api_key=os.getenv("APPLYMATE_ANTHROPIC_API_KEY", "").strip(),
        applymate_groq_api_key=os.getenv("APPLYMATE_GROQ_API_KEY", "").strip(),
        applymate_openrouter_api_key=os.getenv("APPLYMATE_OPENROUTER_API_KEY", "").strip(),
        gemini_model=os.getenv("APPLYMATE_GEMINI_MODEL", "gemini-2.0-flash-lite").strip(),
        openai_model=os.getenv("APPLYMATE_OPENAI_MODEL", "gpt-4o-mini").strip(),
        anthropic_model=os.getenv("APPLYMATE_ANTHROPIC_MODEL", "claude-haiku-4-5").strip(),
        groq_model=os.getenv("APPLYMATE_GROQ_MODEL", "llama-3.3-70b-versatile").strip(),
        openrouter_default_model=os.getenv("APPLYMATE_OPENROUTER_MODEL", "").strip(),
        free_daily_limit=_int_env("AI_FREE_TIER_DAILY_LIMIT", 10),
        free_monthly_limit=_int_env("AI_FREE_TIER_MONTHLY_LIMIT", 100),
        paid_daily_limit=_int_env("AI_PAID_TIER_DAILY_LIMIT", 200),
        paid_monthly_limit=_int_env("AI_PAID_TIER_MONTHLY_LIMIT", 2000),
        provider_store_dir=os.getenv("AI_PROVIDER_STORE_DIR", "data/ai_providers").strip(),
        usage_store_dir=os.getenv("AI_USAGE_STORE_DIR", "data/ai_usage").strip(),
        request_timeout_seconds=_int_env("AI_REQUEST_TIMEOUT_SECONDS", 30),
    )
