from __future__ import annotations

import logging
from typing import Any

from job_scraper.extractors import extract_keywords
from job_scraper.normalization import generate_search_terms, infer_category, normalize_location, normalize_title
from job_scraper.source_status import FAILED, OK, PROVIDER_API, PROVIDER_DISABLED, PROVIDER_REQUIRED, SourceScrapeResult, SourceStatus
from job_scraper.utils import clean_text, fetch_json, infer_country, parse_state


logger = logging.getLogger(__name__)


def _first_apply_link(item: dict[str, Any]) -> str | None:
    apply_options = item.get("apply_options") or item.get("apply_links") or []
    if isinstance(apply_options, list):
        for option in apply_options:
            if not isinstance(option, dict):
                continue
            link = clean_text(option.get("link") or option.get("apply_link"))
            if link:
                return link
    return None


def _detected_extensions(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("detected_extensions") or item.get("extensions") or {}
    return value if isinstance(value, dict) else {}


def _normalize_provider_job(item: dict[str, Any], source_url: str, source_name: str) -> dict[str, Any] | None:
    title = clean_text(item.get("title") or item.get("job_title"))
    company = clean_text(item.get("company_name") or item.get("company"))
    extensions = _detected_extensions(item)
    location = clean_text(item.get("location") or extensions.get("location"))
    job_url = clean_text(
        item.get("job_url")
        or item.get("link")
        or item.get("apply_link")
        or item.get("share_link")
        or item.get("via_link")
        or _first_apply_link(item)
    )
    description = clean_text(item.get("description") or item.get("snippet"))
    if not title or not job_url:
        return None
    keywords = extract_keywords(description)
    location_data = normalize_location(location, work_mode=keywords["work_mode"])
    normalized_title = normalize_title(title)
    category = infer_category(title, description, keywords["required_skills"] + keywords["ats_keywords"] + keywords["domain_terms"])
    search_terms, autocomplete_terms = generate_search_terms(
        title=title,
        normalized_title=normalized_title,
        category=category,
        required_skills=keywords["required_skills"],
        ats_keywords=keywords["ats_keywords"],
    )
    employment_type = clean_text(
        item.get("employment_type")
        or item.get("job_type")
        or extensions.get("schedule_type")
        or extensions.get("employment_type")
    )
    salary_text = clean_text(item.get("salary") or item.get("salary_text") or extensions.get("salary"))
    return {
        "title": title,
        "normalized_title": normalized_title,
        "company": company,
        "location": location_data["location"] or location,
        "city": location_data["city"],
        "state": location_data["state"] or parse_state(location),
        "country": location_data["country"] or infer_country(location, title, description),
        "source": source_name,
        "source_external_id": clean_text(item.get("job_id") or item.get("id") or item.get("job_id_encoded")),
        "source_url": source_url,
        "job_url": job_url,
        "description": description,
        **keywords,
        "work_mode": location_data["work_mode"] or keywords["work_mode"],
        "employment_type": employment_type or keywords["employment_type"],
        "salary_text": salary_text or keywords["salary_text"],
        "posted_at": clean_text(item.get("posted_at") or extensions.get("posted_at")),
        "category": category,
        "search_terms": search_terms,
        "autocomplete_terms": autocomplete_terms,
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
                source_name = "google_jobs_provider"
            elif provider == "scraperapi":
                if not scraperapi_api_key:
                    logger.info("GOOGLE_JOBS_PROVIDER=scraperapi but SCRAPERAPI_API_KEY is missing.")
                    return []
                raw_jobs = _scraperapi_jobs(query_text, scraperapi_api_key, timeout)
                source_name = "google_jobs_provider"
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
