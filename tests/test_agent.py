from pathlib import Path

import pytest

from codereview_agent.agent import CodeReviewAgent
from codereview_agent.config import Settings
from codereview_agent.models import PatchResponse, ReviewIssue


MALFORMED_COUNT_PATCH = """--- a/sample.py
+++ b/sample.py
@@ -1,7 +1,5 @@
 def run():
-    return 1
+    return 2
"""


class FakeReviewer:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def generate_patch(self, _issue: ReviewIssue, _source: str) -> PatchResponse:
        return PatchResponse(file="sample.py", summary="已替换返回值", patch=MALFORMED_COUNT_PATCH)


def test_agent_normalizes_generated_patch_before_returning(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def run():\n    return 1\n", encoding="utf-8")
    monkeypatch.setattr("codereview_agent.agent.LLMReviewer", FakeReviewer)
    agent = CodeReviewAgent(
        Settings(api_key="test-key", base_url="https://example.test/v1", model="test-model")
    )
    issue = ReviewIssue(
        category="bug",
        severity="medium",
        file="sample.py",
        line=2,
        title="返回值错误",
        explanation="函数返回了错误的值。",
        suggestion="返回正确的值。",
    )

    result = agent.generate_patch(tmp_path, issue)

    assert "@@ -1,2 +1,2 @@" in result.patch


def test_agent_uses_separate_patch_character_limit(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def run():\n    return 1\n" + "#" * 100_000, encoding="utf-8")
    monkeypatch.setattr("codereview_agent.agent.LLMReviewer", FakeReviewer)
    agent = CodeReviewAgent(
        Settings(api_key="test-key", base_url="https://example.test/v1", model="test-model")
    )
    issue = ReviewIssue(
        category="bug",
        severity="medium",
        file="sample.py",
        line=1,
        title="示例问题",
        explanation="示例说明。",
        suggestion="示例建议。",
    )

    result = agent.generate_patch(tmp_path, issue)

    assert result.file == "sample.py"


def test_agent_rejects_source_above_patch_character_limit(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("x" * 300_001, encoding="utf-8")
    monkeypatch.setattr("codereview_agent.agent.LLMReviewer", FakeReviewer)
    agent = CodeReviewAgent(
        Settings(api_key="test-key", base_url="https://example.test/v1", model="test-model")
    )
    issue = ReviewIssue(
        category="bug",
        severity="medium",
        file="sample.py",
        line=1,
        title="示例问题",
        explanation="示例说明。",
        suggestion="示例建议。",
    )

    with pytest.raises(ValueError, match="300,000"):
        agent.generate_patch(tmp_path, issue)
