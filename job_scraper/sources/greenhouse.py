from __future__ import annotations

from urllib.parse import urlparse

from job_scraper.extractors import extract_keywords
from job_scraper.utils import clean_text, infer_country, parse_state


def _board_token(source_url: str) -> str | None:
    parsed = urlparse(source_url)
    if parsed.path.strip("/"):
        return parsed.path.strip("/").split("/")[0]
    host = parsed.netloc.split(".")
    if host:
        return host[0]
    return None


def scrape_greenhouse_jobs(source_url: str, timeout: int = 30) -> list[dict]:
    token = _board_token(source_url)
    if not token:
        return []

    from job_scraper.utils import fetch_json

    api_url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    payload = fetch_json(api_url, timeout=timeout)
    jobs = []
    for item in payload.get("jobs", []):
        title = clean_text(item.get("title"))
        job_url = clean_text(item.get("absolute_url"))
        if not title or not job_url:
            continue

        location = clean_text((item.get("location") or {}).get("name"))
        description = clean_text(item.get("content"))
        keywords = extract_keywords(description)
        jobs.append(
            {
                "title": title,
                "company": clean_text(item.get("company_name")),
                "location": location,
                "state": parse_state(location),
                "country": infer_country(location, title, description),
                "source": "greenhouse",
                "source_external_id": clean_text(item.get("id")),
                "source_url": source_url,
                "job_url": job_url,
                "description": description,
                **keywords,
                "posted_at": clean_text(item.get("updated_at")),
                "raw_payload": item,
            }
        )
    return jobs
