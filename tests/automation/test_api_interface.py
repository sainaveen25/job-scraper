from automation import continue_application, submit_application
from automation.api import (
    get_apply_session,
    post_apply_continue,
    post_apply_save_answer,
    post_apply_session_continue,
    post_apply_session_create,
    post_apply_session_fill_page,
    post_apply_session_save_answer,
    post_apply_session_start,
    post_apply_session_submit,
    post_apply_submit,
    post_extension_apply_session_create,
)


def test_apply_callables_are_exported():
    assert callable(continue_application)
    assert callable(submit_application)
    assert callable(post_apply_continue)
    assert callable(post_apply_save_answer)
    assert callable(post_apply_submit)
    assert callable(post_apply_session_create)
    assert callable(get_apply_session)
    assert callable(post_apply_session_start)
    assert callable(post_apply_session_fill_page)
    assert callable(post_apply_session_continue)
    assert callable(post_apply_session_save_answer)
    assert callable(post_apply_session_submit)
    assert callable(post_extension_apply_session_create)
