from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

import requests

from job_scraper.extractors import extract_keywords
from job_scraper.normalization import normalize_location
from job_scraper.utils import clean_text, fetch_json, infer_country, parse_state


logger = logging.getLogger(__name__)
_SALARY_RE = re.compile(
    r"(\$[\d,]+(?:\.\d+)?(?:\s*-\s*\$[\d,]+(?:\.\d+)?)?(?:\s*/\s*(?:year|yr|hour|hr))?)",
    re.IGNORECASE,
)


def _site_token(source_url: str) -> str | None:
    parsed = urlparse(source_url)
    path = parsed.path.strip("/")
    if path:
        return path.split("/")[0]
    return None


def scrape_lever_jobs(source_url: str, timeout: int = 30) -> list[dict]:
    token = _site_token(source_url)
    if not token:
        return []

    api_url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    try:
        payload = fetch_json(api_url, timeout=timeout)
    except requests.RequestException as exc:
        logger.info("Lever source %s could not be fetched this run: %s", source_url, exc)
        return []

    jobs = []
    for item in payload:
        title = clean_text(item.get("text"))
        job_url = clean_text(item.get("hostedUrl") or item.get("applyUrl"))
        if not title or not job_url:
            continue
        categories = item.get("categories") or {}
        # allLocations can be a list of strings; join them properly
        raw_location = categories.get("location")
        all_locations = categories.get("allLocations")
        if not raw_location and isinstance(all_locations, list):
            raw_location = ", ".join(str(loc) for loc in all_locations if loc)
        elif not raw_location and isinstance(all_locations, str):
            raw_location = all_locations
        location = clean_text(raw_location)
        description = clean_text(item.get("descriptionPlain") or item.get("description"))
        keywords = extract_keywords(description)
        salary_match = _SALARY_RE.search(description or "")
        salary_text = clean_text(salary_match.group(1)) if salary_match else None
        location_data = normalize_location(
            location,
            work_mode=clean_text(categories.get("workplaceType")) or keywords["work_mode"],
        )
        jobs.append(
            {
                "title": title,
                "company": clean_text(item.get("company")),
                "location": location_data["location"],
                "city": location_data["city"],
                "state": location_data["state"] or parse_state(location),
                "country": location_data["country"] or infer_country(location, title, description),
                "source": "lever",
                "source_external_id": clean_text(item.get("id")),
                "source_url": source_url,
                "job_url": job_url,
                "description": description,
                **keywords,
                "employment_type": clean_text(categories.get("commitment")) or keywords["employment_type"],
                "work_mode": location_data["work_mode"] or keywords["work_mode"],
                "salary_text": salary_text or keywords["salary_text"],
                "team": clean_text(categories.get("team")),
                "posted_at": clean_text(item.get("createdAt")),
                "raw_payload": item,
            }
        )
    return jobs
