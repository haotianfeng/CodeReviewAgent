from codereview_agent.config import Settings


def test_placeholder_api_key_is_treated_as_unconfigured(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "your_opencode_go_api_key_here")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")

    settings = Settings.from_env()

    assert settings.api_key is None
    assert settings.base_url == "https://example.test/v1"
