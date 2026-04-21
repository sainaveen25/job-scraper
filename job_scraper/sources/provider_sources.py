from __future__ import annotations

import logging
from typing import Any
from urllib.parse import parse_qs, urlparse

from job_scraper.sources.google_jobs import _normalize_provider_job
from job_scraper.utils import fetch_json


logger = logging.getLogger(__name__)


def _query_from_source_url(source_name: str, source_url: str) -> str:
    parsed = urlparse(source_url)
    params = parse_qs(parsed.query)
    query = (
        params.get("q", [""])[0]
        or params.get("keywords", [""])[0]
        or params.get("search", [""])[0]
        or params.get("k", [""])[0]
        or source_name
    )
    location = params.get("l", [""])[0] or params.get("location", [""])[0]
    return " ".join(part for part in (query, location) if part).strip()


def scrape_job_board_provider(
    *,
    source_name: str,
    source_url: str,
    provider: str,
    serpapi_api_key: str,
    scraperapi_api_key: str,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    provider = (provider or "disabled").lower()
    query = _query_from_source_url(source_name, source_url)

    if provider == "disabled":
        return []

    if provider == "serpapi":
        if not serpapi_api_key:
            logger.info("%s provider is serpapi but SERPAPI_API_KEY is missing.", source_name)
            return []
        raw_jobs = fetch_json(
            "https://serpapi.com/search.json",
            timeout=timeout,
            params={"engine": "google_jobs", "q": f"{query} {source_name}", "api_key": serpapi_api_key},
        )
        items = raw_jobs.get("jobs_results", []) if isinstance(raw_jobs, dict) else []
        source_label = f"{source_name}_serpapi"
    elif provider == "scraperapi":
        if not scraperapi_api_key:
            logger.info("%s provider is scraperapi but SCRAPERAPI_API_KEY is missing.", source_name)
            return []
        raw_jobs = fetch_json(
            "https://api.scraperapi.com/structured/google/jobs",
            timeout=timeout,
            params={"api_key": scraperapi_api_key, "query": f"{query} {source_name}"},
        )
        items = (raw_jobs.get("jobs", []) or raw_jobs.get("jobs_results", [])) if isinstance(raw_jobs, dict) else []
        source_label = f"{source_name}_scraperapi"
    else:
        logger.info("%s provider=custom has no built-in client configured.", source_name)
        return []

    jobs: list[dict[str, Any]] = []
    for item in items:
        normalized = _normalize_provider_job(item, source_url=f"provider:{provider}:{query}", source_name=source_label)
        if normalized:
            normalized["source_url"] = source_url
            jobs.append(normalized)
    return jobs
