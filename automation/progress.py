from __future__ import annotations

from dataclasses import asdict
from typing import Any

from automation.models import Field, MappedField, PageProgress, RunLog, UnknownField, ValidationResult


def build_page_progress(
    *,
    platform: str,
    step: int,
    fields: list[Field],
    known: list[MappedField],
    unknown: list[UnknownField],
    validation: ValidationResult | None,
    has_next: bool,
    has_submit: bool,
    current_url: str | None = None,
    page_title: str | None = None,
    screenshot_path: str | None = None,
    screenshots: list[str] | None = None,
    logs: list[RunLog] | None = None,
) -> PageProgress:
    missing = validation.missing_required if validation else []
    blocked = bool(missing or unknown or (validation and validation.needs_review))
    return PageProgress(
        page_detected=platform,
        step=step,
        current_url=current_url,
        page_title=page_title,
        screenshot_path=screenshot_path,
        fields_found=fields,
        fields_autofilled=known,
        unresolved_fields=unknown,
        required_missing=missing,
        ready_for_next=has_next and not blocked,
        ready_for_submit=has_submit and not blocked,
        screenshots=screenshots or ([screenshot_path] if screenshot_path else []),
        logs=logs or [],
    )


def progress_to_dict(progress: PageProgress | None) -> dict[str, Any] | None:
    if progress is None:
        return None
    payload = asdict(progress)
    payload.update(
        {
            "fields_detected": payload["fields_found"],
            "fields_filled": payload["fields_autofilled"],
            "unresolved_fields": payload["unresolved_fields"],
            "ready_for_next": payload["ready_for_next"],
            "ready_for_submit": payload["ready_for_submit"],
        }
    )
    return payload
