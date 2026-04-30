import pytest

from automation.memory import FieldMemoryStore
from automation.models import FieldMemoryEntry


def test_memory_upsert_persists_reusable_answer(tmp_path):
    store = FieldMemoryStore(tmp_path / "memory.json")
    saved = store.upsert(
        FieldMemoryEntry(
            original_question="Are you authorized to work in the United States?",
            normalized_question="authorized to work",
            answer="Yes",
            answer_type="radio",
            platform="lever",
        )
    )
    assert saved.normalized_question == "authorized to work"
    assert store.load()[0].answer == "Yes"


def test_memory_refuses_plain_text_password_storage(tmp_path):
    store = FieldMemoryStore(tmp_path / "memory.json")
    with pytest.raises(ValueError):
        store.upsert(
            FieldMemoryEntry(
                original_question="Account password",
                normalized_question="password",
                answer="super-secret",
                answer_type="password",
            )
        )
