from __future__ import annotations

from typing import Any

from automation.apply_sessions import ApplySessionService
from automation.memory import FieldMemoryStore
from automation.profile_store import ProfileStore
from automation.resume_import import hydrate_profile_from_resume, preview_resume_profile_merge
from automation.runner import (
    continue_application,
    prepare_application,
    run_application,
    save_field_memory,
    submit_application,
)


_APPLY_SESSION_SERVICE = ApplySessionService()
_PROFILE_STORE = ProfileStore()
_FIELD_MEMORY_STORE = FieldMemoryStore()
_THEME_PREFERENCES: dict[str, str] = {}


def post_apply_prepare(payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/apply/prepare."""
    return prepare_application(payload)


def post_apply_run(payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/apply/run."""
    return run_application(payload)


def post_apply_continue(payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/apply/continue."""
    return continue_application(payload)


def post_apply_save_field_memory(payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/apply/save-answer."""
    return save_field_memory(payload)


def post_apply_save_answer(payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/apply/save-answer."""
    return save_field_memory(payload)


def post_apply_submit(payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/apply/submit."""
    return submit_application(payload)


def post_apply_session_create(payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/apply-session/create for the website flow."""
    return _APPLY_SESSION_SERVICE.create(payload, client="web")


def post_apply_session_handoff(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/apply-session/:id/extension-handoff."""
    return _APPLY_SESSION_SERVICE.handoff(session_id, {**payload, "client": "web"})


def get_apply_session(session_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Callable equivalent of GET /api/apply-session/:id for the website flow."""
    return _APPLY_SESSION_SERVICE.get(session_id, payload or {})


def post_apply_session_start(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/apply-session/:id/start for the website flow."""
    return _APPLY_SESSION_SERVICE.start(session_id, payload, client="web")


def post_apply_session_fill_page(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/apply-session/:id/fill-page for browser-agnostic assist."""
    return _APPLY_SESSION_SERVICE.fill_page(session_id, {**payload, "client": payload.get("client") or "web"})


def post_apply_session_continue(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/apply-session/:id/continue for the website flow."""
    return _APPLY_SESSION_SERVICE.continue_session(session_id, {**payload, "client": payload.get("client") or "web"})


def post_apply_session_save_answer(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/apply-session/:id/save-answer for the website flow."""
    return _APPLY_SESSION_SERVICE.save_answer(session_id, {**payload, "client": payload.get("client") or "web"})


def post_apply_session_submit(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/apply-session/:id/submit for explicit-confirm submit."""
    return _APPLY_SESSION_SERVICE.submit(session_id, {**payload, "client": payload.get("client") or "web"})


def post_extension_apply_session_create(payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/extension/apply-session/create."""
    return _APPLY_SESSION_SERVICE.create(payload, issue_extension_token=True, client="extension")


def post_extension_apply_session_handoff(payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/extension/apply-session/handoff."""
    session_id = str(payload.get("sessionId") or payload.get("session_id") or "")
    return _APPLY_SESSION_SERVICE.handoff(session_id, payload)


def get_extension_install() -> dict[str, Any]:
    """Stable extension install metadata route for web apps that previously hit a 404."""
    return {
        "ok": True,
        "installUrl": "/extension/install",
        "downloadUrl": "/extension/download",
        "packageName": "applymate-ai-extension",
        "manualAssistAvailable": True,
    }


def get_theme_preference(payload: dict[str, Any]) -> dict[str, Any]:
    user_id = str(payload.get("userId") or payload.get("user_id") or (payload.get("auth") or {}).get("userId") or "anonymous")
    return {"userId": user_id, "theme": _THEME_PREFERENCES.get(user_id, "system")}


def post_theme_preference(payload: dict[str, Any]) -> dict[str, Any]:
    user_id = str(payload.get("userId") or payload.get("user_id") or (payload.get("auth") or {}).get("userId") or "anonymous")
    theme = str(payload.get("theme") or "system")
    if theme not in {"light", "dark", "system"}:
        raise ValueError("theme must be light, dark, or system")
    _THEME_PREFERENCES[user_id] = theme
    return {"userId": user_id, "theme": theme, "status": "saved"}


def get_profile(user_id: str) -> dict[str, Any]:
    return {"userId": user_id, "profile": _PROFILE_STORE.load(user_id)}


def post_profile_update(payload: dict[str, Any]) -> dict[str, Any]:
    user_id = str(payload.get("userId") or payload.get("user_id") or (payload.get("auth") or {}).get("userId"))
    profile = _PROFILE_STORE.merge(user_id, dict(payload.get("profile") or payload), source="manual")
    return {"userId": user_id, "profile": profile, "status": "saved"}


def post_resume_import_preview(payload: dict[str, Any]) -> dict[str, Any]:
    return preview_resume_profile_merge(dict(payload.get("currentProfile") or {}), dict(payload.get("parsedResume") or {}))


def post_resume_import_hydrate(payload: dict[str, Any]) -> dict[str, Any]:
    user_id = str(payload.get("userId") or payload.get("user_id") or (payload.get("auth") or {}).get("userId"))
    return hydrate_profile_from_resume(
        user_id=user_id,
        parsed_resume=dict(payload.get("parsedResume") or {}),
        profile_store=_PROFILE_STORE,
        resume_path=payload.get("resumePath"),
        resume_id=payload.get("resumeId"),
    )


def get_questionnaire_status(user_id: str) -> dict[str, Any]:
    answers = [entry for entry in _FIELD_MEMORY_STORE.load() if not entry.sensitive]
    return {"userId": user_id, "answers": [entry.__dict__ for entry in answers], "status": "ready"}


def get_extension_apply_session(session_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Callable equivalent of GET /api/extension/apply-session/:id."""
    payload = payload or {}
    return _APPLY_SESSION_SERVICE.get(session_id, {**payload, "client": "extension"})


def post_extension_apply_session_start(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/extension/apply-session/:id/start."""
    return _APPLY_SESSION_SERVICE.start(session_id, payload, issue_extension_token=True, client="extension")


def post_extension_apply_session_fill_page(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/extension/apply-session/:id/fill-page."""
    return _APPLY_SESSION_SERVICE.fill_page(session_id, {**payload, "client": "extension"})


def post_extension_apply_session_continue(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/extension/apply-session/:id/continue."""
    return _APPLY_SESSION_SERVICE.continue_session(session_id, {**payload, "client": "extension"})


def post_extension_apply_session_save_answer(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/extension/apply-session/:id/save-answer."""
    return _APPLY_SESSION_SERVICE.save_answer(session_id, {**payload, "client": "extension"})


def post_extension_apply_session_submit(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Callable equivalent of POST /api/extension/apply-session/:id/submit."""
    return _APPLY_SESSION_SERVICE.submit(session_id, {**payload, "client": "extension"})


# ---------------------------------------------------------------------------
# AI Provider Management API
# ---------------------------------------------------------------------------

_AI_PROVIDER_STORE = None
_AI_USAGE_STORE = None
_AI_ROUTER = None


def _get_ai_provider_store():
    global _AI_PROVIDER_STORE
    if _AI_PROVIDER_STORE is None:
        from automation.ai.provider_store import UserAIProviderStore
        _AI_PROVIDER_STORE = UserAIProviderStore()
    return _AI_PROVIDER_STORE


def _get_ai_usage_store():
    global _AI_USAGE_STORE
    if _AI_USAGE_STORE is None:
        from automation.ai.usage_store import AIUsageStore
        _AI_USAGE_STORE = AIUsageStore()
    return _AI_USAGE_STORE


def _get_ai_router():
    global _AI_ROUTER
    if _AI_ROUTER is None:
        from automation.ai.router import ProviderRouter
        _AI_ROUTER = ProviderRouter(
            provider_store=_get_ai_provider_store(),
            usage_store=_get_ai_usage_store(),
        )
    return _AI_ROUTER


def _auth_user_id(payload: dict[str, Any]) -> str:
    auth = payload.get("auth") or {}
    return str(
        payload.get("userId") or payload.get("user_id")
        or auth.get("userId") or auth.get("user_id") or ""
    )


def get_ai_provider_status(payload: dict[str, Any]) -> dict[str, Any]:
    """
    GET /api/ai-providers
    Return the user's configured AI providers (masked — no API keys).
    """
    user_id = _auth_user_id(payload)
    if not user_id:
        return {"ok": False, "error": "Authenticated user required."}
    providers = _get_ai_provider_store().list_for_user(user_id)
    return {"ok": True, "providers": providers}


def post_ai_provider_save(payload: dict[str, Any]) -> dict[str, Any]:
    """
    POST /api/ai-providers/save
    Save or update a BYOK provider API key.

    Payload fields:
      provider        (required)  one of: gemini openai anthropic groq openrouter
      apiKey          (required)  plaintext key — encrypted server-side, never stored plain
      model           (optional)  override default model
      useForResumeTailoring   (optional, bool)
      useForAtsAnalysis       (optional, bool)
      useForCoverLetters      (optional, bool)
      useForJobMatch          (optional, bool)
      useForQuestionHelp      (optional, bool)
      enabled         (optional, bool)
    """
    user_id = _auth_user_id(payload)
    if not user_id:
        return {"ok": False, "error": "Authenticated user required."}

    provider = str(payload.get("provider") or "").lower().strip()
    api_key = str(payload.get("apiKey") or payload.get("api_key") or "").strip()
    if not provider:
        return {"ok": False, "error": "provider is required."}
    if not api_key:
        return {"ok": False, "error": "apiKey is required."}

    try:
        setting = _get_ai_provider_store().save(
            user_id=user_id,
            provider=provider,
            plaintext_key=api_key,
            model=str(payload.get("model") or ""),
            use_for_resume_tailoring=bool(payload.get("useForResumeTailoring", True)),
            use_for_ats_analysis=bool(payload.get("useForAtsAnalysis", True)),
            use_for_cover_letters=bool(payload.get("useForCoverLetters", True)),
            use_for_job_match=bool(payload.get("useForJobMatch", True)),
            use_for_question_help=bool(payload.get("useForQuestionHelp", True)),
            enabled=bool(payload.get("enabled", True)),
        )
        return {"ok": True, "provider": setting.to_safe_dict()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def post_ai_provider_delete(payload: dict[str, Any]) -> dict[str, Any]:
    """DELETE /api/ai-providers/:provider — remove a saved BYOK key."""
    user_id = _auth_user_id(payload)
    if not user_id:
        return {"ok": False, "error": "Authenticated user required."}
    provider = str(payload.get("provider") or "").lower().strip()
    if not provider:
        return {"ok": False, "error": "provider is required."}
    deleted = _get_ai_provider_store().delete(user_id, provider)
    return {"ok": True, "deleted": deleted}


def post_ai_provider_test(payload: dict[str, Any]) -> dict[str, Any]:
    """
    POST /api/ai-providers/test
    Validate a BYOK key by sending a minimal request server-side.

    The API key is decrypted server-side and never returned to the client.
    Returns: { ok, valid, provider, errorCode, userMessage }
    """
    user_id = _auth_user_id(payload)
    if not user_id:
        return {"ok": False, "error": "Authenticated user required."}

    provider = str(payload.get("provider") or "").lower().strip()
    if not provider:
        return {"ok": False, "error": "provider is required."}

    api_key = _get_ai_provider_store().get_decrypted_key(user_id, provider)
    if not api_key:
        return {"ok": False, "valid": False, "provider": provider, "errorCode": "invalid_api_key",
                "userMessage": "No saved key found for this provider."}

    # Import and build a throwaway adapter just for validation
    try:
        from automation.ai.router import _build_byok_adapter
        from automation.ai.config import get_ai_config
        cfg = get_ai_config()
        model = cfg.default_model(provider)
        adapter = _build_byok_adapter(provider, api_key, model)
        valid = adapter.validate_key(api_key)
    except Exception:
        valid = False

    status = "ok" if valid else "invalid_key"
    _get_ai_provider_store().update_test_status(user_id, provider, status=status)

    return {
        "ok": True,
        "valid": valid,
        "provider": provider,
        "errorCode": None if valid else "invalid_api_key",
        "userMessage": None if valid else "The API key is invalid or has expired.",
    }


def post_tailor_resume(payload: dict[str, Any]) -> dict[str, Any]:
    """
    POST /api/resume/tailor
    Tailor a resume using the BYOK provider router.

    Delegates to automation.resume_tailor.tailor_resume.
    Returns the ResumeTailorOutput dict with providerUsed/modelUsed/usedByok.
    """
    from automation.resume_contract import ResumeTailorInput
    from automation.resume_tailor import tailor_resume

    user_id = _auth_user_id(payload)
    if not user_id:
        return {"ok": False, "error": "Authenticated user required."}

    inp = ResumeTailorInput(
        job_title=str(payload.get("jobTitle") or payload.get("job_title") or ""),
        description_text=str(payload.get("descriptionText") or payload.get("description_text") or ""),
        target_domain=str(payload.get("targetDomain") or payload.get("target_domain") or ""),
        user_id=user_id,
        resume_kind=payload.get("resumeKind") or payload.get("resume_kind") or "tailored",
        full_name=payload.get("fullName") or payload.get("full_name"),
        email=payload.get("email"),
        phone=payload.get("phone"),
        education=list(payload.get("education") or []),
        work_experience=list(payload.get("workExperience") or payload.get("work_experience") or []),
        skills=list(payload.get("skills") or []),
        linkedin_url=payload.get("linkedinUrl") or payload.get("linkedin_url"),
        github_url=payload.get("githubUrl") or payload.get("github_url"),
        portfolio_url=payload.get("portfolioUrl") or payload.get("portfolio_url"),
        selected_resume_id=payload.get("selectedResumeId"),
        selected_resume_label=payload.get("selectedResumeLabel"),
        selected_resume_content=payload.get("selectedResumeContent"),
        preferred_format=payload.get("preferredFormat") or "markdown",
    )

    result = tailor_resume(
        inp,
        router=_get_ai_router(),
        user_tier=str(payload.get("userTier") or "free"),
        fallback=bool(payload.get("fallback", True)),
    )
    return result.to_dict()

