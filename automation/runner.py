from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from automation.browser import BrowserSession, screenshot
from automation.config import AutomationSettings, get_settings
from automation.field_mapping import map_fields, normalize_question
from automation.memory import FieldMemoryStore
from automation.models import (
    AutomationMode,
    FieldMemoryEntry,
    FillResult,
    JobContext,
    ResumeArtifact,
    RunLog,
    RunHistory,
    RunStatus,
    UserProfile,
)
from automation.platforms import PLATFORM_ADAPTERS
from automation.progress import build_page_progress, progress_to_dict
from automation.validators import can_submit


class ApplyAutomationService:
    def __init__(
        self,
        *,
        memory_store: FieldMemoryStore | None = None,
        settings: AutomationSettings | None = None,
    ) -> None:
        self.memory_store = memory_store or FieldMemoryStore()
        self.settings = settings or get_settings()
        self._runs: dict[str, dict[str, Any]] = {}

    def detect_platform(self, url: str):
        for adapter in PLATFORM_ADAPTERS:
            if adapter.detect(url):
                return adapter
        return PLATFORM_ADAPTERS[-1]

    async def prepare_async(
        self,
        *,
        job: dict[str, Any] | JobContext,
        resume: dict[str, Any] | ResumeArtifact | None = None,
        profile: dict[str, Any] | UserProfile | None = None,
        mode: str | AutomationMode = AutomationMode.ASSISTED,
    ) -> dict[str, Any]:
        job_context = _coerce_job(job)
        resume_artifact = _coerce_resume(resume)
        user_profile = UserProfile.from_mapping(profile)
        run_id = str(uuid.uuid4())
        selected_mode = AutomationMode(mode)
        adapter = self.detect_platform(job_context.url or "")
        history = RunHistory(
            run_id=run_id,
            job_id=job_context.job_id,
            resume_id=resume_artifact.label if resume_artifact else None,
            platform=adapter.name,
            mode=selected_mode,
            status=RunStatus.PREVIEW_READY,
        )

        async with BrowserSession(self.settings).open() as (page, _context):
            await page.goto(job_context.url, wait_until="domcontentloaded")
            fields = await adapter.scan_fields(page)
            known, unknown = map_fields(fields, user_profile, self.memory_store.load())
            validation = await adapter.validate(page, fields, known)
            current_url = getattr(page, "url", None)
            try:
                page_title = await page.title()
            except Exception:
                page_title = None
            has_next = await adapter.detect_next_button(page)
            has_submit = await adapter.detect_submit_button(page)
            shot = await screenshot(page, self.settings.artifact_dir, run_id, "prepare")

        history.detected_fields = fields
        history.unmapped_fields = unknown
        if shot:
            history.screenshots.append(shot)
        history.logs.append(
            RunLog(
                event="prepare_complete",
                message="Prepared assisted application run.",
                step=1,
                details={"fields_detected": len(fields), "unresolved_fields": len(unknown)},
            )
        )
        self._runs[run_id] = {
            "job": job_context,
            "resume": resume_artifact,
            "profile": user_profile,
            "platform": adapter.name,
            "mode": selected_mode,
            "history": history,
        }
        progress = build_page_progress(
            platform=adapter.name,
            step=1,
            fields=fields,
            known=known,
            unknown=unknown,
            validation=validation,
            has_next=has_next,
            has_submit=has_submit,
            current_url=current_url,
            page_title=page_title,
            screenshot_path=shot,
            logs=history.logs,
        )
        result = FillResult(ok=True, known_fields=known, unknown_fields=unknown, validation=validation, progress=progress)
        if shot:
            result.screenshots.append(shot)
        return _response(True, adapter.name, run_id, known, unknown, history, result)

    async def run_async(
        self,
        *,
        run_id: str,
        mode: str | AutomationMode = AutomationMode.ASSISTED,
        allow_submit: bool = False,
    ) -> dict[str, Any]:
        record = self._runs.get(run_id)
        if not record:
            return {"ok": False, "runId": run_id, "error": "Unknown run id."}

        selected_mode = AutomationMode(mode)
        adapter = self.detect_platform(record["job"].url or "")
        history: RunHistory = record["history"]
        history.mode = selected_mode
        result = FillResult(ok=False)

        try:
            async with BrowserSession(self.settings).open() as (page, _context):
                await page.goto(record["job"].url, wait_until="domcontentloaded")
                if selected_mode == AutomationMode.PREVIEW:
                    fields = await adapter.scan_fields(page)
                    known, unknown = map_fields(fields, record["profile"], self.memory_store.load())
                    result = FillResult(ok=True, known_fields=known, unknown_fields=unknown)
                    history.status = RunStatus.PREVIEW_READY
                else:
                    result = await adapter.fill_fields(
                        page,
                        record["profile"],
                        self.memory_store.load(),
                        record["job"],
                        record["resume"],
                    )
                    history.detected_fields = result.progress.fields_found if result.progress else []
                    if selected_mode == AutomationMode.SUBMIT:
                        validation = result.validation or await adapter.validate(page)
                        result.validation = validation
                        ready_for_submit = bool(result.progress and result.progress.ready_for_submit)
                        if can_submit(selected_mode.value, allow_submit, validation) and ready_for_submit:
                            result.submit = await adapter.submit(page)
                            history.status = RunStatus.SUBMITTED if result.submit.submitted else RunStatus.NEEDS_REVIEW
                        else:
                            history.status = RunStatus.READY_FOR_SUBMIT if validation.ok and ready_for_submit else RunStatus.NEEDS_REVIEW
                            result.logs.append(
                                RunLog(
                                    event="submit_blocked",
                                    message="Submit requires explicit confirmation and a ready final page.",
                                    level="warning",
                                    step=result.progress.step if result.progress else None,
                                    details={"allow_submit": allow_submit, "ready_for_submit": ready_for_submit},
                                )
                            )
                    else:
                        if result.progress and result.progress.ready_for_next:
                            history.status = RunStatus.READY_FOR_NEXT
                        elif result.progress and result.progress.ready_for_submit:
                            history.status = RunStatus.READY_FOR_SUBMIT
                        else:
                            history.status = RunStatus.FILLED_WAITING_REVIEW
                shot = await screenshot(page, self.settings.artifact_dir, run_id, "run")
                if shot:
                    history.screenshots.append(shot)
                    result.screenshots.append(shot)
                    if result.progress:
                        result.progress.screenshot_path = shot
                        result.progress.screenshots.append(shot)
        except Exception as exc:
            history.status = RunStatus.FAILED
            history.errors.append(str(exc))
            return {"ok": False, "runId": run_id, "status": history.status.value, "error": str(exc)}

        history.unmapped_fields = result.unknown_fields
        history.logs.extend(result.logs)
        if result.progress and result.progress.logs is not result.logs:
            history.logs.extend(result.progress.logs)
        history.updated_at = datetime.now(timezone.utc).isoformat()
        return _response(result.ok, adapter.name, run_id, result.known_fields, result.unknown_fields, history, result)

    async def continue_async(self, *, run_id: str) -> dict[str, Any]:
        record = self._runs.get(run_id)
        if not record:
            return {"ok": False, "runId": run_id, "error": "Unknown run id."}

        adapter = self.detect_platform(record["job"].url or "")
        history: RunHistory = record["history"]
        result = FillResult(ok=False)
        try:
            async with BrowserSession(self.settings).open() as (page, _context):
                await page.goto(record["job"].url, wait_until="domcontentloaded")
                result = await adapter.fill_fields(
                    page,
                    record["profile"],
                    self.memory_store.load(),
                    record["job"],
                    record["resume"],
                )
                if result.progress and result.progress.ready_for_next:
                    moved = await adapter.continue_to_next(page)
                    result.logs.append(
                        RunLog(
                            event="continue_clicked" if moved else "continue_not_clicked",
                            message="Clicked next/continue control." if moved else "No next/continue control clicked.",
                            level="info" if moved else "warning",
                            step=result.progress.step,
                        )
                    )
                    if moved:
                        record["job"].metadata["step"] = int(record["job"].metadata.get("step", 1)) + 1
                        history.status = RunStatus.ASSISTED_READY
                    else:
                        history.status = RunStatus.NEEDS_REVIEW
                elif result.progress and result.progress.ready_for_submit:
                    history.status = RunStatus.READY_FOR_SUBMIT
                else:
                    history.status = RunStatus.NEEDS_REVIEW
                shot = await screenshot(page, self.settings.artifact_dir, run_id, f"continue-{record['job'].metadata.get('step', 1)}")
                if shot:
                    history.screenshots.append(shot)
                    result.screenshots.append(shot)
                    if result.progress:
                        result.progress.screenshot_path = shot
                        result.progress.screenshots.append(shot)
        except Exception as exc:
            history.status = RunStatus.FAILED
            history.errors.append(str(exc))
            return {"ok": False, "runId": run_id, "status": history.status.value, "error": str(exc)}

        history.unmapped_fields = result.unknown_fields
        history.logs.extend(result.logs)
        if result.progress and result.progress.logs is not result.logs:
            history.logs.extend(result.progress.logs)
        history.updated_at = datetime.now(timezone.utc).isoformat()
        return _response(result.ok, adapter.name, run_id, result.known_fields, result.unknown_fields, history, result)

    async def submit_async(self, *, run_id: str, confirm: bool = False) -> dict[str, Any]:
        return await self.run_async(run_id=run_id, mode=AutomationMode.SUBMIT, allow_submit=confirm)

    def prepare(self, **kwargs: Any) -> dict[str, Any]:
        return asyncio.run(self.prepare_async(**kwargs))

    def run(self, **kwargs: Any) -> dict[str, Any]:
        return asyncio.run(self.run_async(**kwargs))

    def continue_run(self, **kwargs: Any) -> dict[str, Any]:
        return asyncio.run(self.continue_async(**kwargs))

    def submit(self, **kwargs: Any) -> dict[str, Any]:
        return asyncio.run(self.submit_async(**kwargs))

    def save_field_memory(self, payload: dict[str, Any]) -> dict[str, Any]:
        original = payload.get("originalQuestion") or payload.get("original_question") or ""
        normalized = payload.get("normalizedQuestion") or payload.get("normalized_question") or normalize_question(original)
        entry = FieldMemoryEntry(
            original_question=original,
            normalized_question=normalized,
            answer=payload.get("answer"),
            answer_type=payload.get("answerType") or payload.get("answer_type") or "text",
            platform=payload.get("platform"),
            source_url=payload.get("sourceUrl") or payload.get("source_url"),
            confidence=float(payload.get("confidence", 1.0)),
        )
        saved = self.memory_store.upsert(entry)
        return {"ok": True, "fieldMemory": asdict(saved)}


