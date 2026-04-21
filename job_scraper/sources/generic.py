from __future__ import annotations

import logging

import requests

from job_scraper.extractors import extract_keywords
from job_scraper.utils import absolute_url, clean_text, fetch_html, first_text, infer_country, make_selector, parse_state


logger = logging.getLogger(__name__)
KEYWORDS = ("job", "jobs", "career", "careers", "opening", "position", "requisition")


def scrape_generic_jobs(source_url: str, timeout: int = 30) -> list[dict]:
    try:
        html = fetch_html(source_url, timeout=timeout)
    except Exception as exc:
        if isinstance(exc, requests.HTTPError) and getattr(exc.response, "status_code", None) == 403:
            raise
        logger.warning("Failed to fetch generic source %s: %s", source_url, exc)
        return []

    selector = make_selector(html, source_url)
    detail_urls = []
    for link in selector.css("a::attr(href)").getall():
        absolute = absolute_url(source_url, clean_text(link))
        if absolute and any(keyword in absolute.lower() for keyword in KEYWORDS):
            detail_urls.append(absolute)

    jobs = []
    seen: set[str] = set()
    for detail_url in detail_urls[:50]:
        if detail_url in seen:
            continue
        seen.add(detail_url)
        try:
            detail_html = fetch_html(detail_url, timeout=timeout)
        except Exception as exc:
            logger.warning("Failed to fetch generic job detail %s: %s", detail_url, exc)
            continue
        detail_selector = make_selector(detail_html, detail_url)
        title = clean_text(detail_selector.css("h1::text").get() or detail_selector.css("title::text").get())
        description = first_text(detail_selector, "main", "article", "body")
        if not title or len(title.split()) < 2:
            continue
        keywords = extract_keywords(description)
        location = clean_text(detail_selector.find_by_regex(r"(Remote|[A-Za-z ]+, [A-Z]{2})", first_match=True).text if detail_selector.find_by_regex(r"(Remote|[A-Za-z ]+, [A-Z]{2})", first_match=True) else None)
        jobs.append(
            {
                "title": title,
                "company": None,
                "location": location,
                "state": parse_state(location),
                "country": infer_country(location, title, description),
                "source": "generic",
                "source_external_id": None,
                "source_url": source_url,
                "job_url": detail_url,
                "description": description,
                **keywords,
                "raw_payload": {"detail_url": detail_url},
            }
        )
    return jobs
