"""
Live-scraping integration tests for all job-scraper sources.

Each test hits the actual source URL and asserts the scraper returns
structurally valid job dicts.  Tests are marked ``live`` so they can be
skipped in offline CI with:

    pytest -m "not live"

Run them directly with:

    pytest tests/job_scraper/test_live_scrape.py -v -m live
"""
from __future__ import annotations

import pytest

from job_scraper.config import JobScraperSettings
from job_scraper.sources.portal_router import (
    detect_source_type,
    route_and_scrape_source_with_status,
)
from job_scraper.normalization import normalize_location, infer_category
from job_scraper.filters import apply_light_filter, dedupe_jobs



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_JOB_KEYS = {"title", "job_url", "source"}


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


def _assert_jobs_valid(jobs: list[dict], source_label: str) -> None:
    assert isinstance(jobs, list), f"{source_label}: expected list, got {type(jobs)}"
    assert len(jobs) > 0, f"{source_label}: scraper returned 0 jobs"
    for i, job in enumerate(jobs):
        missing = REQUIRED_JOB_KEYS - set(job.keys())
        assert not missing, (
            f"{source_label} job[{i}] missing required keys: {missing}\n  job={job}"
        )
        assert job["title"], f"{source_label} job[{i}] has empty title"
        assert job["job_url"], f"{source_label} job[{i}] has empty job_url"


# ---------------------------------------------------------------------------
# Source-detection unit tests (fast, no network)
# ---------------------------------------------------------------------------

class TestSourceDetection:
    """Verify detect_source_type handles all URLs correctly."""

    @pytest.mark.parametrize("url,expected", [
        ("https://remoteok.com/remote-dev-jobs", "remoteok"),
        ("https://weworkremotely.com/categories/remote-programming-jobs", "weworkremotely"),
        ("https://builtin.com/jobs", "builtin"),
        ("https://himalayas.app/jobs", "himalayas"),
        ("https://www.linkedin.com/jobs/search/", "linkedin"),
        ("https://www.indeed.com/jobs?q=python", "indeed"),
        ("https://www.dice.com/jobs?q=python", "dice"),
        ("https://www.glassdoor.com/Job/index.htm", "glassdoor"),
        ("https://www.ziprecruiter.com/jobs-search", "ziprecruiter"),
        ("https://jobs.lever.co/pointclickcare", "lever"),
        ("https://boards.greenhouse.io/company", "greenhouse"),
        ("https://example.myworkdayjobs.com/en-US/careers", "workday"),
        ("https://workday.wd5.myworkdayjobs.com/en-US/Workday", "workday"),
        ("https://www.google.com/search?q=jobs", "google_jobs_search"),
        ("https://somerandomblog.com/jobs", "generic"),
    ])
    def test_detects_source_type(self, url, expected):
        assert detect_source_type(url) == expected


# ---------------------------------------------------------------------------
# Normalization unit tests (fast, no network)
# ---------------------------------------------------------------------------

class TestNormalization:
    """Verify core normalization helpers work correctly."""

    @pytest.mark.parametrize("location,city,state,country,work_mode", [
        ("Dallas, TX", "Dallas", "TX", "United States", None),
        ("Remote - United States", None, None, "United States", "Remote"),
        ("New York, NY, USA", "New York", "NY", "United States", None),
        ("Toronto, ON, Canada", "Toronto", "ON", "Canada", None),
        ("London, United Kingdom", "London", None, "United Kingdom", None),
        ("Hybrid - Chicago, IL", "Chicago", "IL", "United States", "Hybrid"),
        ("San Francisco, CA (On-site)", "San Francisco", "CA", "United States", "On-site"),
        (None, None, None, None, None),
        ("Remote", None, None, None, "Remote"),
    ])
    def test_normalize_location(self, location, city, state, country, work_mode):
        result = normalize_location(location)
        assert result["city"] == city, f"city mismatch for {location!r}"
        assert result["state"] == state, f"state mismatch for {location!r}"
        assert result["country"] == country, f"country mismatch for {location!r}"
        assert result["work_mode"] == work_mode, f"work_mode mismatch for {location!r}"

    @pytest.mark.parametrize("title,description,expected_category", [
        ("Senior Data Engineer", "Build ETL pipelines with Spark", "data_engineering"),
        ("Salesforce Developer", "Apex, Lightning, and integrations", "salesforce"),
        ("Workday Analyst", "HCM and business processes", "workday"),
        ("Frontend Developer", "React and TypeScript applications", "frontend"),
        ("Machine Learning Engineer", "LLM fine-tuning and inference", "ai_ml"),
        ("DevOps Engineer", "Kubernetes and Terraform IaC", "devops"),
        ("QA Automation Engineer", "Selenium and Playwright tests", "qa"),
        ("Business Analyst", "Requirements and reporting", "business_analysis"),
        ("Cloud Architect", "AWS and Azure infrastructure", "cloud"),
        ("Product Manager", "Roadmap and delivery", "product"),
    ])
    def test_infer_category(self, title, description, expected_category):
        result = infer_category(title, description)
        assert result == expected_category, (
            f"Expected {expected_category!r} for {title!r}, got {result!r}"
        )


