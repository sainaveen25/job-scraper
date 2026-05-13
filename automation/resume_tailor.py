"""
automation/resume_tailor.py
============================
Domain-aware resume tailoring powered by the ProviderRouter.

This module:
  - Builds a structured, non-software-biased prompt from ResumeTailorInput.
  - Routes the prompt through ProviderRouter (BYOK or managed fallback).
  - Parses the AI response into ResumeSection objects.
  - Returns a ResumeTailorOutput with provider/model/byok metadata.

The existing ResumeTailorOutput contract is extended with providerUsed,
modelUsed, usedByok — fully backward-compatible.
"""
from __future__ import annotations

import re
import logging
from typing import Any

from automation.ai.adapters.base import AIErrorCode
from automation.ai.router import ProviderRouter
from automation.resume_contract import (
    ResumeError,
    ResumeErrorCode,
    ResumeExportMeta,
    ResumeSection,
    ResumeTailorInput,
    ResumeTailorOutput,
    build_resume_error,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(inp: ResumeTailorInput) -> str:
    """
    Build a structured, domain-agnostic tailoring prompt.

    The prompt is intentionally non-software-biased:
      - uses inp.target_domain as the primary context
      - skips "tech stack" framing for non-tech domains
      - formats bullet style appropriate to the domain
    """
    sections: list[str] = []

    # Role + domain context
    sections.append(
        f"You are an expert resume writer specializing in {inp.target_domain.replace('_', ' ')} roles."
    )
    sections.append(
        f"Tailor the following resume for the role of '{inp.job_title}'. "
        "Write in a professional, ATS-friendly style for this specific domain. "
        "Do NOT assume the role is in software engineering unless the domain indicates it. "
        "Focus on metrics, impact, and terminology relevant to the target domain."
    )

    # Job description
    if inp.description_text:
        sections.append(
            "## Job Description (use this to tailor the resume):\n" + inp.description_text[:3000]
        )

    # User profile
    profile_lines: list[str] = []
    if inp.full_name:
        profile_lines.append(f"Name: {inp.full_name}")
    if inp.email:
        profile_lines.append(f"Email: {inp.email}")
    if inp.linkedin_url:
        profile_lines.append(f"LinkedIn: {inp.linkedin_url}")
    if inp.github_url:
        profile_lines.append(f"GitHub: {inp.github_url}")
    if inp.portfolio_url:
        profile_lines.append(f"Portfolio: {inp.portfolio_url}")
    if profile_lines:
        sections.append("## Candidate Contact:\n" + "\n".join(profile_lines))

    # Skills
    if inp.skills:
        sections.append("## Skills:\n" + ", ".join(inp.skills))

    # Work experience
    if inp.work_experience:
        exp_parts = []
        for exp in inp.work_experience:
            title = exp.get("title", "")
            company = exp.get("company", "")
            dates = f"{exp.get('startDate', '')} – {exp.get('endDate', 'Present')}"
            bullets = exp.get("bullets") or []
            desc = exp.get("description", "")
            part = f"{title} @ {company} ({dates})"
            if bullets:
                part += "\n" + "\n".join(f"  • {b}" for b in bullets)
            elif desc:
                part += f"\n  {desc}"
            exp_parts.append(part)
        sections.append("## Work Experience:\n" + "\n\n".join(exp_parts))

    # Education
    if inp.education:
        edu_parts = []
        for edu in inp.education:
            degree = edu.get("degree", "")
            field = edu.get("field", "")
            institution = edu.get("institution", "")
            dates = f"{edu.get('startDate', '')} – {edu.get('endDate', '')}"
            edu_parts.append(f"{degree} in {field} — {institution} ({dates})".strip(" —()"))
        sections.append("## Education:\n" + "\n".join(edu_parts))

    # Base resume content (for tailored variant)
    if inp.selected_resume_content:
        sections.append(
            "## Base Resume (use this as the starting point; tailor to the job):\n"
            + inp.selected_resume_content[:4000]
        )

    # Output instructions
    resume_kind_label = "tailored" if inp.resume_kind == "tailored" else "base"
    sections.append(
        f"## Output Instructions:\n"
        f"Generate a {resume_kind_label} resume in clean Markdown format.\n"
        f"Structure it with these sections (use ## heading for each):\n"
        f"  1. Summary (3–4 sentences tailored to the role and domain)\n"
        f"  2. Skills (grouped by relevance to the job description)\n"
        f"  3. Work Experience (most recent first, bullet-point achievements)\n"
        f"  4. Education\n"
        f"  5. (Optional) Certifications, Publications, Awards — only if present in the profile\n"
        f"\n"
        f"Rules:\n"
        f"  - Use specific, quantified achievements where possible.\n"
        f"  - Match keywords from the job description naturally.\n"
        f"  - Do not fabricate experience or education.\n"
        f"  - Do not include placeholder text.\n"
        f"  - Output ONLY the resume Markdown, no preamble or explanation.\n"
    )

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE)


