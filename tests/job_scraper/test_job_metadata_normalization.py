from __future__ import annotations

from datetime import datetime, timedelta, timezone

from job_scraper.filters import apply_light_filter
from job_scraper.normalization import choose_posted_at, generate_search_terms, infer_category, normalize_location
from scraper.normalizers.job_normalizer import normalize_job


def test_choose_posted_at_parses_relative_source_time():
    now = datetime(2026, 4, 28, 18, 0, tzinfo=timezone.utc)

    freshness = choose_posted_at("5 hours ago", scraped_at=now)

    assert freshness["posted_at"] == (now - timedelta(hours=5)).isoformat()
    assert freshness["posted_at_raw"] == "5 hours ago"
    assert freshness["posted_at_source"] == "source"
    assert freshness["scraped_at"] == now.isoformat()


def test_choose_posted_at_falls_back_to_scraped_at_when_missing():
    now = datetime(2026, 4, 28, 18, 0, tzinfo=timezone.utc)

    freshness = choose_posted_at(None, scraped_at=now)

    assert freshness["posted_at"] == now.isoformat()
    assert freshness["posted_at_source"] == "fallback"
    assert freshness["scraped_at"] == now.isoformat()


def test_apply_light_filter_keeps_missing_posted_at_via_scraped_fallback():
    jobs = [
        {
            "title": "Backend Engineer",
            "job_url": "https://example.com/jobs/1",
            "description": "Build APIs with Python and AWS",
            "raw_payload": {},
        }
    ]

    filtered = apply_light_filter(jobs, max_job_age_hours=24)

    assert len(filtered) == 1
    assert filtered[0]["posted_at_source"] == "fallback"
    assert filtered[0]["posted_at"]


def test_normalize_location_extracts_city_state_country_and_remote():
    normalized = normalize_location("Remote - United States")

    assert normalized["city"] is None
    assert normalized["state"] is None
    assert normalized["country"] == "United States"
    assert normalized["work_mode"] == "Remote"


def test_normalize_job_extracts_us_location_fields():
    normalized = normalize_job(
        {
            "title": "Java Backend Developer",
            "job_url": "https://example.com/jobs/1",
            "location": "Dallas, TX",
            "posted_at": "2026-04-28T10:00:00Z",
            "required_skills": ["Java", "Spring Boot"],
            "description": "Backend APIs with Java and Spring Boot",
        }
    )

    assert normalized is not None
    assert normalized["city"] == "Dallas"
    assert normalized["state"] == "TX"
    assert normalized["country"] == "United States"


def test_normalize_job_generates_title_and_search_metadata():
    normalized = normalize_job(
        {
            "title": "Senior Java Full Stack Engineer",
            "job_url": "https://example.com/jobs/2",
            "location": "Remote - United States",
            "posted_at": "1 hour ago",
            "required_skills": ["Java", "Spring Boot"],
            "description": "Build backend APIs and full stack features in Java",
        }
    )

    assert normalized is not None
    assert normalized["normalized_title"] == "senior java full stack engineer"
    assert "java developer" in normalized["autocomplete_terms"]
    assert "full stack java developer" in normalized["autocomplete_terms"]
    assert "backend java developer" in normalized["search_terms"]


def test_generate_search_terms_keeps_java_distinct_from_javascript():
    search_terms, autocomplete_terms = generate_search_terms(
        title="Senior Java Developer",
        normalized_title="senior java developer",
        category="backend",
        required_skills=["Java"],
        ats_keywords=["Java"],
    )

    assert "java" in search_terms
    assert "javascript" not in search_terms
    assert "java developer" in autocomplete_terms


def test_generate_search_terms_avoids_data_partial_noise():
    search_terms, autocomplete_terms = generate_search_terms(
        title="Data Analyst",
        normalized_title="data analyst",
        category="data_analytics",
        required_skills=["SQL"],
        ats_keywords=["Tableau"],
    )

    assert "data analyst" in autocomplete_terms
    assert "data" in autocomplete_terms
    assert "dat" not in search_terms


def test_category_inference_supports_requested_taxonomy():
    assert infer_category("Senior Data Engineer", "Build Spark ETL pipelines") == "data_engineering"
    assert infer_category("Salesforce Developer", "Apex and integrations") == "salesforce"
    assert infer_category("Workday Analyst", "HCM business processes") == "workday"


def test_normalized_schema_completeness_and_legacy_aliases():
    normalized = normalize_job(
        {
            "title": "Business Analyst",
            "job_url": "https://example.com/jobs/3",
            "location": "Toronto, ON, Canada",
            "source": "lever",
            "source_mode": "direct_http",
            "source_status": "ok",
            "posted_at": "2026-04-28T12:00:00Z",
            "description": "SQL reporting and business analysis",
        }
    )

    assert normalized is not None
    for key in (
        "title",
        "normalized_title",
        "location",
        "city",
        "state",
        "country",
        "source",
        "source_mode",
        "source_status",
        "job_url",
        "posted_at",
        "posted_at_raw",
        "posted_at_source",
        "scraped_at",
        "category",
        "search_terms",
        "autocomplete_terms",
        "raw_payload",
    ):
        assert key in normalized
    assert normalized["jobUrl"] == normalized["job_url"]
    assert normalized["postedAt"] == normalized["posted_at"]
