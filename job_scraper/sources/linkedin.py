from __future__ import annotations

import logging
import re
from urllib.parse import urlparse, urlunparse

import requests

from job_scraper.extractors import extract_keywords
from job_scraper.normalization import normalize_location
from job_scraper.utils import clean_text, fetch_html, infer_country, make_selector, parse_state


logger = logging.getLogger(__name__)

# LinkedIn encodes tracking params into URLs — strip them for clean job URLs
_TRACKING_PARAMS = {"position", "pageNum", "refId", "trackingId"}


def _clean_linkedin_url(url: str) -> str:
    """Strip LinkedIn tracking query parameters from a job URL."""
    if not url:
        return url
    parsed = urlparse(url)
    # Keep only the path — tracking params add noise; the path uniquely IDs the job
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def scrape_linkedin_jobs(source_url: str, timeout: int = 30) -> list[dict]:
    """
    Scrape LinkedIn job search results by parsing the server-rendered HTML.

    LinkedIn renders a list of ``div[data-entity-urn]`` elements that each contain
    a job card with title (h3), company (h4 / .base-search-card__subtitle a),
    location, and the job URL.  This avoids following individual detail pages
    and keeps the scraper fast and reliable.
    """
    try:
        html = fetch_html(source_url, timeout=timeout)
    except Exception as exc:
        if isinstance(exc, requests.HTTPError) and getattr(exc.response, "status_code", None) == 403:
            raise
        logger.info("LinkedIn fetch failed for %s: %s", source_url, exc)
        return []

    selector = make_selector(html, source_url)

    # Each job card is a <div data-entity-urn="urn:li:jobPosting:..."> element
    cards = selector.css("div[data-entity-urn]")
    if not cards:
        logger.info("LinkedIn: no job cards found for %s", source_url)
        return []

    jobs: list[dict] = []
    seen_ids: set[str] = set()

    for card in cards:
        urn = clean_text(card.attrib.get("data-entity-urn", ""))
        job_id = urn.split(":")[-1] if urn else None

        # Skip duplicates (LinkedIn sometimes repeats cards)
        if job_id and job_id in seen_ids:
            continue
        if job_id:
            seen_ids.add(job_id)

        # Title — stored in the <h3> inside the card
        title_nodes = card.css("h3::text")
        title_raw = title_nodes[0].text if title_nodes else ""
        title = re.sub(r"\s+", " ", title_raw or "").strip() if title_raw else None
        title = clean_text(title)
        if not title:
            continue

        # Company — <h4> or explicitly classed subtitle anchor
        company_nodes = card.css(".base-search-card__subtitle a::text")
        company_raw = company_nodes[0].text if company_nodes else ""
        if not company_raw:
            h4_nodes = card.css("h4::text")
            company_raw = h4_nodes[0].text if h4_nodes else ""
        company = clean_text(re.sub(r"\s+", " ", company_raw or "").strip())

        # Location
        loc_nodes = card.css("[class*='location']::text")
        location_raw = loc_nodes[0].text if loc_nodes else ""
        location = clean_text(re.sub(r"\s+", " ", location_raw or "").strip())

        # Job URL
        link_nodes = card.css("a.base-card__full-link::attr(href)")
        raw_link = link_nodes[0].text if link_nodes else ""
        if not raw_link:
            # Fallback: first <a> with href inside the card
            a_nodes = card.css("a::attr(href)")
            raw_link = a_nodes[0].text if a_nodes else ""
        job_url = _clean_linkedin_url(clean_text(raw_link) or "")

        location_data = normalize_location(location)
        keywords = extract_keywords(None)  # No description available from search cards

        jobs.append(
            {
                "title": title,
                "company": company,
                "location": location_data["location"] or location,
                "city": location_data["city"],
                "state": location_data["state"] or parse_state(location),
                "country": location_data["country"] or infer_country(location, title),
                "source": "linkedin",
                "source_external_id": job_id,
                "source_url": source_url,
                "job_url": job_url or source_url,
                "description": None,
                **keywords,
                "work_mode": location_data["work_mode"] or keywords["work_mode"],
                "raw_payload": {"urn": urn},
            }
        )

    if not jobs:
        logger.info("LinkedIn best-effort scrape returned no jobs for %s", source_url)
    return jobs
