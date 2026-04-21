from __future__ import annotations

import logging

import requests

from job_scraper.sources.generic import scrape_generic_jobs


logger = logging.getLogger(__name__)


def scrape_linkedin_jobs(source_url: str, timeout: int = 30) -> list[dict]:
    try:
        jobs = scrape_generic_jobs(source_url, timeout=timeout)
        for job in jobs:
            job["source"] = "linkedin"
        if not jobs:
            logger.info("LinkedIn best-effort scrape returned no jobs for %s", source_url)
        return jobs
    except Exception as exc:
        if isinstance(exc, requests.HTTPError) and getattr(exc.response, "status_code", None) == 403:
            raise
        logger.info("LinkedIn best-effort scrape failed for %s: %s", source_url, exc)
        return []
