"""
automation/ai/usage_store.py
=============================
Per-user AI usage event log and limit enforcement.

Usage events are appended to:
    <usage_store_dir>/<user_id>/usage.jsonl

Free-tier users are limited by ``AI_FREE_TIER_DAILY_LIMIT`` and
``AI_FREE_TIER_MONTHLY_LIMIT`` on managed (ApplyMate) key usage.
BYOK requests are logged but do NOT count toward managed key cost limits.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automation.ai.config import get_ai_config


@dataclass
class AIUsageEvent:
    user_id: str
    feature_type: str
    provider: str
    model: str
    used_byok: bool
    status: str             # "ok" | "error"
    input_tokens: int | None = None
    output_tokens: int | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class LimitResult:
    allowed: bool
    daily_used: int
    daily_limit: int
    monthly_used: int
    monthly_limit: int
    reason: str | None = None


class UsageLimitExceeded(Exception):
    """Raised when a managed-key request exceeds the user's tier limit."""

    def __init__(self, result: LimitResult) -> None:
        self.result = result
        super().__init__(result.reason or "AI usage limit exceeded")


class AIUsageStore:
    """
    Append-only JSONL usage log per user with limit enforcement.

    Thread/process safety: each append is a single write call; on POSIX
    this is atomic for small payloads.  For production use, replace with
    a database-backed implementation.
    """

    def __init__(self, store_dir: str | Path | None = None) -> None:
        cfg = get_ai_config()
        self._dir = Path(store_dir or cfg.usage_store_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _user_file(self, user_id: str) -> Path:
        safe_id = "".join(c for c in user_id if c.isalnum() or c in "-_")[:64] or "unknown"
        return self._dir / safe_id / "usage.jsonl"

    def _iter_events(self, user_id: str) -> list[AIUsageEvent]:
        path = self._user_file(user_id)
        if not path.exists():
            return []
        events: list[AIUsageEvent] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    events.append(AIUsageEvent(**{k: data[k] for k in AIUsageEvent.__dataclass_fields__ if k in data}))
                except (KeyError, TypeError, json.JSONDecodeError):
                    continue
        except OSError:
            pass
        return events

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_event(
        self,
        user_id: str,
        feature_type: str,
        provider: str,
        model: str,
        *,
        used_byok: bool,
        status: str = "ok",
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> AIUsageEvent:
        """Append a usage event to the user's log file."""
        event = AIUsageEvent(
            user_id=user_id,
            feature_type=feature_type,
            provider=provider,
            model=model,
            used_byok=used_byok,
            status=status,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        path = self._user_file(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(event)) + "\n")
        return event

    def get_daily_count(self, user_id: str, *, managed_only: bool = True) -> int:
        """Count managed-key requests today (UTC)."""
        today = datetime.now(timezone.utc).date().isoformat()
        return sum(
            1
            for e in self._iter_events(user_id)
            if e.created_at[:10] == today and e.status == "ok" and (not managed_only or not e.used_byok)
        )

    def get_monthly_count(self, user_id: str, *, managed_only: bool = True) -> int:
        """Count managed-key requests this calendar month (UTC)."""
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        return sum(
            1
            for e in self._iter_events(user_id)
            if e.created_at[:7] == month and e.status == "ok" and (not managed_only or not e.used_byok)
        )

    def check_limit(self, user_id: str, *, tier: str = "free") -> LimitResult:
        """
        Check whether *user_id* is within their managed-key usage limits.

        Args:
            tier: ``"free"`` or ``"paid"``

        Returns:
            A :class:`LimitResult`.  If ``allowed`` is False, the caller
            should raise :class:`UsageLimitExceeded` or return an error.
        """
        cfg = get_ai_config()
        if tier == "paid":
            daily_limit = cfg.paid_daily_limit
            monthly_limit = cfg.paid_monthly_limit
        else:
            daily_limit = cfg.free_daily_limit
            monthly_limit = cfg.free_monthly_limit

        daily_used = self.get_daily_count(user_id, managed_only=True)
        monthly_used = self.get_monthly_count(user_id, managed_only=True)

        if daily_used >= daily_limit:
            return LimitResult(
                allowed=False,
                daily_used=daily_used,
                daily_limit=daily_limit,
                monthly_used=monthly_used,
                monthly_limit=monthly_limit,
                reason=f"Daily AI limit reached ({daily_used}/{daily_limit}).  Add your own AI key or upgrade.",
            )
        if monthly_used >= monthly_limit:
            return LimitResult(
                allowed=False,
                daily_used=daily_used,
                daily_limit=daily_limit,
                monthly_used=monthly_used,
                monthly_limit=monthly_limit,
                reason=f"Monthly AI limit reached ({monthly_used}/{monthly_limit}).  Add your own AI key or upgrade.",
            )
        return LimitResult(
            allowed=True,
            daily_used=daily_used,
            daily_limit=daily_limit,
            monthly_used=monthly_used,
            monthly_limit=monthly_limit,
        )