# ---------------------------------------------------------------------------
# Filter / dedupe unit tests (fast, no network)
# ---------------------------------------------------------------------------

class TestFiltersAndDedupe:
    """Verify apply_light_filter and dedupe_jobs logic."""

    def test_light_filter_stamps_fallback_posted_at(self):
        # Title must be ≥2 words with a job-related word to pass is_job_like
        jobs = [{"title": "Software Developer", "job_url": "https://example.com/1", "description": "Build APIs"}]
        filtered = apply_light_filter(jobs, max_job_age_hours=24)
        assert len(filtered) == 1
        assert filtered[0]["posted_at_source"] == "fallback"
        assert filtered[0]["posted_at"]

    def test_light_filter_drops_old_jobs(self):
        jobs = [
            {"title": "Old Job", "job_url": "https://example.com/2", "posted_at": "2000-01-01T00:00:00+00:00"},
        ]
        filtered = apply_light_filter(jobs, max_job_age_hours=24)
        assert len(filtered) == 0

    def test_dedupe_removes_same_url(self):
        jobs = [
            {"title": "Dev", "job_url": "https://example.com/job/1", "source": "remoteok"},
            {"title": "Dev (dupe)", "job_url": "https://example.com/job/1", "source": "remoteok"},
        ]
        result = dedupe_jobs(jobs)
        assert len(result) == 1

    def test_dedupe_keeps_distinct_urls(self):
        jobs = [
            {"title": "Dev A", "job_url": "https://example.com/job/1", "source": "remoteok"},
            {"title": "Dev B", "job_url": "https://example.com/job/2", "source": "remoteok"},
        ]
        result = dedupe_jobs(jobs)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Portal router — provider-disabled / gated sources (no network needed)
# ---------------------------------------------------------------------------

class TestProviderGatedSources:
    """Validate that gated sources surface correct statuses without network access."""

    def test_linkedin_no_provider_returns_provider_required(self, monkeypatch):
        monkeypatch.setattr(
            "job_scraper.sources.portal_router.scrape_linkedin_jobs",
            lambda *a, **kw: [],
        )
        result = route_and_scrape_source_with_status(
            "https://www.linkedin.com/jobs/search/?keywords=python",
            settings=_settings(linkedin_provider="disabled"),
        )
        assert result.jobs == []
        assert result.status.status in ("provider_required", "blocked_403")

    def test_glassdoor_no_provider_returns_provider_required(self, monkeypatch):
        monkeypatch.setattr(
            "job_scraper.sources.portal_router.scrape_glassdoor_jobs",
            lambda *a, **kw: [],
        )
        result = route_and_scrape_source_with_status(
            "https://www.glassdoor.com/Job/index.htm",
            settings=_settings(glassdoor_provider="disabled"),
        )
        assert result.jobs == []
        assert result.status.status in ("provider_required", "blocked_403")

    def test_ziprecruiter_no_provider_returns_provider_required(self, monkeypatch):
        monkeypatch.setattr(
            "job_scraper.sources.portal_router.scrape_ziprecruiter_jobs",
            lambda *a, **kw: [],
        )
        result = route_and_scrape_source_with_status(
            "https://www.ziprecruiter.com/jobs-search",
            settings=_settings(ziprecruiter_provider="disabled"),
        )
        assert result.jobs == []
        assert result.status.status in ("provider_required", "blocked_403")

    def test_workday_no_browser_returns_browser_required(self, monkeypatch):
        monkeypatch.setattr(
            "job_scraper.sources.portal_router.scrape_workday_jobs",
            lambda *a, **kw: [],
        )
        result = route_and_scrape_source_with_status(
            "https://example.myworkdayjobs.com/en-US/careers",
            enable_browser_fetcher=False,
            settings=_settings(),
        )
        assert result.status.status == "browser_required"
        assert "ENABLE_BROWSER_FETCHER=true" in result.status.message

    def test_monster_disabled_returns_provider_disabled(self):
        result = route_and_scrape_source_with_status(
            "https://www.monster.com/jobs/search/?q=python",
            settings=_settings(),
        )
        assert result.status.status == "provider_disabled"

    def test_talent_disabled_returns_provider_disabled(self):
        result = route_and_scrape_source_with_status(
            "https://www.talent.com/jobs?k=python",
            settings=_settings(),
        )
        assert result.status.status == "provider_disabled"


