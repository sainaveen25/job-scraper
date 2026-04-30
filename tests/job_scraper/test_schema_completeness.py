"""Tests for full normalized job schema completeness and Lovable alias fields."""
from __future__ import annotations

from scraper.normalizers.job_normalizer import normalize_job


REQUIRED_SNAKE_CASE_FIELDS = [
    "title",
    "normalized_title",
    "company",
    "location",
    "city",
    "state",
    "country",
    "source",
    "source_mode",
    "source_status",
    "source_external_id",
    "source_url",
    "job_url",
    "description",
    "required_skills",
    "preferred_skills",
    "ats_keywords",
    "domain_terms",
    "responsibilities",
    "work_mode",
    "employment_type",
    "salary_text",
    "posted_at",
    "posted_at_raw",
    "posted_at_source",
    "scraped_at",
    "category",
    "search_terms",
    "autocomplete_terms",
    "raw_payload",
]

LOVABLE_ALIAS_FIELDS = [
    "jobUrl",
    "sourceUrl",
    "sourceExternalId",
    "workMode",
    "employmentType",
    "salaryText",
    "postedAt",
    "rawPayload",
    "requiredSkills",
    "preferredSkills",
    "atsKeywords",
    "domainTerms",
]


def _minimal_job(**overrides):
    base = {
        "title": "Software Engineer",
        "job_url": "https://example.com/jobs/1",
        "location": "Dallas, TX",
        "source": "lever",
        "source_mode": "direct_http",
        "source_status": "ok",
        "posted_at": "2026-04-28T10:00:00Z",
        "description": "Build backend APIs with Python and AWS",
    }
    base.update(overrides)
    return base


def test_all_required_snake_case_fields_present():
    result = normalize_job(_minimal_job())
    assert result is not None
    for field in REQUIRED_SNAKE_CASE_FIELDS:
        assert field in result, f"Missing field: {field!r}"


def test_lovable_alias_fields_present():
    result = normalize_job(_minimal_job())
    assert result is not None
    for field in LOVABLE_ALIAS_FIELDS:
        assert field in result, f"Missing Lovable alias: {field!r}"


def test_alias_values_match_snake_case():
    result = normalize_job(_minimal_job())
    assert result is not None
    assert result["jobUrl"] == result["job_url"]
    assert result["postedAt"] == result["posted_at"]
    assert result["workMode"] == result["work_mode"]
    assert result["employmentType"] == result["employment_type"]
    assert result["salaryText"] == result["salary_text"]
    assert result["requiredSkills"] == result["required_skills"]
    assert result["preferredSkills"] == result["preferred_skills"]
    assert result["atsKeywords"] == result["ats_keywords"]


def test_none_returns_when_no_title():
    result = normalize_job({"job_url": "https://example.com/1", "description": "No title here"})
    assert result is None


def test_none_returns_when_no_url():
    result = normalize_job({"title": "Engineer", "description": "No URL here"})
    assert result is None


def test_normalize_job_us_location():
    result = normalize_job(_minimal_job(location="Austin, TX"))
    assert result is not None
    assert result["city"] == "Austin"
    assert result["state"] == "TX"
    assert result["country"] == "United States"


def test_normalize_job_canada_location():
    result = normalize_job(_minimal_job(location="Toronto, ON, Canada"))
    assert result is not None
    assert result["city"] == "Toronto"
    assert result["state"] == "ON"
    assert result["country"] == "Canada"


def test_normalize_job_remote_location():
    result = normalize_job(_minimal_job(location="Remote - United States"))
    assert result is not None
    assert result["work_mode"] == "Remote"
    assert result["country"] == "United States"
    assert result["city"] is None


def test_category_is_inferred():
    result = normalize_job(_minimal_job(
        title="Data Engineer",
        description="Spark ETL pipeline development with Databricks",
    ))
    assert result is not None
    assert result["category"] == "data_engineering"


def test_search_terms_and_autocomplete_populated():
    result = normalize_job(_minimal_job(
        title="Senior Java Developer",
        required_skills=["Java", "Spring Boot"],
    ))
    assert result is not None
    assert isinstance(result["search_terms"], list)
    assert len(result["search_terms"]) > 0
    assert isinstance(result["autocomplete_terms"], list)
    assert len(result["autocomplete_terms"]) > 0
    assert "java" in result["search_terms"]
    assert "java developer" in result["autocomplete_terms"]


def test_posted_at_source_is_stamped():
    result = normalize_job(_minimal_job(posted_at="2 hours ago"))
    assert result is not None
    assert result["posted_at_source"] in {"source", "fallback"}
    assert result["posted_at"] is not None
    assert result["scraped_at"] is not None


def test_raw_payload_preserved():
    job = _minimal_job()
    job["some_custom_field"] = "custom_value"
    result = normalize_job(job)
    assert result is not None
    assert "some_custom_field" in result["raw_payload"]


def test_skills_are_lists():
    result = normalize_job(_minimal_job(
        required_skills=["Python", "AWS"],
        ats_keywords=["Docker"],
    ))
    assert result is not None
    assert isinstance(result["required_skills"], list)
    assert isinstance(result["preferred_skills"], list)
    assert isinstance(result["ats_keywords"], list)
    assert isinstance(result["domain_terms"], list)
    assert isinstance(result["responsibilities"], list)


def test_source_defaults():
    result = normalize_job({
        "title": "Engineer",
        "job_url": "https://example.com/jobs/2",
    })
    assert result is not None
    assert result["source"] == "scrapling"
    assert result["source_mode"] == "direct_http"
    assert result["source_status"] == "ok"
