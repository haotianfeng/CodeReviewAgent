from __future__ import annotations

from pathlib import Path

from .config import Settings
from .llm import LLMReviewer
from .models import PatchResponse, ReviewIssue, ReviewMetadata, ReviewReport
from .prompts import build_review_prompt
from .patcher import PatchError, normalize_unified_patch, safe_relative_path
from .tools import collect_source_files, run_python_static_checks

MAX_PATCH_ATTEMPTS = 3


class CodeReviewAgent:
    """Orchestrates project inspection, deterministic checks, and LLM review."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()

    def review(self, project_dir: str | Path, dry_run: bool = False) -> ReviewReport:
        project_path = Path(project_dir).resolve()
        files = collect_source_files(project_path, self.settings.max_files, self.settings.max_chars)
        if not files:
            raise ValueError("No supported source files were found in the project directory.")

        static_findings = run_python_static_checks(files)
        if dry_run or not self.settings.api_key:
            return self._offline_report(project_path, files, static_findings)

        reviewer = LLMReviewer(self.settings.api_key, self.settings.model, self.settings.base_url)
        prompt = build_review_prompt([(item.path, item.content) for item in files], static_findings)
        report = reviewer.review(prompt)
        report.metadata.project = str(project_path)
        report.metadata.mode = "llm"
        report.metadata.files_reviewed = str(len(files))
        report.metadata.model = self.settings.model
        return report

    def generate_patch(self, project_dir: str | Path, issue: ReviewIssue) -> PatchResponse:
        """Generate a patch for one issue without modifying the source workspace."""
        if not self.settings.api_key:
            raise RuntimeError("生成 Patch 需要配置 OPENAI_API_KEY。")

        project_path = Path(project_dir).resolve()
        relative_file = safe_relative_path(issue.file)
        source_path = (project_path / relative_file).resolve()
        if project_path not in source_path.parents or not source_path.is_file():
            raise ValueError(f"审查问题对应的文件不存在：{issue.file}")
        try:
            source = source_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"无法按 UTF-8 读取文件：{issue.file}") from exc
        if len(source) > self.settings.max_patch_chars:
            raise ValueError(
                f"文件超过 Patch 字符限制（{self.settings.max_patch_chars:,}），暂不生成 Patch：{issue.file}"
            )

        reviewer = LLMReviewer(self.settings.api_key, self.settings.model, self.settings.base_url)
        feedback: str | None = None
        last_error: str | None = None
        for _attempt in range(MAX_PATCH_ATTEMPTS):
            patch = (
                reviewer.generate_patch(issue, source, feedback=feedback)
                if feedback
                else reviewer.generate_patch(issue, source)
            )
            try:
                if patch.file != issue.file:
                    raise PatchError(f"模型返回了错误的 Patch 文件：{patch.file}")
                normalized_patch = normalize_unified_patch(patch.patch, source, expected_file=issue.file)
            except PatchError as exc:
                last_error = str(exc)
                feedback = str(exc)
                continue
            return patch.model_copy(update={"patch": normalized_patch})
        raise ValueError(
            f"模型生成的 Patch 连续 {MAX_PATCH_ATTEMPTS} 次无法通过安全校验：{last_error}"
        )

    @staticmethod
    def _offline_report(project_path: Path, files, static_findings) -> ReviewReport:
        issues = [ReviewIssue.model_validate(item) for item in static_findings]
        score = max(0, 100 - min(60, len(issues) * 15))
        return ReviewReport(
            summary=(
                "离线审查已完成，使用了确定性的 Python 检查。"
                "配置 OPENAI_API_KEY 后可启用大模型辅助审查。"
            ),
            score=score,
            issues=issues,
            strengths=[f"已安全收集 {len(files)} 个受支持的源代码文件。"],
            metadata=ReviewMetadata(
                project=str(project_path),
                mode="offline",
                files_reviewed=str(len(files)),
            ),
        )