# ---------------------------------------------------------------------------
# Live network tests — each tagged @pytest.mark.live
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestLiveRemoteOK:
    """Live scrape: remoteok.com JSON API."""

    def test_remoteok_returns_jobs(self):
        from job_scraper.sources.remoteok import scrape_remoteok_jobs
        jobs = scrape_remoteok_jobs("https://remoteok.com/remote-dev-jobs", timeout=30)
        _assert_jobs_valid(jobs, "remoteok")
        assert all(j["source"] == "remoteok" for j in jobs)

    def test_remoteok_jobs_have_expected_fields(self):
        from job_scraper.sources.remoteok import scrape_remoteok_jobs
        jobs = scrape_remoteok_jobs("https://remoteok.com/remote-dev-jobs", timeout=30)
        job = jobs[0]
        for key in ("title", "company", "location", "job_url", "source", "source_url"):
            assert key in job, f"remoteok job missing key: {key}"

    def test_remoteok_via_portal_router(self):
        result = route_and_scrape_source_with_status(
            "https://remoteok.com/remote-dev-jobs",
            settings=_settings(),
        )
        assert result.status.status == "ok"
        assert result.status.mode == "direct_http"
        assert result.status.jobsFound > 0


@pytest.mark.live
class TestLiveWeWorkRemotely:
    """Live scrape: weworkremotely.com HTML."""

    def test_wwr_returns_jobs(self):
        from job_scraper.sources.weworkremotely import scrape_weworkremotely_jobs
        jobs = scrape_weworkremotely_jobs(
            "https://weworkremotely.com/categories/remote-programming-jobs",
            timeout=30,
        )
        _assert_jobs_valid(jobs, "weworkremotely")

    def test_wwr_jobs_have_expected_fields(self):
        from job_scraper.sources.weworkremotely import scrape_weworkremotely_jobs
        jobs = scrape_weworkremotely_jobs(
            "https://weworkremotely.com/categories/remote-programming-jobs",
            timeout=30,
        )
        job = jobs[0]
        assert job["source"] == "weworkremotely"
        assert job["job_url"].startswith("http")

    def test_wwr_via_portal_router(self):
        result = route_and_scrape_source_with_status(
            "https://weworkremotely.com/categories/remote-programming-jobs",
            settings=_settings(),
        )
        assert result.status.mode == "direct_http"
        assert result.status.status in ("ok", "zero_results")


