from __future__ import annotations

import logging
import requests
from urllib.parse import urlparse

from job_scraper.config import JobScraperSettings
from job_scraper.source_status import (
    BLOCKED_403,
    BROWSER_RENDERED,
    BROWSER_REQUIRED,
    DIRECT_HTTP,
    DISABLED_UNTIL_CONFIGURED,
    FAILED,
    OK,
    PROVIDER_API,
    PROVIDER_DISABLED,
    PROVIDER_REQUIRED,
    ZERO_RESULTS,
    SourceScrapeResult,
    SourceStatus,
)
from job_scraper.sources.builtin import scrape_builtin_jobs
from job_scraper.sources.dice import scrape_dice_jobs
from job_scraper.sources.generic import scrape_generic_jobs
from job_scraper.sources.glassdoor import scrape_glassdoor_jobs
from job_scraper.sources.greenhouse import scrape_greenhouse_jobs
from job_scraper.sources.himalayas import scrape_himalayas_jobs
from job_scraper.sources.indeed import scrape_indeed_jobs
from job_scraper.sources.lever import scrape_lever_jobs
from job_scraper.sources.linkedin import scrape_linkedin_jobs
from job_scraper.sources.provider_sources import scrape_job_board_provider
from job_scraper.sources.remoteok import scrape_remoteok_jobs
from job_scraper.sources.weworkremotely import scrape_weworkremotely_jobs
from job_scraper.sources.workday import scrape_workday_jobs
from job_scraper.sources.ziprecruiter import scrape_ziprecruiter_jobs


logger = logging.getLogger(__name__)

DIRECT_HTTP_SOURCES = {
    "remoteok",
    "weworkremotely",
    "builtin",
    "himalayas",
    "greenhouse",
    "lever",
    "dice",
    "generic",
}
PROVIDER_REQUIRED_SOURCES = {"linkedin", "indeed", "glassdoor", "ziprecruiter"}


def detect_source_type(url: str) -> str:
    lowered = url.lower()
    parsed = urlparse(lowered)
    host = parsed.netloc
    path = parsed.path

    if "remoteok.com" in host:
        return "remoteok"
    if "weworkremotely.com" in host:
        return "weworkremotely"
    if "builtin.com" in host:
        return "builtin"
    if "himalayas.app" in host:
        return "himalayas"
    if "boards.greenhouse.io" in host or host.endswith("greenhouse.io"):
        return "greenhouse"
    if "jobs.lever.co" in host:
        return "lever"
    if "myworkdayjobs.com" in host or "workdayjobs.com" in host:
        return "workday"
    if host.endswith("linkedin.com"):
        return "linkedin"
    if "indeed.com" in host:
        return "indeed"
    if "dice.com" in host:
        return "dice"
    if "glassdoor.com" in host:
        return "glassdoor"
    if "ziprecruiter.com" in host:
        return "ziprecruiter"
    if "monster.com" in host:
        return "monster"
    if "talent.com" in host:
        return "talent"
    if host.endswith("google.com") and path.startswith("/search"):
        return "google_jobs_search"
    return "generic"


def source_mode_for_type(source_type: str) -> str:
    if source_type in DIRECT_HTTP_SOURCES:
        return DIRECT_HTTP
    if source_type == "workday":
        return BROWSER_RENDERED
    if source_type in PROVIDER_REQUIRED_SOURCES or source_type == "google_jobs_search":
        return PROVIDER_API
    return DISABLED_UNTIL_CONFIGURED


def _status(source_type: str, source_url: str, mode: str, status: str, jobs: list[dict], message: str) -> SourceStatus:
    return SourceStatus(source=source_type, url=source_url, mode=mode, status=status, jobsFound=len(jobs), message=message)


def _result(source_type: str, source_url: str, mode: str, status: str, jobs: list[dict], message: str) -> SourceScrapeResult:
    return SourceScrapeResult(jobs=jobs, status=_status(source_type, source_url, mode, status, jobs, message))


def _jobs_status(jobs: list[dict]) -> str:
    return OK if jobs else ZERO_RESULTS


def _provider_setting(settings: JobScraperSettings, source_type: str) -> str:
    return {
        "linkedin": settings.linkedin_provider,
        "indeed": settings.indeed_provider,
        "glassdoor": settings.glassdoor_provider,
        "ziprecruiter": settings.ziprecruiter_provider,
    }.get(source_type, "disabled")


def _is_blocked_http_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    return isinstance(exc, requests.HTTPError) and getattr(response, "status_code", None) == 403


