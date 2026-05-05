from __future__ import annotations

import requests

from job_scraper.config import JobScraperSettings
from job_scraper.source_status import BLOCKED_403, BROWSER_REQUIRED, PROVIDER_DISABLED, PROVIDER_REQUIRED
from job_scraper.query_builder import build_global_queries
from job_scraper.sources.google_jobs import scrape_google_jobs_provider, scrape_google_jobs_provider_with_status
from job_scraper.sources.portal_router import route_and_scrape_source_with_status, source_mode_for_type
from job_scraper.sources.workday import is_workday_board_url, scrape_workday_jobs
from job_scraper.utils import maybe_fetch_with_browser


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


def test_valid_workday_board_urls_are_detected():
    assert is_workday_board_url("https://workday.wd5.myworkdayjobs.com/Workday")
    assert is_workday_board_url("https://sec.wd3.myworkdayjobs.com/Samsung_Careers")
    assert is_workday_board_url("https://pfizer.wd1.myworkdayjobs.com/PfizerCareers")
    assert is_workday_board_url("https://asmglobal.wd1.myworkdayjobs.com/careers")
    assert not is_workday_board_url("https://pfizer.wd1.myworkdayjobs.com/PfizerCareers/job/New-York/Engineer_R1")


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
    assert result.status.message == "Indeed direct scraping blocked; provider/API path required for reliable production use."


def test_ziprecruiter_403_is_blocked_not_failed(monkeypatch):
    def blocked(*args, **kwargs):
        raise _http_403()

    monkeypatch.setattr("job_scraper.sources.portal_router.scrape_ziprecruiter_jobs", blocked)

    result = route_and_scrape_source_with_status(
        "https://www.ziprecruiter.com/jobs-search?search=electrical+engineer",
        settings=_settings(ziprecruiter_provider="disabled"),
    )

    assert result.jobs == []
    assert result.status.mode == "provider_api"
    assert result.status.status == BLOCKED_403
    assert "Provider/API access is required for reliable production use" in result.status.message


def test_linkedin_disabled_provider_reports_provider_required(monkeypatch):
    monkeypatch.setattr("job_scraper.sources.portal_router.scrape_linkedin_jobs", lambda *args, **kwargs: [])

    result = route_and_scrape_source_with_status(
        "https://www.linkedin.com/jobs/search/?keywords=python",
        settings=_settings(linkedin_provider="disabled"),
    )

    assert result.jobs == []
    assert result.status.status == PROVIDER_REQUIRED
    assert result.status.mode == "provider_api"


def test_linkedin_best_effort_ok_when_direct_results_exist(monkeypatch):
    monkeypatch.setattr(
        "job_scraper.sources.portal_router.scrape_linkedin_jobs",
        lambda *args, **kwargs: [{"title": "Electrical Engineer", "job_url": "https://linkedin.com/jobs/view/1"}],
    )

    result = route_and_scrape_source_with_status(
        "https://www.linkedin.com/jobs/search/?keywords=electrical+engineer",
        settings=_settings(linkedin_provider="disabled"),
    )

    assert result.status.status == "ok"
    assert result.status.mode == "provider_api"
    assert result.jobs[0]["title"] == "Electrical Engineer"


def test_remoteok_403_is_blocked_not_failed(monkeypatch):
    def blocked(*args, **kwargs):
        raise _http_403()

    monkeypatch.setattr("job_scraper.sources.portal_router.scrape_remoteok_jobs", blocked)

    result = route_and_scrape_source_with_status(
        "https://remoteok.com/remote-dev-jobs",
        settings=_settings(),
    )

    assert result.jobs == []
    assert result.status.mode == "direct_http"
    assert result.status.status == BLOCKED_403
    assert "RemoteOK JSON endpoint returned 403" in result.status.message


def test_himalayas_browser_disabled_rejection_is_zero_results(monkeypatch):
    monkeypatch.setattr("job_scraper.sources.himalayas.fetch_html", lambda *args, **kwargs: (_ for _ in ()).throw(_http_403()))
    monkeypatch.setattr("job_scraper.sources.himalayas.maybe_fetch_with_browser", lambda *args, **kwargs: None)

    result = route_and_scrape_source_with_status(
        "https://himalayas.app/jobs/developer",
        enable_browser_fetcher=False,
        settings=_settings(),
    )

    assert result.jobs == []
    assert result.status.mode == "direct_http"
    assert result.status.status == "zero_results"


def test_browser_fetcher_unavailable_degrades_without_exception(monkeypatch, caplog):
    monkeypatch.setattr("job_scraper.utils.browser_fetcher_available", lambda: (False, "missing Python dependency: playwright"))

    with caplog.at_level("INFO"):
        html = maybe_fetch_with_browser("https://example.com/jobs", enabled=True)

    assert html is None
    assert "Browser fetcher disabled for this run: missing Python dependency: playwright" in caplog.text


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


def test_workday_detail_zero_is_not_browser_required(monkeypatch):
    monkeypatch.setattr("job_scraper.sources.portal_router.scrape_workday_jobs", lambda *args, **kwargs: [])

    result = route_and_scrape_source_with_status(
        "https://pfizer.wd1.myworkdayjobs.com/PfizerCareers/job/New-York-NY/Electrical-Engineer_R1",
        enable_browser_fetcher=False,
        settings=_settings(),
    )

    assert result.jobs == []
    assert result.status.status == "zero_results"
    assert result.status.mode == "browser_rendered"


