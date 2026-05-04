from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlparse

from job_scraper.extractors import extract_keywords
from job_scraper.normalization import (
    choose_posted_at,
    generate_search_terms,
    infer_category,
    normalize_location,
    normalize_title,
)
from job_scraper.utils import (
    absolute_url,
    clean_text,
    fetch_html,
    first_text,
    infer_country,
    make_selector,
    maybe_fetch_with_browser,
    parse_state,
)


logger = logging.getLogger(__name__)
JSON_SCRIPT_RE = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.IGNORECASE | re.DOTALL)
REQ_ID_RE = re.compile(r"(?:Requisition|Req(?:uisition)? ID)\s*[:#]?\s*([A-Z0-9-]+)", re.IGNORECASE)
POSTED_RE = re.compile(
    r"(?:Posted|Date Posted|Posted Date|Posted On|Date)\s*[:#]?\s*"
    r"("
    r"\d+\s*(?:minute|minutes|min|mins|hour|hours|hr|hrs|day|days)\s+ago"
    r"|just posted|just now|posted today|today|yesterday"
    r"|[A-Z][a-z]{2,8}\s+\d{1,2},\s+\d{4}"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{4}-\d{2}-\d{2}(?:[T ][0-9:.+-Z]+)?"
    r")",
    re.IGNORECASE,
)
_SALARY_RE = re.compile(
    r"(\$[\d,]+(?:\.\d+)?(?:\s*[-–]\s*\$[\d,]+(?:\.\d+)?)?(?:\s*/\s*(?:year|yr|hour|hr))?)",
    re.IGNORECASE,
)
_LOCATION_RE = re.compile(
    r"\b(Remote|Hybrid|On[- ]?[Ss]ite|[A-Za-z ]{2,30},\s*[A-Z]{2}(?:,\s*[A-Za-z ]+)?)",
)
_EMPLOYMENT_TYPE_RE = re.compile(r"\b(Full[- ]time|Part[- ]time|Contract|Internship|Temporary)\b", re.IGNORECASE)


def is_workday_board_url(source_url: str) -> bool:
    parsed = urlparse(source_url)
    if "workdayjobs.com" not in parsed.netloc.lower():
        return False
    lowered_path = parsed.path.lower()
    if "/job/" in lowered_path:
        return False
    return bool(parsed.path.strip("/"))


def _add_search_metadata(job: dict) -> dict:
    category = infer_category(
        job.get("title"),
        job.get("description"),
        list(job.get("required_skills") or []) + list(job.get("ats_keywords") or []) + list(job.get("domain_terms") or []),
    )
    normalized_title = normalize_title(job.get("title"))
    search_terms, autocomplete_terms = generate_search_terms(
        title=job.get("title"),
        normalized_title=normalized_title,
        category=category,
        required_skills=list(job.get("required_skills") or []),
        ats_keywords=list(job.get("ats_keywords") or []),
    )
    job["normalized_title"] = normalized_title
    job["category"] = category
    job["search_terms"] = search_terms
    job["autocomplete_terms"] = autocomplete_terms
    return job


