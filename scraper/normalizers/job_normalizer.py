from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from typing import Any

from job_scraper.normalization import (
    choose_posted_at,
    generate_search_terms,
    infer_category,
    normalize_country,
    normalize_location,
    normalize_title,
)


_WHITESPACE_RE = re.compile(r"\s+")
_LIST_SPLIT_RE = re.compile(r"[,;\n|]")


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)

    cleaned = _WHITESPACE_RE.sub(" ", value).strip()
    return cleaned or None


def _pick_first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _normalize_list(value: Any) -> list[str]:
    items: list[str] = []

    if value is None:
        raw_values: list[Any] = []
    elif isinstance(value, str):
        raw_values = [part for part in _LIST_SPLIT_RE.split(value)]
    elif isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    else:
        raw_values = [value]

    for raw_value in raw_values:
        if isinstance(raw_value, (list, tuple, set)):
            for nested in raw_value:
                cleaned_nested = _clean_text(nested)
                if cleaned_nested:
                    items.append(cleaned_nested)
            continue

        cleaned = _clean_text(raw_value)
        if cleaned:
            items.append(cleaned)

    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        lowered = item.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped


def normalize_job(raw_job: dict[str, Any], default_source: str = "scrapling") -> dict[str, Any] | None:
    if not isinstance(raw_job, dict):
        raise TypeError(f"Expected each raw job to be a dict, got {type(raw_job).__name__}")

    title = _clean_text(_pick_first(raw_job, "title", "job_title", "position", "role"))
    job_url = _clean_text(_pick_first(raw_job, "jobUrl", "job_url", "url", "link", "href", "apply_url"))

    if not title or not job_url:
        return None

    description = _clean_text(_pick_first(raw_job, "description", "details", "summary", "body", "content"))
    required_skills = _normalize_list(_pick_first(raw_job, "requiredSkills", "required_skills", "skills"))
    preferred_skills = _normalize_list(_pick_first(raw_job, "preferredSkills", "preferred_skills"))
    ats_keywords = _normalize_list(_pick_first(raw_job, "atsKeywords", "ats_keywords", "keywords"))
    domain_terms = _normalize_list(_pick_first(raw_job, "domainTerms", "domain_terms"))
    responsibilities = _normalize_list(_pick_first(raw_job, "responsibilities", "duties"))

    location_data = normalize_location(
        _pick_first(raw_job, "location", "job_location", "city_state", "place"),
        state=_pick_first(raw_job, "state", "region", "province"),
        country=_pick_first(raw_job, "country"),
        work_mode=_pick_first(raw_job, "workMode", "work_mode", "remote_type", "workplace_type"),
    )

    source = _clean_text(_pick_first(raw_job, "source", "source_name")) or default_source
    source_mode = _clean_text(_pick_first(raw_job, "source_mode", "sourceMode")) or "direct_http"
    source_status = _clean_text(_pick_first(raw_job, "source_status", "sourceStatus")) or "ok"
    scraped_at_value = _pick_first(raw_job, "scraped_at", "scrapedAt")
    scraped_dt = None
    if scraped_at_value:
        try:
            scraped_dt = datetime.fromisoformat(str(scraped_at_value).replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            scraped_dt = None
    freshness = choose_posted_at(
        _pick_first(raw_job, "postedAt", "posted_at", "date_posted", "published_at"),
        scraped_at=scraped_dt or datetime.now(timezone.utc),
    )

    normalized_title = normalize_title(title)
    category = _clean_text(_pick_first(raw_job, "category")) or infer_category(
        title,
        description,
        required_skills + ats_keywords + domain_terms,
    )
    search_terms, autocomplete_terms = generate_search_terms(
        title=title,
        normalized_title=normalized_title,
        category=category,
        required_skills=required_skills,
        ats_keywords=ats_keywords,
    )

    normalized = {
        "title": title,
        "normalized_title": normalized_title,
        "company": _clean_text(_pick_first(raw_job, "company", "company_name", "employer", "organization")),
        "location": location_data["location"],
        "city": _clean_text(_pick_first(raw_job, "city")) or location_data["city"],
        "state": location_data["state"],
        "country": location_data["country"] or normalize_country(_pick_first(raw_job, "country")),
        "source": source,
        "source_mode": source_mode,
        "source_status": source_status,
        "source_external_id": _clean_text(
            _pick_first(raw_job, "sourceExternalId", "source_external_id", "external_id", "job_id", "id")
        ),
        "source_url": _clean_text(_pick_first(raw_job, "sourceUrl", "source_url", "listing_url", "source_link")),
        "job_url": job_url,
        "description": description,
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "ats_keywords": ats_keywords,
        "domain_terms": domain_terms,
        "responsibilities": responsibilities,
        "work_mode": location_data["work_mode"],
        "employment_type": _clean_text(_pick_first(raw_job, "employmentType", "employment_type", "job_type")),
        "salary_text": _clean_text(_pick_first(raw_job, "salaryText", "salary_text", "salary", "compensation")),
        "posted_at": freshness["posted_at"],
        "posted_at_raw": freshness["posted_at_raw"],
        "posted_at_source": freshness["posted_at_source"],
        "scraped_at": freshness["scraped_at"],
        "category": category,
        "search_terms": search_terms,
        "autocomplete_terms": autocomplete_terms,
        "raw_payload": copy.deepcopy(raw_job),
    }

    # Backwards-compatible Lovable keys.
    normalized["jobUrl"] = normalized["job_url"]
    normalized["sourceUrl"] = normalized["source_url"]
    normalized["sourceExternalId"] = normalized["source_external_id"]
    normalized["workMode"] = normalized["work_mode"]
    normalized["employmentType"] = normalized["employment_type"]
    normalized["salaryText"] = normalized["salary_text"]
    normalized["postedAt"] = normalized["posted_at"]
    normalized["rawPayload"] = normalized["raw_payload"]
    normalized["requiredSkills"] = normalized["required_skills"]
    normalized["preferredSkills"] = normalized["preferred_skills"]
    normalized["atsKeywords"] = normalized["ats_keywords"]
    normalized["domainTerms"] = normalized["domain_terms"]

    return normalized


def normalize_jobs(raw_jobs: list[dict[str, Any]], default_source: str = "scrapling") -> tuple[list[dict[str, Any]], int]:
    normalized_jobs: list[dict[str, Any]] = []
    seen_job_urls: set[str] = set()
    skipped_count = 0

    for raw_job in raw_jobs:
        normalized = normalize_job(raw_job, default_source=default_source)
        if normalized is None:
            skipped_count += 1
            continue

        dedupe_key = normalized["job_url"].strip()
        if dedupe_key in seen_job_urls:
            skipped_count += 1
            continue

        seen_job_urls.add(dedupe_key)
        normalized_jobs.append(normalized)

    return normalized_jobs, skipped_count
