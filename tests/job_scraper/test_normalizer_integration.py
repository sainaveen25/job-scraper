from job_scraper.sources.google_jobs import scrape_google_jobs_provider
from scraper.normalizers.job_normalizer import normalize_jobs


def test_invalid_job_skipping():
    raw_jobs = [
        {"title": "Valid Job", "job_url": "https://example.com/jobs/1"},
        {"title": "", "job_url": "https://example.com/jobs/2"},
        {"title": "Missing Url"},
    ]
    normalized, skipped = normalize_jobs(raw_jobs)
    assert len(normalized) == 1
    assert skipped == 2


def test_google_jobs_disabled_mode():
    jobs = scrape_google_jobs_provider(
        queries=[{"query": "Software Engineering jobs United States", "category": "Software Engineering"}],
        provider="disabled",
        serpapi_api_key="",
        scraperapi_api_key="",
        max_queries=5,
        max_results_per_query=10,
    )
    assert jobs == []
