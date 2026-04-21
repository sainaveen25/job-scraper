from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import re
from typing import Any

from job_scraper.extractors import is_job_like, normalize_text, tag_category


_HOURS_AGO_RE = re.compile(r"(\d+)\s*(hour|hours|hr|hrs)\s+ago", re.IGNORECASE)
_DAYS_AGO_RE = re.compile(r"(\d+)\s*(day|days)\s+ago", re.IGNORECASE)
_MINUTES_AGO_RE = re.compile(r"(\d+)\s*(minute|minutes|min|mins)\s+ago", re.IGNORECASE)


def _parse_posted_at(value: Any, now: datetime) -> datetime | None:
    text = normalize_text(value)
    if not text:
        return None

    if text.isdigit():
        number = int(text)
        if number > 10_000_000_000:
            number = number / 1000
        return datetime.fromtimestamp(number, tz=timezone.utc)

    lowered = text.lower()
    if lowered in {"today", "just now"}:
        return now
    if lowered == "yesterday":
        return now - timedelta(days=1)

    match = _MINUTES_AGO_RE.search(lowered)
    if match:
        return now - timedelta(minutes=int(match.group(1)))

    match = _HOURS_AGO_RE.search(lowered)
    if match:
        return now - timedelta(hours=int(match.group(1)))

    match = _DAYS_AGO_RE.search(lowered)
    if match:
        return now - timedelta(days=int(match.group(1)))

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass

    try:
        parsed = parsedate_to_datetime(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


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

        posted_at = _parse_posted_at(job.get("posted_at"), now)
        if posted_at is None:
            continue
        if posted_at < now - timedelta(hours=max_job_age_hours):
            continue

        raw_payload = dict(job.get("raw_payload") or {})
        raw_payload["category"] = tag_category(title, description)
        raw_payload["postedAtParsedUtc"] = posted_at.isoformat()
        job["raw_payload"] = raw_payload
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
