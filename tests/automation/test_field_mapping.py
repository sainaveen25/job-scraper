from automation.field_mapping import map_fields, normalize_question
from automation.models import Field, FieldMemoryEntry, FieldType, UserProfile


def test_common_label_variants_map_to_profile():
    fields = [
        Field("Given Name", FieldType.TEXT, selector="#first"),
        Field("Surname", FieldType.TEXT, selector="#last"),
        Field("Mobile Phone", FieldType.TEXT, selector="#phone"),
        Field("LinkedIn URL", FieldType.TEXT, selector="#linkedin"),
    ]
    known, unknown = map_fields(
        fields,
        UserProfile(
            first_name="Ada",
            last_name="Lovelace",
            phone="555-0100",
            linkedin_url="https://linkedin.com/in/ada",
        ),
    )

    assert not unknown
    assert {item.profile_key for item in known} == {"first_name", "last_name", "phone", "linkedin_url"}


def test_unknown_field_capture():
    known, unknown = map_fields([Field("Years of Rust experience", FieldType.TEXT, selector="#rust")], UserProfile())
    assert known == []
    assert unknown[0].field.normalized_question == "years of rust experience"
    assert unknown[0].reason == "unmapped"


def test_field_memory_reuse():
    fields = [Field("Years of Java experience", FieldType.TEXT, selector="#java")]
    memory = [
        FieldMemoryEntry(
            original_question="Years of Java experience",
            normalized_question=normalize_question("Years of Java experience"),
            answer="5",
            answer_type="text",
            platform="greenhouse",
        )
    ]
    known, unknown = map_fields(fields, UserProfile(), memory)
    assert not unknown
    assert known[0].value == "5"
    assert known[0].source == "memory"


def test_sensitive_demographic_questions_require_review():
    known, unknown = map_fields([Field("Veteran status", FieldType.SELECT, selector="#veteran")], UserProfile())
    assert known == []
    assert unknown[0].reason == "sensitive_question_requires_review"


def test_sensitive_memory_is_not_reused_for_demographic_questions():
    memory = [
        FieldMemoryEntry(
            original_question="Veteran status",
            normalized_question=normalize_question("Veteran status"),
            answer="I decline to answer",
            answer_type="select",
            sensitive=True,
        )
    ]

    known, unknown = map_fields([Field("Veteran status", FieldType.SELECT, selector="#veteran")], UserProfile(), memory)

    assert known == []
    assert unknown[0].reason == "sensitive_question_requires_review"
