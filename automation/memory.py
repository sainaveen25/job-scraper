from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from automation.field_mapping import is_sensitive_question, normalize_question
from automation.models import FieldMemoryEntry


SENSITIVE_MEMORY_KEYS = {"password", "passcode", "secret", "token"}


class FieldMemoryStore:
    def __init__(self, path: str | Path = "data/apply_field_memory.json") -> None:
        self.path = Path(path)

    def load(self) -> list[FieldMemoryEntry]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [FieldMemoryEntry(**item) for item in payload if isinstance(item, dict)]

    def save(self, entries: list[FieldMemoryEntry]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(entry) for entry in entries], indent=2), encoding="utf-8")

    def upsert(self, entry: FieldMemoryEntry) -> FieldMemoryEntry:
        if _looks_like_password(entry.original_question, entry.normalized_question):
            raise ValueError("Refusing to persist third-party website passwords or secrets.")
        entry.normalized_question = normalize_question(entry.normalized_question or entry.original_question)
        entry.sensitive = entry.sensitive or is_sensitive_question(entry.original_question)
        entry.last_used_at = datetime.now(timezone.utc).isoformat()

        entries = self.load()
        replaced = False
        for idx, existing in enumerate(entries):
            if existing.normalized_question == entry.normalized_question and existing.platform == entry.platform:
                entries[idx] = entry
                replaced = True
                break
        if not replaced:
            entries.append(entry)
        self.save(entries)
        return entry


def _looks_like_password(*labels: Any) -> bool:
    text = " ".join(str(label or "").casefold() for label in labels)
    return any(key in text for key in SENSITIVE_MEMORY_KEYS)
