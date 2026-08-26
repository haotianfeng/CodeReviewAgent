from codereview_agent.llm import PATCH_SYSTEM_PROMPT
from codereview_agent.prompts import SYSTEM_PROMPT


def test_review_prompt_requires_simplified_chinese_natural_language() -> None:
    assert "summary" in SYSTEM_PROMPT
    assert "title" in SYSTEM_PROMPT
    assert "explanation" in SYSTEM_PROMPT
    assert "suggestion" in SYSTEM_PROMPT
    assert "strengths" in SYSTEM_PROMPT
    assert "必须全部使用简体中文" in SYSTEM_PROMPT

    prompt = SYSTEM_PROMPT
    assert "简体中文" in prompt


def test_review_input_prompt_is_in_chinese() -> None:
    from codereview_agent.prompts import build_review_prompt

    prompt = build_review_prompt([("input.py", "return 1\n")], [])
    assert prompt.startswith("请审查以下项目文件")
    assert "input.py" in prompt


def test_patch_prompt_requires_simplified_chinese_summary_and_verification() -> None:
    assert "summary 和 verification 必须全部使用简体中文" in PATCH_SYSTEM_PROMPT
