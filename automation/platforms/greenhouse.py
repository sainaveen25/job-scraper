from __future__ import annotations

from urllib.parse import urlparse

from automation.platforms.base import PlatformAdapter


class GreenhouseAdapter(PlatformAdapter):
    name = "greenhouse"

    def detect(self, url: str, page=None) -> bool:
        host = urlparse(url).netloc.casefold()
        return "greenhouse.io" in host or "boards.greenhouse" in host
