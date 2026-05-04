from __future__ import annotations

from abc import ABC
from typing import Any

from automation.field_detection import scan_dom_fields
from automation.field_mapping import map_fields
from automation.models import Field, FieldMemoryEntry, FillResult, JobContext, ResumeArtifact, RunLog, SubmitResult, UserProfile
from automation.progress import build_page_progress
from automation.resume_upload import upload_resume as upload_resume_file
from automation.validators import validate_required_fields


class PlatformAdapter(ABC):
    name = "generic"
    next_button_selectors = ()
    submit_button_selectors = ()
    resume_input_selectors = ()

    def detect(self, url: str, page: Any | None = None) -> bool:
        return False

    async def scan_fields(self, page: Any) -> list[Field]:
        return await scan_dom_fields(page)

    async def upload_resume(self, page: Any, resume_path: str | None) -> bool:
        return await upload_resume_file(page, resume_path, selectors=self.resume_input_selectors)

    async def detect_next_button(self, page: Any) -> bool:
        return await _has_enabled_control(page, self.next_button_selectors + NEXT_BUTTON_SELECTORS)

    async def detect_submit_button(self, page: Any) -> bool:
        return await _has_enabled_control(page, self.submit_button_selectors + SUBMIT_BUTTON_SELECTORS)

    async def continue_to_next(self, page: Any) -> bool:
        return await _click_first_enabled(page, self.next_button_selectors + NEXT_BUTTON_SELECTORS)

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
        step = int(job.metadata.get("step", 1)) if job and job.metadata else 1
        logs: list[RunLog] = [
            RunLog(
                event="fields_detected",
                message=f"Detected {len(fields)} fields on {self.name} page.",
                step=step,
                details={"field_count": len(fields)},
            )
        ]
        for mapped in known:
            if mapped.field.selector:
                try:
                    await fill_one(page, mapped)
                    logs.append(
                        RunLog(
                            event="field_filled",
                            message=f"Filled {mapped.field.label or mapped.field.name}.",
                            step=step,
                            details={"selector": mapped.field.selector, "source": mapped.source},
                        )
                    )
                except Exception as exc:
                    logs.append(
                        RunLog(
                            event="field_fill_failed",
                            message=f"Failed to fill {mapped.field.label!r}: {exc}",
                            level="warning",
                            step=step,
                            details={"selector": mapped.field.selector},
                        )
                    )
        uploaded = await self.upload_resume(page, resume.path if resume else None)
        logs.append(
            RunLog(
                event="resume_upload",
                message="Uploaded selected resume." if uploaded else "No resume uploaded.",
                level="info" if uploaded else "warning",
                step=step,
                details={"resume_label": resume.label if resume else None},
            )
        )
        validation = validate_required_fields(fields, known)
        has_next = await self.detect_next_button(page)
        has_submit = await self.detect_submit_button(page)
        current_url, page_title = await _page_metadata(page)
        if validation.missing_required:
            logs.append(
                RunLog(
                    event="validation_blocked",
                    message="Required fields are missing before continuing.",
                    level="warning",
                    step=step,
                    details={"missing_required": [field.label for field in validation.missing_required]},
                )
            )
        progress = build_page_progress(
            platform=self.name,
            step=step,
            fields=fields,
            known=known,
            unknown=unknown,
            validation=validation,
            has_next=has_next,
            has_submit=has_submit,
            current_url=current_url,
            page_title=page_title,
            logs=logs,
        )
        return FillResult(
            ok=True,
            known_fields=known,
            unknown_fields=unknown,
            uploaded_resume=uploaded,
            validation=validation,
            progress=progress,
            logs=logs,
        )

    async def validate(self, page: Any, fields: list[Field] | None = None, mapped: list[Any] | None = None):
        scanned = fields or await self.scan_fields(page)
        return validate_required_fields(scanned, mapped or [])

    async def submit(self, page: Any):
        clicked = await _click_first_enabled(page, self.submit_button_selectors + SUBMIT_BUTTON_SELECTORS)
        if clicked:
            return SubmitResult(ok=True, submitted=True, message="Clicked submit control.")
        return SubmitResult(ok=False, submitted=False, message="No enabled submit control found.")


NEXT_BUTTON_SELECTORS = (
    "button:has-text('Next')",
    "button:has-text('Continue')",
    "button:has-text('Save and Continue')",
    "button:has-text('Review')",
    "input[type='button'][value*='Next' i]",
    "input[type='submit'][value*='Continue' i]",
    "a:has-text('Next')",
    "a:has-text('Continue')",
)

SUBMIT_BUTTON_SELECTORS = (
    "button[type='submit']:has-text('Submit')",
    "button[type='submit']:has-text('Apply')",
    "input[type='submit'][value*='Submit' i]",
    "input[type='submit'][value*='Apply' i]",
    "button:has-text('Submit Application')",
    "button:has-text('Submit')",
    "button:has-text('Apply')",
    "button:has-text('Send')",
)


async def _has_enabled_control(page: Any, selectors: tuple[str, ...]) -> bool:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if await locator.count() > 0 and await locator.is_enabled():
                return True
        except Exception:
            continue
    return False


async def _click_first_enabled(page: Any, selectors: tuple[str, ...]) -> bool:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if await locator.count() > 0 and await locator.is_enabled():
                await locator.click()
                return True
        except Exception:
            continue
    return False


async def _page_metadata(page: Any) -> tuple[str | None, str | None]:
    current_url = getattr(page, "url", None)
    page_title = None
    try:
        page_title = await page.title()
    except Exception:
        page_title = None
    return current_url, page_title


async def fill_one(page: Any, mapped: Any) -> None:
    field = mapped.field
    value = mapped.value
    locator = page.locator(field.selector).first
    if field.field_type.value in {"text", "textarea", "unknown"}:
        await locator.fill(str(value))
    elif field.field_type.value == "select":
        await _select_best_option(locator, field.options, str(value))
    elif field.field_type.value == "checkbox":
        if bool(value):
            await locator.check()
        else:
            await locator.uncheck()
    elif field.field_type.value == "radio":
        await locator.check()


async def _select_best_option(locator: Any, options: list[str], value: str) -> None:
    lower_value = value.casefold()
    for option in options:
        if option.casefold() == lower_value:
            await locator.select_option(label=option)
            return
    for option in options:
        if lower_value in option.casefold() or option.casefold() in lower_value:
            await locator.select_option(label=option)
            return
    try:
        await locator.select_option(label=value)
    except Exception:
        await locator.select_option(value=value)
