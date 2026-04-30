from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from job_scraper.extractors import is_job_like, normalize_text
from job_scraper.normalization import choose_posted_at, infer_category, parse_posted_at


def apply_light_filter(jobs: list[dict[str, Any]], max_job_age_hours: int = 24) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for job in jobs:
        title = job.get("title")
        description = job.get("description")
        if not job.get("job_url") or not title:
            continue
        if not is_job_like(title, description):
            continue

        freshness = choose_posted_at(job.get("posted_at"), scraped_at=now)
        posted_at_text = freshness["posted_at"]
        posted_at_tuple = parse_posted_at(posted_at_text, now=now)
        posted_at = (
            datetime.fromisoformat(posted_at_tuple[0].replace("Z", "+00:00"))
            if posted_at_tuple[0]
            else now
        )
        if posted_at < now - timedelta(hours=max_job_age_hours):
            continue

        raw_payload = dict(job.get("raw_payload") or {})
        category = infer_category(
            title,
            description,
            list(job.get("required_skills") or []) + list(job.get("ats_keywords") or []),
        )
        raw_payload["category"] = category
        raw_payload["postedAtParsedUtc"] = posted_at.isoformat()
        job["raw_payload"] = raw_payload
        job["category"] = category
        job.update(freshness)
        filtered.append(job)
    return filtered


def dedupe_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for job in jobs:
        source_id = normalize_text(job.get("source_external_id"))
        job_url = normalize_text(job.get("job_url"))
        title = normalize_text(job.get("title")).casefold()
        company = normalize_text(job.get("company")).casefold()
        location = normalize_text(job.get("location")).casefold()

        keys = [
            f"id:{source_id.casefold()}" if source_id else "",
            f"url:{job_url.casefold()}" if job_url else "",
            f"triple:{title}|{company}|{location}",
        ]
        if any(key and key in seen for key in keys):
            continue
        for key in keys:
            if key:
                seen.add(key)
        deduped.append(job)
    return deduped
