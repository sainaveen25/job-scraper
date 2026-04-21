from __future__ import annotations

import logging

from job_scraper.extractors import extract_keywords
from job_scraper.utils import (
    absolute_url,
    append_query_params,
    clean_text,
    fetch_html,
    first_text,
    infer_country,
    make_selector,
    parse_state,
)


logger = logging.getLogger(__name__)


def build_google_careers_urls(source_url: str, search_queries: list[dict] | None = None) -> list[str]:
    if not search_queries:
        return [source_url]
    urls = [source_url]
    for query in search_queries:
        urls.append(
            append_query_params(
                source_url,
                q=clean_text(query.get("title")),
                location=clean_text(query.get("location")),
            )
        )
    return list(dict.fromkeys(urls))


def scrape_google_careers_jobs(source_url: str, search_queries: list[dict] | None = None, timeout: int = 30) -> list[dict]:
    jobs: list[dict] = []
    seen_urls: set[str] = set()

    for listing_url in build_google_careers_urls(source_url, search_queries):
        try:
            html = fetch_html(listing_url, timeout=timeout)
        except Exception as exc:
            logger.warning("Failed to fetch Google Careers page %s: %s", listing_url, exc)
            continue

        selector = make_selector(html, listing_url)
        links = selector.css("a::attr(href)").getall()
        detail_urls = []
        for link in links:
            absolute = absolute_url(listing_url, clean_text(link))
            if absolute and "/jobs/results/" in absolute.lower():
                detail_urls.append(absolute)

        for detail_url in detail_urls[:100]:
            if detail_url in seen_urls:
                continue
            seen_urls.add(detail_url)
            try:
                detail_html = fetch_html(detail_url, timeout=timeout)
            except Exception as exc:
                logger.warning("Failed to fetch Google Careers detail %s: %s", detail_url, exc)
                continue
            detail_selector = make_selector(detail_html, detail_url)
            title = clean_text(detail_selector.css("h1::text").get() or detail_selector.css("title::text").get())
            if not title:
                continue
            location = clean_text(detail_selector.find_by_regex(r"(Remote|[A-Za-z ]+, [A-Z]{2})", first_match=True).text if detail_selector.find_by_regex(r"(Remote|[A-Za-z ]+, [A-Z]{2})", first_match=True) else None)
            description = first_text(detail_selector, "main", "body")
            source_external_id = clean_text(detail_selector.find_by_regex(r"Job ID\s*[:#]?\s*\w+", first_match=True).text if detail_selector.find_by_regex(r"Job ID\s*[:#]?\s*\w+", first_match=True) else None)
            posted_at = clean_text(detail_selector.find_by_regex(r"(Posted|Date posted)\s*[:#]?\s*.+", first_match=True).text if detail_selector.find_by_regex(r"(Posted|Date posted)\s*[:#]?\s*.+", first_match=True) else None)
            keywords = extract_keywords(description)
            jobs.append(
                {
                    "title": title,
                    "company": "Google",
                    "location": location,
                    "state": parse_state(location),
                    "country": infer_country(location, title, description),
                    "source": "google_careers",
                    "source_external_id": source_external_id,
                    "source_url": source_url,
                    "job_url": detail_url,
                    "description": description,
                    **keywords,
                    "posted_at": posted_at,
                    "raw_payload": {"listing_url": listing_url, "detail_url": detail_url},
                }
            )

    if not jobs:
        logger.info("Google Careers parsing returned no jobs for %s", source_url)
    return jobs
