from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from scraper.config import load_environment


DEFAULT_JOB_CATEGORIES: tuple[str, ...] = (
    "Software Engineering",
    "Backend Development",
    "Frontend Development",
    "Full Stack Development",
    "Data Analytics",
    "Business Analysis",
    "Data Engineering",
    "DevOps",
    "Cloud Engineering",
    "QA Automation",
    "Product Management",
    "Project Management",
    "Cybersecurity",
    "AI Engineering",
    "Machine Learning",
    "Database Administration",
    "Salesforce",
    "Workday",
    "IT Support",
    "Systems Administration",
)

DEFAULT_JOB_LOCATIONS: tuple[str, ...] = (
    "United States",
    "Remote",
    "Texas",
    "California",
    "New York",
    "New Jersey",
    "Illinois",
    "Georgia",
    "Florida",
    "Washington",
)


@dataclass(frozen=True)
class JobScraperSettings:
    source_urls: tuple[str, ...]
    global_job_categories: tuple[str, ...]
    global_job_locations: tuple[str, ...]
    max_job_age_hours: int = 24
    enable_browser_fetcher: bool = False
    browser_fetcher_timeout_seconds: int = 30
    request_timeout_seconds: int = 30
    google_jobs_provider: str = "disabled"
    serpapi_api_key: str = ""
    scraperapi_api_key: str = ""
    linkedin_provider: str = "disabled"
    indeed_provider: str = "disabled"
    glassdoor_provider: str = "disabled"
    ziprecruiter_provider: str = "disabled"
    source_failure_policy: str = "continue"
    google_jobs_max_queries_per_run: int = 25
    google_jobs_max_results_per_query: int = 20
    use_user_preferences_for_ranking_only: bool = True


def _parse_list(name: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    return tuple(chunk.strip() for chunk in raw_value.replace("\r", "\n").replace(",", "\n").split("\n") if chunk.strip())


def _parse_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name, "").strip().lower()
    if not raw_value:
        return default
    return raw_value in {"1", "true", "yes", "on"}


def _parse_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")
    return value


def _parse_provider(name: str) -> str:
    provider = os.getenv(name, "disabled").strip().lower() or "disabled"
    allowed = {"disabled", "serpapi", "scraperapi", "custom"}
    if provider not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(sorted(allowed))}")
    return provider


@lru_cache(maxsize=1)
def get_job_scraper_settings() -> JobScraperSettings:
    load_environment()
    return JobScraperSettings(
        source_urls=_parse_list("JOB_SOURCE_URLS"),
        global_job_categories=_parse_list("GLOBAL_JOB_CATEGORIES", DEFAULT_JOB_CATEGORIES),
        global_job_locations=_parse_list("GLOBAL_JOB_LOCATIONS", DEFAULT_JOB_LOCATIONS),
        max_job_age_hours=_parse_int("SCRAPE_MAX_JOB_AGE_HOURS", 24),
        enable_browser_fetcher=_parse_bool("ENABLE_BROWSER_FETCHER", default=False),
        browser_fetcher_timeout_seconds=_parse_int("BROWSER_FETCHER_TIMEOUT_SECONDS", 30),
        request_timeout_seconds=_parse_int("SCRAPER_REQUEST_TIMEOUT_SECONDS", 30),
        google_jobs_provider=_parse_provider("GOOGLE_JOBS_PROVIDER"),
        serpapi_api_key=os.getenv("SERPAPI_API_KEY", "").strip(),
        scraperapi_api_key=os.getenv("SCRAPERAPI_API_KEY", "").strip(),
        linkedin_provider=_parse_provider("LINKEDIN_PROVIDER"),
        indeed_provider=_parse_provider("INDEED_PROVIDER"),
        glassdoor_provider=_parse_provider("GLASSDOOR_PROVIDER"),
        ziprecruiter_provider=_parse_provider("ZIPRECRUITER_PROVIDER"),
        source_failure_policy=os.getenv("SOURCE_FAILURE_POLICY", "continue").strip().lower() or "continue",
        google_jobs_max_queries_per_run=_parse_int("GOOGLE_JOBS_MAX_QUERIES_PER_RUN", 25),
        google_jobs_max_results_per_query=_parse_int("GOOGLE_JOBS_MAX_RESULTS_PER_QUERY", 20),
        use_user_preferences_for_ranking_only=_parse_bool("USE_USER_PREFERENCES_FOR_RANKING_ONLY", default=True),
    )
