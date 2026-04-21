from __future__ import annotations

import logging
from urllib.parse import urlparse

import requests

from job_scraper.extractors import extract_keywords
from job_scraper.utils import clean_text, fetch_json, infer_country, parse_state


logger = logging.getLogger(__name__)


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
        location = clean_text(categories.get("location"))
        description = clean_text(item.get("descriptionPlain") or item.get("description"))
        keywords = extract_keywords(description)
        jobs.append(
            {
                "title": title,
                "company": clean_text(item.get("company")),
                "location": location,
                "state": parse_state(location),
                "country": infer_country(location, title, description),
                "source": "lever",
                "source_external_id": clean_text(item.get("id")),
                "source_url": source_url,
                "job_url": job_url,
                "description": description,
                **keywords,
                "employment_type": clean_text(categories.get("commitment")) or keywords["employment_type"],
                "posted_at": clean_text(item.get("createdAt")),
                "raw_payload": item,
            }
        )
    return jobs
