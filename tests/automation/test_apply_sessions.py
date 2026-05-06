import pytest

from automation.apply_sessions import ApplySessionAuthError, ApplySessionService, ApplySessionStore
from automation.memory import FieldMemoryStore


def _service(tmp_path):
    return ApplySessionService(
        store=ApplySessionStore(tmp_path / "sessions.json"),
        memory_store=FieldMemoryStore(tmp_path / "memory.json"),
        token_secret="test-secret",
    )


def _auth():
    return {"userId": "user_123", "sessionToken": "applymate-session-token"}


def _create_payload():
    return {
        "auth": _auth(),
        "job": {
            "id": "job_1",
            "userId": "user_123",
            "title": "Backend Engineer",
            "company": "Acme",
            "applyUrl": "https://jobs.lever.co/acme/123",
        },
        "resume": {"id": "resume_1", "userId": "user_123", "fileName": "backend.pdf", "mimeType": "application/pdf"},
        "profile": {"userId": "user_123", "first_name": "Ada", "email": "ada@example.com"},
        "savedAnswers": [
            {
                "originalQuestion": "Are you authorized to work in the United States?",
                "answer": "Yes",
                "answerType": "radio",
                "platform": "lever",
            }
        ],
    }


def test_apply_session_create_returns_website_first_payload(tmp_path):
    service = _service(tmp_path)

    result = service.create(_create_payload())

    assert result["sessionId"]
    assert "extensionToken" not in result
    assert result["client"] == "web"
    assert result["extensionOptional"]
    assert result["manualAssistAvailable"]
    assert result["webControlCenter"]["extensionRequired"] is False
    assert result["manualAssist"]["canUseWithoutExtension"]
    assert result["platform"] == "lever"
    assert result["job"]["title"] == "Backend Engineer"
    assert result["resume"]["id"] == "resume_1"
    assert result["profile"]["email"] == "ada@example.com"
    assert result["fieldMemory"][0]["answer"] == "Yes"
    assert result["unresolvedFields"] == []


def test_apply_session_validates_user_ownership(tmp_path):
    service = _service(tmp_path)
    payload = _create_payload()
    payload["resume"]["userId"] = "other_user"

    with pytest.raises(ApplySessionAuthError):
        service.create(payload)


def test_extension_token_can_fetch_session_without_user_session_token(tmp_path):
    service = _service(tmp_path)
    created = service.create(_create_payload(), issue_extension_token=True, client="extension")

    fetched = service.get(created["sessionId"], {"extensionToken": created["extensionToken"]})

    assert fetched["sessionId"] == created["sessionId"]
    assert fetched["client"] == "extension"
    assert fetched["job"]["id"] == "job_1"


def test_apply_session_handoff_attaches_resume_and_extension_route(tmp_path):
    service = _service(tmp_path)
    created = service.create(_create_payload())

    handoff = service.handoff(created["sessionId"], {"auth": _auth()})

    assert handoff["extensionToken"]
    assert handoff["extensionHandoff"]["route"] == "/api/extension/apply-session/handoff"
    assert handoff["extensionHandoff"]["installUrl"] == "/extension/install"
    assert handoff["extensionHandoff"]["applyUrl"] == "https://jobs.lever.co/acme/123"
    assert handoff["resumeUpload"]["fileType"] == "pdf"
    assert handoff["resumeUpload"]["uploadPreference"] == "pdf"


def test_fill_page_returns_browser_agnostic_manual_assist(tmp_path):
    service = _service(tmp_path)
    created = service.create(_create_payload())

    result = service.fill_page(
        created["sessionId"],
        {
            "auth": _auth(),
            "currentUrl": "https://jobs.lever.co/acme/123/apply",
            "pageTitle": "Apply",
            "hasNext": True,
            "fields": [
                {"label": "First Name", "selector": "#first", "type": "text", "required": True},
                {"label": "Email", "selector": "#email", "type": "text", "required": True},
                {"label": "Account password", "selector": "#password", "type": "password", "required": True},
            ],
        },
    )

    assert result["progress"]["page_title"] == "Apply"
    assert len(result["fieldsFilled"]) == 2
    assert result["fillInstructions"][0]["selector"] == "#first"
    assert result["manualAssist"]["mode"] == "browser_agnostic"
    assert result["manualAssist"]["steps"][0]["label"] == "First Name"
    assert result["webControlCenter"]["extensionRequired"] is False
    assert result["unresolvedFields"][0]["reason"] == "password_requires_manual_entry"
    assert not result["progress"]["ready_for_next"]


def test_manual_assist_matrix_preserves_job_resume_and_generic_fallback(tmp_path):
    service = _service(tmp_path)
    cases = [
        ("chrome", "https://boards.greenhouse.io/acme/jobs/123", "greenhouse"),
        ("safari", "https://jobs.lever.co/acme/123", "lever"),
        ("firefox", "https://builtin.com/job/acme/backend-engineer", "generic"),
    ]

    for browser, url, platform in cases:
        payload = _create_payload()
        payload["job"]["id"] = f"job_{browser}"
        payload["job"]["applyUrl"] = url
        created = service.create(payload, client=browser)
        filled = service.fill_page(
            created["sessionId"],
            {
                "auth": _auth(),
                "client": browser,
                "currentUrl": url,
                "pageTitle": f"{browser} application",
                "fields": [{"label": "Email", "selector": "#email", "type": "text", "required": True}],
            },
        )

        assert filled["client"] == browser
        assert filled["platform"] == platform
        assert filled["job"]["id"] == f"job_{browser}"
        assert filled["resume"]["id"] == "resume_1"
        assert filled["manualAssist"]["canUseWithoutExtension"]
        assert filled["webControlCenter"]["extensionRequired"] is False


