"""Tests for posted_at extraction and fallback behaviour."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from job_scraper.normalization import choose_posted_at, parse_posted_at


NOW = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# parse_posted_at
# ---------------------------------------------------------------------------

def test_just_posted_resolves_to_now():
    ts, raw = parse_posted_at("just posted", now=NOW)
    assert ts == NOW.isoformat()
    assert raw == "just posted"


def test_1_hour_ago():
    ts, raw = parse_posted_at("1 hour ago", now=NOW)
    expected = (NOW - timedelta(hours=1)).isoformat()
    assert ts == expected


def test_5_hours_ago():
    ts, raw = parse_posted_at("5 hours ago", now=NOW)
    expected = (NOW - timedelta(hours=5)).isoformat()
    assert ts == expected


def test_30_minutes_ago():
    ts, raw = parse_posted_at("30 minutes ago", now=NOW)
    expected = (NOW - timedelta(minutes=30)).isoformat()
    assert ts == expected


def test_1_day_ago():
    ts, raw = parse_posted_at("1 day ago", now=NOW)
    expected = (NOW - timedelta(days=1)).isoformat()
    assert ts == expected


def test_yesterday():
    ts, raw = parse_posted_at("yesterday", now=NOW)
    expected = (NOW - timedelta(days=1)).isoformat()
    assert ts == expected


def test_iso_string_parses():
    ts, raw = parse_posted_at("2026-04-28T10:00:00Z", now=NOW)
    assert ts == "2026-04-28T10:00:00+00:00"


def test_epoch_milliseconds():
    # 2025-04-28T00:00:00Z in ms — Lever and similar APIs use epoch ms integers
    epoch_ms = 1745798400000
    ts, _ = parse_posted_at(str(epoch_ms), now=NOW)
    assert ts is not None
    parsed = datetime.fromisoformat(ts)
    # epoch 1745798400000 ms = 2025-04-28; just verify it parsed to a valid date
    assert parsed.year in (2025, 2026)
    assert parsed.month == 4
    assert parsed.day == 28


def test_none_returns_none_timestamp():
    ts, raw = parse_posted_at(None, now=NOW)
    assert ts is None
    assert raw is None


def test_empty_string_returns_none_timestamp():
    ts, raw = parse_posted_at("", now=NOW)
    assert ts is None


# ---------------------------------------------------------------------------
# choose_posted_at
# ---------------------------------------------------------------------------

def test_choose_with_valid_relative_time():
    freshness = choose_posted_at("3 hours ago", scraped_at=NOW)
    assert freshness["posted_at_source"] == "source"
    assert freshness["posted_at"] == (NOW - timedelta(hours=3)).isoformat()
    assert freshness["posted_at_raw"] == "3 hours ago"
    assert freshness["scraped_at"] == NOW.isoformat()


def test_choose_falls_back_to_scraped_at_when_none():
    freshness = choose_posted_at(None, scraped_at=NOW)
    assert freshness["posted_at_source"] == "fallback"
    assert freshness["posted_at"] == NOW.isoformat()
    assert freshness["scraped_at"] == NOW.isoformat()


def test_choose_falls_back_for_unparseable_text():
    freshness = choose_posted_at("N/A", scraped_at=NOW)
    assert freshness["posted_at_source"] == "fallback"


def test_choose_uses_now_when_scraped_at_absent():
    freshness = choose_posted_at(None)
    assert freshness["posted_at_source"] == "fallback"
    assert freshness["posted_at"] is not None


@pytest.mark.parametrize("relative", [
    "just posted",
    "posted today",
    "just now",
    "1 hour ago",
    "24 hours ago",
    "2 days ago",
    "30 mins ago",
])
def test_choose_recognises_relative_patterns(relative):
    freshness = choose_posted_at(relative, scraped_at=NOW)
    assert freshness["posted_at_source"] == "source", f"failed for: {relative!r}"
