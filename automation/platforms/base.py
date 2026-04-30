from __future__ import annotations

from abc import ABC
from typing import Any

from automation.field_detection import scan_dom_fields
from automation.field_mapping import map_fields
from automation.models import Field, FieldMemoryEntry, FillResult, JobContext, ResumeArtifact, UserProfile
from automation.resume_upload import upload_resume as upload_resume_file
from automation.validators import validate_required_fields


class PlatformAdapter(ABC):
    name = "generic"

    def detect(self, url: str, page: Any | None = None) -> bool:
        return False

    async def scan_fields(self, page: Any) -> list[Field]:
        return await scan_dom_fields(page)

    async def upload_resume(self, page: Any, resume_path: str | None) -> bool:
        return await upload_resume_file(page, resume_path)

    async def fill_fields(
        self,
        page: Any,
        profile: UserProfile,
        memory: list[FieldMemoryEntry],
        job: JobContext,
        resume: ResumeArtifact | None,
    ) -> FillResult:
        fields = await self.scan_fields(page)
        known, unknown = map_fields(fields, profile, memory)
        logs: list[str] = []
        for mapped in known:
            if mapped.field.selector:
                try:
                    await fill_one(page, mapped)
                except Exception as exc:
                    logs.append(f"Failed to fill {mapped.field.label!r}: {exc}")
        uploaded = await self.upload_resume(page, resume.path if resume else None)
        validation = validate_required_fields(fields, known)
        return FillResult(
            ok=True,
            known_fields=known,
            unknown_fields=unknown,
            uploaded_resume=uploaded,
            validation=validation,
            logs=logs,
        )

    async def validate(self, page: Any, fields: list[Field] | None = None, mapped: list[Any] | None = None):
        scanned = fields or await self.scan_fields(page)
        return validate_required_fields(scanned, mapped or [])

    async def submit(self, page: Any):
        from automation.models import SubmitResult

        candidates = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Submit')",
            "button:has-text('Apply')",
            "button:has-text('Send')",
        ]
        for selector in candidates:
            locator = page.locator(selector).first
            try:
                if await locator.count() > 0 and await locator.is_enabled():
                    await locator.click()
                    return SubmitResult(ok=True, submitted=True, message="Clicked submit control.")
            except Exception:
                continue
        return SubmitResult(ok=False, submitted=False, message="No enabled submit control found.")


async def fill_one(page: Any, mapped: Any) -> None:
    field = mapped.field
    value = mapped.value
    locator = page.locator(field.selector).first
    if field.field_type.value in {"text", "textarea", "unknown"}:
        await locator.fill(str(value))
    elif field.field_type.value == "select":
        try:
            await locator.select_option(label=str(value))
        except Exception:
            await locator.select_option(value=str(value))
    elif field.field_type.value == "checkbox":
        if bool(value):
            await locator.check()
        else:
            await locator.uncheck()
    elif field.field_type.value == "radio":
        await locator.check()
