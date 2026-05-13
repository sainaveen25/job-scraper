"""
tests/automation/test_apply_session_contract.py
================================================
Tests for the enriched Apply Session payload — resumeKind, domain,
matchScore / scoreSource, profileLinks, selectedResumeMeta, descriptionPreview,
and platformSupport in the extension handoff.
"""
from __future__ import annotations

import pytest

from automation.apply_sessions import ApplySessionService, ApplySessionStore
from automation.memory import FieldMemoryStore


def _service(tmp_path):
    return ApplySessionService(
        store=ApplySessionStore(tmp_path / "sessions.json"),
        memory_store=FieldMemoryStore(tmp_path / "memory.json"),
        token_secret="test-secret",
    )


def _auth():
    return {"userId": "user_123", "sessionToken": "applymate-session-token"}


def _base_payload(**overrides):
    payload = {
        "auth": _auth(),
        "job": {
            "id": "job_1",
            "userId": "user_123",
            "title": "Senior Data Engineer",
            "company": "DataCo",
            "applyUrl": "https://boards.greenhouse.io/dataco/jobs/123",
            "description": "Build ETL pipelines using Spark and Databricks.",
            "category": "data_engineering",
        },
        "resume": {
            "id": "resume_1",
            "userId": "user_123",
            "fileName": "ada_resume.pdf",
            "mimeType": "application/pdf",
        },
        "profile": {
            "userId": "user_123",
            "first_name": "Ada",
            "email": "ada@example.com",
            "linkedin_url": "https://linkedin.com/in/ada",
            "github_url": "https://github.com/ada",
            "portfolio_url": "https://ada.dev",
        },
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# resumeKind field
# ---------------------------------------------------------------------------

def test_create_session_with_resume_kind_tailored(tmp_path):
    service = _service(tmp_path)
    result = service.create(_base_payload(resumeKind="tailored"))
    assert result["resumeKind"] == "tailored"


def test_create_session_with_resume_kind_base(tmp_path):
    service = _service(tmp_path)
    result = service.create(_base_payload(resumeKind="base"))
    assert result["resumeKind"] == "base"


def test_create_session_resume_kind_defaults_to_none_when_missing(tmp_path):
    service = _service(tmp_path)
    result = service.create(_base_payload())
    # When not provided, should be None (not an error).
    assert "resumeKind" in result


# ---------------------------------------------------------------------------
# domain / category field
# ---------------------------------------------------------------------------

def test_create_session_domain_from_payload(tmp_path):
    service = _service(tmp_path)
    result = service.create(_base_payload(domain="data_engineering"))
    assert result["domain"] == "data_engineering"


def test_create_session_domain_falls_back_to_job_category(tmp_path):
    service = _service(tmp_path)
    result = service.create(_base_payload())  # job has "category": "data_engineering"
    assert result["domain"] == "data_engineering"


# ---------------------------------------------------------------------------
# matchScore / scoreSource
# ---------------------------------------------------------------------------

def test_create_session_match_score_normalised_from_fraction(tmp_path):
    service = _service(tmp_path)
    result = service.create(_base_payload(matchScore=0.87))
    assert result["matchScore"] == 87.0
    assert result["scoreSource"] == "provided"


def test_create_session_match_score_from_job_ats_score(tmp_path):
    service = _service(tmp_path)
    payload = _base_payload()
    payload["job"]["atsScore"] = 92
    result = service.create(payload)
    assert result["matchScore"] == 92.0
    assert result["scoreSource"] == "ats_match"


def test_create_session_match_score_from_job_relevance_score(tmp_path):
    service = _service(tmp_path)
    payload = _base_payload()
    payload["job"]["relevanceScore"] = 0.75
    result = service.create(payload)
    assert result["matchScore"] == 75.0
    assert result["scoreSource"] == "relevance"


def test_create_session_match_score_none_when_absent(tmp_path):
    service = _service(tmp_path)
    result = service.create(_base_payload())
    assert result["matchScore"] is None
    assert result["scoreSource"] is None


# ---------------------------------------------------------------------------
# Handoff payload enrichment
# ---------------------------------------------------------------------------

def test_handoff_payload_includes_job_title_and_company(tmp_path):
    service = _service(tmp_path)
    created = service.create(_base_payload(resumeKind="tailored"))
    handoff = service.handoff(created["sessionId"], {"auth": _auth()})
    ext = handoff["extensionHandoff"]

    assert ext["jobTitle"] == "Senior Data Engineer"
    assert ext["company"] == "DataCo"


def test_handoff_payload_includes_resume_kind(tmp_path):
    service = _service(tmp_path)
    created = service.create(_base_payload(resumeKind="tailored"))
    handoff = service.handoff(created["sessionId"], {"auth": _auth()})
    ext = handoff["extensionHandoff"]

    assert ext["resumeKind"] == "tailored"


def test_handoff_payload_includes_match_score(tmp_path):
    service = _service(tmp_path)
    payload = _base_payload(matchScore=0.9)
    created = service.create(payload)
    handoff = service.handoff(created["sessionId"], {"auth": _auth()})
    ext = handoff["extensionHandoff"]

    assert ext["matchScore"] == 90.0
    assert ext["scoreSource"] == "provided"


def test_handoff_payload_includes_domain(tmp_path):
    service = _service(tmp_path)
    created = service.create(_base_payload(domain="data_engineering"))
    handoff = service.handoff(created["sessionId"], {"auth": _auth()})
    ext = handoff["extensionHandoff"]

    assert ext["domain"] == "data_engineering"


def test_handoff_payload_includes_profile_links(tmp_path):
    service = _service(tmp_path)
    created = service.create(_base_payload())
    handoff = service.handoff(created["sessionId"], {"auth": _auth()})
    ext = handoff["extensionHandoff"]

    links = ext["profileLinks"]
    assert links["linkedinUrl"] == "https://linkedin.com/in/ada"
    assert links["githubUrl"] == "https://github.com/ada"
    assert links["portfolioUrl"] == "https://ada.dev"


def test_handoff_payload_includes_selected_resume_meta(tmp_path):
    service = _service(tmp_path)
    created = service.create(_base_payload(resumeKind="tailored"))
    handoff = service.handoff(created["sessionId"], {"auth": _auth()})
    ext = handoff["extensionHandoff"]

    meta = ext["selectedResumeMeta"]
    assert meta["id"] == "resume_1"
    assert meta["fileName"] == "ada_resume.pdf"
    assert meta["fileType"] == "pdf"


def test_handoff_payload_includes_platform_support_map(tmp_path):
    service = _service(tmp_path)
    created = service.create(_base_payload())
    handoff = service.handoff(created["sessionId"], {"auth": _auth()})
    ext = handoff["extensionHandoff"]

    platform_support = ext["platformSupport"]
    assert isinstance(platform_support, dict)
    # greenhouse should be detected from the apply URL.
    assert "greenhouse" in platform_support
    # generic must always be present.
    assert platform_support.get("generic") is True


def test_handoff_payload_includes_description_preview(tmp_path):
    service = _service(tmp_path)
    created = service.create(_base_payload())
    handoff = service.handoff(created["sessionId"], {"auth": _auth()})
    ext = handoff["extensionHandoff"]

    preview = ext.get("descriptionPreview")
    assert preview is not None
    assert "ETL" in preview or "pipelines" in preview or len(preview) > 0


# ---------------------------------------------------------------------------
# applicationAnswers field
# ---------------------------------------------------------------------------

def test_create_session_application_answers_stored(tmp_path):
    service = _service(tmp_path)
    payload = _base_payload()
    payload["applicationAnswers"] = [{"question": "Are you authorized?", "answer": "Yes"}]
    result = service.create(payload)
    assert result["applicationAnswers"] == [{"question": "Are you authorized?", "answer": "Yes"}]


def test_create_session_application_answers_defaults_empty(tmp_path):
    service = _service(tmp_path)
    result = service.create(_base_payload())
    assert result["applicationAnswers"] == []


# ---------------------------------------------------------------------------
# Persistence round-trip
# ---------------------------------------------------------------------------

def test_session_round_trip_preserves_new_fields(tmp_path):
    service = _service(tmp_path)
    payload = _base_payload(resumeKind="tailored", domain="data_engineering", matchScore=0.85)
    created = service.create(payload)
    session_id = created["sessionId"]

    # Reload from disk.
    service2 = _service(tmp_path)
    fetched = service2.get(session_id, {"auth": _auth()})

    assert fetched["resumeKind"] == "tailored"
    assert fetched["domain"] == "data_engineering"
    assert fetched["matchScore"] == 85.0
    assert fetched["scoreSource"] == "provided"
