from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from automation.config import AutomationSettings, get_settings


class BrowserSession:
    def __init__(self, settings: AutomationSettings | None = None) -> None:
        self.settings = settings or get_settings()

    @asynccontextmanager
    async def open(self) -> AsyncIterator[tuple[Any, Any]]:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError("Playwright is required for live autofill runs. Install playwright and browsers.") from exc

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=self.settings.headless)
            context = await browser.new_context()
            context.set_default_timeout(self.settings.timeout_ms)
            page = await context.new_page()
            try:
                yield page, context
            finally:
                await context.close()
                await browser.close()


async def screenshot(page: Any, artifact_dir: Path, run_id: str, name: str) -> str | None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / run_id / f"{name}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        await page.screenshot(path=str(path), full_page=True)
    except Exception:
        return None
    return str(path)