_DEFAULT_SERVICE = ApplyAutomationService()


def prepare_application(payload: dict[str, Any]) -> dict[str, Any]:
    return _DEFAULT_SERVICE.prepare(
        job=payload.get("job") or {"job_id": payload.get("jobId"), "url": payload.get("jobUrl")},
        resume=payload.get("resume") or {"path": payload.get("resumePath", ""), "label": payload.get("tailoredResumeId")},
        profile=payload.get("profile"),
        mode=payload.get("mode", "assisted"),
    )


def run_application(payload: dict[str, Any]) -> dict[str, Any]:
    return _DEFAULT_SERVICE.run(
        run_id=payload["runId"],
        mode=payload.get("mode", "assisted"),
        allow_submit=bool(payload.get("allowSubmit", False)),
    )


def continue_application(payload: dict[str, Any]) -> dict[str, Any]:
    return _DEFAULT_SERVICE.continue_run(run_id=payload["runId"])


def submit_application(payload: dict[str, Any]) -> dict[str, Any]:
    return _DEFAULT_SERVICE.submit(run_id=payload["runId"], confirm=bool(payload.get("confirm") or payload.get("allowSubmit")))


def save_field_memory(payload: dict[str, Any]) -> dict[str, Any]:
    return _DEFAULT_SERVICE.save_field_memory(payload)


