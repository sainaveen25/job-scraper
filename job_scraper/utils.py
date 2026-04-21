from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests

from scrapling.parser import Selector

from job_scraper.extractors import normalize_text


logger = logging.getLogger(__name__)
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

COUNTRY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bcanada\b", re.IGNORECASE), "Canada"),
    (re.compile(r"\bunited states\b|\busa\b|\bu\.s\.a\b|\bus\b", re.IGNORECASE), "USA"),
    (re.compile(r"\bunited kingdom\b|\buk\b|\bu\.k\.\b|\bengland\b", re.IGNORECASE), "United Kingdom"),
    (re.compile(r"\bindia\b", re.IGNORECASE), "India"),
    (re.compile(r"\bgermany\b", re.IGNORECASE), "Germany"),
    (re.compile(r"\bfrance\b", re.IGNORECASE), "France"),
    (re.compile(r"\bspain\b", re.IGNORECASE), "Spain"),
    (re.compile(r"\bitaly\b", re.IGNORECASE), "Italy"),
    (re.compile(r"\bnetherlands\b", re.IGNORECASE), "Netherlands"),
    (re.compile(r"\bpoland\b", re.IGNORECASE), "Poland"),
    (re.compile(r"\bireland\b", re.IGNORECASE), "Ireland"),
    (re.compile(r"\bsingapore\b", re.IGNORECASE), "Singapore"),
    (re.compile(r"\baustralia\b", re.IGNORECASE), "Australia"),
    (re.compile(r"\bnew zealand\b", re.IGNORECASE), "New Zealand"),
    (re.compile(r"\bphilippines\b", re.IGNORECASE), "Philippines"),
    (re.compile(r"\bpakistan\b", re.IGNORECASE), "Pakistan"),
    (re.compile(r"\buae\b|\bunited arab emirates\b", re.IGNORECASE), "United Arab Emirates"),
)


def fetch_html(url: str, timeout: int = 30) -> str:
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def fetch_json(url: str, timeout: int = 30, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    response = requests.get(url, headers={**REQUEST_HEADERS, **(headers or {})}, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def maybe_fetch_with_browser(url: str, enabled: bool = False, timeout: int = 30000) -> str | None:
    if not enabled:
        return None
    try:
        from scrapling.fetchers import DynamicFetcher

        response = DynamicFetcher.fetch(url, timeout=timeout, network_idle=True, headless=True)
        return response.html_content
    except Exception as exc:  # pragma: no cover
        logger.warning("Browser fetch failed for %s: %s", url, exc)
        return None


def make_selector(html: str | bytes, url: str) -> Selector:
    if isinstance(html, str):
        return Selector(html.encode("utf-8", errors="ignore"), url=url)
    return Selector(html, url=url)


def absolute_url(base_url: str, maybe_relative: str | None) -> str | None:
    if not maybe_relative:
        return None
    return urljoin(base_url, maybe_relative)


def clean_text(value: Any) -> str | None:
    text = normalize_text(value)
    return text or None


def parse_state(location: str | None) -> str | None:
    cleaned = clean_text(location)
    if not cleaned:
        return None
    if "," in cleaned:
        parts = [part.strip() for part in cleaned.split(",") if part.strip()]
        if len(parts) >= 2:
            return parts[-1]
    return None


def infer_country(*values: Any) -> str | None:
    combined = " ".join(part for part in (clean_text(value) or "" for value in values) if part).strip()
    if not combined:
        return None

    for pattern, country in COUNTRY_PATTERNS:
        if pattern.search(combined):
            return country

    return None


def append_query_params(url: str, **params: str | None) -> str:
    parsed = urlparse(url)
    current = parse_qs(parsed.query)
    for key, value in params.items():
        if value:
            current[key] = [value]
    new_query = urlencode(current, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


def extract_json_from_scripts(html: str) -> list[Any]:
    selector = make_selector(html, "")
    payloads: list[Any] = []
    for script in selector.css('script[type="application/ld+json"]::text').getall():
        try:
            payloads.append(json.loads(script))
        except json.JSONDecodeError:
            continue
    return payloads


def first_text(selector: Selector, *css_queries: str) -> str | None:
    for query in css_queries:
        nodes = selector.css(query)
        if nodes:
            text = clean_text(nodes[0].get_all_text(strip=True))
            if text:
                return text
    return None
