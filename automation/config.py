from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AutomationSettings:
    headless: bool = True
    timeout_ms: int = 30_000
    artifact_dir: Path = Path("artifacts/apply_runs")


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "y", "on"}


def get_settings() -> AutomationSettings:
    timeout = os.getenv("PLAYWRIGHT_TIMEOUT_MS", "30000")
    try:
        timeout_ms = int(timeout)
    except ValueError:
        timeout_ms = 30_000
    return AutomationSettings(
        headless=_bool_env("AUTOFILL_HEADLESS", True),
        timeout_ms=timeout_ms,
        artifact_dir=Path(os.getenv("AUTOFILL_ARTIFACT_DIR", "artifacts/apply_runs")),
    )
