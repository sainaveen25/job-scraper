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
    READY_FOR_NEXT = "ready_for_next"
    READY_FOR_SUBMIT = "ready_for_submit"
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
class RunLog:
    event: str
    message: str
    level: str = "info"
    step: int | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: dict[str, Any] = field(default_factory=dict)


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
class PageProgress:
    page_detected: str
    step: int = 1
    current_url: str | None = None
    page_title: str | None = None
    screenshot_path: str | None = None
    fields_found: list[Field] = field(default_factory=list)
    fields_autofilled: list[MappedField] = field(default_factory=list)
    unresolved_fields: list[UnknownField] = field(default_factory=list)
    required_missing: list[Field] = field(default_factory=list)
    ready_for_next: bool = False
    ready_for_submit: bool = False
    screenshots: list[str] = field(default_factory=list)
    logs: list[RunLog] = field(default_factory=list)


@dataclass
class FillResult:
    ok: bool
    known_fields: list[MappedField] = field(default_factory=list)
    unknown_fields: list[UnknownField] = field(default_factory=list)
    uploaded_resume: bool = False
    validation: ValidationResult | None = None
    submit: SubmitResult | None = None
    progress: PageProgress | None = None
    screenshots: list[str] = field(default_factory=list)
    logs: list[RunLog] = field(default_factory=list)


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
    logs: list[RunLog] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ApplySession:
    session_id: str
    user_id: str
    job: dict[str, Any]
    resume: dict[str, Any] | None = None
    profile: dict[str, Any] = field(default_factory=dict)
    field_memory: list[FieldMemoryEntry] = field(default_factory=list)
    platform: str = "generic"
    status: str = "created"
    progress: dict[str, Any] = field(default_factory=dict)
    unresolved_fields: list[UnknownField] = field(default_factory=list)
    run_history: list[RunLog] = field(default_factory=list)
    current_url: str | None = None
    page_title: str | None = None
    screenshot_path: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_client_payload(self, *, extension_token: str | None = None, client: str = "web") -> dict[str, Any]:
        payload = {
            "sessionId": self.session_id,
            "job": self.job,
            "resume": self.resume,
            "profile": self.profile,
            "fieldMemory": [asdict(entry) for entry in self.field_memory],
            "platform": self.platform,
            "status": self.status,
            "progress": self.progress,
            "unresolvedFields": [asdict(item) for item in self.unresolved_fields],
            "runHistory": [asdict(item) for item in self.run_history],
            "pageTitle": self.page_title,
            "currentUrl": self.current_url,
            "screenshotPath": self.screenshot_path,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "client": client,
            "extensionOptional": True,
            "manualAssistAvailable": True,
            "submitRequiresExplicitConfirmation": True,
        }
        if extension_token:
            payload["extensionToken"] = extension_token
        return payload

    def to_extension_payload(self, *, extension_token: str | None = None) -> dict[str, Any]:
        return self.to_client_payload(extension_token=extension_token, client="extension")
