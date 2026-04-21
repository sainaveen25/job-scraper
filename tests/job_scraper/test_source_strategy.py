from __future__ import annotations

import requests

from job_scraper.config import JobScraperSettings
from job_scraper.source_status import BLOCKED_403, BROWSER_REQUIRED, PROVIDER_DISABLED, PROVIDER_REQUIRED
from job_scraper.sources.google_jobs import scrape_google_jobs_provider_with_status
from job_scraper.sources.portal_router import route_and_scrape_source_with_status, source_mode_for_type


def _settings(**overrides) -> JobScraperSettings:
    values = {
        "source_urls": (),
        "global_job_categories": (),
        "global_job_locations": (),
        "serpapi_api_key": "",
        "scraperapi_api_key": "",
    }
    values.update(overrides)
    return JobScraperSettings(**values)


def _http_403() -> requests.HTTPError:
    response = requests.Response()
    response.status_code = 403
    error = requests.HTTPError("403 Forbidden")
    error.response = response
    return error


def test_source_modes_classify_high_value_sources():
    assert source_mode_for_type("greenhouse") == "direct_http"
    assert source_mode_for_type("workday") == "browser_rendered"
    assert source_mode_for_type("indeed") == "provider_api"


def test_indeed_403_is_blocked_not_failed(monkeypatch):
    def blocked(*args, **kwargs):
        raise _http_403()

    monkeypatch.setattr("job_scraper.sources.portal_router.scrape_indeed_jobs", blocked)

    result = route_and_scrape_source_with_status(
        "https://www.indeed.com/jobs?q=python",
        settings=_settings(indeed_provider="disabled"),
    )

    assert result.jobs == []
    assert result.status.mode == "provider_api"
    assert result.status.status == BLOCKED_403
    assert "Configure provider API" in result.status.message


def test_linkedin_disabled_provider_reports_provider_required(monkeypatch):
    monkeypatch.setattr("job_scraper.sources.portal_router.scrape_linkedin_jobs", lambda *args, **kwargs: [])

    result = route_and_scrape_source_with_status(
        "https://www.linkedin.com/jobs/search/?keywords=python",
        settings=_settings(linkedin_provider="disabled"),
    )

    assert result.jobs == []
    assert result.status.status == PROVIDER_REQUIRED
    assert result.status.mode == "provider_api"


def test_workday_without_browser_reports_browser_required(monkeypatch):
    monkeypatch.setattr("job_scraper.sources.portal_router.scrape_workday_jobs", lambda *args, **kwargs: [])

    result = route_and_scrape_source_with_status(
        "https://example.myworkdayjobs.com/careers",
        enable_browser_fetcher=False,
        settings=_settings(),
    )

    assert result.jobs == []
    assert result.status.status == BROWSER_REQUIRED
    assert result.status.mode == "browser_rendered"
    assert "ENABLE_BROWSER_FETCHER=true" in result.status.message


def test_google_jobs_disabled_is_provider_disabled():
    result = scrape_google_jobs_provider_with_status(
        queries=[],
        provider="disabled",
        serpapi_api_key="",
        scraperapi_api_key="",
        max_queries=5,
        max_results_per_query=20,
    )

    assert result.jobs == []
    assert result.status.status == PROVIDER_DISABLED
    assert result.status.mode == "provider_api"
