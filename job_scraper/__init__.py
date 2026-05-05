"""ApplyMate job scraper package.

Keep package import lightweight so test collection and provider modules do not
pull in the full scraper runtime graph before dependencies are ready.
"""

from typing import Any

__all__ = ["scrape_all_sources"]


def __getattr__(name: str) -> Any:
    if name == "scrape_all_sources":
        from job_scraper.main import scrape_all_sources

        return scrape_all_sources
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
