from __future__ import annotations

import json
import logging
import re

from job_scraper.extractors import extract_keywords
from job_scraper.utils import absolute_url, clean_text, fetch_html, first_text, infer_country, make_selector, maybe_fetch_with_browser, parse_state


logger = logging.getLogger(__name__)
JSON_SCRIPT_RE = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)


def _extract_jobs_from_ld_json(html: str, source_url: str) -> list[dict]:
    jobs: list[dict] = []
    for match in JSON_SCRIPT_RE.findall(html):
        try:
            payload = json.loads(match.strip())
        except json.JSONDecodeError:
            continue
        entries = payload if isinstance(payload, list) else [payload]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            title = clean_text(entry.get("title"))
            job_url = clean_text(entry.get("url")) or source_url
            if not title or not job_url:
                continue
            location = clean_text(entry.get("jobLocation", {}).get("address", {}).get("addressLocality"))
            description = clean_text(entry.get("description"))
            keywords = extract_keywords(description)
            jobs.append(
                {
                    "title": title,
                    "company": clean_text(entry.get("hiringOrganization", {}).get("name")),
                    "location": location,
                    "state": parse_state(location),
                    "country": infer_country(location, title, description),
                    "source": "workday",
                    "source_external_id": clean_text(entry.get("identifier", {}).get("value")),
                    "source_url": source_url,
                    "job_url": job_url,
                    "description": description,
                    **keywords,
                    "employment_type": clean_text(entry.get("employmentType")) or keywords["employment_type"],
                    "posted_at": clean_text(entry.get("datePosted")),
                    "raw_payload": entry,
                }
            )
    return jobs


def scrape_workday_jobs(
    source_url: str,
    timeout: int = 30,
    enable_browser_fetcher: bool = False,
    browser_timeout_seconds: int = 30,
) -> list[dict]:
    html = fetch_html(source_url, timeout=timeout)
    jobs = _extract_jobs_from_ld_json(html, source_url)
    if jobs:
        return jobs

    selector = make_selector(html, source_url)
    links = selector.css("a::attr(href)").getall()
    detail_links = []
    for link in links:
        absolute = absolute_url(source_url, clean_text(link))
        if absolute and "/job/" in absolute.lower():
            detail_links.append(absolute)

    if not detail_links:
        browser_html = maybe_fetch_with_browser(
            source_url,
            enabled=enable_browser_fetcher,
            timeout=browser_timeout_seconds * 1000,
        )
        if browser_html:
            selector = make_selector(browser_html, source_url)
            detail_links = [
                absolute_url(source_url, clean_text(link))
                for link in selector.css("a::attr(href)").getall()
                if absolute_url(source_url, clean_text(link)) and "/job/" in absolute_url(source_url, clean_text(link)).lower()
            ]

    if not detail_links:
        logger.info("Workday source requires browser rendering; skipping for this run.")
        return []

    jobs = []
    seen_urls: set[str] = set()
    for detail_url in detail_links[:50]:
        if not detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        try:
            detail_html = fetch_html(detail_url, timeout=timeout)
        except Exception as exc:
            logger.warning("Failed to fetch Workday detail page %s: %s", detail_url, exc)
            continue
        detail_selector = make_selector(detail_html, detail_url)
        title = clean_text(detail_selector.css("h1::text").get() or detail_selector.css("title::text").get())
        description = first_text(detail_selector, "main", "body")
        if not title or not detail_url:
            continue
        location = clean_text(detail_selector.find_by_regex(r"(Remote|[A-Za-z ]+, [A-Z]{2})", first_match=True).text if detail_selector.find_by_regex(r"(Remote|[A-Za-z ]+, [A-Z]{2})", first_match=True) else None)
        requisition = clean_text(detail_selector.find_by_regex(r"(Requisition|Req(uisition)? ID)\s*[:#]?\s*\w+", first_match=True).text if detail_selector.find_by_regex(r"(Requisition|Req(uisition)? ID)\s*[:#]?\s*\w+", first_match=True) else None)
        posted_at = clean_text(detail_selector.find_by_regex(r"(Posted|Date Posted)\s*[:#]?\s*.+", first_match=True).text if detail_selector.find_by_regex(r"(Posted|Date Posted)\s*[:#]?\s*.+", first_match=True) else None)
        keywords = extract_keywords(description)
        jobs.append(
            {
                "title": title,
                "company": None,
                "location": location,
                "state": parse_state(location),
                "country": infer_country(location, title, description),
                "source": "workday",
                "source_external_id": requisition,
                "source_url": source_url,
                "job_url": detail_url,
                "description": description,
                **keywords,
                "posted_at": posted_at,
                "raw_payload": {"detail_url": detail_url},
            }
        )
    return jobs
