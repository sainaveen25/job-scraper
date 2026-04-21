from __future__ import annotations

import logging
import time

from scraper.config import get_settings, load_environment
from scraper.run_once import configure_logging, run_ingestion_cycle


logger = logging.getLogger(__name__)


def main() -> int:
    configure_logging()
    load_environment()
    settings = get_settings()

    logger.info("Starting scraper scheduler with interval=%s seconds", settings.scraper_interval_seconds)

    try:
        while True:
            cycle_started = time.time()
            logger.info("Scraper cycle started")
            try:
                summary = run_ingestion_cycle(use_sample=False)
                logger.info(
                    "Scraper cycle completed: raw=%s normalized=%s inserted=%s updated=%s skipped=%s "
                    "ingest_failed=%s failed_sources=%s duration_seconds=%.2f",
                    summary["raw_count"],
                    summary["normalized_count"],
                    summary["inserted"],
                    summary["updated"],
                    summary["skipped"],
                    summary.get("failed", 0),
                    summary["failed_sources_count"],
                    summary["duration_seconds"],
                )
            except Exception:
                logger.exception("Scraper cycle failed")

            elapsed = time.time() - cycle_started
            sleep_seconds = max(settings.scraper_interval_seconds - elapsed, 0)
            logger.info("Next scraper cycle in %.1f seconds", sleep_seconds)
            time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by Ctrl+C")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