def test_extension_flow_still_issues_optional_token_and_fill_instructions(tmp_path):
    service = _service(tmp_path)
    created = service.create(_create_payload(), issue_extension_token=True, client="extension")

    result = service.fill_page(
        created["sessionId"],
        {
            "extensionToken": created["extensionToken"],
            "fields": [{"label": "First Name", "selector": "#first", "type": "text"}],
        },
    )

    assert created["extensionToken"]
    assert result["client"] == "extension"
    assert result["fillInstructions"][0]["selector"] == "#first"
    assert result["manualAssist"]["canUseWithoutExtension"]


def test_extension_rejects_stale_page_session(tmp_path):
    service = _service(tmp_path)
    created = service.create(_create_payload(), issue_extension_token=True, client="extension")

    with pytest.raises(ApplySessionAuthError):
        service.fill_page(
            created["sessionId"],
            {
                "extensionToken": created["extensionToken"],
                "currentUrl": "https://boards.greenhouse.io/other/jobs/999",
                "fields": [{"label": "First Name", "selector": "#first", "type": "text"}],
            },
        )


def test_control_center_reports_real_page_state(tmp_path):
    service = _service(tmp_path)
    created = service.create(_create_payload())

    result = service.fill_page(
        created["sessionId"],
        {
            "auth": _auth(),
            "currentUrl": "https://jobs.lever.co/acme/123/apply",
            "fields": [{"label": "Email", "selector": "#email", "type": "text", "required": True}],
            "hasSubmit": True,
        },
    )

    center = result["webControlCenter"]
    assert center["pageUrl"] == "https://jobs.lever.co/acme/123/apply"
    assert center["platform"] == "lever"
    assert center["fieldsDetected"] == 1
    assert center["fieldsFilled"] == 1
    assert center["unresolvedFields"] == 0
    assert center["readyForSubmit"] is True


def test_save_answer_clears_matching_unresolved_field_and_updates_history(tmp_path):
    service = _service(tmp_path)
    created = service.create(_create_payload())
    filled = service.fill_page(
        created["sessionId"],
        {
            "auth": _auth(),
            "fields": [{"label": "What is your notice period?", "selector": "#notice", "type": "text", "required": True}],
        },
    )
    assert len(filled["unresolvedFields"]) == 1

    saved = service.save_answer(
        created["sessionId"],
        {
            "auth": _auth(),
            "label": "What is your notice period?",
            "answer": "Two weeks",
            "answerType": "text",
        },
    )

    assert saved["savedAnswer"]["answer"] == "Two weeks"
    assert saved["unresolvedFields"] == []
    assert saved["manualAssist"]["unresolvedFields"] == []
    assert saved["runHistory"][-1]["event"] == "answer_saved"


def test_save_answer_refuses_third_party_passwords(tmp_path):
    service = _service(tmp_path)
    created = service.create(_create_payload(), issue_extension_token=True, client="extension")

    with pytest.raises(ValueError):
        service.save_answer(
            created["sessionId"],
            {
                "extensionToken": created["extensionToken"],
                "label": "Employer site password",
                "answer": "plain-text-secret",
                "answerType": "password",
            },
        )


def test_profile_common_questions_power_autofill_without_sensitive_guessing(tmp_path):
    service = _service(tmp_path)
    payload = _create_payload()
    payload["profile"]["common_questions"] = {"years of python experience": "6"}
    payload["profile"]["sensitive_answer_rules"] = {
        "veteran status": {"approved": True, "value": "I decline to answer"}
    }
    created = service.create(payload, issue_extension_token=True, client="extension")

    result = service.fill_page(
        created["sessionId"],
        {
            "extensionToken": created["extensionToken"],
            "currentUrl": "https://jobs.lever.co/acme/123",
            "fields": [
                {"label": "Years of Python experience", "selector": "#python", "type": "text"},
                {"label": "Veteran status", "selector": "#veteran", "type": "select"},
                {"label": "Gender", "selector": "#gender", "type": "select"},
            ],
        },
    )

    assert [item["value"] for item in result["fieldsFilled"]] == ["6", "I decline to answer"]
    assert result["fieldsFilled"][1]["requiresReview"] is True
    assert result["unresolvedFields"][0]["reason"] == "sensitive_question_requires_review"


def test_submit_requires_explicit_confirmation(tmp_path):
    service = _service(tmp_path)
    created = service.create(_create_payload(), issue_extension_token=True, client="extension")

    blocked = service.submit(created["sessionId"], {"extensionToken": created["extensionToken"]})
    confirmed = service.submit(created["sessionId"], {"extensionToken": created["extensionToken"], "confirm": True})

    assert not blocked["ok"]
    assert blocked["error"] == "explicit_submit_confirmation_required"
    assert blocked["submitted"] is False
    assert confirmed["ok"]
    assert confirmed["submitted"] is False
    assert confirmed["submitInstruction"]["requiresExplicitConfirmation"]
    assert confirmed["runHistory"][-1]["event"] == "submit_confirmed"
