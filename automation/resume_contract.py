"""
resume_contract.py
==================
Backend data contract for resume generation, tailoring, and export.

This module defines:
  - ``ResumeErrorCode``     — categorised error codes returned to the frontend.
  - ``ResumeError``         — structured error object (user message + log detail kept separate).
  - ``ResumeSection``       — one structured section in a generated resume.
  - ``ResumeExportMeta``    — metadata attached to every export.
  - ``ResumeTailorInput``   — validated input contract for the tailor edge function.
  - ``ResumeTailorOutput``  — unified output contract (success or error).
  - ``build_resume_error``  — classify any Python exception into a ``ResumeError``.

Companion TypeScript interfaces live in ``extension/resume_contract.ts``.

AI Prompt Guidance (non-software-biased)
-----------------------------------------
When building prompts from ``ResumeTailorInput``:
  - Use ``target_domain`` (not "software engineer") as the primary context.
  - Use ``job_title`` as the specific role.
  - Use ``description_text`` as the clean JD — never raw HTML.
  - Do NOT assume the user is a software engineer.  Domains include:
    electrical, mechanical, civil, data, business analysis, biomedical, etc.
  - Tailor bullet points and section language to the specific domain.
  - For non-software domains, skip "tech stack" sections unless relevant.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error contract
# ---------------------------------------------------------------------------

class ResumeErrorCode(str, Enum):
    """Categorised error codes sent to the frontend."""

    RATE_LIMITED = "rate_limited"
    CREDITS_EXHAUSTED = "credits_exhausted"
    AI_EMPTY = "ai_empty"
    AI_UPSTREAM = "ai_upstream"
    INVALID_INPUT = "invalid_input"
    UNKNOWN = "unknown"


_USER_MESSAGES: dict[ResumeErrorCode, str] = {
    ResumeErrorCode.RATE_LIMITED: "You've hit the rate limit. Please wait a moment and try again.",
    ResumeErrorCode.CREDITS_EXHAUSTED: "You've used all available AI credits for this period. Please upgrade or wait for your credits to reset.",
    ResumeErrorCode.AI_EMPTY: "The AI returned an empty response. Please try again.",
    ResumeErrorCode.AI_UPSTREAM: "The AI service is temporarily unavailable. Please try again in a few seconds.",
    ResumeErrorCode.INVALID_INPUT: "Some required information is missing or invalid. Please check your profile and job details.",
    ResumeErrorCode.UNKNOWN: "An unexpected error occurred. Please try again.",
}


@dataclass
class ResumeError:
    """
    Structured error returned to the frontend.

    ``user_message`` is safe to display in the UI.
    ``log_detail``   is logged server-side only — never sent to the UI.
    """

    code: ResumeErrorCode
    user_message: str
    log_detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "userMessage": self.user_message,
        }


# ---------------------------------------------------------------------------
# Content contract
# ---------------------------------------------------------------------------

@dataclass
class ResumeSection:
    """
    One structured section of a generated resume.

    ``section_type`` maps to a known section kind:
      summary | experience | education | skills | projects |
      certifications | publications | awards | custom
    """

    section_type: str
    heading: str
    content: str  # Markdown or plain text

    def to_dict(self) -> dict[str, Any]:
        return {
            "sectionType": self.section_type,
            "heading": self.heading,
            "content": self.content,
        }


# ---------------------------------------------------------------------------
# Export metadata
# ---------------------------------------------------------------------------

@dataclass
class ResumeExportMeta:
    """Metadata attached to every resume export or generation result."""

    resume_kind: Literal["base", "tailored"]
    format: str = "markdown"   # markdown | pdf | docx | html
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    job_title: str | None = None
    target_domain: str | None = None
    ats_optimised: bool = True
    include_links: bool = True   # LinkedIn / GitHub / Portfolio when available

    def to_dict(self) -> dict[str, Any]:
        return {
            "resumeKind": self.resume_kind,
            "format": self.format,
            "generatedAt": self.generated_at,
            "jobTitle": self.job_title,
            "targetDomain": self.target_domain,
            "atsOptimised": self.ats_optimised,
            "includeLinks": self.include_links,
        }


# ---------------------------------------------------------------------------
# Tailor input contract
# ---------------------------------------------------------------------------

@dataclass
class ResumeTailorInput:
    """
    Full validated input for a resume-tailoring request.

    Validated by the backend before the AI prompt is built.
    Maps directly to the TypeScript ``ResumeTailorInput`` interface.
    """

    # Job context (required for tailoring)
    job_title: str
    description_text: str  # clean plain text — never raw HTML
    target_domain: str      # e.g. "data_engineering", "electrical_engineering"

    # User profile (required)
    user_id: str
    resume_kind: Literal["base", "tailored"] = "tailored"

    # Profile sections (optional but improve quality)
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    education: list[dict[str, Any]] = field(default_factory=list)
    work_experience: list[dict[str, Any]] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)

    # Links (included in export when provided)
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None

    # Selected base resume context (for tailored variant)
    selected_resume_id: str | None = None
    selected_resume_label: str | None = None
    selected_resume_content: str | None = None  # raw text of base resume

    # Extra options
    preferred_format: str = "markdown"  # markdown | pdf | docx

    def validate(self) -> list[str]:
        """Return a list of validation error messages (empty = valid)."""
        errors: list[str] = []
        if not self.job_title or not self.job_title.strip():
            errors.append("job_title is required")
        if not self.description_text or not self.description_text.strip():
            errors.append("description_text is required")
        if not self.target_domain or not self.target_domain.strip():
            errors.append("target_domain is required")
        if not self.user_id:
            errors.append("user_id is required")
        if self.resume_kind not in ("base", "tailored"):
            errors.append("resume_kind must be 'base' or 'tailored'")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "jobTitle": self.job_title,
            "descriptionText": self.description_text,
            "targetDomain": self.target_domain,
            "userId": self.user_id,
            "resumeKind": self.resume_kind,
            "fullName": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "education": self.education,
            "workExperience": self.work_experience,
            "skills": self.skills,
            "linkedinUrl": self.linkedin_url,
            "githubUrl": self.github_url,
            "portfolioUrl": self.portfolio_url,
            "selectedResumeId": self.selected_resume_id,
            "selectedResumeLabel": self.selected_resume_label,
            "preferredFormat": self.preferred_format,
        }


# ---------------------------------------------------------------------------
# Tailor output contract
# ---------------------------------------------------------------------------

@dataclass
class ResumeTailorOutput:
    """
    Unified output for the resume-tailor edge function.

    On success:  ``error`` is None, ``sections`` and ``raw_content`` are set.
    On failure:  ``error`` is set, ``sections`` and ``raw_content`` may be None.
    """

    export_meta: ResumeExportMeta
    sections: list[ResumeSection] = field(default_factory=list)
    raw_content: str | None = None    # Full markdown / docx / PDF content
    error: ResumeError | None = None
    ok: bool = True
    # Provider context (populated by resume_tailor.py / ProviderRouter)
    provider_used: str = ""
    model_used: str = ""
    used_byok: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "exportMeta": self.export_meta.to_dict(),
            "sections": [s.to_dict() for s in self.sections],
            "rawContent": self.raw_content,
            "error": self.error.to_dict() if self.error else None,
            "providerUsed": self.provider_used,
            "modelUsed": self.model_used,
            "usedByok": self.used_byok,
        }


# ---------------------------------------------------------------------------
# Error classifier
# ---------------------------------------------------------------------------

def build_resume_error(
    exc: Exception | str,
    *,
    code: ResumeErrorCode | None = None,
    log: bool = True,
) -> ResumeError:
    """
    Classify *exc* into a :class:`ResumeError` with a user-safe message.

    The raw technical detail is logged at ERROR level but is **never**
    included in the returned object (so it won't leak to the UI).

    Args:
        exc:  The exception or error string to classify.
        code: Force a specific error code (overrides auto-detection).
        log:  Whether to log the technical detail.  Set to False in tests.
    """
    detail = str(exc)

    if code is None:
        detail_lower = detail.lower()
        if "429" in detail or "rate limit" in detail_lower or "rate_limit" in detail_lower:
            code = ResumeErrorCode.RATE_LIMITED
        elif "402" in detail or "credit" in detail_lower or "quota" in detail_lower:
            code = ResumeErrorCode.CREDITS_EXHAUSTED
        elif "empty" in detail_lower or "no content" in detail_lower or detail.strip() == "":
            code = ResumeErrorCode.AI_EMPTY
        elif any(
            token in detail_lower
            for token in ("upstream", "timeout", "503", "502", "504", "connection", "openai", "anthropic")
        ):
            code = ResumeErrorCode.AI_UPSTREAM
        elif any(token in detail_lower for token in ("missing", "invalid", "required", "validation")):
            code = ResumeErrorCode.INVALID_INPUT
        else:
            code = ResumeErrorCode.UNKNOWN

    if log:
        logger.error("Resume generation error [%s]: %s", code.value, detail)

    return ResumeError(
        code=code,
        user_message=_USER_MESSAGES[code],
        log_detail=detail,
    )


# ---------------------------------------------------------------------------
# Helper — build output from validation errors
# ---------------------------------------------------------------------------

def validation_error_output(
    errors: list[str],
    *,
    resume_kind: Literal["base", "tailored"] = "tailored",
    job_title: str | None = None,
    target_domain: str | None = None,
) -> ResumeTailorOutput:
    """Return a failed :class:`ResumeTailorOutput` for input validation errors."""
    err = ResumeError(
        code=ResumeErrorCode.INVALID_INPUT,
        user_message=_USER_MESSAGES[ResumeErrorCode.INVALID_INPUT],
        log_detail="; ".join(errors),
    )
    return ResumeTailorOutput(
        ok=False,
        export_meta=ResumeExportMeta(
            resume_kind=resume_kind,
            job_title=job_title,
            target_domain=target_domain,
        ),
        error=err,
    )
