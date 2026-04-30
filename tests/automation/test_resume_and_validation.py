from automation.models import Field, FieldType, MappedField
from automation.resume_upload import is_supported_resume
from automation.validators import can_submit, validate_required_fields


def test_resume_file_type_support():
    assert is_supported_resume("resume.pdf")
    assert is_supported_resume("resume.docx")
    assert not is_supported_resume("resume.exe")


def test_validation_blocks_missing_required_before_submit():
    fields = [Field("Email", FieldType.TEXT, selector="#email", required=True)]
    validation = validate_required_fields(fields, [])
    assert not validation.ok
    assert not can_submit("submit", True, validation)


def test_submit_requires_explicit_allow_submit():
    fields = [Field("Email", FieldType.TEXT, selector="#email", required=True)]
    mapped = [MappedField(field=fields[0], profile_key="email", value="ada@example.com", source="profile", confidence=0.9)]
    validation = validate_required_fields(fields, mapped)
    assert validation.ok
    assert not can_submit("submit", False, validation)
    assert can_submit("submit", True, validation)
