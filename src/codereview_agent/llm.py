from __future__ import annotations

import json

from openai import OpenAI

from .models import PatchResponse, ReviewIssue, ReviewReport
from .prompts import SYSTEM_PROMPT


PATCH_SYSTEM_PROMPT = """You are a senior software engineer creating a minimal, safe code fix.
Return a structured response containing a unified diff for exactly one existing file.
The diff must use the supplied relative path in both the --- and +++ headers.
Change only what is needed to address the supplied review issue.
Do not include Markdown fences, explanations, or changes to unrelated files inside patch.
If the issue cannot be fixed safely from the supplied source, return an empty patch and explain why.
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
            "Generate a minimal unified diff for this review issue.\n\n"
            f"Review issue:\n{json.dumps(issue.model_dump(), ensure_ascii=False, indent=2)}\n\n"
            f"Source file ({issue.file}):\n{source}"
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
