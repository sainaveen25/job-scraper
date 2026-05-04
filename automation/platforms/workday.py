from __future__ import annotations

from urllib.parse import urlparse

from automation.platforms.base import PlatformAdapter


class WorkdayAdapter(PlatformAdapter):
    name = "workday"
    next_button_selectors = (
        "button[data-automation-id='bottom-navigation-next-button']",
        "button[data-automation-id='pageFooterNextButton']",
        "button:has-text('Save and Continue')",
        "button:has-text('Next')",
    )
    submit_button_selectors = (
        "button[data-automation-id='bottom-navigation-submit-button']",
        "button[data-automation-id='submit']",
        "button:has-text('Submit')",
    )
    resume_input_selectors = (
        "input[type='file'][data-automation-id*='resume' i]",
        "input[type='file'][aria-label*='resume' i]",
    )

    def detect(self, url: str, page=None) -> bool:
        host = urlparse(url).netloc.casefold()
        return "myworkdayjobs.com" in host or "workdayjobs.com" in host
