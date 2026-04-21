from __future__ import annotations

import logging

from job_scraper.sources.generic import scrape_generic_jobs


logger = logging.getLogger(__name__)


def scrape_dice_jobs(source_url: str, timeout: int = 30) -> list[dict]:
    try:
        jobs = scrape_generic_jobs(source_url, timeout=timeout)
        if not jobs:
            logger.info("Dice best-effort scrape returned no jobs for %s", source_url)
        return jobs
    except Exception as exc:
        logger.info("Dice best-effort scrape failed for %s: %s", source_url, exc)
        return []
