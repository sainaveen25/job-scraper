from automation.profile_store import CONFIRMED_KEYS, ProfileStore
from automation.resume_import import hydrate_profile_from_resume, preview_resume_profile_merge, resume_metadata


def test_resume_import_merges_without_overwriting_confirmed_profile_data(tmp_path):
    store = ProfileStore(tmp_path / "profiles.json")
    store.save(
        "user_1",
        {
            "email": "confirmed@example.com",
            CONFIRMED_KEYS: ["email"],
            "skills": ["Python"],
        },
    )

    result = hydrate_profile_from_resume(
        user_id="user_1",
        profile_store=store,
        resume_path=tmp_path / "resume.pdf",
        resume_id="resume_1",
        parsed_resume={
            "name": "Ada Lovelace",
            "email": "resume@example.com",
            "phone": "555-0100",
            "education": [{"school": "University of London"}],
            "work_experience": [{"company": "Acme", "title": "Engineer"}],
            "skills": ["Python", "TypeScript"],
        },
    )

    assert result["profile"]["email"] == "confirmed@example.com"
    assert result["profile"]["phone"] == "555-0100"
    assert result["profile"]["education"][0]["school"] == "University of London"
    assert result["profile"]["skills"] == ["Python", "TypeScript"]
    assert result["resume"]["fileType"] == "pdf"
    assert result["overwritesConfirmedFields"] is False


def test_resume_import_supports_docx_metadata_and_preview_merge():
    metadata = resume_metadata("Ada Resume.docx", resume_id="resume_2", upload_preference="docx")
    preview = preview_resume_profile_merge(
        {"first_name": "Ada", CONFIRMED_KEYS: ["first_name"]},
        {"first_name": "A.", "last_name": "Lovelace"},
    )

    assert metadata["mimeType"].endswith("wordprocessingml.document")
    assert metadata["uploadPreference"] == "docx"
    assert preview["mergedProfile"]["first_name"] == "Ada"
    assert preview["mergedProfile"]["last_name"] == "Lovelace"
