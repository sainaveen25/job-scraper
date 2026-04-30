from __future__ import annotations

from automation.platforms.base import PlatformAdapter


class GenericAdapter(PlatformAdapter):
    name = "generic"

    def detect(self, url: str, page=None) -> bool:
        return True
