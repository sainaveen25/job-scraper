from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


DIRECT_HTTP = "direct_http"
BROWSER_RENDERED = "browser_rendered"
PROVIDER_API = "provider_api"
DISABLED_UNTIL_CONFIGURED = "disabled_until_configured"

OK = "ok"
ZERO_RESULTS = "zero_results"
BLOCKED_403 = "blocked_403"
BROWSER_REQUIRED = "browser_required"
PROVIDER_REQUIRED = "provider_required"
PROVIDER_DISABLED = "provider_disabled"
FAILED = "failed"

SOURCE_STATUSES: tuple[str, ...] = (
    OK,
    ZERO_RESULTS,
    BLOCKED_403,
    BROWSER_REQUIRED,
    PROVIDER_REQUIRED,
    PROVIDER_DISABLED,
    FAILED,
)


@dataclass(frozen=True)
class SourceStatus:
    source: str
    url: str
    mode: str
    status: str
    jobsFound: int = 0
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "url": self.url,
            "mode": self.mode,
            "status": self.status,
            "jobsFound": self.jobsFound,
            "message": self.message,
        }


@dataclass(frozen=True)
class SourceScrapeResult:
    jobs: list[dict]
    status: SourceStatus


@dataclass(frozen=True)
class SourceRunSummary:
    statuses: list[SourceStatus] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        counts = {status: 0 for status in SOURCE_STATUSES}
        for source_status in self.statuses:
            counts[source_status.status] = counts.get(source_status.status, 0) + 1
        return counts

    def direct_http_ok_count(self) -> int:
        return sum(1 for item in self.statuses if item.mode == DIRECT_HTTP and item.status == OK)
