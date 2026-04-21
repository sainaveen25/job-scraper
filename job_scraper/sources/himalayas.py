from __future__ import annotations

import logging

from job_scraper.extractors import extract_keywords
from job_scraper.utils import absolute_url, clean_text, fetch_html, infer_country, make_selector, maybe_fetch_with_browser, parse_state


logger = logging.getLogger(__name__)


def scrape_himalayas_jobs(source_url: str, timeout: int = 30, enable_browser_fetcher: bool = False) -> list[dict]:
    try:
        html = fetch_html(source_url, timeout=timeout)
    except Exception as exc:
        browser_html = maybe_fetch_with_browser(source_url, enabled=enable_browser_fetcher, timeout=timeout * 1000)
        if not browser_html:
            logger.info("Himalayas blocked or rejected %s; skipping for this run: %s", source_url, exc)
            return []
        html = browser_html
    selector = make_selector(html, source_url)
    jobs = []
    for card in selector.css("a[href*='/jobs/']"):
        href = clean_text(card.attrib.get("href") if hasattr(card, "attrib") else None)
        job_url = absolute_url(source_url, href)
        title = clean_text(card.css("h3::text").get() or card.css("h2::text").get())
        company = clean_text(card.css("p::text").get())
        location = clean_text(card.find_by_regex(r"(Remote|[A-Za-z ]+, [A-Z]{2})", first_match=True).text if card.find_by_regex(r"(Remote|[A-Za-z ]+, [A-Z]{2})", first_match=True) else None)
        description = clean_text(card.get_all_text(" ", strip=True))
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
                "source": "himalayas",
                "source_external_id": None,
                "source_url": source_url,
                "job_url": job_url,
                "description": description,
                **keywords,
                "raw_payload": {"html_excerpt": card.html_content[:1000]},
            }
        )
    return jobs
