from scraper.normalizers.job_normalizer import normalize_job


def test_normalizer_infers_country_from_location():
    normalized = normalize_job(
        {
            "title": "Backend Engineer",
            "job_url": "https://example.com/jobs/1",
            "location": "Toronto, Canada",
        }
    )

    assert normalized is not None
    assert normalized["country"] == "Canada"


def test_normalizer_does_not_force_usa_when_country_unknown():
    normalized = normalize_job(
        {
            "title": "Backend Engineer",
            "job_url": "https://example.com/jobs/2",
            "location": "Remote",
        }
    )

    assert normalized is not None
    assert normalized["country"] is None
