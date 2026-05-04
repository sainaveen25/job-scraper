from __future__ import annotations

from urllib.parse import urlparse

from automation.platforms.base import PlatformAdapter


class LeverAdapter(PlatformAdapter):
    name = "lever"
    next_button_selectors = (
        ".postings-btn:has-text('Next')",
        ".template-btn-submit:has-text('Next')",
        "button:has-text('Continue')",
    )
    submit_button_selectors = (
        ".postings-btn-submit:has-text('Submit')",
        ".template-btn-submit:has-text('Submit')",
        "button:has-text('Submit Application')",
    )
    resume_input_selectors = (
        "input[type='file'][name='resume']",
        "input[type='file'][id*='resume']",
    )

    def detect(self, url: str, page=None) -> bool:
        host = urlparse(url).netloc.casefold()
        return host.endswith("lever.co") or "jobs.lever.co" in host