def _coerce_job(value: dict[str, Any] | JobContext) -> JobContext:
    if isinstance(value, JobContext):
        return value
    return JobContext(
        job_id=value.get("job_id") or value.get("jobId"),
        url=value.get("url") or value.get("job_url") or value.get("jobUrl"),
        title=value.get("title"),
        company=value.get("company"),
        metadata={key: val for key, val in value.items() if key not in {"job_id", "jobId", "url", "job_url", "jobUrl"}},
    )


def _coerce_resume(value: dict[str, Any] | ResumeArtifact | None) -> ResumeArtifact | None:
    if isinstance(value, ResumeArtifact) or value is None:
        return value
    return ResumeArtifact(path=value.get("path") or "", mime_type=value.get("mime_type"), label=value.get("label") or value.get("id"))


def _response(
    ok: bool,
    platform: str,
    run_id: str,
    known: list[Any],
    unknown: list[Any],
    history: RunHistory,
    result: FillResult | None = None,
) -> dict[str, Any]:
    step = result.progress.step if result and result.progress else 1
    detected_fields = result.progress.fields_found if result and result.progress else history.detected_fields
    progress_payload = progress_to_dict(result.progress) if result else None
    return {
        "ok": ok,
        "platform": platform,
        "step": step,
        "current_url": progress_payload.get("current_url") if progress_payload else None,
        "page_title": progress_payload.get("page_title") if progress_payload else None,
        "screenshot_path": progress_payload.get("screenshot_path") if progress_payload else None,
        "fieldsDetected": [asdict(field) for field in detected_fields],
        "fieldsFilled": [asdict(item) for item in known],
        "unresolvedFields": [asdict(item) for item in unknown],
        "fields_detected": [asdict(field) for field in detected_fields],
        "fields_filled": [asdict(item) for item in known],
        "unresolved_fields": [asdict(item) for item in unknown],
        "progress": progress_payload,
        "screenshots": result.screenshots if result else history.screenshots,
        "logs": [asdict(item) for item in (result.logs if result else history.logs)],
        "readiness": {
            "knownFieldCount": len(known),
            "unknownFieldCount": len(unknown),
            "uploadedResume": bool(result.uploaded_resume) if result else False,
            "readyForNext": bool(result and result.progress and result.progress.ready_for_next),
            "readyForSubmit": bool(result and result.progress and result.progress.ready_for_submit),
            "canSubmit": bool(result and result.validation and result.validation.ok),
        },
        "knownFields": [asdict(item) for item in known],
        "unknownFields": [asdict(item) for item in unknown],
        "runId": run_id,
        "status": history.status.value,
        "history": history.to_dict(),
    }
