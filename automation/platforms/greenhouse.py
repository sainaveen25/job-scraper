from __future__ import annotations

from urllib.parse import urlparse

from automation.platforms.base import PlatformAdapter


class GreenhouseAdapter(PlatformAdapter):
    name = "greenhouse"
    next_button_selectors = (
        "#submit_app",
        "button:has-text('Next')",
        "button:has-text('Continue')",
    )
    submit_button_selectors = (
        "#submit_app:has-text('Submit Application')",
        "#submit_app",
        "button:has-text('Submit Application')",
    )
    resume_input_selectors = (
        "input[type='file'][name='job_application[resume]']",
        "input[type='file'][id*='resume']",
    )

    def detect(self, url: str, page=None) -> bool:
        host = urlparse(url).netloc.casefold()
        return "greenhouse.io" in host or "boards.greenhouse" in host
