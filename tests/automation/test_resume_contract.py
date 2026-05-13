"""
tests/automation/test_resume_contract.py
=========================================
Unit tests for automation.resume_contract.
"""
from __future__ import annotations

import pytest

from automation.resume_contract import (
    ResumeErrorCode,
    ResumeError,
    ResumeSection,
    ResumeExportMeta,
    ResumeTailorInput,
    ResumeTailorOutput,
    build_resume_error,
    validation_error_output,
)


def test_build_resume_error_classifies_rate_limit_429():
    err = build_resume_error("HTTP 429 Too Many Requests", log=False)
    assert err.code == ResumeErrorCode.RATE_LIMITED


def test_build_resume_error_classifies_credit_exhausted():
    err = build_resume_error("402 Payment Required: quota exceeded", log=False)
    assert err.code == ResumeErrorCode.CREDITS_EXHAUSTED


def test_build_resume_error_classifies_ai_empty():
    err = build_resume_error("AI returned empty content", log=False)
    assert err.code == ResumeErrorCode.AI_EMPTY


def test_build_resume_error_classifies_ai_upstream():
    err = build_resume_error("upstream timeout from OpenAI", log=False)
    assert err.code == ResumeErrorCode.AI_UPSTREAM


def test_build_resume_error_classifies_invalid_input():
    err = build_resume_error("missing required field: job_title", log=False)
    assert err.code == ResumeErrorCode.INVALID_INPUT


def test_build_resume_error_classifies_unknown():
    err = build_resume_error("some completely unrecognized error", log=False)
    assert err.code == ResumeErrorCode.UNKNOWN


def test_resume_error_to_dict_excludes_log_detail():
    err = ResumeError(
        code=ResumeErrorCode.AI_EMPTY,
        user_message="The AI returned nothing.",
        log_detail="Raw exception: blah blah internal trace",
    )
    d = err.to_dict()
    assert "logDetail" not in d
    assert "log_detail" not in d
    assert d["code"] == "ai_empty"


def test_build_resume_error_force_code():
    err = build_resume_error("some error", code=ResumeErrorCode.CREDITS_EXHAUSTED, log=False)
    assert err.code == ResumeErrorCode.CREDITS_EXHAUSTED


def test_export_meta_includes_resume_kind():
    meta = ResumeExportMeta(resume_kind="tailored", job_title="Data Engineer", target_domain="data_engineering")
    d = meta.to_dict()
    assert d["resumeKind"] == "tailored"
    assert d["targetDomain"] == "data_engineering"
    assert "generatedAt" in d


def test_tailor_input_validates_ok():
    inp = ResumeTailorInput(
        job_title="Electrical Engineer",
        description_text="Design power systems.",
        target_domain="electrical_engineering",
        user_id="user_abc",
    )
    assert inp.validate() == []


def test_tailor_input_catches_missing_job_title():
    inp = ResumeTailorInput(
        job_title="", description_text="desc", target_domain="foo", user_id="u"
    )
    assert any("job_title" in e for e in inp.validate())


def test_tailor_input_catches_missing_description():
    inp = ResumeTailorInput(
        job_title="Civil Engineer", description_text="", target_domain="civil", user_id="u"
    )
    assert any("description_text" in e for e in inp.validate())


def test_tailor_input_to_dict_camel_case():
    inp = ResumeTailorInput(
        job_title="Data Analyst",
        description_text="Analyze datasets.",
        target_domain="data_analytics",
        user_id="u1",
        resume_kind="tailored",
        linkedin_url="https://linkedin.com/in/ada",
        skills=["Python", "SQL"],
    )
    d = inp.to_dict()
    assert d["jobTitle"] == "Data Analyst"
    assert d["resumeKind"] == "tailored"
    assert d["linkedinUrl"] == "https://linkedin.com/in/ada"
    assert "Python" in d["skills"]


def test_tailor_input_non_software_domain():
    inp = ResumeTailorInput(
        job_title="Relay Protection Designer",
        description_text="Design protective relay schemes.",
        target_domain="power_systems",
        user_id="u2",
        resume_kind="base",
    )
    assert inp.validate() == []
    assert inp.to_dict()["targetDomain"] == "power_systems"


def test_tailor_output_success_to_dict():
    meta = ResumeExportMeta(resume_kind="tailored")
    sections = [ResumeSection(section_type="summary", heading="Summary", content="Experienced engineer.")]
    out = ResumeTailorOutput(ok=True, export_meta=meta, sections=sections, raw_content="# Summary")
    d = out.to_dict()
    assert d["ok"] is True
    assert d["error"] is None
    assert len(d["sections"]) == 1


def test_tailor_output_error_to_dict():
    meta = ResumeExportMeta(resume_kind="tailored")
    err = build_resume_error("429 rate limit", log=False)
    out = ResumeTailorOutput(ok=False, export_meta=meta, error=err)
    d = out.to_dict()
    assert d["ok"] is False
    assert d["error"]["code"] == "rate_limited"


def test_validation_error_output_helper():
    out = validation_error_output(
        ["job_title is required"],
        resume_kind="tailored",
        target_domain="mechanical_engineering",
    )
    assert out.ok is False
    assert out.error.code == ResumeErrorCode.INVALID_INPUT
    assert out.export_meta.target_domain == "mechanical_engineering"
