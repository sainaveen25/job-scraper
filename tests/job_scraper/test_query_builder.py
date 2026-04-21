from job_scraper.query_builder import build_global_queries


def test_build_global_queries():
    queries = build_global_queries(["Software Engineering", "Data Engineering"], ["United States", "Remote"])
    assert len(queries) == 4
    assert queries[0]["query"]

