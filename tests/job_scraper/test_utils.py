from job_scraper.filters import dedupe_jobs
from job_scraper.sources.portal_router import detect_source_type
from job_scraper.utils import infer_country


def test_detect_source_type_remoteok():
    assert detect_source_type("https://remoteok.com/remote-dev-jobs") == "remoteok"


def test_detect_source_type_workday():
    assert detect_source_type("https://company.wd1.myworkdayjobs.com/example") == "workday"


def test_detect_source_type_greenhouse():
    assert detect_source_type("https://boards.greenhouse.io/example") == "greenhouse"


def test_detect_source_type_linkedin():
    assert detect_source_type("https://www.linkedin.com/jobs/search/") == "linkedin"


def test_detect_source_type_indeed():
    assert detect_source_type("https://www.indeed.com/jobs") == "indeed"


def test_detect_source_type_dice():
    assert detect_source_type("https://www.dice.com/jobs") == "dice"


def test_detect_source_type_google_jobs_search():
    assert detect_source_type("https://www.google.com/search?q=java+jobs&udm=8") == "google_jobs_search"


def test_dedupe_by_url_and_id_and_triple():
    jobs = [
        {"title": "Backend Engineer", "company": "A", "location": "Remote", "job_url": "https://example.com/1", "source_external_id": "x1"},
        {"title": "Backend Engineer", "company": "A", "location": "Remote", "job_url": "https://example.com/1", "source_external_id": "x1"},
        {"title": "Backend Engineer", "company": "A", "location": "Remote", "job_url": "https://example.com/2", "source_external_id": ""},
    ]
    deduped = dedupe_jobs(jobs)
    assert len(deduped) == 1


def test_infer_country_from_location_or_title():
    assert infer_country("Toronto, Canada") == "Canada"
    assert infer_country("(Canada) - Product Manager", None) == "Canada"
