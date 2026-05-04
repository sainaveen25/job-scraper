from __future__ import annotations

from pathlib import Path
from typing import Any


FILE_INPUT_SELECTOR = "input[type='file']"
RESUME_HINT_SELECTORS = (
    "input[type='file'][name*='resume' i], "
    "input[type='file'][id*='resume' i], "
    "input[type='file'][aria-label*='resume' i], "
    "input[type='file'][accept*='.pdf' i], "
    "input[type='file'][accept*='.doc' i], "
    "input[type='file']",
    "input[type='file'][name*='cv' i], input[type='file'][id*='cv' i]",
    "input[type='file'][data-qa*='resume' i], input[type='file'][data-testid*='resume' i]",
)
RESUME_HINT_SELECTOR = RESUME_HINT_SELECTORS[0]


def is_supported_resume(path: str | None) -> bool:
    if not path:
        return False
    suffix = Path(path).suffix.casefold()
    return suffix in {".pdf", ".docx", ".doc"}


async def upload_resume(page: Any, resume_path: str | None, selectors: tuple[str, ...] | list[str] = ()) -> bool:
    if not resume_path or not is_supported_resume(resume_path) or not Path(resume_path).exists():
        return False
    for selector in tuple(selectors) + RESUME_HINT_SELECTORS:
        locator = page.locator(selector).first
        try:
            if await locator.count() == 0:
                continue
            await locator.set_input_files(resume_path)
            return True
        except Exception:
            continue
    return False
