from types import SimpleNamespace

from codereview_agent.llm import LLMReviewer
from codereview_agent.models import PatchResponse, ReviewIssue


class FakeResponses:
    def parse(self, **kwargs):
        assert kwargs["text_format"] is PatchResponse
        return SimpleNamespace(
            output_parsed=PatchResponse(
                file="input.py",
                summary="Replace unsafe evaluation",
                patch="--- a/input.py\n+++ b/input.py\n@@ -1,1 +1,1 @@\n-return eval(value)\n+return value\n",
            )
        )


class FakeClient:
    def __init__(self, **kwargs):
        self.responses = FakeResponses()


def test_generate_patch_uses_responses_structured_output(monkeypatch) -> None:
    monkeypatch.setattr("codereview_agent.llm.OpenAI", FakeClient)
    issue = ReviewIssue(
        category="security",
        severity="high",
        file="input.py",
        line=1,
        title="Dynamic code execution is unsafe",
        explanation="Input is evaluated dynamically.",
        suggestion="Use a safe parser.",
    )

    result = LLMReviewer("test-key", "test-model", "https://example.test/v1").generate_patch(
        issue,
        "return eval(value)\n",
    )

    assert result.file == "input.py"
    assert result.patch.startswith("--- a/input.py")
