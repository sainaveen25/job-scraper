from job_scraper.config import DEFAULT_JOB_CATEGORIES
from job_scraper.query_builder import build_global_queries


def test_build_global_queries():
    queries = build_global_queries(["Software Engineering", "Data Engineering"], ["United States", "Remote"])
    assert len(queries) == 4
    assert queries[0]["query"]


def test_default_global_categories_are_broad_stem():
    expected = {
        "Software Engineering",
        "Data Analytics",
        "Electrical Engineer",
        "Relay Designer",
        "Hardware Engineer",
        "Mechanical Engineer",
        "Civil Engineer",
        "Robotics Engineer",
        "Biomedical Engineer",
    }
    assert expected.issubset(set(DEFAULT_JOB_CATEGORIES))
