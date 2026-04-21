from __future__ import annotations

import logging
from typing import Any

from job_scraper.extractors import extract_keywords
from job_scraper.source_status import FAILED, OK, PROVIDER_API, PROVIDER_DISABLED, PROVIDER_REQUIRED, SourceScrapeResult, SourceStatus
from job_scraper.utils import clean_text, fetch_json, infer_country, parse_state


logger = logging.getLogger(__name__)


def _normalize_provider_job(item: dict[str, Any], source_url: str, source_name: str) -> dict[str, Any] | None:
    title = clean_text(item.get("title") or item.get("job_title"))
    company = clean_text(item.get("company_name") or item.get("company"))
    location = clean_text(item.get("location") or item.get("detected_extensions", {}).get("location"))
    job_url = clean_text(item.get("job_url") or item.get("link") or item.get("apply_link"))
    description = clean_text(item.get("description") or item.get("snippet"))
    if not title or not job_url:
        return None
    keywords = extract_keywords(description)
    return {
        "title": title,
        "company": company,
        "location": location,
        "state": parse_state(location),
        "country": infer_country(location, title, description),
        "source": source_name,
        "source_external_id": clean_text(item.get("job_id") or item.get("id")),
        "source_url": source_url,
        "job_url": job_url,
        "description": description,
        **keywords,
        "posted_at": clean_text(item.get("posted_at") or item.get("detected_extensions", {}).get("posted_at")),
        "raw_payload": item,
    }


def _serpapi_jobs(query: str, api_key: str, timeout: int) -> list[dict[str, Any]]:
    payload = fetch_json(
        "https://serpapi.com/search.json",
        timeout=timeout,
        params={"engine": "google_jobs", "q": query, "api_key": api_key},
    )
    return payload.get("jobs_results", []) if isinstance(payload, dict) else []


def _scraperapi_jobs(query: str, api_key: str, timeout: int) -> list[dict[str, Any]]:
    payload = fetch_json(
        "https://api.scraperapi.com/structured/google/jobs",
        timeout=timeout,
        params={"api_key": api_key, "query": query},
    )
    if isinstance(payload, dict):
        return payload.get("jobs", []) or payload.get("jobs_results", [])
    return []


def scrape_google_jobs_provider(
    queries: list[dict[str, str]],
    provider: str,
    serpapi_api_key: str,
    scraperapi_api_key: str,
    max_queries: int,
    max_results_per_query: int,
    timeout: int = 30,
) -> list[dict]:
    provider = (provider or "disabled").lower()
    if provider == "disabled":
        logger.info("Google Jobs provider disabled.")
        return []

    jobs: list[dict] = []
    selected_queries = queries[:max_queries]
    for query in selected_queries:
        query_text = query.get("query") or ""
        try:
            if provider == "serpapi":
                if not serpapi_api_key:
                    logger.info("GOOGLE_JOBS_PROVIDER=serpapi but SERPAPI_API_KEY is missing.")
                    return []
                raw_jobs = _serpapi_jobs(query_text, serpapi_api_key, timeout)
                source_name = "google_jobs_serpapi"
            elif provider == "scraperapi":
                if not scraperapi_api_key:
                    logger.info("GOOGLE_JOBS_PROVIDER=scraperapi but SCRAPERAPI_API_KEY is missing.")
                    return []
                raw_jobs = _scraperapi_jobs(query_text, scraperapi_api_key, timeout)
                source_name = "google_jobs_scraperapi"
            else:
                logger.info("Unknown GOOGLE_JOBS_PROVIDER=%s; skipping.", provider)
                return []
        except Exception as exc:
            logger.warning("Google Jobs provider query failed for %s: %s", query_text, exc)
            continue

        for item in raw_jobs[:max_results_per_query]:
            normalized = _normalize_provider_job(item, source_url=f"provider:{provider}:{query_text}", source_name=source_name)
            if normalized:
                normalized["raw_payload"]["category_query"] = query.get("category")
                jobs.append(normalized)
    return jobs


def scrape_google_jobs_provider_with_status(
    queries: list[dict[str, str]],
    provider: str,
    serpapi_api_key: str,
    scraperapi_api_key: str,
    max_queries: int,
    max_results_per_query: int,
    timeout: int = 30,
) -> SourceScrapeResult:
    provider = (provider or "disabled").lower()
    source_url = f"provider:{provider}:google_jobs"
    if provider == "disabled":
        message = "Google Jobs provider disabled. Set GOOGLE_JOBS_PROVIDER=serpapi or scraperapi to enable."
        logger.info(message)
        return SourceScrapeResult(
            jobs=[],
            status=SourceStatus("google_jobs", source_url, PROVIDER_API, PROVIDER_DISABLED, 0, message),
        )
    if provider == "serpapi" and not serpapi_api_key:
        message = "GOOGLE_JOBS_PROVIDER=serpapi but SERPAPI_API_KEY is missing."
        logger.info(message)
        return SourceScrapeResult(
            jobs=[],
            status=SourceStatus("google_jobs", source_url, PROVIDER_API, PROVIDER_REQUIRED, 0, message),
        )
    if provider == "scraperapi" and not scraperapi_api_key:
        message = "GOOGLE_JOBS_PROVIDER=scraperapi but SCRAPERAPI_API_KEY is missing."
        logger.info(message)
        return SourceScrapeResult(
            jobs=[],
            status=SourceStatus("google_jobs", source_url, PROVIDER_API, PROVIDER_REQUIRED, 0, message),
        )
    if provider not in {"serpapi", "scraperapi"}:
        message = f"Unknown GOOGLE_JOBS_PROVIDER={provider}; skipping."
        logger.info(message)
        return SourceScrapeResult(
            jobs=[],
            status=SourceStatus("google_jobs", source_url, PROVIDER_API, PROVIDER_REQUIRED, 0, message),
        )

    try:
        jobs = scrape_google_jobs_provider(
            queries=queries,
            provider=provider,
            serpapi_api_key=serpapi_api_key,
            scraperapi_api_key=scraperapi_api_key,
            max_queries=max_queries,
            max_results_per_query=max_results_per_query,
            timeout=timeout,
        )
    except Exception as exc:
        message = f"Google Jobs provider failed: {exc}"
        logger.warning(message)
        return SourceScrapeResult(
            jobs=[],
            status=SourceStatus("google_jobs", source_url, PROVIDER_API, FAILED, 0, message),
        )

    status = OK if jobs else PROVIDER_REQUIRED
    message = "Google Jobs provider returned jobs." if jobs else "Google Jobs provider returned no jobs."
    return SourceScrapeResult(
        jobs=jobs,
        status=SourceStatus("google_jobs", source_url, PROVIDER_API, status, len(jobs), message),
    )