def test_workday_browser_enabled_extracts_listing_fallback(monkeypatch):
    html = """
    <html><body>
      <section data-automation-id="jobCard">
        <a data-automation-id="jobTitle" href="/Workday/job/Austin-TX/Controls-Engineer_R1">Controls Engineer</a>
        <span data-automation-id="locations">Austin, TX, United States</span>
        <span data-automation-id="postedOn">Posted 2 days ago</span>
        <span>Full-time $110,000 - $140,000 / year PLC SCADA controls automation</span>
      </section>
    </body></html>
    """
    monkeypatch.setattr("job_scraper.sources.workday.fetch_html", lambda *args, **kwargs: "<html></html>")
    monkeypatch.setattr("job_scraper.sources.workday.requests.post", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("skip CXS")))
    monkeypatch.setattr("job_scraper.sources.workday.maybe_fetch_with_browser", lambda *args, **kwargs: html)

    result = route_and_scrape_source_with_status(
        "https://workday.wd5.myworkdayjobs.com/Workday",
        enable_browser_fetcher=True,
        settings=_settings(),
    )

    assert result.status.status == "ok"
    assert result.status.mode == "browser_rendered"
    assert result.jobs[0]["title"] == "Controls Engineer"
    assert result.jobs[0]["city"] == "Austin"
    assert result.jobs[0]["state"] == "TX"
    assert result.jobs[0]["employment_type"] == "Full-time"
    assert result.jobs[0]["salary_text"]
    assert result.jobs[0]["category"] == "controls_automation"
    assert "controls engineer" in result.jobs[0]["autocomplete_terms"]


def test_workday_cxs_api_extracts_jobs_before_browser(monkeypatch):
    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    html = """
    <script>
      window.workday = {
        tenant: "workday",
        siteId: "Workday"
      };
    </script>
    """

    def fake_post(url, **kwargs):
        assert url == "https://workday.wd5.myworkdayjobs.com/wday/cxs/workday/Workday/jobs"
        assert kwargs["json"]["limit"] == 20
        return FakeResponse({
            "jobPostings": [
                {
                    "title": "Senior Machine Learning Engineer",
                    "externalPath": "/job/Canada-ON-Toronto/Senior-Machine-Learning-Engineer_JR-0106107",
                    "locationsText": "Toronto, ON, Canada",
                    "postedOn": "Posted Today",
                    "remoteType": "Flex",
                    "bulletFields": ["JR-0106107"],
                }
            ]
        })

    def fake_get(url, **kwargs):
        assert url.endswith("/job/Canada-ON-Toronto/Senior-Machine-Learning-Engineer_JR-0106107")
        return FakeResponse({
            "jobPostingInfo": {
                "title": "Senior Machine Learning Engineer",
                "jobDescription": "<p>Build machine learning services with Python.</p>",
                "location": "Toronto, ON, Canada",
                "startDate": "2026-05-05",
                "timeType": "Full Time",
                "jobReqId": "JR-0106107",
                "remoteType": "Flex",
                "externalUrl": "https://workday.wd5.myworkdayjobs.com/Workday/job/Canada-ON-Toronto/Senior-Machine-Learning-Engineer_JR-0106107",
            }
        })

    monkeypatch.setattr("job_scraper.sources.workday.fetch_html", lambda *args, **kwargs: html)
    monkeypatch.setattr("job_scraper.sources.workday.requests.post", fake_post)
    monkeypatch.setattr("job_scraper.sources.workday.requests.get", fake_get)
    monkeypatch.setattr("job_scraper.sources.workday.maybe_fetch_with_browser", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("browser should not be needed")))

    jobs = scrape_workday_jobs("https://workday.wd5.myworkdayjobs.com/en-US/Workday", enable_browser_fetcher=True)

    assert len(jobs) == 1
    assert jobs[0]["title"] == "Senior Machine Learning Engineer"
    assert jobs[0]["source_external_id"] == "JR-0106107"
    assert jobs[0]["city"] == "Toronto"
    assert jobs[0]["country"] == "Canada"


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


def test_google_jobs_provider_query_generation():
    queries = build_global_queries(["Electrical Engineer", "Relay Designer", "Java Developer"], ["United States"])
    assert [item["query"] for item in queries] == [
        "Electrical Engineer jobs United States",
        "Relay Designer jobs United States",
        "Java Developer jobs United States",
    ]


def test_google_jobs_provider_results_are_normalized(monkeypatch):
    raw_payload = {
        "jobs_results": [
            {
                "title": "Electrical Engineer",
                "company_name": "GridCo",
                "location": "Austin, TX, United States",
                "job_id": "g-1",
                "apply_options": [{"link": "https://example.com/apply"}],
                "description": "Power systems, relay design, substation, and controls.",
                "detected_extensions": {
                    "posted_at": "2 days ago",
                    "schedule_type": "Full-time",
                    "salary": "$110,000 - $140,000",
                },
            }
        ]
    }
    monkeypatch.setattr("job_scraper.sources.google_jobs.fetch_json", lambda *args, **kwargs: raw_payload)

    jobs = scrape_google_jobs_provider(
        queries=[{"query": "Electrical Engineer jobs United States", "category": "Electrical Engineer"}],
        provider="serpapi",
        serpapi_api_key="test-key",
        scraperapi_api_key="",
        max_queries=1,
        max_results_per_query=5,
        timeout=5,
    )

    assert len(jobs) == 1
    job = jobs[0]
    assert job["source"] == "google_jobs_provider"
    assert job["title"] == "Electrical Engineer"
    assert job["city"] == "Austin"
    assert job["state"] == "TX"
    assert job["country"] == "United States"
    assert job["job_url"] == "https://example.com/apply"
    assert job["employment_type"] == "Full-time"
    assert job["salary_text"] == "$110,000 - $140,000"
    assert job["category"] == "power_systems"
    assert "electrical engineer" in job["autocomplete_terms"]