def _scrape_provider_source(
    source_type: str,
    source_url: str,
    settings: JobScraperSettings,
    timeout: int,
) -> SourceScrapeResult:
    provider = _provider_setting(settings, source_type)
    if provider != "disabled":
        try:
            jobs = scrape_job_board_provider(
                source_name=source_type,
                source_url=source_url,
                provider=provider,
                serpapi_api_key=settings.serpapi_api_key,
                scraperapi_api_key=settings.scraperapi_api_key,
                timeout=timeout,
            )
        except Exception as exc:
            logger.warning("%s provider query failed for %s: %s", source_type, source_url, exc)
            return _result(source_type, source_url, PROVIDER_API, FAILED, [], f"{source_type} provider query failed: {exc}")
        if jobs:
            return _result(source_type, source_url, PROVIDER_API, OK, jobs, f"{source_type} provider returned jobs.")
        return _result(
            source_type,
            source_url,
            PROVIDER_API,
            PROVIDER_REQUIRED,
            [],
            f"{source_type} provider is configured but returned no jobs or lacks required API key.",
        )

    direct_scraper = {
        "linkedin": scrape_linkedin_jobs,
        "indeed": scrape_indeed_jobs,
        "glassdoor": scrape_glassdoor_jobs,
        "ziprecruiter": scrape_ziprecruiter_jobs,
    }[source_type]
    try:
        jobs = direct_scraper(source_url, timeout=timeout)
    except Exception as exc:
        if _is_blocked_http_error(exc):
            message = f"{source_type.title()} direct scraping returned 403. Configure provider API to enable this source."
            logger.info(message)
            return _result(source_type, source_url, PROVIDER_API, BLOCKED_403, [], message)
        logger.info("%s direct scrape failed and provider is disabled for %s: %s", source_type, source_url, exc)
        return _result(
            source_type,
            source_url,
            PROVIDER_API,
            PROVIDER_REQUIRED,
            [],
            f"{source_type.title()} requires provider/API access for production. Configure {source_type.upper()}_PROVIDER.",
        )

    if jobs:
        return _result(source_type, source_url, PROVIDER_API, OK, jobs, f"{source_type} direct scrape returned jobs.")
    return _result(
        source_type,
        source_url,
        PROVIDER_API,
        PROVIDER_REQUIRED,
        [],
        f"{source_type.title()} needs provider/API access for production. Configure {source_type.upper()}_PROVIDER.",
    )


def route_and_scrape_source_with_status(
    source_url: str,
    timeout: int = 30,
    enable_browser_fetcher: bool = False,
    browser_fetcher_timeout_seconds: int = 30,
    broad_queries: list[dict] | None = None,
    settings: JobScraperSettings | None = None,
) -> SourceScrapeResult:
    del broad_queries
    source_type = detect_source_type(source_url)
    mode = source_mode_for_type(source_type)

    if settings is None:
        from job_scraper.config import get_job_scraper_settings

        settings = get_job_scraper_settings()

    try:
        if source_type == "remoteok":
            jobs = scrape_remoteok_jobs(source_url, timeout=timeout)
        elif source_type == "weworkremotely":
            jobs = scrape_weworkremotely_jobs(source_url, timeout=timeout)
        elif source_type == "builtin":
            jobs = scrape_builtin_jobs(source_url, timeout=timeout)
        elif source_type == "himalayas":
            jobs = scrape_himalayas_jobs(source_url, timeout=timeout, enable_browser_fetcher=enable_browser_fetcher)
        elif source_type == "greenhouse":
            jobs = scrape_greenhouse_jobs(source_url, timeout=timeout)
        elif source_type == "lever":
            jobs = scrape_lever_jobs(source_url, timeout=timeout)
        elif source_type == "dice":
            jobs = scrape_dice_jobs(source_url, timeout=timeout)
        elif source_type == "workday":
            jobs = scrape_workday_jobs(
                source_url,
                timeout=timeout,
                enable_browser_fetcher=enable_browser_fetcher,
                browser_timeout_seconds=browser_fetcher_timeout_seconds,
            )
            if jobs:
                return _result(source_type, source_url, BROWSER_RENDERED, OK, jobs, "Workday returned jobs.")
            if not enable_browser_fetcher:
                message = "Workday requires browser rendering. Enable ENABLE_BROWSER_FETCHER=true."
                logger.info("%s URL=%s", message, source_url)
                return _result(source_type, source_url, BROWSER_RENDERED, BROWSER_REQUIRED, [], message)
            message = "Workday browser rendering returned no jobs or browser dependencies are unavailable."
            return _result(source_type, source_url, BROWSER_RENDERED, BROWSER_REQUIRED, [], message)
        elif source_type in PROVIDER_REQUIRED_SOURCES:
            return _scrape_provider_source(source_type, source_url, settings, timeout)
        elif source_type in {"monster", "talent"}:
            message = f"Portal {source_type} is disabled until configured."
            logger.info("%s URL=%s", message, source_url)
            return _result(source_type, source_url, DISABLED_UNTIL_CONFIGURED, PROVIDER_DISABLED, [], message)
        elif source_type == "google_jobs_search":
            message = "Google Jobs must use GOOGLE_JOBS_PROVIDER; direct Google HTML scraping is disabled."
            logger.info("%s URL=%s", message, source_url)
            return _result(source_type, source_url, PROVIDER_API, PROVIDER_DISABLED, [], message)
        else:
            jobs = scrape_generic_jobs(source_url, timeout=timeout)
    except Exception as exc:
        if source_type in PROVIDER_REQUIRED_SOURCES and _is_blocked_http_error(exc):
            message = f"{source_type.title()} direct scraping returned 403. Configure provider API to enable this source."
            return _result(source_type, source_url, PROVIDER_API, BLOCKED_403, [], message)
        logger.warning("Source failed for %s: %s", source_url, exc)
        return _result(source_type, source_url, mode, FAILED, [], f"Source failed: {exc}")

    status = _jobs_status(jobs)
    message = "Source returned jobs." if jobs else "Source returned zero jobs."
    return _result(source_type, source_url, mode, status, jobs, message)


def route_and_scrape_source(
    source_url: str,
    timeout: int = 30,
    enable_browser_fetcher: bool = False,
    broad_queries: list[dict] | None = None,
) -> list[dict]:
    return route_and_scrape_source_with_status(
        source_url=source_url,
        timeout=timeout,
        enable_browser_fetcher=enable_browser_fetcher,
        broad_queries=broad_queries,
    ).jobs
