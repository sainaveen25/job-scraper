from __future__ import annotations

import logging
from typing import Any

import requests

from scraper.config import get_settings


logger = logging.getLogger(__name__)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = [str(item) for item in value if str(item).strip()]
    else:
        values = [str(value)]

    deduped: list[str] = []
    seen: set[str] = set()
    for item in values:
        cleaned = item.strip()
        if not cleaned:
            continue
        lowered = cleaned.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(cleaned)
    return deduped


def _extract_payload(response_json: Any) -> dict[str, Any]:
    if not isinstance(response_json, dict):
        raise ValueError("Lovable search preferences response must be a JSON object")

    for key in ("data", "result"):
        nested = response_json.get(key)
        if isinstance(nested, dict):
            return nested
    return response_json


def _query_key(query: dict[str, Any]) -> tuple[Any, ...]:
    title = _clean_text(query.get("title")) or ""
    location = _clean_text(query.get("location")) or ""
    state = _clean_text(query.get("state")) or ""
    work_mode = _clean_text(query.get("workMode")) or ""
    return (
        title.casefold(),
        location.casefold(),
        state.casefold(),
        work_mode.casefold(),
        tuple(item.casefold() for item in query.get("skills", [])),
    )


def _build_queries_from_profiles(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for profile in profiles:
        titles = _normalize_list(profile.get("targetRoles") or profile.get("roles") or profile.get("titles"))
        locations = _normalize_list(profile.get("locations"))
        states = _normalize_list(profile.get("states"))
        work_modes = _normalize_list(profile.get("workModes") or profile.get("work_modes"))
        skills = _normalize_list(profile.get("skills"))

        if not titles:
            continue

        location_values = locations or [None]
        state_values = states or [None]
        work_mode_values = work_modes or [None]

        for title in titles:
            for location in location_values:
                for state in state_values:
                    for work_mode in work_mode_values:
                        query = {
                            "title": title,
                            "location": _clean_text(location),
                            "state": _clean_text(state),
                            "workMode": _clean_text(work_mode),
                            "skills": skills,
                            "matchedPreferenceHints": skills,
                        }
                        key = _query_key(query)
                        if key in seen:
                            continue
                        seen.add(key)
                        deduped.append(query)

    return deduped


def _normalize_query(raw_query: dict[str, Any]) -> dict[str, Any] | None:
    title = _clean_text(raw_query.get("title") or raw_query.get("searchTitle") or raw_query.get("role"))
    if not title:
        return None

    skills = _normalize_list(raw_query.get("skills"))
    hints = _normalize_list(raw_query.get("matchedPreferenceHints") or skills)

    return {
        "title": title,
        "location": _clean_text(raw_query.get("location") or raw_query.get("searchLocation")),
        "state": _clean_text(raw_query.get("state") or raw_query.get("searchState")),
        "workMode": _clean_text(raw_query.get("workMode") or raw_query.get("searchWorkMode")),
        "skills": skills,
        "matchedPreferenceHints": hints,
    }


def fetch_search_preferences_from_lovable(timeout: int = 30) -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.lovable_search_preferences_url:
        raise RuntimeError("LOVABLE_SEARCH_PREFERENCES_URL is required")
    if not settings.lovable_scraper_ingest_token:
        raise RuntimeError("LOVABLE_SCRAPER_INGEST_TOKEN is required")

    headers = {"Authorization": f"Bearer {settings.lovable_scraper_ingest_token}"}
    response = requests.get(settings.lovable_search_preferences_url, headers=headers, timeout=timeout)

    if response.status_code in (401, 403):
        raise PermissionError(
            "Lovable search preferences rejected the scraper credentials. "
            "Check LOVABLE_SCRAPER_INGEST_TOKEN and endpoint permissions."
        )

    response.raise_for_status()
    payload = _extract_payload(response.json())

    raw_queries = payload.get("searchQueries")
    raw_profiles = payload.get("profiles")

    queries: list[dict[str, Any]] = []
    if isinstance(raw_queries, list):
        for raw_query in raw_queries:
            if not isinstance(raw_query, dict):
                continue
            normalized = _normalize_query(raw_query)
            if normalized:
                queries.append(normalized)

    if not queries and isinstance(raw_profiles, list):
        profile_dicts = [profile for profile in raw_profiles if isinstance(profile, dict)]
        queries = _build_queries_from_profiles(profile_dicts)

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for query in queries:
        key = _query_key(query)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(query)

    logger.info("Fetched %s deduplicated search queries from Lovable", len(deduped))
    return deduped
