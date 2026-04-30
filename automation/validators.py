from __future__ import annotations

from automation.models import Field, FieldType, MappedField, ValidationResult


def validate_required_fields(fields: list[Field], mapped_fields: list[MappedField]) -> ValidationResult:
    mapped_selectors = {item.field.selector for item in mapped_fields if item.value not in (None, "")}
    missing = [
        field
        for field in fields
        if field.required
        and field.field_type not in {FieldType.FILE, FieldType.PASSWORD}
        and field.selector not in mapped_selectors
    ]
    needs_review = [item.field for item in mapped_fields if item.requires_review or item.field.sensitive]
    return ValidationResult(
        ok=not missing and not needs_review,
        missing_required=missing,
        needs_review=needs_review,
        message=None if not missing else "Required fields are missing.",
    )


def can_submit(mode: str, allow_submit: bool, validation: ValidationResult) -> bool:
    return mode == "submit" and allow_submit and validation.ok
