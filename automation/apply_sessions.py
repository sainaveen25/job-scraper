from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from automation.field_mapping import map_fields, normalize_question
from automation.memory import FieldMemoryStore
from automation.models import (
    ApplySession,
    Field,
    FieldMemoryEntry,
    FieldType,
    JobContext,
    ResumeArtifact,
    RunLog,
    UnknownField,
    UserProfile,
)
from automation.platforms import PLATFORM_ADAPTERS
from automation.progress import build_page_progress, progress_to_dict
from automation.validators import validate_required_fields


DEFAULT_TOKEN_TTL_SECONDS = 900


class ApplySessionAuthError(PermissionError):
    pass


class ApplySessionStore:
    def __init__(self, path: str | Path = "data/apply_sessions.json") -> None:
        self.path = Path(path)
        self._sessions: dict[str, ApplySession] = {}
        self._loaded = False

    def load_all(self) -> dict[str, ApplySession]:
        if self._loaded:
            return self._sessions
        self._loaded = True
        if not self.path.exists():
            return self._sessions
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._sessions
        for item in payload if isinstance(payload, list) else []:
            session = _session_from_dict(item)
            if session:
                self._sessions[session.session_id] = session
        return self._sessions

    def get(self, session_id: str) -> ApplySession | None:
        return self.load_all().get(session_id)

    def save(self, session: ApplySession) -> ApplySession:
        self.load_all()[session.session_id] = session
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([_session_to_dict(item) for item in self._sessions.values()], indent=2),
            encoding="utf-8",
        )
        return session


