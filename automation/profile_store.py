from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from automation.field_mapping import is_sensitive_question, normalize_question
from automation.models import UserProfile


CONFIRMED_KEYS = "_confirmed_fields"


class ProfileStore:
    def __init__(self, path: str | Path = "data/apply_profiles.json") -> None:
        self.path = Path(path)

    def load(self, user_id: str) -> dict[str, Any]:
        payload = self._read()
        profile = payload.get(user_id) if isinstance(payload, dict) else None
        return dict(profile or {})

    def save(self, user_id: str, profile: dict[str, Any]) -> dict[str, Any]:
        payload = self._read()
        normalized = normalize_profile(profile)
        normalized["userId"] = user_id
        payload[user_id] = normalized
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return normalized

    def merge(self, user_id: str, incoming: dict[str, Any], *, source: str = "manual") -> dict[str, Any]:
        current = self.load(user_id)
        merged = merge_profile(current, incoming, source=source)
        return self.save(user_id, merged)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}


def normalize_profile(profile: dict[str, Any]) -> dict[str, Any]:
    normalized = UserProfile.from_mapping(profile).__dict__.copy()
    normalized["skills"] = list(dict.fromkeys(normalized.get("skills") or []))
    normalized["education"] = _list_of_dicts(normalized.get("education"))
    normalized["work_experience"] = _list_of_dicts(normalized.get("work_experience"))
    normalized["common_questions"] = {
        normalize_question(key): value
        for key, value in dict(normalized.get("common_questions") or {}).items()
        if value not in (None, "")
    }
    rules = dict(normalized.get("sensitive_answer_rules") or {})
    normalized["sensitive_answer_rules"] = {
        normalize_question(key): (
            {"approved": bool(value.get("approved")), "value": value.get("value")}
            if isinstance(value, dict)
            else {"approved": bool(value)}
        )
        for key, value in rules.items()
        if is_sensitive_question(key)
    }
    return normalized


def merge_profile(current: dict[str, Any], incoming: dict[str, Any], *, source: str = "manual") -> dict[str, Any]:
    merged = normalize_profile(current)
    incoming_normalized = normalize_profile(incoming)
    confirmed = set(current.get(CONFIRMED_KEYS) or [])
    for key, value in incoming_normalized.items():
        if key in {"extras", CONFIRMED_KEYS} or value in (None, "", [], {}):
            continue
        if key in confirmed and source == "resume_import":
            continue
        if isinstance(value, list):
            merged[key] = _merge_lists(merged.get(key) or [], value)
        elif isinstance(value, dict):
            merged[key] = {**dict(merged.get(key) or {}), **value}
        elif merged.get(key) in (None, "") or source != "resume_import":
            merged[key] = value
    merged[CONFIRMED_KEYS] = sorted(confirmed | set(incoming.get(CONFIRMED_KEYS) or []))
    return merged


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, dict)]


def _merge_lists(current: list[Any], incoming: list[Any]) -> list[Any]:
    seen: set[str] = set()
    merged: list[Any] = []
    for item in current + incoming:
        key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item).casefold()
        if key not in seen:
            merged.append(item)
            seen.add(key)
    return merged
