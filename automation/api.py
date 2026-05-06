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
