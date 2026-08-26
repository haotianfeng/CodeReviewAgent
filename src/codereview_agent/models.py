from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Severity = Literal["critical", "high", "medium", "low", "info"]


class ReviewIssue(BaseModel):
    """One actionable finding in a code review."""

    category: str = Field(description="bug, security, performance, style, or maintainability")
    severity: Severity
    file: str
    line: int | None = None
    title: str
    explanation: str
    suggestion: str


class ReviewMetadata(BaseModel):
    """Fixed runtime metadata fields kept compatible with strict JSON Schema."""

    project: str = Field(default="", description="Absolute path or project identifier")
    mode: str = Field(default="", description="Review mode, normally offline or llm")
    files_reviewed: str = Field(default="", description="Number of reviewed source files")
    model: str = Field(default="", description="Model identifier used for the review")


class ReviewReport(BaseModel):
    """Stable output contract for the CLI, web UI, and future GitHub bot."""

    summary: str
    score: int = Field(ge=0, le=100)
    issues: list[ReviewIssue] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    metadata: ReviewMetadata = Field(default_factory=ReviewMetadata)


class PatchResponse(BaseModel):
    """A review-driven, human-confirmable code change."""

    file: str
    summary: str
    patch: str = Field(default="", description="A unified diff for one existing source file")
    verification: list[str] = Field(default_factory=list)
