from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Severity = Literal["critical", "high", "medium", "low", "info"]


class ReviewIssue(BaseModel):
    """代码审查中的一个可执行问题。"""

    category: str = Field(description="问题类别，例如 bug、security、performance、style 或 maintainability")
    severity: Severity
    file: str = Field(description="问题所在的源代码相对路径")
    line: int | None = Field(default=None, description="问题所在行号；无法确定时为 null")
    title: str = Field(description="使用简体中文书写的简短问题标题")
    explanation: str = Field(description="使用简体中文说明问题原因和影响")
    suggestion: str = Field(description="使用简体中文给出具体、可执行的修复建议")


class ReviewMetadata(BaseModel):
    """与严格 JSON Schema 兼容的固定运行时元数据字段。"""

    project: str = Field(default="", description="绝对路径或项目标识")
    mode: str = Field(default="", description="审查模式，通常为 offline 或 llm")
    files_reviewed: str = Field(default="", description="已审查的源代码文件数量")
    model: str = Field(default="", description="本次审查使用的模型标识")


class ReviewReport(BaseModel):
    """供命令行、网页界面和 GitHub Bot 使用的稳定输出契约。"""

    summary: str = Field(description="使用简体中文书写的整体审查总结")
    score: int = Field(ge=0, le=100, description="0 到 100 的代码质量评分")
    issues: list[ReviewIssue] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list, description="使用简体中文书写的代码优点")
    metadata: ReviewMetadata = Field(default_factory=ReviewMetadata)


class PatchResponse(BaseModel):
    """由审查结果驱动、可由用户确认的代码变更。"""

    file: str = Field(description="Patch 对应的源代码相对路径")
    summary: str = Field(description="使用简体中文书写的 Patch 说明")
    patch: str = Field(default="", description="针对一个已存在源代码文件的 Unified Diff")
    verification: list[str] = Field(default_factory=list, description="使用简体中文书写的验证建议")
