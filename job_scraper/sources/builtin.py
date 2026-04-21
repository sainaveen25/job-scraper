from __future__ import annotations

import logging

from job_scraper.extractors import extract_keywords
from job_scraper.utils import absolute_url, clean_text, extract_json_from_scripts, fetch_html, infer_country, make_selector, parse_state


logger = logging.getLogger(__name__)


def scrape_builtin_jobs(source_url: str, timeout: int = 30) -> list[dict]:
    html = fetch_html(source_url, timeout=timeout)
    selector = make_selector(html, source_url)

    listing_links: list[str] = []
    for link in selector.css("a[href*='/job/']"):
        href = clean_text(link.attrib.get("href") if hasattr(link, "attrib") else None)
        job_url = absolute_url(source_url, href)
        if job_url and job_url not in listing_links:
            listing_links.append(job_url)

    jobs = []
    for job_url in listing_links[:30]:
        try:
            detail_html = fetch_html(job_url, timeout=timeout)
        except Exception as exc:
            logger.warning("Failed to fetch builtin job detail %s: %s", job_url, exc)
            continue

        payloads = extract_json_from_scripts(detail_html)
        detail_selector = make_selector(detail_html, job_url)
        title = company = location = posted_at = description = None
        source_external_id = None

        for payload in payloads:
            graph = payload.get("@graph") if isinstance(payload, dict) else None
            nodes = graph if isinstance(graph, list) else [payload]
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                if node.get("@type") == "JobPosting":
                    title = clean_text(node.get("title")) or title
                    description = clean_text(node.get("description")) or description
                    company = clean_text((node.get("hiringOrganization") or {}).get("name")) or company
                    posted_at = clean_text(node.get("datePosted")) or posted_at
                    source_external_id = clean_text(node.get("identifier", {}).get("value")) or source_external_id
                    job_location = node.get("jobLocation") or {}
                    if isinstance(job_location, list) and job_location:
                        job_location = job_location[0]
                    if isinstance(job_location, dict):
                        address = job_location.get("address") or {}
                        location = (
                            clean_text(address.get("addressLocality"))
                            or clean_text(address.get("addressRegion"))
                            or location
                        )
                    break

        title = title or clean_text(detail_selector.css("h1::text").get() or detail_selector.css("title::text").get())
        if not description:
            main_node = detail_selector.css("main")
            description = clean_text(main_node[0].get_all_text(" ", strip=True) if main_node else None)

        if not location:
            meta = clean_text(detail_selector.css('meta[name="description"]::attr(content)').get())
            location = meta

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
                "source": "builtin",
                "source_external_id": source_external_id,
                "source_url": source_url,
                "job_url": job_url,
                "description": description,
                **keywords,
                "posted_at": posted_at,
                "raw_payload": {"job_url": job_url},
            }
        )
    return jobs
