from __future__ import annotations

import asyncio
import argparse
import ast
import importlib
import inspect
import logging
import os
import time
from pathlib import Path
from typing import Any, Iterable

from scraper.clients.lovable_preferences import fetch_search_preferences_from_lovable
from scraper.config import get_settings, load_environment
from scraper.exporters.lovable_ingest import send_jobs_to_lovable
from scraper.normalizers.job_normalizer import normalize_jobs


logger = logging.getLogger(__name__)
COMMON_ENTRYPOINT_NAMES = (
    "scrape_all_sources",
    "run_all_spiders",
    "collect_jobs",
    "crawl_jobs",
    "main",
)
IGNORED_DISCOVERY_DIRS = {
    ".git",
    ".github",
    ".venv",
    "agent-skill",
    "docs",
    "images",
    "scraper",
    "scrapling",
    "tests",
    "__pycache__",
}


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def sample_job() -> dict[str, Any]:
    return {
        "title": "Java Backend Developer",
        "company": "Qode",
        "location": "Dallas, TX",
        "source": "Manual Test",
        "jobUrl": "https://example.com/jobs/java-backend-test",
        "description": "Java, Spring Boot, AWS, SQL, REST APIs, Docker, Kubernetes.",
    }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _to_module_path(file_path: Path) -> str:
    return ".".join(file_path.relative_to(_repo_root()).with_suffix("").parts)


def _load_callable(entrypoint: str):
    if ":" not in entrypoint:
        raise ValueError("Entrypoint must be in the format module.submodule:function_name")

    module_name, function_name = entrypoint.split(":", 1)
    module = importlib.import_module(module_name)
    try:
        candidate = getattr(module, function_name)
    except AttributeError as exc:
        raise LookupError(f"Entrypoint {entrypoint!r} could not be resolved") from exc

    if not callable(candidate):
        raise TypeError(f"Entrypoint {entrypoint!r} is not callable")
    return candidate


