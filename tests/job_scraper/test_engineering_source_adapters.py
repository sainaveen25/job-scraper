from __future__ import annotations

from job_scraper.sources.dice import scrape_dice_jobs
from job_scraper.sources.workday import scrape_workday_jobs
from scraper.normalizers.job_normalizer import normalize_job


def test_dice_extracts_engineering_job_metadata(monkeypatch):
    listing_html = '<a href="/job-detail/abc">Electrical Engineer</a>'
    detail_html = """
    <html><body>
    <script type="application/ld+json">
    {
      "@type": "JobPosting",
      "title": "Electrical Engineer",
      "description": "Power systems, relay design, substation, controls, and circuit design.",
      "datePosted": "2026-05-01",
      "employmentType": "FULL_TIME",
      "hiringOrganization": {"name": "GridCo"},
      "jobLocation": [{
        "address": {
          "addressLocality": "Austin",
          "addressRegion": "TX",
          "addressCountry": "US"
        }
      }],
      "identifier": {"value": "DICE-1"}
    }
    </script>
    </body></html>
    """

    def fake_fetch(url, timeout=30):
        return detail_html if "job-detail" in url else listing_html

    monkeypatch.setattr("job_scraper.sources.dice.fetch_html", fake_fetch)

    jobs = scrape_dice_jobs("https://www.dice.com/jobs?q=electrical+engineer", timeout=5)
    assert len(jobs) == 1
    job = jobs[0]
    assert job["title"] == "Electrical Engineer"
    assert job["city"] == "Austin"
    assert job["state"] == "TX"
    assert job["employment_type"] == "FULL_TIME"

    normalized = normalize_job(job, default_source="dice")
    assert normalized is not None
    assert normalized["category"] == "power_systems"
    assert "electrical engineer" in normalized["autocomplete_terms"]
    assert "relay design" in normalized["search_terms"]


def test_workday_ld_json_extracts_engineering_job_metadata(monkeypatch):
    html = """
    <html><body>
    <script type="application/ld+json">
    {
      "@type": "JobPosting",
      "title": "Hardware Validation Engineer",
      "url": "https://example.myworkdayjobs.com/job/123",
      "description": "Validation testing for hardware, FPGA boards, and embedded firmware.",
      "datePosted": "2026-05-02",
      "employmentType": "Full-time",
      "hiringOrganization": {"name": "DeviceCo"},
      "jobLocation": [{
        "address": {
          "addressLocality": "San Jose",
          "addressRegion": "CA",
          "addressCountry": "US"
        }
      }],
      "identifier": {"value": "WD-1"}
    }
    </script>
    </body></html>
    """

    monkeypatch.setattr("job_scraper.sources.workday.fetch_html", lambda *args, **kwargs: html)

    jobs = scrape_workday_jobs("https://example.myworkdayjobs.com/en-US/careers", timeout=5)
    assert len(jobs) == 1
    job = jobs[0]
    assert job["title"] == "Hardware Validation Engineer"
    assert job["city"] == "San Jose"
    assert job["state"] == "CA"
    assert job["employment_type"] == "Full-time"

    normalized = normalize_job(job, default_source="workday")
    assert normalized is not None
    assert normalized["category"] == "hardware_engineering"
    assert "hardware engineer" in normalized["search_terms"]
    assert "validation" in normalized["search_terms"]
