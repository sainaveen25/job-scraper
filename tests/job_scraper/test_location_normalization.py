"""Tests for normalize_location covering city/state/country/work_mode extraction."""
from __future__ import annotations

import pytest

from job_scraper.normalization import normalize_location


@pytest.mark.parametrize("location,exp_city,exp_state,exp_country,exp_work_mode", [
    # Standard US city, state
    ("Dallas, TX", "Dallas", "TX", "United States", None),
    ("Austin, Texas", "Austin", "TX", "United States", None),
    ("New York, NY", "New York", "NY", "United States", None),
    ("San Francisco, CA", "San Francisco", "CA", "United States", None),

    # Remote — US
    ("Remote - United States", None, None, "United States", "Remote"),
    ("Remote, United States", None, None, "United States", "Remote"),
    ("Remote (US)", None, None, None, "Remote"),
    ("Remote", None, None, None, "Remote"),

    # Hybrid
    ("Hybrid - Chicago, IL", "Chicago", "IL", "United States", "Hybrid"),
    ("Chicago, IL (Hybrid)", "Chicago", "IL", "United States", "Hybrid"),

    # On-site
    ("San Francisco, CA (On-site)", "San Francisco", "CA", "United States", "On-site"),

    # Canada
    ("Toronto, ON, Canada", "Toronto", "ON", "Canada", None),
    ("Vancouver, BC, Canada", "Vancouver", "BC", "Canada", None),

    # UK
    ("London, United Kingdom", "London", None, "United Kingdom", None),

    # India
    ("Bangalore, India", "Bangalore", None, "India", None),
    ("Hyderabad, India", "Hyderabad", None, "India", None),

    # Full US with country
    ("New York, NY, USA", "New York", "NY", "United States", None),

    # None / empty
    (None, None, None, None, None),
    ("", None, None, None, None),
])
def test_normalize_location(location, exp_city, exp_state, exp_country, exp_work_mode):
    result = normalize_location(location)
    assert result["city"] == exp_city, f"city mismatch for {location!r}: got {result['city']!r}"
    assert result["state"] == exp_state, f"state mismatch for {location!r}: got {result['state']!r}"
    assert result["country"] == exp_country, f"country mismatch for {location!r}: got {result['country']!r}"
    assert result["work_mode"] == exp_work_mode, f"work_mode mismatch for {location!r}: got {result['work_mode']!r}"


def test_state_infers_us_country():
    result = normalize_location("Houston, TX")
    assert result["country"] == "United States"
    assert result["state"] == "TX"


def test_state_infers_canada_country():
    result = normalize_location("Calgary, AB")
    assert result["country"] == "Canada"
    assert result["state"] == "AB"


def test_explicit_work_mode_overrides_location():
    result = normalize_location("New York, NY", work_mode="Remote")
    assert result["work_mode"] == "Remote"
    # City is still extracted from the location string
    assert result["city"] == "New York"
    assert result["state"] == "NY"


def test_explicit_country_arg():
    result = normalize_location("Berlin", country="Germany")
    assert result["country"] == "Germany"


def test_state_arg_propagated():
    result = normalize_location("Austin", state="TX")
    assert result["state"] == "TX"
    assert result["country"] == "United States"


@pytest.mark.parametrize("location,expected_mode", [
    ("Remote - United States", "Remote"),
    ("Hybrid position in New York", "Hybrid"),
    ("On-site New York, NY", "On-site"),
    ("In-office Dallas TX", "On-site"),
])
def test_work_mode_patterns(location, expected_mode):
    result = normalize_location(location)
    assert result["work_mode"] == expected_mode, f"For {location!r}: got {result['work_mode']!r}"
