from __future__ import annotations

import re
from typing import Any

from automation.models import Field, FieldMemoryEntry, FieldType, MappedField, UnknownField, UserProfile


_NON_WORD_RE = re.compile(r"[^a-z0-9]+")
_SENSITIVE_RE = re.compile(
    r"\b(gender|race|ethnicity|veteran|disability|disabled|sexual orientation|pronouns|protected)\b",
    re.IGNORECASE,
)

FIELD_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("first_name", ("first name", "given name", "preferred first name")),
    ("last_name", ("last name", "surname", "family name")),
    ("full_name", ("full name", "legal name", "name")),
    ("email", ("email", "e-mail")),
    ("phone", ("phone", "mobile", "telephone", "cell")),
    ("address_line_1", ("address line 1", "street address", "address 1")),
    ("address_line_2", ("address line 2", "apt", "suite", "address 2")),
    ("city", ("city",)),
    ("state", ("state", "province", "region")),
    ("zip", ("zip", "postal code", "postcode")),
    ("country", ("country",)),
    ("linkedin_url", ("linkedin", "linkedin url", "linkedin profile")),
    ("github_url", ("github", "github url", "github profile")),
    ("portfolio_url", ("portfolio", "personal website", "portfolio url")),
    ("website", ("website", "web site")),
    ("current_title", ("current title", "job title", "current role")),
    ("years_experience", ("years of experience", "years experience", "experience years")),
    ("work_authorization", ("authorized to work", "work authorization", "legally authorized")),
    ("sponsorship_required", ("require sponsorship", "need sponsorship", "visa sponsorship")),
    ("willing_to_relocate", ("willing to relocate", "relocate")),
    ("desired_salary", ("desired salary", "salary expectation", "compensation expectation")),
    ("available_start_date", ("available start", "start date", "available to start")),
    ("notice_period", ("notice period",)),
)


def normalize_question(label: str | None) -> str:
    text = (label or "").casefold()
    text = _NON_WORD_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_sensitive_question(label: str | None) -> bool:
    return bool(label and _SENSITIVE_RE.search(label))


def infer_profile_key(field: Field) -> tuple[str | None, float]:
    haystack = normalize_question(" ".join(part for part in (field.label, field.name) if part))
    if not haystack:
        return None, 0.0
    for key, variants in FIELD_PATTERNS:
        for variant in variants:
            normalized_variant = normalize_question(variant)
            if normalized_variant == haystack:
                return key, 0.98
            if normalized_variant in haystack:
                return key, 0.86
    return None, 0.0


def _coerce_answer(value: Any, field_type: FieldType) -> Any:
    if isinstance(value, bool):
        if field_type == FieldType.CHECKBOX:
            return value
        return "Yes" if value else "No"
    return value


def map_fields(
    fields: list[Field],
    profile: UserProfile,
    memory_entries: list[FieldMemoryEntry] | None = None,
) -> tuple[list[MappedField], list[UnknownField]]:
    memory_by_question = {
        normalize_question(entry.normalized_question or entry.original_question): entry
        for entry in (memory_entries or [])
        if entry.answer not in (None, "")
    }
    known: list[MappedField] = []
    unknown: list[UnknownField] = []

    for field in fields:
        field.normalized_question = normalize_question(field.label or field.name)
        field.sensitive = field.sensitive or is_sensitive_question(field.label)
        if field.field_type == FieldType.PASSWORD:
            unknown.append(UnknownField(field, "password_requires_manual_entry"))
            continue
        if field.sensitive:
            unknown.append(UnknownField(field, "sensitive_question_requires_review"))
            continue

        profile_key, confidence = infer_profile_key(field)
        value = profile.value_for(profile_key) if profile_key else None
        if value not in (None, ""):
            known.append(
                MappedField(
                    field=field,
                    profile_key=profile_key,
                    value=_coerce_answer(value, field.field_type),
                    source="profile",
                    confidence=confidence,
                    requires_review=confidence < 0.8,
                )
            )
            continue

        memory_entry = memory_by_question.get(field.normalized_question)
        if memory_entry:
            memory_entry.last_used_at = None
            known.append(
                MappedField(
                    field=field,
                    value=_coerce_answer(memory_entry.answer, field.field_type),
                    source="memory",
                    confidence=memory_entry.confidence,
                    requires_review=memory_entry.sensitive or memory_entry.confidence < 0.8,
                )
            )
            continue

        unknown.append(UnknownField(field, "unmapped"))

    return known, unknown
