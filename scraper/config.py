from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


DEFAULT_INTERVAL_SECONDS = 300
DEFAULT_BATCH_SIZE = 100


@dataclass(frozen=True)
class Settings:
    lovable_ingest_url: str
    lovable_search_preferences_url: str
    lovable_scraper_ingest_token: str
    scraper_interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    scraper_batch_size: int = DEFAULT_BATCH_SIZE
    job_source_urls: tuple[str, ...] = ()


def load_environment() -> None:
    """Load environment variables from a local .env file if present."""
    load_dotenv(override=False)


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default

    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer, got {value!r}") from exc

    if parsed <= 0:
        raise ValueError(f"Environment variable {name} must be greater than 0, got {parsed}")

    return parsed


def _get_list(name: str) -> tuple[str, ...]:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return ()

    values = []
    for chunk in raw_value.replace("\r", "\n").replace(",", "\n").split("\n"):
        cleaned = chunk.strip()
        if cleaned:
            values.append(cleaned)
    return tuple(values)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_environment()
    return Settings(
        lovable_ingest_url=os.getenv("LOVABLE_INGEST_URL", "").strip(),
        lovable_search_preferences_url=os.getenv("LOVABLE_SEARCH_PREFERENCES_URL", "").strip(),
        lovable_scraper_ingest_token=os.getenv("LOVABLE_SCRAPER_INGEST_TOKEN", "").strip(),
        scraper_interval_seconds=_get_int("SCRAPER_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS),
        scraper_batch_size=_get_int("SCRAPER_BATCH_SIZE", DEFAULT_BATCH_SIZE),
        job_source_urls=_get_list("JOB_SOURCE_URLS"),
    )