class ApplySessionService:
    def __init__(
        self,
        *,
        store: ApplySessionStore | None = None,
        memory_store: FieldMemoryStore | None = None,
        token_secret: str | None = None,
        token_ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
    ) -> None:
        self.store = store or ApplySessionStore()
        self.memory_store = memory_store or FieldMemoryStore()
        self.token_secret = token_secret or os.getenv("APPLYMATE_EXTENSION_TOKEN_SECRET") or secrets.token_urlsafe(32)
        self.token_ttl_seconds = token_ttl_seconds

    def create(self, payload: dict[str, Any], *, issue_extension_token: bool = False, client: str = "web") -> dict[str, Any]:
        user_id = _require_user_session(payload)
        job = dict(payload.get("job") or {})
        resume = dict(payload.get("resume") or {}) if payload.get("resume") else None
        profile = dict(payload.get("profile") or {})
        _validate_owned("job", job, user_id)
        if resume:
            _validate_owned("resume", resume, user_id)
        _validate_owned("profile", profile, user_id)

        session_id = payload.get("sessionId") or str(uuid.uuid4())
        platform = payload.get("platform") or _detect_platform(_apply_url(job))
        field_memory = _coerce_memory(payload.get("fieldMemory") or payload.get("savedAnswers") or [])
        session = ApplySession(
            session_id=session_id,
            user_id=user_id,
            job=job,
            resume=resume,
            profile=profile,
            field_memory=field_memory,
            platform=platform,
            current_url=_apply_url(job),
            run_history=[
                RunLog(
                    event="apply_session_created",
                    message="Created apply session.",
                    details={"platform": platform, "client": client},
                )
            ],
        )
        self.store.save(session)
        token = self._mint_token(session) if issue_extension_token else None
        return _with_control_center(session.to_client_payload(extension_token=token, client=client))

    def get(self, session_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        session = self._require_session(session_id, payload or {})
        return _with_control_center(session.to_client_payload(client=_client_from_payload(payload or {})))

    def start(self, session_id: str, payload: dict[str, Any], *, issue_extension_token: bool = False, client: str = "web") -> dict[str, Any]:
        session = self._require_session(session_id, payload)
        current_url = payload.get("currentUrl") or payload.get("current_url") or session.current_url
        if current_url:
            session.current_url = current_url
            session.platform = payload.get("platform") or _detect_platform(current_url)
        session.status = "started"
        session.run_history.append(
            RunLog(
                event="apply_session_started",
                message="Started apply session.",
                details={"client": client},
            )
        )
        session.touch()
        self.store.save(session)
        token = self._mint_token(session) if issue_extension_token else None
        return _with_control_center(session.to_client_payload(extension_token=token, client=client))

    def fill_page(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        session = self._require_session(session_id, payload)
        fields = _coerce_fields(payload.get("fields") or payload.get("fieldsDetected") or [])
        if not fields:
            fields = _coerce_fields(payload.get("page", {}).get("fields") or [])
        page_title = payload.get("pageTitle") or payload.get("page_title")
        current_url = payload.get("currentUrl") or payload.get("current_url") or session.current_url
        screenshot_path = payload.get("screenshotPath") or payload.get("screenshot_path")
        if current_url:
            session.current_url = current_url
            session.platform = payload.get("platform") or _detect_platform(current_url)
        if page_title:
            session.page_title = page_title
        if screenshot_path:
            session.screenshot_path = screenshot_path

        profile = UserProfile.from_mapping(session.profile)
        known, unknown = map_fields(fields, profile, session.field_memory + self.memory_store.load())
        validation = validate_required_fields(fields, known)
        progress = build_page_progress(
            platform=session.platform,
            step=int(payload.get("step") or session.progress.get("step") or 1),
            fields=fields,
            known=known,
            unknown=unknown,
            validation=validation,
            has_next=bool(payload.get("hasNext") or payload.get("has_next")),
            has_submit=bool(payload.get("hasSubmit") or payload.get("has_submit")),
            current_url=session.current_url,
            page_title=session.page_title,
            screenshot_path=session.screenshot_path,
        )
        session.progress = progress_to_dict(progress) or {}
        session.unresolved_fields = unknown
        session.status = "filled_waiting_review"
        session.run_history.append(
            RunLog(
                event="page_fill_planned",
                message="Mapped current page fields for assisted autofill.",
                step=progress.step,
                details={
                    "fields_detected": len(fields),
                    "fields_filled": len(known),
                    "unresolved_fields": len(unknown),
                    "debug_logs": list(payload.get("debugLogs") or payload.get("debug_logs") or []),
                },
            )
        )
        session.touch()
        self.store.save(session)
        response = session.to_client_payload(client=_client_from_payload(payload))
        response["fieldsDetected"] = [asdict(field) for field in fields]
        response["fieldsFilled"] = [asdict(item) for item in known]
        response["fillInstructions"] = [_fill_instruction(item) for item in known] + _resume_fill_instructions(fields, session.resume)
        response["resumeUpload"] = _resume_upload_instruction(session.resume)
        response["runStatus"] = session.status
        return _with_control_center(response)

    def continue_session(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        session = self._require_session(session_id, payload)
        step = int(session.progress.get("step") or 1) + 1
        session.progress["step"] = step
        session.status = "continued"
        session.run_history.append(RunLog(event="continue_requested", message="User requested next page.", step=step))
        session.touch()
        self.store.save(session)
        response = session.to_client_payload(client=_client_from_payload(payload))
        response["continueAllowed"] = True
        response["runStatus"] = session.status
        return _with_control_center(response)

    def save_answer(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        session = self._require_session(session_id, payload)
        answer_payload = payload.get("answer") if isinstance(payload.get("answer"), dict) else payload
        original = answer_payload.get("originalQuestion") or answer_payload.get("original_question") or answer_payload.get("label") or ""
        normalized = answer_payload.get("normalizedQuestion") or answer_payload.get("normalized_question") or normalize_question(original)
        entry = FieldMemoryEntry(
            original_question=original,
            normalized_question=normalized,
            answer=answer_payload.get("value", answer_payload.get("answer")),
            answer_type=answer_payload.get("answerType") or answer_payload.get("answer_type") or "text",
            platform=answer_payload.get("platform") or session.platform,
            source_url=answer_payload.get("sourceUrl") or answer_payload.get("source_url") or session.current_url,
            confidence=float(answer_payload.get("confidence", 1.0)),
        )
        saved = self.memory_store.upsert(entry)
        session.field_memory = _replace_memory(session.field_memory, saved)
        session.unresolved_fields = [
            item
            for item in session.unresolved_fields
            if normalize_question(item.field.normalized_question or item.field.label or item.field.name or "") != saved.normalized_question
        ]
        session.run_history.append(RunLog(event="answer_saved", message="Saved reusable answer.", details={"question": saved.normalized_question}))
        session.touch()
        self.store.save(session)
        response = session.to_client_payload(client=_client_from_payload(payload))
        response["savedAnswer"] = asdict(saved)
        return _with_control_center(response)

    def submit(self, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        session = self._require_session(session_id, payload)
        confirm = bool(payload.get("confirm") or payload.get("allowSubmit") or payload.get("explicitConfirmation"))
        if not confirm:
            session.status = "ready_for_submit"
            session.run_history.append(
                RunLog(
                    event="submit_blocked",
                    message="Final submit requires explicit confirmation.",
                    level="warning",
                )
            )
            session.touch()
            self.store.save(session)
            response = session.to_client_payload(client=_client_from_payload(payload))
            response["ok"] = False
            response["submitted"] = False
            response["error"] = "explicit_submit_confirmation_required"
            return _with_control_center(response)
        session.status = "submit_confirmed"
        session.run_history.append(RunLog(event="submit_confirmed", message="User explicitly confirmed final submit."))
        session.touch()
        self.store.save(session)
        response = session.to_client_payload(client=_client_from_payload(payload))
        response["ok"] = True
        response["submitted"] = False
        response["submitInstruction"] = {"action": "click_submit", "requiresExplicitConfirmation": True}
        return _with_control_center(response)

    def _require_session(self, session_id: str, payload: dict[str, Any]) -> ApplySession:
        session = self.store.get(session_id)
        if not session:
            raise LookupError("Unknown apply session.")
        user_id = self._authenticate(payload, session)
        if user_id != session.user_id:
            raise ApplySessionAuthError("Apply session does not belong to the authenticated user.")
        return session

    def _authenticate(self, payload: dict[str, Any], session: ApplySession) -> str:
        token = payload.get("extensionToken") or payload.get("extension_token")
        if token:
            token_session_id, user_id = self._verify_token(token)
            if token_session_id != session.session_id:
                raise ApplySessionAuthError("Extension token is not valid for this apply session.")
            return user_id
        return _require_user_session(payload)

    def _mint_token(self, session: ApplySession) -> str:
        expires_at = int((datetime.now(timezone.utc) + timedelta(seconds=self.token_ttl_seconds)).timestamp())
        nonce = secrets.token_urlsafe(12)
        body = f"v1.{session.session_id}.{session.user_id}.{expires_at}.{nonce}"
        signature = _b64(hmac.new(self.token_secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest())
        return f"{body}.{signature}"

    def _verify_token(self, token: str) -> tuple[str, str]:
        parts = token.split(".")
        if len(parts) != 6 or parts[0] != "v1":
            raise ApplySessionAuthError("Invalid extension token.")
        body = ".".join(parts[:-1])
        expected = _b64(hmac.new(self.token_secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, parts[-1]):
            raise ApplySessionAuthError("Invalid extension token signature.")
        try:
            expires_at = int(parts[3])
        except ValueError as exc:
            raise ApplySessionAuthError("Invalid extension token expiry.") from exc
        if expires_at < int(datetime.now(timezone.utc).timestamp()):
            raise ApplySessionAuthError("Extension token expired.")
        return parts[1], parts[2]


def _require_user_session(payload: dict[str, Any]) -> str:
    auth = payload.get("auth") or {}
    user_id = payload.get("userId") or payload.get("user_id") or auth.get("userId") or auth.get("user_id")
    session_token = payload.get("userSessionToken") or payload.get("user_session_token") or auth.get("sessionToken") or auth.get("session_token")
    if not user_id or not session_token:
        raise ApplySessionAuthError("Authenticated ApplyMate user session is required.")
    if len(str(session_token)) < 12:
        raise ApplySessionAuthError("ApplyMate session token is invalid.")
    return str(user_id)


def _validate_owned(resource_name: str, value: dict[str, Any], user_id: str) -> None:
    owner = value.get("userId") or value.get("user_id") or value.get("ownerUserId") or value.get("owner_user_id")
    if owner is not None and str(owner) != user_id:
        raise ApplySessionAuthError(f"{resource_name} does not belong to the authenticated user.")


def _apply_url(job: dict[str, Any]) -> str | None:
    return job.get("applyUrl") or job.get("apply_url") or job.get("jobUrl") or job.get("job_url") or job.get("url")


def _detect_platform(url: str | None) -> str:
    for adapter in PLATFORM_ADAPTERS:
        if adapter.detect(url or ""):
            return adapter.name
    return "generic"


def _coerce_fields(items: list[dict[str, Any]]) -> list[Field]:
    fields: list[Field] = []
    for item in items:
        if isinstance(item, Field):
            fields.append(item)
            continue
        if not isinstance(item, dict):
            continue
        raw_type = item.get("fieldType") or item.get("field_type") or item.get("type") or "text"
        try:
            field_type = FieldType(str(raw_type).lower())
        except ValueError:
            field_type = FieldType.UNKNOWN
        fields.append(
            Field(
                label=item.get("label") or item.get("ariaLabel") or item.get("placeholder") or item.get("name") or "",
                field_type=field_type,
                selector=item.get("selector"),
                name=item.get("name"),
                required=bool(item.get("required", False)),
                options=list(item.get("options") or []),
                value=item.get("value"),
                sensitive=bool(item.get("sensitive", False)),
            )
        )
    return fields


def _coerce_memory(items: list[dict[str, Any]]) -> list[FieldMemoryEntry]:
    entries: list[FieldMemoryEntry] = []
    for item in items:
        if isinstance(item, FieldMemoryEntry):
            entries.append(item)
        elif isinstance(item, dict):
            original = item.get("originalQuestion") or item.get("original_question") or item.get("label") or ""
            entries.append(
                FieldMemoryEntry(
                    original_question=original,
                    normalized_question=item.get("normalizedQuestion") or item.get("normalized_question") or normalize_question(original),
                    answer=item.get("answer", item.get("value")),
                    answer_type=item.get("answerType") or item.get("answer_type") or "text",
                    platform=item.get("platform"),
                    source_url=item.get("sourceUrl") or item.get("source_url"),
                    confidence=float(item.get("confidence", 1.0)),
                    sensitive=bool(item.get("sensitive", False)),
                    last_used_at=item.get("lastUsedAt") or item.get("last_used_at"),
                )
            )
    return entries


def _replace_memory(entries: list[FieldMemoryEntry], saved: FieldMemoryEntry) -> list[FieldMemoryEntry]:
    return [entry for entry in entries if not (entry.normalized_question == saved.normalized_question and entry.platform == saved.platform)] + [saved]


def _fill_instruction(mapped: Any) -> dict[str, Any]:
    return {
        "selector": mapped.field.selector,
        "name": mapped.field.name,
        "groupSelector": f'input[type="radio"][name="{mapped.field.name}"]' if mapped.field.field_type.value == "radio" and mapped.field.name else None,
        "label": mapped.field.label,
        "fieldType": mapped.field.field_type.value,
        "value": mapped.value,
        "source": mapped.source,
        "requiresReview": mapped.requires_review,
    }


def _resume_fill_instructions(fields: list[Field], resume: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not resume:
        return []
    instructions = []
    for field in fields:
        if field.field_type.value != "file":
            continue
        instructions.append(
            {
                "selector": field.selector,
                "name": field.name,
                "label": field.label or "Resume",
                "fieldType": "file",
                "value": resume.get("id") or resume.get("label") or resume.get("fileName") or resume.get("filename"),
                "source": "resume",
                "requiresReview": True,
            }
        )
    return instructions


def _resume_upload_instruction(resume: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "available": bool(resume),
        "resumeId": resume.get("id") or resume.get("label") if resume else None,
        "fileName": resume.get("fileName") or resume.get("filename") if resume else None,
        "mimeType": resume.get("mimeType") or resume.get("mime_type") if resume else None,
    }


def _client_from_payload(payload: dict[str, Any]) -> str:
    if payload.get("extensionToken") or payload.get("extension_token"):
        return "extension"
    return str(payload.get("client") or "web")


def _with_control_center(payload: dict[str, Any]) -> dict[str, Any]:
    fill_instructions = list(payload.get("fillInstructions") or [])
    unresolved_fields = list(payload.get("unresolvedFields") or [])
    resume_upload = payload.get("resumeUpload") or _resume_upload_instruction(payload.get("resume"))
    manual_steps = [
        {
            "label": item.get("label") or item.get("name") or item.get("selector") or "Field",
            "value": item.get("value"),
            "fieldType": item.get("fieldType") or "text",
            "requiresReview": bool(item.get("requiresReview")),
        }
        for item in fill_instructions
        if item.get("fieldType") != "file"
    ]
    manual_resume = {
        **resume_upload,
        "requiresManualSelection": bool(resume_upload.get("available")),
        "instruction": "Select the saved resume file in the browser file picker." if resume_upload.get("available") else None,
    }
    payload["manualAssist"] = {
        "mode": "browser_agnostic",
        "canUseWithoutExtension": True,
        "platform": payload.get("platform") or "generic",
        "currentUrl": payload.get("currentUrl"),
        "pageTitle": payload.get("pageTitle"),
        "steps": manual_steps,
        "resumeUpload": manual_resume,
        "unresolvedFields": unresolved_fields,
        "submitRequiresExplicitConfirmation": True,
    }
    payload["webControlCenter"] = {
        "available": True,
        "extensionRequired": False,
        "extensionEnhancementAvailable": True,
        "sessionId": payload.get("sessionId"),
        "status": payload.get("status"),
        "progress": payload.get("progress") or {},
        "runStatus": payload.get("runStatus") or payload.get("status"),
        "manualAssist": payload["manualAssist"],
    }
    return payload


def _session_to_dict(session: ApplySession) -> dict[str, Any]:
    return {
        **session.to_client_payload(),
        "userId": session.user_id,
    }


def _session_from_dict(item: dict[str, Any]) -> ApplySession | None:
    try:
        return ApplySession(
            session_id=item["sessionId"],
            user_id=item["userId"],
            job=item.get("job") or {},
            resume=item.get("resume"),
            profile=item.get("profile") or {},
            field_memory=_coerce_memory(item.get("fieldMemory") or []),
            platform=item.get("platform") or "generic",
            status=item.get("status") or "created",
            progress=item.get("progress") or {},
            unresolved_fields=[
                UnknownField(_field_from_dict(entry["field"]), entry.get("reason", "unmapped"))
                for entry in item.get("unresolvedFields") or []
                if isinstance(entry, dict) and isinstance(entry.get("field"), dict)
            ],
            run_history=[RunLog(**entry) for entry in item.get("runHistory") or [] if isinstance(entry, dict)],
            current_url=item.get("currentUrl"),
            page_title=item.get("pageTitle"),
            screenshot_path=item.get("screenshotPath"),
            created_at=item.get("createdAt") or datetime.now(timezone.utc).isoformat(),
            updated_at=item.get("updatedAt") or datetime.now(timezone.utc).isoformat(),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _field_from_dict(item: dict[str, Any]) -> Field:
    raw_type = item.get("field_type") or item.get("fieldType") or item.get("field_type") or "text"
    if isinstance(raw_type, FieldType):
        field_type = raw_type
    else:
        try:
            field_type = FieldType(str(raw_type).lower())
        except ValueError:
            field_type = FieldType.UNKNOWN
    return Field(
        label=item.get("label") or "",
        field_type=field_type,
        selector=item.get("selector"),
        name=item.get("name"),
        required=bool(item.get("required", False)),
        options=list(item.get("options") or []),
        value=item.get("value"),
        sensitive=bool(item.get("sensitive", False)),
        normalized_question=item.get("normalized_question") or item.get("normalizedQuestion"),
        confidence=float(item.get("confidence", 0.0)),
    )
