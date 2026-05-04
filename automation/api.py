from __future__ import annotations

from typing import Any

from automation.apply_sessions import ApplySessionService
from automation.runner import (
    continue_application,
    prepare_application,
    run_application,
    save_field_memory,
    submit_application,
)


_APPLY_SESSION_SERVICE = ApplySessionService()


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
