from codereview_agent.session import clear_session_state, normalize_user_api_key


def test_normalize_user_api_key_does_not_accept_empty_or_placeholder() -> None:
    assert normalize_user_api_key("") is None
    assert normalize_user_api_key("  ") is None
    assert normalize_user_api_key("your_opencode_go_api_key_here") is None
    assert normalize_user_api_key("  session-key  ") == "session-key"


def test_clear_session_state_removes_credentials_and_review_artifacts() -> None:
    state = {
        "user_api_key": "session-key",
        "api_key_input": "session-key",
        "report": object(),
        "workspace": object(),
        "patches": {},
        "patch_applications": {},
        "review_count": 3,
        "demo_authenticated": True,
        "offline_mode": False,
        "severity_filter": ["high"],
        "patch_issue_selector": 0,
        "unrelated_state": "keep",
    }

    clear_session_state(state)

    assert state == {"unrelated_state": "keep"}