@pytest.mark.live
class TestLiveIndeed:
    """Live scrape: Indeed RSS feed."""

    def test_indeed_rss_returns_jobs(self):
        import requests as req_lib
        from job_scraper.sources.indeed import scrape_indeed_jobs

        try:
            jobs = scrape_indeed_jobs("https://www.indeed.com/jobs?q=python&l=remote", timeout=30)
            # If no 403, assert structural validity
            assert isinstance(jobs, list)
            if jobs:
                _assert_jobs_valid(jobs, "indeed")
                assert all(j["source"] == "indeed" for j in jobs)
        except req_lib.HTTPError as exc:
            # Indeed's RSS endpoint frequently returns 403 — this is the expected
            # production behaviour; the portal router surfaces it as "blocked_403".
            assert getattr(exc.response, "status_code", None) == 403, (
                f"Unexpected HTTPError status from Indeed: {exc}"
            )

    def test_indeed_rss_url_is_correctly_built(self):
        from job_scraper.sources.indeed import _build_rss_url
        rss = _build_rss_url("https://www.indeed.com/jobs?q=python&l=remote&sort=date")
        assert "rss" in rss
        assert "q=python" in rss
        assert "l=remote" in rss

    def test_indeed_blank_query_defaults_to_jobs(self):
        from job_scraper.sources.indeed import _build_rss_url
        rss = _build_rss_url("https://www.indeed.com/jobs")
        assert "q=jobs" in rss

    def test_indeed_via_portal_router(self):
        result = route_and_scrape_source_with_status(
            "https://www.indeed.com/jobs?q=python",
            settings=_settings(indeed_provider="disabled"),
        )
        # Without a provider, Indeed either returns jobs via RSS or blocks
        assert result.status.status in ("ok", "zero_results", "blocked_403", "provider_required")


@pytest.mark.live
class TestLiveDice:
    """Live scrape: Dice.com detail pages."""

    def test_dice_returns_jobs(self):
        from job_scraper.sources.dice import scrape_dice_jobs
        jobs = scrape_dice_jobs(
            "https://www.dice.com/jobs?q=python+developer&location=remote",
            timeout=30,
        )
        # Dice may return zero results if blocked or no listing links found
        assert isinstance(jobs, list)
        if jobs:
            _assert_jobs_valid(jobs, "dice")
            for job in jobs:
                assert job["source"] == "dice"
                assert "dice.com/job-detail" in job["job_url"]

    def test_dice_via_portal_router(self):
        result = route_and_scrape_source_with_status(
            "https://www.dice.com/jobs?q=python+developer&location=remote",
            settings=_settings(),
        )
        assert result.status.mode == "direct_http"
        assert result.status.status in ("ok", "zero_results", "failed")


@pytest.mark.live
class TestLiveLinkedIn:
    """Live scrape: LinkedIn job cards (best-effort, likely blocked)."""

    def test_linkedin_scrape_is_graceful(self):
        from job_scraper.sources.linkedin import scrape_linkedin_jobs
        # LinkedIn almost always blocks; test that the scraper doesn't raise
        try:
            jobs = scrape_linkedin_jobs(
                "https://www.linkedin.com/jobs/search/?keywords=python+developer",
                timeout=20,
            )
            assert isinstance(jobs, list)
            if jobs:
                _assert_jobs_valid(jobs, "linkedin")
        except Exception as exc:
            # Only acceptable exceptions are 403/network errors handled upstream
            assert "403" in str(exc) or "HTTPError" in type(exc).__name__, (
                f"Unexpected exception from linkedin scraper: {exc}"
            )

    def test_linkedin_via_portal_router_with_provider_disabled(self):
        result = route_and_scrape_source_with_status(
            "https://www.linkedin.com/jobs/search/?keywords=python",
            settings=_settings(linkedin_provider="disabled"),
        )
        assert result.status.status in (
            "ok", "zero_results", "blocked_403", "provider_required"
        )


@pytest.mark.live
class TestLiveHimalayas:
    """Live scrape: Himalayas.app HTML."""

    def test_himalayas_returns_jobs_or_zero(self):
        from job_scraper.sources.himalayas import scrape_himalayas_jobs
        jobs = scrape_himalayas_jobs("https://himalayas.app/jobs", timeout=30)
        assert isinstance(jobs, list)
        if jobs:
            _assert_jobs_valid(jobs, "himalayas")

    def test_himalayas_via_portal_router(self):
        result = route_and_scrape_source_with_status(
            "https://himalayas.app/jobs",
            settings=_settings(),
        )
        assert result.status.mode == "direct_http"
        assert result.status.status in ("ok", "zero_results", "failed")