def _job_location_address(entry: dict) -> dict:
    job_location = entry.get("jobLocation") or {}
    if isinstance(job_location, list):
        job_location = next((item for item in job_location if isinstance(item, dict)), {})
    address = job_location.get("address") if isinstance(job_location, dict) else {}
    if isinstance(address, list):
        address = next((item for item in address if isinstance(item, dict)), {})
    return address if isinstance(address, dict) else {}


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
            address = _job_location_address(entry)
            location = clean_text(
                ", ".join(
                    part
                    for part in (
                        clean_text(address.get("addressLocality")),
                        clean_text(address.get("addressRegion")),
                        clean_text(address.get("addressCountry")),
                    )
                    if part
                )
            )
            description = clean_text(entry.get("description"))
            keywords = extract_keywords(description)
            location_data = normalize_location(
                location,
                work_mode=keywords["work_mode"],
            )
            jobs.append(
                _add_search_metadata({
                    "title": title,
                    "company": clean_text(entry.get("hiringOrganization", {}).get("name")),
                    "location": location_data["location"],
                    "city": location_data["city"],
                    "state": location_data["state"] or parse_state(location),
                    "country": location_data["country"] or infer_country(location, title, description),
                    "source": "workday",
                    "source_external_id": clean_text(entry.get("identifier", {}).get("value")),
                    "source_url": source_url,
                    "job_url": job_url,
                    "description": description,
                    **keywords,
                    "work_mode": location_data["work_mode"] or keywords["work_mode"],
                    "employment_type": clean_text(entry.get("employmentType")) or keywords["employment_type"],
                    "posted_at": clean_text(entry.get("datePosted")),
                    "raw_payload": entry,
                })
            )
    return jobs


