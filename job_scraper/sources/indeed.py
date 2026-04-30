from __future__ import annotations

import logging
import re

import requests

from job_scraper.extractors import extract_keywords
from job_scraper.normalization import normalize_location
from job_scraper.utils import clean_text, infer_country, parse_state


logger = logging.getLogger(__name__)

# Indeed's public RSS feed — no auth required and not behind CAPTCHA
_RSS_BASE = "https://www.indeed.com/rss"

# Regex to parse the RSS <item> blocks quickly without a full XML parser
_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.DOTALL)
_TAG_RE = re.compile(r"<(?P<tag>[a-zA-Z:]+)[^>]*>(?P<val>.*?)</(?P=tag)>", re.DOTALL)


def _parse_rss_items(rss_text: str) -> list[dict]:
    """Parse <item> blocks from an Indeed RSS feed into dicts."""
    jobs: list[dict] = []
    for item_match in _ITEM_RE.finditer(rss_text):
        item_xml = item_match.group(1)
        fields: dict[str, str] = {}
        for tag_match in _TAG_RE.finditer(item_xml):
            tag = tag_match.group("tag").lower().split(":")[-1]  # strip namespace
            val = tag_match.group("val").strip()
            # Strip CDATA wrappers
            val = re.sub(r"<!\[CDATA\[(.*?)]]>", r"\1", val, flags=re.DOTALL).strip()
            fields[tag] = val
        title = clean_text(fields.get("title"))
        link = clean_text(fields.get("link") or fields.get("guid"))
        if not title or not link:
            continue
        # author / source contains "Company - Location"
        author = clean_text(fields.get("author") or fields.get("source") or "")
        company: str | None = None
        location: str | None = None
        if author and " - " in author:
            parts = author.split(" - ", 1)
            company = clean_text(parts[0])
            location = clean_text(parts[1])
        description = clean_text(re.sub(r"<[^>]+>", " ", fields.get("description") or ""))
        pub_date = clean_text(fields.get("pubdate") or fields.get("pubDate"))
        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "description": description,
            "job_url": link,
            "posted_at": pub_date,
        })
    return jobs


def _build_rss_url(source_url: str) -> str:
    """
    Derive an Indeed RSS feed URL from a standard /jobs search URL.

    E.g. ``https://www.indeed.com/jobs?q=python&l=remote``
         -> ``https://www.indeed.com/rss?q=python&l=remote``
    """
    from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
    parsed = urlparse(source_url)
    params = parse_qs(parsed.query)
    # Keep only query params that Indeed RSS accepts
    rss_params = {}
    for key in ("q", "l", "radius", "sort", "jt", "fromage"):
        vals = params.get(key)
        if vals:
            rss_params[key] = vals[0]
    if not rss_params.get("q"):
        rss_params["q"] = "jobs"
    return f"{_RSS_BASE}?{urlencode(rss_params)}"


def scrape_indeed_jobs(source_url: str, timeout: int = 30) -> list[dict]:
    """
    Scrape Indeed jobs via their public RSS feed.

    Indeed blocks HTML scraping aggressively (returns 403), but their RSS
    endpoint is publicly accessible and returns structured XML without CAPTCHA.
    Falls back to an empty list + raises on hard 403 so the portal router can
    surface a helpful message to configure INDEED_PROVIDER.
    """
    rss_url = _build_rss_url(source_url)
    try:
        response = requests.get(
            rss_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
            timeout=timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        status_code = getattr(exc.response, "status_code", None)
        if status_code == 403:
            raise  # Let portal_router surface the BLOCKED_403 message
        logger.info("Indeed RSS fetch failed for %s (rss=%s): %s", source_url, rss_url, exc)
        return []
    except Exception as exc:
        logger.info("Indeed RSS fetch failed for %s (rss=%s): %s", source_url, rss_url, exc)
        return []

    content_type = response.headers.get("Content-Type", "")
    if "xml" not in content_type and not response.text.strip().startswith("<"):
        logger.info("Indeed RSS returned unexpected content type %s for %s", content_type, rss_url)
        return []

    raw_jobs = _parse_rss_items(response.text)
    jobs: list[dict] = []
    for raw in raw_jobs:
        title = raw["title"]
        location = raw.get("location")
        description = raw.get("description")
        keywords = extract_keywords(description)
        location_data = normalize_location(location, work_mode=keywords["work_mode"])
        jobs.append(
            {
                "title": title,
                "company": raw.get("company"),
                "location": location_data["location"] or location,
                "city": location_data["city"],
                "state": location_data["state"] or parse_state(location),
                "country": location_data["country"] or infer_country(location, title, description),
                "source": "indeed",
                "source_external_id": None,
                "source_url": source_url,
                "job_url": raw.get("job_url") or source_url,
                "description": description,
                **keywords,
                "work_mode": location_data["work_mode"] or keywords["work_mode"],
                "posted_at": raw.get("posted_at"),
                "raw_payload": {"rss_url": rss_url},
            }
        )

    if not jobs:
        logger.info("Indeed RSS returned no jobs for %s (rss=%s)", source_url, rss_url)
    return jobs
