from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from scraper.config import get_settings


logger = logging.getLogger(__name__)
FAILED_JOB_DIR = Path("scraper_failed_jobs")


def _chunked(items: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def _extract_count(payload: Any, key: str) -> int:
    if isinstance(payload, dict):
        raw_value = payload.get(key)
        if raw_value is None and isinstance(payload.get("data"), dict):
            raw_value = payload["data"].get(key)
        if raw_value is None and isinstance(payload.get("result"), dict):
            raw_value = payload["result"].get(key)
        if raw_value is None:
            return 0
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            return 0
    return 0


def _post_batch(
    session: requests.Session,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: int,
) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(1, 4):
        try:
            response = session.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.RequestException as exc:
            last_error = exc
            if attempt == 3:
                break
            sleep_seconds = 2 ** (attempt - 1)
            logger.warning("Lovable ingest network error on attempt %s/3: %s", attempt, exc)
            time.sleep(sleep_seconds)
            continue

        if response.status_code in (401, 403):
            raise PermissionError(
                "Lovable ingest rejected the scraper credentials. "
                "Check LOVABLE_SCRAPER_INGEST_TOKEN and endpoint permissions."
            )

        if response.status_code in (408, 409, 425, 429) or 500 <= response.status_code < 600:
            if attempt == 3:
                response.raise_for_status()
            sleep_seconds = 2 ** (attempt - 1)
            logger.warning(
                "Lovable ingest transient error on attempt %s/3: HTTP %s",
                attempt,
                response.status_code,
            )
            time.sleep(sleep_seconds)
            continue

        response.raise_for_status()

        if not response.content:
            return {}

        try:
            return response.json()
        except ValueError:
            logger.warning("Lovable ingest returned a non-JSON body; counts will use safe fallbacks.")
            return {}

    if last_error is not None:
        raise RuntimeError("Lovable ingest failed after 3 attempts") from last_error

    raise RuntimeError("Lovable ingest failed after 3 attempts")


def _response_preview(exc: Exception) -> str:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        text = (exc.response.text or "").strip()
        if text:
            return text[:500]
    return ""


def _merge_counts(*results: dict[str, Any]) -> dict[str, Any]:
    merged = {"received": 0, "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
    for result in results:
        merged["received"] += int(result.get("received", 0))
        merged["inserted"] += int(result.get("inserted", 0))
        merged["updated"] += int(result.get("updated", 0))
        merged["skipped"] += int(result.get("skipped", 0))
        merged["failed"] += int(result.get("failed", 0))
    return merged


def _clean_string(value: str, limit: int = 20000) -> str:
    return value.replace("\x00", "").strip()[:limit]


def _sanitize_json_value(value: Any, *, depth: int = 0) -> Any:
    if depth >= 4:
        return _clean_string(str(value), limit=1000)

    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _clean_string(value)
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for index, (key, nested) in enumerate(value.items()):
            if index >= 50:
                sanitized["_truncatedKeys"] = True
                break
            sanitized[_clean_string(str(key), limit=120)] = _sanitize_json_value(nested, depth=depth + 1)
        return sanitized
    if isinstance(value, (list, tuple, set)):
        items = [_sanitize_json_value(item, depth=depth + 1) for item in list(value)[:50]]
        if len(value) > 50:
            items.append("_truncated")
        return items
    return _clean_string(str(value), limit=1000)


def _compact_job_for_retry(job: dict[str, Any]) -> dict[str, Any]:
    compact = {key: _sanitize_json_value(value) for key, value in job.items() if key != "rawPayload"}
    raw_payload = job.get("rawPayload")
    if isinstance(raw_payload, dict):
        compact["rawPayload"] = {
            key: _sanitize_json_value(raw_payload.get(key))
            for key in ("id", "text", "hostedUrl", "applyUrl", "createdAt", "categories", "company")
            if key in raw_payload
        }
        compact["rawPayload"]["_originalKeys"] = sorted(raw_payload.keys())[:100]
        compact["rawPayload"]["_truncated"] = True
    else:
        compact["rawPayload"] = _sanitize_json_value(raw_payload)
    return compact


def _dump_failed_job(job: dict[str, Any], exc: Exception) -> Path | None:
    try:
        FAILED_JOB_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_title = "".join(ch if ch.isalnum() else "_" for ch in (job.get("title") or "job"))[:60].strip("_") or "job"
        path = FAILED_JOB_DIR / f"{stamp}_{safe_title}.json"
        payload = {
            "error": str(exc),
            "job": _sanitize_json_value(job),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path
    except Exception:  # pragma: no cover
        return None


def _send_batch_with_fallback(
    session: requests.Session,
    *,
    url: str,
    headers: dict[str, str],
    source: str,
    batch: list[dict[str, Any]],
    timeout: int,
) -> dict[str, Any]:
    payload = {
        "source": source,
        "scrapedAt": datetime.now(timezone.utc).isoformat(),
        "jobs": batch,
    }

    try:
        result = _post_batch(
            session=session,
            url=url,
            headers=headers,
            payload=payload,
            timeout=timeout,
        )
    except PermissionError:
        raise
    except Exception as exc:
        preview = _response_preview(exc)
        if len(batch) == 1:
            job = batch[0]
            compact_job = _compact_job_for_retry(job)
            if compact_job != job:
                try:
                    logger.warning(
                        "Retrying single failed job with compacted payload: title=%r jobUrl=%r",
                        job.get("title"),
                        job.get("jobUrl") or job.get("job_url"),
                    )
                    compact_result = _post_batch(
                        session=session,
                        url=url,
                        headers=headers,
                        payload={
                            "source": source,
                            "scrapedAt": datetime.now(timezone.utc).isoformat(),
                            "jobs": [compact_job],
                        },
                        timeout=timeout,
                    )
                    return {
                        "received": _extract_count(compact_result, "received") or 1,
                        "inserted": _extract_count(compact_result, "inserted"),
                        "updated": _extract_count(compact_result, "updated"),
                        "skipped": _extract_count(compact_result, "skipped"),
                    }
                except Exception as compact_exc:
                    exc = compact_exc
                    preview = _response_preview(compact_exc)

            dumped_path = _dump_failed_job(job, exc)
            logger.error(
                "Lovable ingest skipped 1 job after repeated batch failure: title=%r jobUrl=%r error=%s%s%s",
                job.get("title"),
                job.get("jobUrl") or job.get("job_url"),
                exc,
                f" body={preview}" if preview else "",
                f" dump={dumped_path}" if dumped_path else "",
            )
            return {"received": 1, "inserted": 0, "updated": 0, "skipped": 1, "failed": 1}

        midpoint = len(batch) // 2
        logger.warning(
            "Lovable ingest batch of %s failed after retries; splitting into %s and %s. error=%s%s",
            len(batch),
            midpoint,
            len(batch) - midpoint,
            exc,
            f" body={preview}" if preview else "",
        )
        left = _send_batch_with_fallback(
            session,
            url=url,
            headers=headers,
            source=source,
            batch=batch[:midpoint],
            timeout=timeout,
        )
        right = _send_batch_with_fallback(
            session,
            url=url,
            headers=headers,
            source=source,
            batch=batch[midpoint:],
            timeout=timeout,
        )
        return _merge_counts(left, right)

    return {
        "received": _extract_count(result, "received") or len(batch),
        "inserted": _extract_count(result, "inserted"),
        "updated": _extract_count(result, "updated"),
        "skipped": _extract_count(result, "skipped"),
        "failed": 0,
    }


def send_jobs_to_lovable(
    jobs: list[dict[str, Any]],
    source: str = "scrapling",
    batch_size: int = 100,
    timeout: int = 60,
) -> dict[str, Any]:
    settings = get_settings()

    if not jobs:
        return {
            "ok": True,
            "received": 0,
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "failed": 0,
            "batches": 0,
        }

    if not settings.lovable_ingest_url:
        raise RuntimeError("LOVABLE_INGEST_URL is required")
    if not settings.lovable_scraper_ingest_token:
        raise RuntimeError("LOVABLE_SCRAPER_INGEST_TOKEN is required")
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")

    headers = {
        "Authorization": f"Bearer {settings.lovable_scraper_ingest_token}",
        "Content-Type": "application/json",
    }

    aggregated = {
        "ok": True,
        "received": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "batches": 0,
    }

    batches = _chunked(jobs, batch_size=batch_size)

    with requests.Session() as session:
        for index, batch in enumerate(batches, start=1):
            result = _send_batch_with_fallback(
                session=session,
                url=settings.lovable_ingest_url,
                headers=headers,
                source=source,
                batch=batch,
                timeout=timeout,
            )

            batch_received = int(result["received"])
            batch_inserted = int(result["inserted"])
            batch_updated = int(result["updated"])
            batch_skipped = int(result["skipped"])
            batch_failed = int(result.get("failed", 0))

            aggregated["received"] += batch_received
            aggregated["inserted"] += batch_inserted
            aggregated["updated"] += batch_updated
            aggregated["skipped"] += batch_skipped
            aggregated["failed"] += batch_failed
            aggregated["batches"] += 1
            if batch_failed:
                aggregated["ok"] = False

            logger.info(
                "Lovable ingest batch %s/%s: received=%s inserted=%s updated=%s skipped=%s failed=%s",
                index,
                len(batches),
                batch_received,
                batch_inserted,
                batch_updated,
                batch_skipped,
                batch_failed,
            )

    return aggregated