def _extract_workday_listing_jobs(html: str, source_url: str) -> list[dict]:
    selector = make_selector(html, source_url)
    card_selectors = [
        '[data-automation-id="jobCard"]',
        'li[data-automation-id*="job"]',
        "section",
        "article",
    ]
    cards = []
    for card_selector in card_selectors:
        cards = selector.css(card_selector)
        if cards:
            break

    jobs: list[dict] = []
    seen_urls: set[str] = set()
    for card in cards[:75]:
        title = clean_text(
            card.css('[data-automation-id="jobTitle"]::text').get()
            or card.css('[data-automation-id="jobPostingTitle"]::text').get()
            or card.css("h3::text").get()
            or card.css("h2::text").get()
            or card.css("a::text").get()
        )
        raw_href = clean_text(
            card.css('[data-automation-id="jobTitle"]::attr(href)').get()
            or card.css('[data-automation-id="jobPostingTitle"]::attr(href)').get()
            or card.css('a[href*="/job/"]::attr(href)').get()
            or card.css("a::attr(href)").get()
        )
        job_url = absolute_url(source_url, raw_href) or source_url
        if not title or not job_url or job_url in seen_urls:
            continue
        if "/job/" not in job_url.lower() and job_url == source_url:
            continue
        seen_urls.add(job_url)

        card_text = clean_text(card.get_all_text(" ", strip=True))
        location = clean_text(
            card.css('[data-automation-id="locations"]::text').get()
            or card.css('[data-automation-id="location"]::text').get()
            or card.css('[data-automation-id="primaryLocation"]::text').get()
            or card.css('[data-automation-id="locationTarget"]::text').get()
        )
        if not location:
            loc_match = _LOCATION_RE.search(card_text)
            location = clean_text(loc_match.group(1)) if loc_match else None
        posted_at = clean_text(
            card.css('[data-automation-id="postedOn"]::text').get()
            or card.css('[data-automation-id="postedDate"]::text').get()
        )
        if not posted_at:
            posted_match = POSTED_RE.search(card_text)
            posted_at = clean_text(posted_match.group(1)) if posted_match else None
        employment_match = _EMPLOYMENT_TYPE_RE.search(card_text)
        employment_type = clean_text(employment_match.group(1)) if employment_match else None
        salary_match = _SALARY_RE.search(card_text)
        salary_text = clean_text(salary_match.group(1)) if salary_match else None

        keywords = extract_keywords(card_text)
        location_data = normalize_location(location, work_mode=keywords["work_mode"])
        jobs.append(
            _add_search_metadata({
                "title": title,
                "company": None,
                "location": location_data["location"],
                "city": location_data["city"],
                "state": location_data["state"] or parse_state(location),
                "country": location_data["country"] or infer_country(location, title, card_text),
                "source": "workday",
                "source_external_id": clean_text(job_url.rstrip("/").split("/")[-1]),
                "source_url": source_url,
                "job_url": job_url,
                "description": card_text,
                **keywords,
                "work_mode": location_data["work_mode"] or keywords["work_mode"],
                "employment_type": employment_type or keywords["employment_type"],
                "salary_text": salary_text or keywords["salary_text"],
                "posted_at": choose_posted_at(posted_at)["posted_at"] if posted_at else None,
                "raw_payload": {"listing_url": job_url},
            })
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
    jobs = _extract_workday_listing_jobs(html, source_url)
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
            jobs = _extract_jobs_from_ld_json(browser_html, source_url) or _extract_workday_listing_jobs(browser_html, source_url)
            if jobs:
                return jobs
            selector = make_selector(browser_html, source_url)
            for link in selector.css("a::attr(href)").getall():
                absolute = absolute_url(source_url, clean_text(link))
                if absolute and "/job/" in absolute.lower():
                    detail_links.append(absolute)

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
        title = clean_text(
            detail_selector.css('[data-automation-id="jobPostingHeader"]::text').get()
            or detail_selector.css('[data-automation-id="jobTitle"]::text').get()
            or detail_selector.css("h1::text").get()
            or detail_selector.css('meta[property="og:title"]::attr(content)').get()
            or detail_selector.css("title::text").get()
        )
        description = first_text(detail_selector, "main", "body")
        if not title or not detail_url:
            continue
        page_text = first_text(detail_selector, "body") or ""
        # Extract company from metadata or <title>; Workday titles are usually "Job Title - Company Name".
        raw_title_tag = clean_text(detail_selector.css("title::text").get()) or ""
        company = clean_text(
            detail_selector.css('meta[property="og:site_name"]::attr(content)').get()
            or detail_selector.css('meta[name="author"]::attr(content)').get()
            or detail_selector.css('[data-automation-id="company"]::text').get()
        )
        if " - " in raw_title_tag:
            parts = raw_title_tag.split(" - ", 1)
            if title == raw_title_tag and parts[0].strip():
                title = parts[0].strip()
            if not company and len(parts) == 2 and parts[1].strip():
                company = parts[1].strip()
        # Location: try CSS selectors first, then page-text regex
        location = (
            clean_text(detail_selector.css('[data-automation-id="locationTarget"]::text').get())
            or clean_text(detail_selector.css('[data-automation-id="locations"]::text').get())
            or clean_text(detail_selector.css('[data-automation-id="primaryLocation"]::text').get())
            or clean_text(detail_selector.css('[class*="location"]::text').get())
        )
        if not location:
            loc_match = _LOCATION_RE.search(page_text)
            location = clean_text(loc_match.group(1)) if loc_match else None
        req_match = REQ_ID_RE.search(page_text)
        requisition = clean_text(req_match.group(1)) if req_match else None
        posted_at = clean_text(
            detail_selector.css('[data-automation-id="postedOn"]::text').get()
            or detail_selector.css('[data-automation-id="postedDate"]::text').get()
        )
        posted_match = POSTED_RE.search(page_text)
        posted_at = posted_at or (clean_text(posted_match.group(1)) if posted_match else None)
        posted_at = choose_posted_at(posted_at)["posted_at"] if posted_at else None
        salary_match = _SALARY_RE.search(page_text)
        salary_text = clean_text(salary_match.group(1)) if salary_match else None
        keywords = extract_keywords(description)
        location_data = normalize_location(location, work_mode=keywords["work_mode"])
        jobs.append(
            _add_search_metadata({
                "title": title,
                "company": company,
                "location": location_data["location"],
                "city": location_data["city"],
                "state": location_data["state"] or parse_state(location),
                "country": location_data["country"] or infer_country(location, title, description),
                "source": "workday",
                "source_external_id": requisition,
                "source_url": source_url,
                "job_url": detail_url,
                "description": description,
                **keywords,
                "work_mode": location_data["work_mode"] or keywords["work_mode"],
                "salary_text": salary_text or keywords["salary_text"],
                "posted_at": posted_at,
                "raw_payload": {"detail_url": detail_url},
            })
        )
    return jobs
