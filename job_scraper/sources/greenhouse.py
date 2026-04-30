from __future__ import annotations

from urllib.parse import urlparse

from job_scraper.extractors import extract_keywords
from job_scraper.normalization import normalize_location
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
        metadata = item.get("metadata") or []
        departments = [clean_text(part.get("name")) for part in item.get("departments") or [] if clean_text(part.get("name"))]
        offices = [clean_text(part.get("name")) for part in item.get("offices") or [] if clean_text(part.get("name"))]
        location_data = normalize_location(
            location,
            work_mode=keywords["work_mode"],
        )
        posted_at = clean_text(item.get("updated_at") or item.get("created_at"))
        requisition_id = clean_text(item.get("requisition_id") or item.get("id"))
        # Extract employment_type from custom metadata fields
        employment_type = keywords["employment_type"]
        for meta_field in metadata:
            field_name = clean_text((meta_field.get("name") or "")).casefold()
            if field_name in {"employment type", "job type", "employment_type"}:
                employment_type = clean_text(meta_field.get("value")) or employment_type
                break
        # Company fallback: use board token when API doesn't return company_name
        company = clean_text(item.get("company_name")) or token
        jobs.append(
            {
                "title": title,
                "company": company,
                "location": location_data["location"],
                "state": location_data["state"] or parse_state(location),
                "country": location_data["country"] or infer_country(location, title, description),
                "city": location_data["city"],
                "source": "greenhouse",
                "source_external_id": requisition_id,
                "source_url": source_url,
                "job_url": job_url,
                "description": description,
                **keywords,
                "work_mode": location_data["work_mode"] or keywords["work_mode"],
                "employment_type": employment_type,
                "posted_at": posted_at,
                "department": ", ".join(part for part in departments if part) or None,
                "team": ", ".join(part for part in departments if part) or None,
                "office": ", ".join(part for part in offices if part) or None,
                "raw_payload": item,
            }
        )
        if metadata:
            jobs[-1]["raw_payload"]["metadata"] = metadata
    return jobs
