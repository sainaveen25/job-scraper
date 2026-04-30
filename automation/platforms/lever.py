from __future__ import annotations

from urllib.parse import urlparse

from automation.platforms.base import PlatformAdapter


class LeverAdapter(PlatformAdapter):
    name = "lever"

    def detect(self, url: str, page=None) -> bool:
        host = urlparse(url).netloc.casefold()
        return host.endswith("lever.co") or "jobs.lever.co" in host
