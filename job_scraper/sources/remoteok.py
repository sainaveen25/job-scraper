from __future__ import annotations

from job_scraper.extractors import extract_keywords
from job_scraper.utils import clean_text, fetch_json, infer_country, parse_state


def scrape_remoteok_jobs(source_url: str, timeout: int = 30) -> list[dict]:
    api_url = source_url.rstrip("/") + ".json"
    payload = fetch_json(api_url, timeout=timeout)
    if not isinstance(payload, list):
        return []

    jobs = []
    for item in payload[1:]:
        if not isinstance(item, dict):
            continue
        title = clean_text(item.get("position"))
        company = clean_text(item.get("company"))
        location = clean_text(item.get("location")) or "Remote"
        job_url = clean_text(item.get("url"))
        description = clean_text(item.get("description"))
        if not title or not job_url:
            continue
        keywords = extract_keywords(description)
        jobs.append(
            {
                "title": title,
                "company": company,
                "location": location,
                "state": parse_state(location),
                "country": infer_country(location, title, description),
                "source": "remoteok",
                "source_external_id": clean_text(item.get("id") or item.get("slug")),
                "source_url": source_url,
                "job_url": job_url,
                "description": description,
                **keywords,
                "salary_text": clean_text(item.get("salary_min")) if item.get("salary_min") else keywords["salary_text"],
                "posted_at": clean_text(item.get("date")),
                "raw_payload": item,
            }
        )
    return jobs