@pytest.mark.live
class TestLiveGreenhouse:
    """Live scrape: Greenhouse.io job boards (public JSON API)."""

    @pytest.mark.parametrize("url", [
        "https://boards.greenhouse.io/anthropic",
        "https://boards.greenhouse.io/stripe",
    ])
    def test_greenhouse_returns_jobs(self, url):
        from job_scraper.sources.greenhouse import scrape_greenhouse_jobs
        jobs = scrape_greenhouse_jobs(url, timeout=30)
        assert isinstance(jobs, list)
        if jobs:
            _assert_jobs_valid(jobs, "greenhouse")
            assert all(j["source"] == "greenhouse" for j in jobs)

    def test_greenhouse_via_portal_router(self):
        result = route_and_scrape_source_with_status(
            "https://boards.greenhouse.io/anthropic",
            settings=_settings(),
        )
        assert result.status.mode == "direct_http"
        assert result.status.status in ("ok", "zero_results", "failed")


@pytest.mark.live
class TestLiveLever:
    """Live scrape: Lever.co public job boards."""

    @pytest.mark.parametrize("url", [
        "https://jobs.lever.co/pointclickcare",
        "https://jobs.lever.co/supermove",
    ])
    def test_lever_returns_jobs(self, url):
        from job_scraper.sources.lever import scrape_lever_jobs
        jobs = scrape_lever_jobs(url, timeout=30)
        assert isinstance(jobs, list)
        if jobs:
            _assert_jobs_valid(jobs, "lever")
            assert all(j["source"] == "lever" for j in jobs)

    def test_lever_via_portal_router(self):
        result = route_and_scrape_source_with_status(
            "https://jobs.lever.co/pointclickcare",
            settings=_settings(),
        )
        assert result.status.mode == "direct_http"
        assert result.status.status in ("ok", "zero_results", "failed")


@pytest.mark.live
class TestLiveBuiltin:
    """Live scrape: Builtin.com job listings."""

    def test_builtin_returns_jobs_or_zero(self):
        from job_scraper.sources.builtin import scrape_builtin_jobs
        jobs = scrape_builtin_jobs("https://builtin.com/jobs", timeout=30)
        assert isinstance(jobs, list)
        if jobs:
            _assert_jobs_valid(jobs, "builtin")

    def test_builtin_via_portal_router(self):
        result = route_and_scrape_source_with_status(
            "https://builtin.com/jobs",
            settings=_settings(),
        )
        assert result.status.mode == "direct_http"
        assert result.status.status in ("ok", "zero_results", "failed")


# ---------------------------------------------------------------------------
# Full pipeline smoke test (mocked ingest)
# ---------------------------------------------------------------------------

@pytest.mark.live
class TestFullPipelineSmoke:
    """
    End-to-end smoke: scrape → normalize → dedupe → ingest (mocked).
    Uses remoteok as the live source since it's the most reliable.
    """

    def test_pipeline_remoteok_to_normalized(self):
        from job_scraper.sources.remoteok import scrape_remoteok_jobs
        from scraper.normalizers.job_normalizer import normalize_jobs

        raw = scrape_remoteok_jobs("https://remoteok.com/remote-dev-jobs", timeout=30)
        assert len(raw) > 0, "RemoteOK returned no jobs — check network"

        # Attach required source metadata
        for job in raw:
            job.setdefault("source_mode", "direct_http")
            job.setdefault("source_status", "ok")

        filtered = apply_light_filter(raw, max_job_age_hours=720)  # wide window for live data
        deduped = dedupe_jobs(filtered)
        normalized, skipped = normalize_jobs(deduped, default_source="remoteok")

        assert len(normalized) > 0, "No jobs survived normalization"
        assert skipped < len(raw), "All jobs were skipped — normalization is broken"

        for job in normalized:
            # Required schema keys must be present
            for key in ("title", "job_url", "source", "posted_at", "category",
                        "search_terms", "autocomplete_terms", "raw_payload"):
                assert key in job, f"Normalized job missing key: {key}"

    def test_pipeline_produces_valid_legacy_aliases(self):
        from job_scraper.sources.remoteok import scrape_remoteok_jobs
        from scraper.normalizers.job_normalizer import normalize_jobs

        raw = scrape_remoteok_jobs("https://remoteok.com/remote-dev-jobs", timeout=30)
        for job in raw:
            job.setdefault("source_mode", "direct_http")
            job.setdefault("source_status", "ok")

        normalized, _ = normalize_jobs(raw[:5], default_source="remoteok")
        for job in normalized:
            assert job.get("jobUrl") == job.get("job_url"), "jobUrl alias mismatch"
            assert job.get("postedAt") == job.get("posted_at"), "postedAt alias mismatch"
