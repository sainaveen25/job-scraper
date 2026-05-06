from automation import continue_application, submit_application
from automation.api import (
    get_apply_session,
    post_apply_continue,
    post_apply_save_answer,
    post_apply_session_continue,
    post_apply_session_create,
    post_apply_session_fill_page,
    post_apply_session_handoff,
    post_apply_session_save_answer,
    post_apply_session_start,
    post_apply_session_submit,
    post_apply_submit,
    post_extension_apply_session_create,
    get_extension_install,
    get_questionnaire_status,
    get_theme_preference,
    post_profile_update,
    post_resume_import_preview,
    post_theme_preference,
)


def test_apply_callables_are_exported():
    assert callable(continue_application)
    assert callable(submit_application)
    assert callable(post_apply_continue)
    assert callable(post_apply_save_answer)
    assert callable(post_apply_submit)
    assert callable(post_apply_session_create)
    assert callable(post_apply_session_handoff)
    assert callable(get_apply_session)
    assert callable(post_apply_session_start)
    assert callable(post_apply_session_fill_page)
    assert callable(post_apply_session_continue)
    assert callable(post_apply_session_save_answer)
    assert callable(post_apply_session_submit)
    assert callable(post_extension_apply_session_create)
    assert callable(get_extension_install)
    assert callable(get_theme_preference)
    assert callable(post_theme_preference)
    assert callable(post_profile_update)
    assert callable(post_resume_import_preview)
    assert callable(get_questionnaire_status)


def test_extension_install_route_contract_prevents_404():
    payload = get_extension_install()

    assert payload["ok"] is True
    assert payload["installUrl"] == "/extension/install"
    assert payload["downloadUrl"] == "/extension/download"
