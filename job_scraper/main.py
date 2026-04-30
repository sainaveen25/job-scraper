from __future__ import annotations

from dataclasses import dataclass
import logging

from job_scraper.config import get_job_scraper_settings
from job_scraper.filters import apply_light_filter, dedupe_jobs
from job_scraper.query_builder import build_global_queries
from job_scraper.source_status import SourceStatus
from job_scraper.sources.google_jobs import scrape_google_jobs_provider_with_status
from job_scraper.sources.portal_router import route_and_scrape_source_with_status


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScrapeAllSourcesResult:
    items: list[dict]
    source_url_count: int
    failed_sources_count: int
    source_statuses: list[SourceStatus]


def _attach_source_metadata(jobs: list[dict], status: SourceStatus) -> list[dict]:
    enriched: list[dict] = []
    for job in jobs:
        copy = dict(job)
        copy.setdefault("source", status.source)
        copy["source_mode"] = status.mode
        copy["source_status"] = status.status
        enriched.append(copy)
    return enriched


def scrape_all_sources(search_queries: list[dict] | None = None) -> ScrapeAllSourcesResult:
    settings = get_job_scraper_settings()
    source_statuses: list[SourceStatus] = []

    if not settings.source_urls and settings.google_jobs_provider == "disabled":
        logger.info("No JOB_SOURCE_URLS configured and GOOGLE_JOBS_PROVIDER is disabled.")
        google_status = scrape_google_jobs_provider_with_status(
            queries=[],
            provider=settings.google_jobs_provider,
            serpapi_api_key=settings.serpapi_api_key,
            scraperapi_api_key=settings.scraperapi_api_key,
            max_queries=settings.google_jobs_max_queries_per_run,
            max_results_per_query=settings.google_jobs_max_results_per_query,
            timeout=settings.request_timeout_seconds,
        ).status
        return ScrapeAllSourcesResult(items=[], source_url_count=0, failed_sources_count=0, source_statuses=[google_status])

    global_queries = build_global_queries(
        categories=list(settings.global_job_categories),
        locations=list(settings.global_job_locations),
    )

    all_jobs: list[dict] = []

    for source_url in settings.source_urls:
        result = route_and_scrape_source_with_status(
            source_url=source_url,
            timeout=settings.request_timeout_seconds,
            enable_browser_fetcher=settings.enable_browser_fetcher,
            browser_fetcher_timeout_seconds=settings.browser_fetcher_timeout_seconds,
            broad_queries=global_queries,
            settings=settings,
        )
        source_statuses.append(result.status)
        logger.info(
            "Source status: source=%s mode=%s status=%s jobs=%s url=%s message=%s",
            result.status.source,
            result.status.mode,
            result.status.status,
            result.status.jobsFound,
            source_url,
            result.status.message,
        )
        all_jobs.extend(
            apply_light_filter(
                _attach_source_metadata(result.jobs, result.status),
                max_job_age_hours=settings.max_job_age_hours,
            )
        )

    google_result = scrape_google_jobs_provider_with_status(
        queries=global_queries,
        provider=settings.google_jobs_provider,
        serpapi_api_key=settings.serpapi_api_key,
        scraperapi_api_key=settings.scraperapi_api_key,
        max_queries=settings.google_jobs_max_queries_per_run,
        max_results_per_query=settings.google_jobs_max_results_per_query,
        timeout=settings.request_timeout_seconds,
    )
    source_statuses.append(google_result.status)
    all_jobs.extend(
        apply_light_filter(
            _attach_source_metadata(google_result.jobs, google_result.status),
            max_job_age_hours=settings.max_job_age_hours,
        )
    )

    failed_sources_count = sum(1 for item in source_statuses if item.status == "failed")

    return ScrapeAllSourcesResult(
        items=dedupe_jobs(all_jobs),
        source_url_count=len(settings.source_urls),
        failed_sources_count=failed_sources_count,
        source_statuses=source_statuses,
    )
