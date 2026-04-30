from __future__ import annotations

from pathlib import Path
from typing import Any


FILE_INPUT_SELECTOR = "input[type='file']"
RESUME_HINT_SELECTOR = (
    "input[type='file'][name*='resume' i], "
    "input[type='file'][id*='resume' i], "
    "input[type='file'][aria-label*='resume' i], "
    "input[type='file']"
)


def is_supported_resume(path: str | None) -> bool:
    if not path:
        return False
    suffix = Path(path).suffix.casefold()
    return suffix in {".pdf", ".docx", ".doc"}


async def upload_resume(page: Any, resume_path: str | None) -> bool:
    if not resume_path or not is_supported_resume(resume_path) or not Path(resume_path).exists():
        return False
    locator = page.locator(RESUME_HINT_SELECTOR).first
    try:
        if await locator.count() == 0:
            return False
        await locator.set_input_files(resume_path)
        return True
    except Exception:
        return False