def _parse_sections(markdown: str) -> list[ResumeSection]:
    """
    Split a markdown resume into ResumeSection objects by ## headings.

    If no headings are found, the entire text is returned as a single
    "full_resume" section.
    """
    if not markdown:
        return []

    _KNOWN_TYPES = {
        "summary": "summary",
        "skills": "skills",
        "work experience": "experience",
        "experience": "experience",
        "education": "education",
        "certifications": "certifications",
        "publications": "publications",
        "awards": "awards",
        "projects": "projects",
    }

    headings = list(_HEADING_RE.finditer(markdown))
    if not headings:
        return [ResumeSection(section_type="full_resume", heading="Resume", content=markdown.strip())]

    sections: list[ResumeSection] = []
    for i, match in enumerate(headings):
        heading_text = match.group(1).strip()
        start = match.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(markdown)
        content = markdown[start:end].strip()
        section_type = _KNOWN_TYPES.get(heading_text.lower(), "custom")
        sections.append(ResumeSection(
            section_type=section_type,
            heading=heading_text,
            content=content,
        ))
    return sections


# ---------------------------------------------------------------------------
# Error code mapping
# ---------------------------------------------------------------------------

_AI_TO_RESUME_ERROR: dict[str, ResumeErrorCode] = {
    AIErrorCode.RATE_LIMITED: ResumeErrorCode.RATE_LIMITED,
    AIErrorCode.CREDITS_EXHAUSTED: ResumeErrorCode.CREDITS_EXHAUSTED,
    AIErrorCode.EMPTY_RESPONSE: ResumeErrorCode.AI_EMPTY,
    AIErrorCode.PROVIDER_UNAVAILABLE: ResumeErrorCode.AI_UPSTREAM,
    AIErrorCode.INVALID_API_KEY: ResumeErrorCode.INVALID_INPUT,
    AIErrorCode.MODEL_NOT_AVAILABLE: ResumeErrorCode.AI_UPSTREAM,
    AIErrorCode.UNKNOWN: ResumeErrorCode.UNKNOWN,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def tailor_resume(
    inp: ResumeTailorInput,
    *,
    router: ProviderRouter | None = None,
    user_tier: str = "free",
    fallback: bool = True,
) -> ResumeTailorOutput:
    """
    Tailor a resume using the AI ProviderRouter.

    Args:
        inp:        Validated ResumeTailorInput.
        router:     ProviderRouter instance (created with defaults if None).
        user_tier:  "free" or "paid" — affects managed key limits.
        fallback:   Whether to fall back to managed key if no BYOK found.

    Returns:
        A ResumeTailorOutput — always returns, never raises.
    """
    # Validate input
    errors = inp.validate()
    if errors:
        return _error_output(inp, ResumeErrorCode.INVALID_INPUT, "; ".join(errors))

    # Build router with defaults if not injected
    if router is None:
        router = ProviderRouter()

    # Build prompt
    prompt = _build_prompt(inp)

    # Route through provider system
    ai_resp = router.route(
        user_id=inp.user_id,
        feature_type="resume_tailor",
        prompt=prompt,
        user_tier=user_tier,
        fallback=fallback,
    )

    # Build export metadata
    meta = ResumeExportMeta(
        resume_kind=inp.resume_kind,
        format=inp.preferred_format,
        job_title=inp.job_title,
        target_domain=inp.target_domain,
    )

    if not ai_resp.success:
        resume_err_code = _AI_TO_RESUME_ERROR.get(
            ai_resp.error_code or "", ResumeErrorCode.UNKNOWN
        )
        return ResumeTailorOutput(
            ok=False,
            export_meta=meta,
            error=ResumeError(
                code=resume_err_code,
                user_message=ai_resp.user_message or "Resume generation failed.",
                log_detail=ai_resp.error_code,
            ),
            provider_used=ai_resp.provider_used,
            model_used=ai_resp.model_used,
            used_byok=ai_resp.used_byok,
        )

    raw_content = ai_resp.output or ""
    sections = _parse_sections(raw_content)

    return ResumeTailorOutput(
        ok=True,
        export_meta=meta,
        sections=sections,
        raw_content=raw_content,
        provider_used=ai_resp.provider_used,
        model_used=ai_resp.model_used,
        used_byok=ai_resp.used_byok,
    )


def _error_output(
    inp: ResumeTailorInput,
    code: ResumeErrorCode,
    detail: str,
) -> ResumeTailorOutput:
    from automation.resume_contract import _USER_MESSAGES
    return ResumeTailorOutput(
        ok=False,
        export_meta=ResumeExportMeta(
            resume_kind=inp.resume_kind,
            job_title=inp.job_title,
            target_domain=inp.target_domain,
        ),
        error=ResumeError(
            code=code,
            user_message=_USER_MESSAGES.get(code, "An error occurred."),
            log_detail=detail,
        ),
        provider_used="",
        model_used="",
        used_byok=False,
    )
