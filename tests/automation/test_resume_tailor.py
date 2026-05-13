"""
tests/automation/test_resume_tailor.py
=======================================
Tests for automation.resume_tailor — prompt building, section parsing,
provider metadata in output, and error mapping.

No real API calls — the router is injected with a mock.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from automation.ai.adapters.base import AIResponse, AIErrorCode
from automation.resume_contract import ResumeTailorInput, ResumeErrorCode
from automation.resume_tailor import _build_prompt, _parse_sections, tailor_resume


def _make_inp(**overrides) -> ResumeTailorInput:
    defaults = dict(
        job_title="Senior Data Engineer",
        description_text="Build ETL pipelines using Spark and Databricks.",
        target_domain="data_engineering",
        user_id="user_tailor_test",
        resume_kind="tailored",
        full_name="Ada Lovelace",
        email="ada@example.com",
        skills=["Python", "Spark", "SQL"],
        work_experience=[{
            "title": "Data Engineer",
            "company": "DataCo",
            "startDate": "2022-01",
            "endDate": "Present",
            "bullets": ["Built 10 ETL pipelines", "Reduced data latency by 40%"],
        }],
        linkedin_url="https://linkedin.com/in/ada",
    )
    defaults.update(overrides)
    return ResumeTailorInput(**defaults)


def _mock_router(output: str | None, success: bool = True, error_code: str | None = None, used_byok: bool = False) -> MagicMock:
    router = MagicMock()
    router.route.return_value = AIResponse(
        success=success,
        output=output,
        provider_used="gemini" if not used_byok else "openai",
        model_used="gemini-2.0-flash-lite" if not used_byok else "gpt-4o-mini",
        used_byok=used_byok,
        error_code=error_code,
        user_message="Error." if not success else None,
    )
    return router


# ---------------------------------------------------------------------------
# Prompt builder tests
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_prompt_contains_job_title(self):
        inp = _make_inp()
        prompt = _build_prompt(inp)
        assert "Senior Data Engineer" in prompt

    def test_prompt_contains_domain(self):
        inp = _make_inp(target_domain="electrical_engineering")
        prompt = _build_prompt(inp)
        assert "electrical engineering" in prompt.lower()

    def test_prompt_contains_description_text(self):
        inp = _make_inp()
        prompt = _build_prompt(inp)
        assert "ETL pipelines" in prompt

    def test_prompt_does_not_assume_software_for_non_tech_domain(self):
        inp = _make_inp(target_domain="civil_engineering", job_title="Structural Engineer")
        prompt = _build_prompt(inp)
        # Should mention civil engineering context
        assert "civil engineering" in prompt.lower()

    def test_prompt_contains_skills(self):
        inp = _make_inp(skills=["Spark", "SQL", "Hadoop"])
        prompt = _build_prompt(inp)
        assert "Spark" in prompt
        assert "SQL" in prompt

    def test_prompt_contains_work_experience_bullets(self):
        inp = _make_inp()
        prompt = _build_prompt(inp)
        assert "Built 10 ETL pipelines" in prompt

    def test_prompt_contains_linkedin_url(self):
        inp = _make_inp()
        prompt = _build_prompt(inp)
        assert "linkedin.com/in/ada" in prompt

    def test_prompt_uses_base_resume_content_when_provided(self):
        inp = _make_inp(selected_resume_content="## Summary\nExperienced engineer.", resume_kind="tailored")
        prompt = _build_prompt(inp)
        assert "Experienced engineer." in prompt


# ---------------------------------------------------------------------------
# Section parser tests
# ---------------------------------------------------------------------------

class TestParseSections:
    def test_parses_summary_section(self):
        md = "## Summary\nI am a data engineer.\n\n## Skills\nPython, SQL"
        sections = _parse_sections(md)
        assert any(s.section_type == "summary" for s in sections)
        assert any(s.section_type == "skills" for s in sections)

    def test_parses_experience_section(self):
        md = "## Work Experience\n• Built ETL pipelines\n\n## Education\nBS Computer Science"
        sections = _parse_sections(md)
        assert any(s.section_type == "experience" for s in sections)
        assert any(s.section_type == "education" for s in sections)

    def test_no_headings_returns_full_resume_section(self):
        md = "Just a plain text resume with no headers at all."
        sections = _parse_sections(md)
        assert len(sections) == 1
        assert sections[0].section_type == "full_resume"

    def test_empty_markdown_returns_empty_list(self):
        sections = _parse_sections("")
        assert sections == []

    def test_custom_section_type(self):
        md = "## Certifications\nAWS Certified Engineer"
        sections = _parse_sections(md)
        assert any(s.section_type == "certifications" for s in sections)


# ---------------------------------------------------------------------------
# tailor_resume integration tests (mocked router)
# ---------------------------------------------------------------------------

class TestTailorResume:
    def test_success_output_has_sections(self):
        mock_router = _mock_router(
            "## Summary\nGreat engineer.\n\n## Skills\nPython, Spark",
            success=True,
        )
        inp = _make_inp()
        out = tailor_resume(inp, router=mock_router)
        assert out.ok is True
        assert len(out.sections) >= 1
        assert out.raw_content is not None

    def test_success_includes_provider_metadata(self):
        mock_router = _mock_router("## Summary\nGreat.", success=True, used_byok=True)
        out = tailor_resume(_make_inp(), router=mock_router)
        assert out.provider_used == "openai"
        assert out.model_used == "gpt-4o-mini"
        assert out.used_byok is True

    def test_managed_provider_sets_used_byok_false(self):
        mock_router = _mock_router("## Summary\nGreat.", success=True, used_byok=False)
        out = tailor_resume(_make_inp(), router=mock_router)
        assert out.used_byok is False

    def test_provider_metadata_in_to_dict(self):
        mock_router = _mock_router("## Summary\nGreat.", success=True, used_byok=True)
        out = tailor_resume(_make_inp(), router=mock_router)
        d = out.to_dict()
        assert "providerUsed" in d
        assert "modelUsed" in d
        assert "usedByok" in d
        assert d["usedByok"] is True

    def test_rate_limit_error_maps_correctly(self):
        mock_router = _mock_router(None, success=False, error_code=AIErrorCode.RATE_LIMITED)
        out = tailor_resume(_make_inp(), router=mock_router)
        assert out.ok is False
        assert out.error is not None
        assert out.error.code == ResumeErrorCode.RATE_LIMITED

    def test_credits_exhausted_error_maps_correctly(self):
        mock_router = _mock_router(None, success=False, error_code=AIErrorCode.CREDITS_EXHAUSTED)
        out = tailor_resume(_make_inp(), router=mock_router)
        assert out.error.code == ResumeErrorCode.CREDITS_EXHAUSTED

    def test_invalid_input_returns_error_without_calling_router(self):
        mock_router = MagicMock()
        inp = _make_inp(job_title="", description_text="")
        out = tailor_resume(inp, router=mock_router)
        assert out.ok is False
        mock_router.route.assert_not_called()

    def test_existing_resume_contract_tests_still_pass(self):
        """Confirm ResumeTailorOutput backward compat — existing fields still present."""
        mock_router = _mock_router("## Summary\nExperienced.", success=True)
        out = tailor_resume(_make_inp(), router=mock_router)
        d = out.to_dict()
        # All original fields must be present
        assert "ok" in d
        assert "exportMeta" in d
        assert "sections" in d
        assert "rawContent" in d
        assert "error" in d
