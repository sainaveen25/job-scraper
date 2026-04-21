from __future__ import annotations

import copy
import re
from typing import Any


_WHITESPACE_RE = re.compile(r"\s+")
_LIST_SPLIT_RE = re.compile(r"[,;\n|]")
_COUNTRY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bcanada\b", re.IGNORECASE), "Canada"),
    (re.compile(r"\bunited states\b|\busa\b|\bu\.s\.a\b|\bus\b", re.IGNORECASE), "USA"),
    (re.compile(r"\bunited kingdom\b|\buk\b|\bu\.k\.\b|\bengland\b", re.IGNORECASE), "United Kingdom"),
    (re.compile(r"\bindia\b", re.IGNORECASE), "India"),
    (re.compile(r"\bgermany\b", re.IGNORECASE), "Germany"),
    (re.compile(r"\bfrance\b", re.IGNORECASE), "France"),
    (re.compile(r"\bspain\b", re.IGNORECASE), "Spain"),
    (re.compile(r"\bitaly\b", re.IGNORECASE), "Italy"),
    (re.compile(r"\bnetherlands\b", re.IGNORECASE), "Netherlands"),
    (re.compile(r"\bpoland\b", re.IGNORECASE), "Poland"),
    (re.compile(r"\bireland\b", re.IGNORECASE), "Ireland"),
    (re.compile(r"\bsingapore\b", re.IGNORECASE), "Singapore"),
    (re.compile(r"\baustralia\b", re.IGNORECASE), "Australia"),
    (re.compile(r"\bnew zealand\b", re.IGNORECASE), "New Zealand"),
    (re.compile(r"\bphilippines\b", re.IGNORECASE), "Philippines"),
    (re.compile(r"\bpakistan\b", re.IGNORECASE), "Pakistan"),
    (re.compile(r"\buae\b|\bunited arab emirates\b", re.IGNORECASE), "United Arab Emirates"),
)


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


def _infer_country(*values: Any) -> str | None:
    combined = " ".join(part for part in (_clean_text(value) or "" for value in values) if part).strip()
    if not combined:
        return None

    for pattern, country in _COUNTRY_PATTERNS:
        if pattern.search(combined):
            return country
    return None


def normalize_job(raw_job: dict[str, Any], default_source: str = "scrapling") -> dict[str, Any] | None:
    if not isinstance(raw_job, dict):
        raise TypeError(f"Expected each raw job to be a dict, got {type(raw_job).__name__}")

    title = _clean_text(_pick_first(raw_job, "title", "job_title", "position", "role"))
    job_url = _clean_text(_pick_first(raw_job, "jobUrl", "job_url", "url", "link", "href", "apply_url"))

    if not title or not job_url:
        return None

    normalized = {
        "title": title,
        "company": _clean_text(_pick_first(raw_job, "company", "company_name", "employer", "organization")),
        "location": _clean_text(_pick_first(raw_job, "location", "job_location", "city_state", "place")),
        "state": _clean_text(_pick_first(raw_job, "state", "region", "province")),
        "country": _clean_text(_pick_first(raw_job, "country"))
        or _infer_country(
            _pick_first(raw_job, "location", "job_location", "city_state", "place"),
            _pick_first(raw_job, "title", "job_title", "position", "role"),
            _pick_first(raw_job, "description", "details", "summary", "body", "content"),
        ),
        "source": _clean_text(_pick_first(raw_job, "source", "source_name")) or default_source,
        "sourceExternalId": _clean_text(
            _pick_first(raw_job, "sourceExternalId", "source_external_id", "external_id", "job_id", "id")
        ),
        "sourceUrl": _clean_text(_pick_first(raw_job, "sourceUrl", "source_url", "listing_url", "source_link")),
        "jobUrl": job_url,
        "description": _clean_text(_pick_first(raw_job, "description", "details", "summary", "body", "content")),
        "requiredSkills": _normalize_list(_pick_first(raw_job, "requiredSkills", "required_skills", "skills")),
        "preferredSkills": _normalize_list(_pick_first(raw_job, "preferredSkills", "preferred_skills")),
        "atsKeywords": _normalize_list(_pick_first(raw_job, "atsKeywords", "ats_keywords", "keywords")),
        "domainTerms": _normalize_list(_pick_first(raw_job, "domainTerms", "domain_terms")),
        "responsibilities": _normalize_list(_pick_first(raw_job, "responsibilities", "duties")),
        "workMode": _clean_text(_pick_first(raw_job, "workMode", "work_mode", "remote_type", "workplace_type")),
        "employmentType": _clean_text(_pick_first(raw_job, "employmentType", "employment_type", "job_type")),
        "salaryText": _clean_text(_pick_first(raw_job, "salaryText", "salary_text", "salary", "compensation")),
        "postedAt": _clean_text(_pick_first(raw_job, "postedAt", "posted_at", "date_posted", "published_at")),
        "searchTitle": _clean_text(_pick_first(raw_job, "searchTitle", "search_title")),
        "searchLocation": _clean_text(_pick_first(raw_job, "searchLocation", "search_location")),
        "searchState": _clean_text(_pick_first(raw_job, "searchState", "search_state")),
        "searchWorkMode": _clean_text(_pick_first(raw_job, "searchWorkMode", "search_work_mode")),
        "matchedPreferenceHints": _normalize_list(
            _pick_first(raw_job, "matchedPreferenceHints", "matched_preference_hints")
        ),
        "rawPayload": copy.deepcopy(raw_job),
    }
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

        dedupe_key = normalized["jobUrl"].strip()
        if dedupe_key in seen_job_urls:
            skipped_count += 1
            continue

        seen_job_urls.add(dedupe_key)
        normalized_jobs.append(normalized)

    return normalized_jobs, skipped_count
