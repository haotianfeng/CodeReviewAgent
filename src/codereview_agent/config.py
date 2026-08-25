from __future__ import annotations

import os
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Settings:
    """Runtime configuration loaded from environment variables and .env."""

    api_key: str | None
    base_url: str | None
    model: str
    max_files: int = 30
    max_chars: int = 50_000
    demo_access_password: str | None = None
    max_reviews_per_session: int = 10

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Settings":
        if load_dotenv is not None:
            load_dotenv(dotenv_path=env_file, override=False)

        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key or api_key in PLACEHOLDER_API_KEYS:
            api_key = None

        return cls(
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL") or DEFAULT_OPENCODE_GO_BASE_URL,
            model=os.getenv("CODE_REVIEW_MODEL", "gpt-5.6-luna"),
            max_files=int(os.getenv("CODE_REVIEW_MAX_FILES", "30")),
            max_chars=int(os.getenv("CODE_REVIEW_MAX_CHARS", "50000")),
            demo_access_password=os.getenv("DEMO_ACCESS_PASSWORD") or None,
            max_reviews_per_session=int(os.getenv("DEMO_MAX_REVIEWS_PER_SESSION", "10")),
        )
