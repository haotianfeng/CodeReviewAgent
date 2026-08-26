from __future__ import annotations

from collections.abc import MutableMapping



PLACEHOLDER_API_KEYS = {
    "your_opencode_go_api_key_here",
    "your_api_key_here",
}


# Values that belong to a browser session only. They are intentionally not
# persisted in a database, cookie, URL, or project file.
SESSION_STATE_KEYS = (
    "user_api_key",
    "api_key_input",
    "report",
    "workspace",
    "patches",
    "patch_applications",
    "review_count",
    "demo_authenticated",
    "offline_mode",
    "severity_filter",
    "patch_issue_selector",
)


def normalize_user_api_key(value: object) -> str | None:
    """Return a usable session API key without exposing or persisting it."""
    if not isinstance(value, str):
        return None
    api_key = value.strip()
    if not api_key or api_key in PLACEHOLDER_API_KEYS:
        return None
    return api_key


def clear_session_state(session_state: MutableMapping[str, object]) -> None:
    """Clear credentials and review artifacts for a browser session."""
    for key in SESSION_STATE_KEYS:
        session_state.pop(key, None)
