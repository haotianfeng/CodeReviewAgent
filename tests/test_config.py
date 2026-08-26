from codereview_agent import config
from codereview_agent.config import Settings


def test_placeholder_api_key_is_treated_as_unconfigured(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "your_opencode_go_api_key_here")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")

    settings = Settings.from_env()

    assert settings.api_key is None
    assert settings.base_url == "https://example.test/v1"


def test_default_source_and_patch_character_limits(monkeypatch) -> None:
    monkeypatch.delenv("CODE_REVIEW_MAX_CHARS", raising=False)
    monkeypatch.delenv("CODE_REVIEW_MAX_PATCH_CHARS", raising=False)
    monkeypatch.setattr(config, "_read_streamlit_secrets", lambda: {})

    settings = Settings.from_env()

    assert settings.max_chars == 100_000
    assert settings.max_patch_chars == 300_000


def test_streamlit_secrets_are_used_when_environment_is_empty(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.setattr(
        config,
        "_read_streamlit_secrets",
        lambda: {
            "OPENAI_API_KEY": "secret-from-streamlit",
            "OPENAI_BASE_URL": "https://example.test/v1",
            "CODE_REVIEW_MODEL": "test-model",
        },
    )

    settings = Settings.from_env()

    assert settings.api_key == "secret-from-streamlit"
    assert settings.base_url == "https://example.test/v1"
    assert settings.model == "test-model"


def test_session_api_key_can_override_application_settings() -> None:
    settings = Settings(
        api_key="application-key",
        base_url="https://example.test/v1",
        model="test-model",
    )

    session_settings = settings.with_api_key("  session-key  ")

    assert settings.api_key == "application-key"
    assert session_settings.api_key == "session-key"
    assert session_settings.base_url == settings.base_url
    assert session_settings.model == settings.model
