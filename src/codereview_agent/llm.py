from __future__ import annotations

import json

from openai import OpenAI

from .models import PatchResponse, ReviewIssue, ReviewReport
from .prompts import SYSTEM_PROMPT


PATCH_SYSTEM_PROMPT = """你是一名资深软件工程师，正在为代码审查问题创建最小且安全的修复。
返回包含 Unified Diff 的结构化响应，且只能修改一个已存在的文件。
Diff 的 --- 和 +++ 文件头必须使用提供的相对路径。
只修改解决当前审查问题所必需的内容。
summary 和 verification 必须全部使用简体中文；file、路径、代码和 Diff 内容保持原格式。
不要在 patch 中加入 Markdown 代码围栏、解释文字或无关文件的修改。
如果无法根据给定源代码安全修复问题，请返回空 patch，并用简体中文说明原因。
"""


class LLMReviewer:
    def __init__(self, api_key: str, model: str, base_url: str | None = None) -> None:
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model

    def review(self, prompt: str) -> ReviewReport:
        response = self.client.responses.parse(
            model=self.model,
            text_format=ReviewReport,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        if response.output_parsed is None:
            raise RuntimeError("The model did not return a structured review report.")
        return response.output_parsed

    def generate_patch(self, issue: ReviewIssue, source: str) -> PatchResponse:
        prompt = (
            "请为以下审查问题生成最小化 Unified Diff。summary 和 verification 必须使用简体中文；"
            "file、路径、代码和 Diff 内容保持原格式。\n\n"
            f"审查问题：\n{json.dumps(issue.model_dump(), ensure_ascii=False, indent=2)}\n\n"
            f"源代码文件（{issue.file}）：\n{source}"
        )
        response = self.client.responses.parse(
            model=self.model,
            text_format=PatchResponse,
            input=[
                {"role": "system", "content": PATCH_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        if response.output_parsed is None:
            raise RuntimeError("The model did not return a structured patch.")
        return response.output_parsed
