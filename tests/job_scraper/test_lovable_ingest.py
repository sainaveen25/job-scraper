from __future__ import annotations

import requests

from scraper.exporters.lovable_ingest import _send_batch_with_fallback


class _DummySession:
    pass


def _job(index: int) -> dict:
    return {
        "title": f"Job {index}",
        "jobUrl": f"https://example.com/jobs/{index}",
    }


def test_send_batch_with_fallback_splits_and_preserves_good_jobs(monkeypatch):
    def fake_post_batch(*, payload, **kwargs):
        jobs = payload["jobs"]
        urls = {job["jobUrl"] for job in jobs}
        if "https://example.com/jobs/2" in urls and len(jobs) > 1:
            response = requests.Response()
            response.status_code = 500
            response._content = b'{"error":"bad payload"}'
            raise requests.HTTPError("500 Server Error", response=response)
        if urls == {"https://example.com/jobs/2"}:
            response = requests.Response()
            response.status_code = 500
            response._content = b'{"error":"still bad"}'
            raise requests.HTTPError("500 Server Error", response=response)
        return {"received": len(jobs), "inserted": len(jobs), "updated": 0, "skipped": 0}

    monkeypatch.setattr("scraper.exporters.lovable_ingest._post_batch", fake_post_batch)

    result = _send_batch_with_fallback(
        _DummySession(),
        url="https://example.com/ingest",
        headers={"Authorization": "Bearer token"},
        source="scrapling",
        batch=[_job(1), _job(2), _job(3)],
        timeout=30,
    )

    assert result == {"received": 3, "inserted": 2, "updated": 0, "skipped": 1, "failed": 1}
