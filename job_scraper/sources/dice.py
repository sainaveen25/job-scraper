from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlparse, urlunparse

from job_scraper.extractors import extract_keywords
from job_scraper.normalization import normalize_location
from job_scraper.utils import absolute_url, clean_text, fetch_html, first_text, infer_country, make_selector, parse_state


logger = logging.getLogger(__name__)
_LD_JSON_RE = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)
_POSTED_RE = re.compile(r"\b(\d+\s*(?:minute|minutes|min|mins|hour|hours|hr|hrs|day|days)\s+ago|just posted)\b", re.IGNORECASE)
_SALARY_RE = re.compile(r"(\$[\d,]+(?:\s*-\s*\$[\d,]+)?(?:\s*/\s*(?:hour|hr|year))?)", re.IGNORECASE)


def _ld_address_value(ld_job: dict, key: str) -> str | None:
    job_location = ld_job.get("jobLocation") or {}
    if isinstance(job_location, list):
        job_location = next((item for item in job_location if isinstance(item, dict)), {})
    address = job_location.get("address") if isinstance(job_location, dict) else {}
    if isinstance(address, list):
        address = next((item for item in address if isinstance(item, dict)), {})
    return clean_text(address.get(key)) if isinstance(address, dict) else None


def _extract_ld_job(html: str) -> dict | None:
    for match in _LD_JSON_RE.findall(html):
        try:
            payload = json.loads(match.strip())
        except json.JSONDecodeError:
            continue
        entries = payload if isinstance(payload, list) else [payload]
        for entry in entries:
            if isinstance(entry, dict) and entry.get("@type") == "JobPosting":
                return entry
    return None


def _detail_urls(source_url: str, html: str) -> list[str]:
    selector = make_selector(html, source_url)
    seen: set[str] = set()
    urls: list[str] = []
    for href in selector.css("a::attr(href)").getall():
        raw = clean_text(href)
        if not raw:
            continue
        # Dice uses both absolute (https://www.dice.com/job-detail/...) and
        # relative (/job-detail/...) URLs
        job_url = absolute_url(source_url, raw)
        if not job_url:
            continue
        # Normalise to strip query params so duplicates collapse
        parsed = urlparse(job_url)
        clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        if "/job-detail/" not in clean_url.lower():
            continue
        if clean_url not in seen:
            seen.add(clean_url)
            urls.append(clean_url)
    return urls


def scrape_dice_jobs(source_url: str, timeout: int = 30) -> list[dict]:
    html = fetch_html(source_url, timeout=timeout)
    jobs: list[dict] = []

    for detail_url in _detail_urls(source_url, html)[:40]:
        try:
            detail_html = fetch_html(detail_url, timeout=timeout)
        except Exception as exc:
            logger.info("Dice detail fetch failed for %s: %s", detail_url, exc)
            continue

        selector = make_selector(detail_html, detail_url)
        ld_job = _extract_ld_job(detail_html) or {}
        title = clean_text(ld_job.get("title")) or clean_text(selector.css("h1::text").get())
        description = clean_text(ld_job.get("description")) or first_text(selector, "main", "article", "body")
        location = clean_text(
            selector.css('[data-cy="location"]::text').get()
            or selector.css('[class*="location"]::text').get()
            or ", ".join(
                part
                for part in (
                    _ld_address_value(ld_job, "addressLocality"),
                    _ld_address_value(ld_job, "addressRegion"),
                    _ld_address_value(ld_job, "addressCountry"),
                )
                if part
            )
        )
        company = clean_text(
            (ld_job.get("hiringOrganization") or {}).get("name")
            or selector.css('[data-cy="companyName"]::text').get()
        )
        posted_at = clean_text(ld_job.get("datePosted"))
        if not posted_at:
            page_text = first_text(selector, "body") or ""
            match = _POSTED_RE.search(page_text)
            posted_at = clean_text(match.group(1)) if match else None
        # Try LD+JSON baseSalary first, then CSS attribute, then page-text regex
        salary_text = None
        base_salary = ld_job.get("baseSalary") or {}
        if isinstance(base_salary, dict):
            salary_value = base_salary.get("value") or {}
            if isinstance(salary_value, dict):
                min_val = salary_value.get("minValue")
                max_val = salary_value.get("maxValue")
                unit = salary_value.get("unitText", "")
                if min_val and max_val:
                    salary_text = f"${min_val:,} - ${max_val:,} {unit}".strip()
                elif min_val:
                    salary_text = f"${min_val:,} {unit}".strip()
        if not salary_text:
            salary_text = clean_text(selector.css('[data-cy="salaryLabel"]::text').get())
        if not salary_text:
            page_text = first_text(selector, "body") or ""
            salary_match = _SALARY_RE.search(page_text)
            salary_text = clean_text(salary_match.group(1)) if salary_match else None
        work_mode = clean_text(
            selector.css('[data-cy="workplaceType"]::text').get() or selector.css('[class*="remote"]::text').get()
        )
        employment_type = clean_text(
            ld_job.get("employmentType")
            or selector.css('[data-cy="employmentType"]::text').get()
            or selector.css('[class*="employment"]::text').get()
        )
        if not title:
            continue

        keywords = extract_keywords(description)
        location_data = normalize_location(location, work_mode=work_mode or keywords["work_mode"])
        jobs.append(
            {
                "title": title,
                "company": company,
                "location": location_data["location"],
                "city": location_data["city"],
                "state": location_data["state"] or parse_state(location),
                "country": location_data["country"] or infer_country(location, title, description),
                "source": "dice",
                "source_external_id": clean_text(
                    ld_job.get("identifier", {}).get("value") or selector.css('[data-cy="jobId"]::text').get()
                ),
                "source_url": source_url,
                "job_url": detail_url,
                "description": description,
                **keywords,
                "work_mode": location_data["work_mode"] or work_mode or keywords["work_mode"],
                "employment_type": employment_type or keywords["employment_type"],
                "salary_text": salary_text or keywords["salary_text"],
                "posted_at": posted_at,
                "raw_payload": {"ld_job": ld_job, "detail_url": detail_url},
            }
        )
    return jobs