def discover_existing_entrypoint() -> tuple[str, Any]:
    explicit_entrypoint = os.getenv("SCRAPER_ENTRYPOINT", "").strip()
    if explicit_entrypoint:
        return explicit_entrypoint, _load_callable(explicit_entrypoint)

    matches: list[tuple[str, str]] = []

    for file_path in _repo_root().rglob("*.py"):
        if any(part in IGNORED_DISCOVERY_DIRS for part in file_path.parts):
            continue

        try:
            module_ast = ast.parse(file_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        for node in module_ast.body:
            if isinstance(node, ast.FunctionDef) and node.name in COMMON_ENTRYPOINT_NAMES:
                matches.append((_to_module_path(file_path), node.name))

    if not matches:
        raise LookupError(
            "No existing scraper entrypoint was found in this repository. "
            "This checkout appears to be the Scrapling library itself, not the job scraper app. "
            "Set SCRAPER_ENTRYPOINT=package.module:function when your job scraper code is available, "
            "or use --sample to verify Lovable ingestion immediately."
        )

    if len(matches) > 1:
        formatted = ", ".join(f"{module}:{function}" for module, function in matches)
        raise LookupError(
            "Multiple potential scraper entrypoints were found. "
            f"Set SCRAPER_ENTRYPOINT to one of: {formatted}"
        )

    module_name, function_name = matches[0]
    entrypoint = f"{module_name}:{function_name}"
    return entrypoint, _load_callable(entrypoint)


def _coerce_raw_jobs(result: Any) -> list[dict[str, Any]]:
    if result is None:
        return []

    if hasattr(result, "items") and isinstance(getattr(result, "items"), Iterable):
        return [item for item in result.items if isinstance(item, dict)]

    if isinstance(result, dict):
        return [result]

    if isinstance(result, (list, tuple, set)):
        return [item for item in result if isinstance(item, dict)]

    if inspect.isgenerator(result):
        return [item for item in result if isinstance(item, dict)]

    raise TypeError(
        "Scraper entrypoint must return an iterable of dict job records or a CrawlResult-like object with .items"
    )


def _extract_run_metadata(result: Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for name in ("source_url_count", "failed_sources_count"):
        value = getattr(result, name, None)
        if value is None:
            continue
        try:
            metadata[name] = int(value)
        except (TypeError, ValueError):
            continue
    source_statuses = getattr(result, "source_statuses", None)
    if isinstance(source_statuses, list):
        metadata["source_statuses"] = [
            item.to_dict() if hasattr(item, "to_dict") else item for item in source_statuses if item is not None
        ]
    return metadata


def _invoke_entrypoint(callable_obj: Any, search_queries: list[dict[str, Any]] | None = None) -> Any:
    signature = inspect.signature(callable_obj)
    kwargs: dict[str, Any] = {}
    if "search_queries" in signature.parameters:
        kwargs["search_queries"] = search_queries
    elif "queries" in signature.parameters:
        kwargs["queries"] = search_queries

    settings = get_settings()
    if "source_urls" in signature.parameters and settings.job_source_urls:
        kwargs["source_urls"] = list(settings.job_source_urls)
    elif "job_source_urls" in signature.parameters and settings.job_source_urls:
        kwargs["job_source_urls"] = list(settings.job_source_urls)

    result = callable_obj(**kwargs)
    if inspect.isawaitable(result):
        return asyncio.run(result)
    return result


def collect_raw_jobs(
    *,
    use_sample: bool = False,
    search_queries: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], str, dict[str, int]]:
    if use_sample:
        return [sample_job()], "sample_job", {"failed_sources_count": 0}

    entrypoint, callable_obj = discover_existing_entrypoint()
    logger.info("Using scraper entrypoint: %s", entrypoint)
    raw_result = _invoke_entrypoint(callable_obj, search_queries=search_queries)
    return _coerce_raw_jobs(raw_result), entrypoint, _extract_run_metadata(raw_result)


def run_ingestion_cycle(*, use_sample: bool = False) -> dict[str, Any]:
    started_at = time.perf_counter()
    settings = get_settings()
    search_queries: list[dict[str, Any]] | None = None
    source_url_count = len(settings.job_source_urls)
    global_category_count = 0

    if not use_sample:
        if settings.job_source_urls:
            logger.info("Using %s configured job source URLs from JOB_SOURCE_URLS", source_url_count)

        if settings.lovable_search_preferences_url:
            try:
                search_queries = fetch_search_preferences_from_lovable()
                if not search_queries:
                    logger.info("No active search preferences found.")
            except Exception as exc:
                logger.warning("Failed to fetch optional search preferences: %s", exc)

        try:
            from job_scraper.config import get_job_scraper_settings

            global_category_count = len(get_job_scraper_settings().global_job_categories)
        except Exception:
            global_category_count = 0

    raw_jobs, entrypoint, run_metadata = collect_raw_jobs(use_sample=use_sample, search_queries=search_queries)
    source_url_count = run_metadata.get("source_url_count", source_url_count)
    failed_sources_count = run_metadata.get("failed_sources_count", 0)
    source_statuses = run_metadata.get("source_statuses", [])
    source_status_counts: dict[str, int] = {}
    direct_http_ok_count = 0
    for source_status in source_statuses:
        if not isinstance(source_status, dict):
            continue
        status = str(source_status.get("status", ""))
        source_status_counts[status] = source_status_counts.get(status, 0) + 1
        if source_status.get("mode") == "direct_http" and status == "ok":
            direct_http_ok_count += 1
    normalized_jobs, normalization_skipped = normalize_jobs(raw_jobs, default_source="scrapling")
    ingest_result = send_jobs_to_lovable(
        normalized_jobs,
        source="scrapling",
        batch_size=settings.scraper_batch_size,
    )

    summary = {
        "entrypoint": entrypoint,
        "source_url_count": source_url_count,
        "global_category_count": global_category_count,
        "search_queries_count": len(search_queries or []),
        "raw_count": len(raw_jobs),
        "normalized_count": len(normalized_jobs),
        "normalization_skipped": normalization_skipped,
        "failed_sources_count": failed_sources_count,
        "source_statuses": source_statuses,
        "source_status_counts": source_status_counts,
        "direct_http_ok_count": direct_http_ok_count,
        "duration_seconds": round(time.perf_counter() - started_at, 2),
        **ingest_result,
    }
    logger.info(
        "Scraper run summary: source_urls=%s raw=%s normalized=%s inserted=%s updated=%s skipped=%s "
        "ingest_failed=%s failed_sources=%s duration_seconds=%.2f",
        summary["source_url_count"],
        summary["raw_count"],
        summary["normalized_count"],
        summary["inserted"],
        summary["updated"],
        summary["skipped"],
        summary.get("failed", 0),
        summary["failed_sources_count"],
        summary["duration_seconds"],
    )
    return summary


def print_summary(summary: dict[str, Any]) -> None:
    print("Scraper run summary")
    print(f"Entrypoint: {summary['entrypoint']}")
    print(f"Source URLs: {summary['source_url_count']}")
    if summary.get("source_status_counts"):
        counts = summary["source_status_counts"]
        print(f"Total sources: {len(summary.get('source_statuses', []))}")
        print(f"Direct HTTP sources ok: {summary.get('direct_http_ok_count', 0)}")
        print("Source summary:")
        for status in ("ok", "zero_results", "blocked_403", "browser_required", "provider_required", "provider_disabled", "failed"):
            print(f"- {status}: {counts.get(status, 0)}")
    print(f"Global categories: {summary['global_category_count']}")
    print(f"Search queries: {summary['search_queries_count']}")
    print(f"Raw jobs found: {summary['raw_count']}")
    print(f"Normalized jobs: {summary['normalized_count']}")
    print(f"Normalization skipped: {summary['normalization_skipped']}")
    print(f"Inserted: {summary['inserted']}")
    print(f"Updated: {summary['updated']}")
    print(f"Skipped: {summary['skipped']}")
    print(f"Lovable ingest failed: {summary.get('failed', 0)}")
    print(f"Failed sources: {summary['failed_sources_count']}")
    print(f"Run duration seconds: {summary['duration_seconds']:.2f}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the scraper once and send jobs to Lovable Cloud.")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Send one built-in sample job to Lovable without running the real scraper entrypoint.",
    )
    return parser


def main() -> int:
    configure_logging()
    load_environment()
    args = build_parser().parse_args()

    try:
        summary = run_ingestion_cycle(use_sample=args.sample)
    except Exception:
        logger.exception("Scraper run failed")
        return 1

    print_summary(summary)
    if not summary.get("ok", True) or int(summary.get("failed", 0)) > 0:
        logger.error("Lovable ingest failed for %s job(s). Exiting with non-zero status.", summary.get("failed", 0))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
