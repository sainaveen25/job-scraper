from __future__ import annotations

from typing import Any

from automation.runner import prepare_application, run_application, save_field_memory


def post_apply_prepare(payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/apply/prepare."""
    return prepare_application(payload)


def post_apply_run(payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/apply/run."""
    return run_application(payload)


def post_apply_save_field_memory(payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/apply/save-field-memory."""
    return save_field_memory(payload)
