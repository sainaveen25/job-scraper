"""Tests for title normalization, search_terms, and autocomplete_terms generation."""
from __future__ import annotations

import pytest

from job_scraper.normalization import generate_search_terms, normalize_title


# ---------------------------------------------------------------------------
# normalize_title
# ---------------------------------------------------------------------------

def test_normalize_title_senior_java_full_stack():
    result = normalize_title("Senior Java Full Stack Engineer")
    assert result == "senior java full stack engineer"


def test_normalize_title_expands_sr_abbreviation():
    result = normalize_title("Sr. Java Developer")
    assert result == "senior java developer"


def test_normalize_title_expands_jr_abbreviation():
    result = normalize_title("Jr Java Developer")
    assert result == "junior java developer"


def test_normalize_title_none_returns_none():
    assert normalize_title(None) is None


def test_normalize_title_empty_returns_none():
    assert normalize_title("") is None


# ---------------------------------------------------------------------------
# generate_search_terms — Java
# ---------------------------------------------------------------------------

def test_java_developer_terms_generated():
    terms, autocomplete = generate_search_terms(
        title="Senior Java Developer",
        normalized_title="senior java developer",
        category="backend",
        required_skills=["Java", "Spring Boot"],
        ats_keywords=["Java"],
    )
    assert "java" in terms
    assert "java developer" in terms
    assert "java engineer" in terms
    assert "backend java developer" in terms


def test_full_stack_java_generates_full_stack_terms():
    terms, autocomplete = generate_search_terms(
        title="Senior Java Full Stack Engineer",
        normalized_title="senior java full stack engineer",
        category="full_stack",
        required_skills=["Java"],
        ats_keywords=[],
    )
    assert "full stack java" in terms
    assert "full stack java developer" in terms
    assert "java developer" in terms


# ---------------------------------------------------------------------------
# generate_search_terms — Java ≠ JavaScript
# ---------------------------------------------------------------------------

def test_java_distinct_from_javascript():
    terms, autocomplete = generate_search_terms(
        title="Senior JavaScript Developer",
        normalized_title="senior javascript developer",
        category="frontend",
        required_skills=["JavaScript"],
        ats_keywords=[],
    )
    # JavaScript title: java terms should NOT be generated
    assert "java developer" not in terms
    assert "backend java developer" not in terms


def test_java_skills_dont_appear_for_javascript_title():
    terms, _ = generate_search_terms(
        title="JavaScript Developer",
        normalized_title="javascript developer",
        category="frontend",
        required_skills=["JavaScript", "TypeScript"],
        ats_keywords=[],
    )
    # javascript and typescript should be excluded from search_terms per existing logic
    assert "javascript" not in terms


# ---------------------------------------------------------------------------
# generate_search_terms — Data Analyst
# ---------------------------------------------------------------------------

def test_data_analyst_generates_data_terms():
    terms, autocomplete = generate_search_terms(
        title="Data Analyst",
        normalized_title="data analyst",
        category="data_analytics",
        required_skills=["SQL"],
        ats_keywords=["Tableau"],
    )
    assert "data" in terms
    assert "data analyst" in terms
    assert "analyst" in terms
    assert "sql analyst" in terms
    # "dat" (a partial) should NOT appear — real prefix search is done by the frontend
    assert "dat" not in terms


def test_data_analyst_in_autocomplete():
    _, autocomplete = generate_search_terms(
        title="Data Analyst",
        normalized_title="data analyst",
        category="data_analytics",
        required_skills=["SQL"],
        ats_keywords=[],
    )
    assert "data analyst" in autocomplete
    assert "data" in autocomplete


# ---------------------------------------------------------------------------
# generate_search_terms — Data Engineer
# ---------------------------------------------------------------------------

def test_data_engineer_generates_etl_terms():
    terms, autocomplete = generate_search_terms(
        title="Data Engineer",
        normalized_title="data engineer",
        category="data_engineering",
        required_skills=["Spark", "ETL"],
        ats_keywords=[],
    )
    assert "data engineer" in terms
    assert "etl" in terms
    assert "etl developer" in terms
    assert "pipeline engineer" in terms
    assert "data" in terms


# ---------------------------------------------------------------------------
# generate_search_terms — Business Analyst
# ---------------------------------------------------------------------------

def test_business_analyst_terms():
    terms, autocomplete = generate_search_terms(
        title="Business Analyst",
        normalized_title="business analyst",
        category="business_analysis",
        required_skills=[],
        ats_keywords=[],
    )
    assert "business analyst" in terms
    assert "analyst" in terms
    assert "business systems analyst" in terms


# ---------------------------------------------------------------------------
# generate_search_terms — Salesforce
# ---------------------------------------------------------------------------

def test_salesforce_developer_terms():
    terms, autocomplete = generate_search_terms(
        title="Salesforce Developer",
        normalized_title="salesforce developer",
        category="salesforce",
        required_skills=["Salesforce"],
        ats_keywords=[],
    )
    assert "salesforce" in terms
    assert "salesforce developer" in terms
    assert "apex" in terms
    assert "lightning" in terms
    assert "crm" in terms


# ---------------------------------------------------------------------------
# generate_search_terms — Workday
# ---------------------------------------------------------------------------

def test_workday_analyst_terms():
    terms, autocomplete = generate_search_terms(
        title="Workday Analyst",
        normalized_title="workday analyst",
        category="workday",
        required_skills=["Workday"],
        ats_keywords=[],
    )
    assert "workday" in terms
    assert "workday analyst" in terms
    assert "hcm" in terms
    assert "workday hcm" in terms
    assert "workday consultant" in terms


# ---------------------------------------------------------------------------
# Deduplication in output
# ---------------------------------------------------------------------------

def test_no_duplicate_terms():
    terms, autocomplete = generate_search_terms(
        title="Java Developer",
        normalized_title="java developer",
        category="backend",
        required_skills=["Java"],
        ats_keywords=["Java"],
    )
    assert len(terms) == len(set(terms)), "Duplicate terms found"


# ---------------------------------------------------------------------------
# Autocomplete minimum length
# ---------------------------------------------------------------------------

def test_autocomplete_terms_min_length_3():
    _, autocomplete = generate_search_terms(
        title="Data Analyst",
        normalized_title="data analyst",
        category="data_analytics",
        required_skills=["SQL"],
        ats_keywords=[],
    )
    for term in autocomplete:
        assert len(term) >= 3, f"Short term in autocomplete: {term!r}"
