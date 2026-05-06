from __future__ import annotations

from pathlib import Path
from typing import Any

from automation.profile_store import ProfileStore, merge_profile


SUPPORTED_RESUME_IMPORT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def resume_metadata(path: str | Path, *, resume_id: str | None = None, upload_preference: str | None = None) -> dict[str, Any]:
    file_path = Path(path)
    suffix = file_path.suffix.casefold()
    return {
        "id": resume_id,
        "fileName": file_path.name,
        "fileType": suffix.lstrip("."),
        "mimeType": SUPPORTED_RESUME_IMPORT_TYPES.get(suffix),
        "uploadPreference": (upload_preference or suffix.lstrip(".")).casefold() or None,
        "importSupported": suffix in SUPPORTED_RESUME_IMPORT_TYPES,
    }


def hydrate_profile_from_resume(
    *,
    user_id: str,
    parsed_resume: dict[str, Any],
    profile_store: ProfileStore,
    resume_path: str | Path | None = None,
    resume_id: str | None = None,
) -> dict[str, Any]:
    profile_patch = _profile_patch_from_resume(parsed_resume)
    merged = profile_store.merge(user_id, profile_patch, source="resume_import")
    return {
        "userId": user_id,
        "profile": merged,
        "resume": resume_metadata(resume_path, resume_id=resume_id) if resume_path else None,
        "status": "merged",
        "overwritesConfirmedFields": False,
    }


def preview_resume_profile_merge(current_profile: dict[str, Any], parsed_resume: dict[str, Any]) -> dict[str, Any]:
    patch = _profile_patch_from_resume(parsed_resume)
    return {
        "profilePatch": patch,
        "mergedProfile": merge_profile(current_profile, patch, source="resume_import"),
    }


def _profile_patch_from_resume(parsed: dict[str, Any]) -> dict[str, Any]:
    personal = dict(parsed.get("personal") or {})
    patch = {
        "personal": personal,
        "first_name": parsed.get("first_name") or personal.get("first_name"),
        "last_name": parsed.get("last_name") or personal.get("last_name"),
        "full_name": parsed.get("name") or parsed.get("full_name") or personal.get("full_name"),
        "email": parsed.get("email") or personal.get("email"),
        "phone": parsed.get("phone") or personal.get("phone"),
        "city": parsed.get("city") or personal.get("city"),
        "state": parsed.get("state") or personal.get("state"),
        "country": parsed.get("country") or personal.get("country"),
        "education": parsed.get("education") or [],
        "work_experience": parsed.get("work_experience") or parsed.get("experience") or [],
        "skills": parsed.get("skills") or [],
    }
    return {key: value for key, value in patch.items() if value not in (None, "", [], {})}
