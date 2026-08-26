from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is declared in pyproject
    load_dotenv = None


DEFAULT_OPENCODE_GO_BASE_URL = "https://opencode.ai/zen/go/v1"
PLACEHOLDER_API_KEYS = {
    "your_opencode_go_api_key_here",
    "your_api_key_here",
}


def _read_streamlit_secrets() -> dict[str, object]:
    """Read Community Cloud secrets without making Streamlit a core dependency."""
    try:
        import streamlit as st

        return dict(st.secrets)
    except (ImportError, FileNotFoundError, RuntimeError, KeyError):
        return {}


@dataclass(frozen=True)
class Settings:
    """Runtime configuration loaded from .env, environment, or Streamlit secrets."""

    api_key: str | None
    base_url: str | None
    model: str
    max_files: int = 30
    max_chars: int = 100_000
    demo_access_password: str | None = None
    max_reviews_per_session: int = 10

    def with_api_key(self, api_key: str | None) -> "Settings":
        """Return a copy using a key supplied by the current browser session."""
        return replace(self, api_key=api_key.strip() if api_key and api_key.strip() else None)

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Settings":
        if load_dotenv is not None:
            load_dotenv(dotenv_path=env_file, override=False)

        secrets = _read_streamlit_secrets()

        def setting(name: str, default: object = "") -> object:
            return os.getenv(name, secrets.get(name, default))

        api_key = str(setting("OPENAI_API_KEY", "")).strip()
        if not api_key or api_key in PLACEHOLDER_API_KEYS:
            api_key = None

        return cls(
            api_key=api_key,
            base_url=str(setting("OPENAI_BASE_URL", "")) or DEFAULT_OPENCODE_GO_BASE_URL,
            model=str(setting("CODE_REVIEW_MODEL", "gpt-5.6-luna")),
            max_files=int(setting("CODE_REVIEW_MAX_FILES", "30")),
            max_chars=int(setting("CODE_REVIEW_MAX_CHARS", "100000")),
            demo_access_password=str(setting("DEMO_ACCESS_PASSWORD", "")) or None,
            max_reviews_per_session=int(setting("DEMO_MAX_REVIEWS_PER_SESSION", "10")),
        )
