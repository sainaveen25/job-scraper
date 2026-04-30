from __future__ import annotations

from urllib.parse import urlparse

from automation.platforms.base import PlatformAdapter


class WorkdayAdapter(PlatformAdapter):
    name = "workday"

    def detect(self, url: str, page=None) -> bool:
        host = urlparse(url).netloc.casefold()
        return "myworkdayjobs.com" in host or "workdayjobs.com" in host
