from __future__ import annotations

import re

from defusedxml import ElementTree

from job_scraper.extractors import extract_keywords
from job_scraper.utils import absolute_url, clean_text, fetch_html, infer_country, parse_state


COMPANY_TITLE_RE = re.compile(r"^(?P<company>[^:]+):\s*(?P<title>.+)$")


def scrape_weworkremotely_jobs(source_url: str, timeout: int = 30) -> list[dict]:
    xml_text = fetch_html(source_url, timeout=timeout)
    root = ElementTree.fromstring(xml_text.encode("utf-8", errors="ignore"))
    jobs = []

    channel = root.find("channel")
    if channel is None:
        return jobs

    for item in channel.findall("item"):
        raw_title = clean_text(item.findtext("title"))
        link = clean_text(item.findtext("link"))
        region = clean_text(item.findtext("region")) or "Remote"
        description = clean_text(item.findtext("description"))
        category = clean_text(item.findtext("category"))
        posted_at = clean_text(item.findtext("pubDate"))

        company = None
        title = raw_title
        if raw_title:
            match = COMPANY_TITLE_RE.match(raw_title)
            if match:
                company = clean_text(match.group("company"))
                title = clean_text(match.group("title"))

        job_url = absolute_url(source_url, link)
        if not title or not job_url:
            continue
        keywords = extract_keywords(description)
        jobs.append(
            {
                "title": title,
                "company": company,
                "location": region,
                "state": parse_state(region),
                "country": infer_country(region, title, description),
                "source": "weworkremotely",
                "source_external_id": None,
                "source_url": source_url,
                "job_url": job_url,
                "description": description,
                **keywords,
                "domain_terms": list(dict.fromkeys(keywords["domain_terms"] + ([category] if category else []))),
                "posted_at": posted_at,
                "raw_payload": {
                    "rss_title": raw_title,
                    "region": region,
                    "category": category,
                    "link": link,
                },
            }
        )
    return jobs
