from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class AutomationMode(str, Enum):
    PREVIEW = "preview"
    ASSISTED = "assisted"
    SUBMIT = "submit"


class RunStatus(str, Enum):
    PREVIEW_READY = "preview_ready"
    ASSISTED_READY = "assisted_ready"
    FILLED_WAITING_REVIEW = "filled_waiting_review"
    SUBMITTED = "submitted"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class FieldType(str, Enum):
    TEXT = "text"
    TEXTAREA = "textarea"
    SELECT = "select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    FILE = "file"
    PASSWORD = "password"
    UNKNOWN = "unknown"


@dataclass
class UserProfile:
    first_name: str | None = None
    last_name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    address_line_1: str | None = None
    address_line_2: str | None = None
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    country: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    website: str | None = None
    current_title: str | None = None
    years_experience: str | int | None = None
    work_authorization: str | bool | None = None
    sponsorship_required: str | bool | None = None
    willing_to_relocate: str | bool | None = None
    desired_salary: str | None = None
    available_start_date: str | None = None
    notice_period: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | "UserProfile" | None) -> "UserProfile":
        if isinstance(value, cls):
            return value
        if not value:
            return cls()
        known = {name for name in cls.__dataclass_fields__ if name != "extras"}
        kwargs = {key: val for key, val in value.items() if key in known}
        extras = {key: val for key, val in value.items() if key not in known}
        return cls(**kwargs, extras=extras)

    def value_for(self, key: str) -> Any:
        return getattr(self, key, None) or self.extras.get(key)


@dataclass
class ResumeArtifact:
    path: str
    mime_type: str | None = None
    label: str | None = None

    @property
    def exists(self) -> bool:
        return bool(self.path) and Path(self.path).exists()


@dataclass
class JobContext:
    job_id: str | None = None
    url: str | None = None
    title: str | None = None
    company: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Field:
    label: str
    field_type: FieldType = FieldType.TEXT
    selector: str | None = None
    name: str | None = None
    required: bool = False
    options: list[str] = field(default_factory=list)
    value: Any = None
    sensitive: bool = False
    normalized_question: str | None = None
    confidence: float = 0.0


@dataclass
class MappedField:
    field: Field
    profile_key: str | None = None
    value: Any = None
    source: str = "unknown"
    confidence: float = 0.0
    requires_review: bool = False


@dataclass
class UnknownField:
    field: Field
    reason: str = "unmapped"


@dataclass
class FieldMemoryEntry:
    original_question: str
    normalized_question: str
    answer: Any
    answer_type: str
    platform: str | None = None
    source_url: str | None = None
    confidence: float = 1.0
    sensitive: bool = False
    last_used_at: str | None = None


@dataclass
class ValidationResult:
    ok: bool
    missing_required: list[Field] = field(default_factory=list)
    needs_review: list[Field] = field(default_factory=list)
    message: str | None = None


@dataclass
class SubmitResult:
    ok: bool
    submitted: bool = False
    message: str | None = None


@dataclass
class FillResult:
    ok: bool
    known_fields: list[MappedField] = field(default_factory=list)
    unknown_fields: list[UnknownField] = field(default_factory=list)
    uploaded_resume: bool = False
    validation: ValidationResult | None = None
    submit: SubmitResult | None = None
    screenshots: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)


@dataclass
class RunHistory:
    run_id: str
    job_id: str | None
    resume_id: str | None
    platform: str
    mode: AutomationMode
    status: RunStatus
    detected_fields: list[Field] = field(default_factory=list)
    unmapped_fields: list[UnknownField] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
