from __future__ import annotations

import ast
import io
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class PatchError(ValueError):
    """Raised when a generated patch is unsafe or cannot be applied."""


@dataclass(frozen=True)
class PatchApplication:
    """Result of applying a patch to an isolated workspace copy."""

    workspace: Path
    changed_file: str
    zip_bytes: bytes


_HUNK_RE = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@"
)


def safe_relative_path(filename: str) -> Path:
    """Return a safe relative path or reject traversal and absolute paths."""
    normalized = filename.replace("\\", "/").strip()
    if not normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:/", normalized):
        raise PatchError(f"不安全的文件路径：{filename}")
    path = PurePosixPath(normalized)
    if any(part in ("", ".", "..") for part in path.parts):
        raise PatchError(f"不安全的文件路径：{filename}")
    return Path(*path.parts)


def _patch_path(header: str) -> Path:
    value = header[4:].split("\t", 1)[0].strip()
    if value.startswith("a/") or value.startswith("b/"):
        value = value[2:]
    return safe_relative_path(value)


def _rewrite_hunk_header(header: str, match: re.Match[str], old_count: int, new_count: int) -> str:
    """Rewrite only hunk line counts while preserving starts and context text."""
    suffix = header[match.end() :]
    return (
        f"@@ -{match.group(1)},{old_count} +{match.group(3)},{new_count} @@"
        f"{suffix}"
    )


def _clean_patch(patch: str) -> list[str]:
    text = patch.replace("\r\n", "\n").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    lines = text.splitlines()
    header_index = next((i for i, line in enumerate(lines) if line.startswith("--- ")), None)
    if header_index is None or header_index + 1 >= len(lines) or not lines[header_index + 1].startswith("+++ "):
        raise PatchError("Patch 缺少有效的 unified diff 文件头")
    return lines[header_index:]


def _parse_patch_lines(
    lines: list[str], *, repair_counts: bool = False
) -> tuple[Path, list[tuple[int, int, list[str]]]]:
    old_path = _patch_path(lines[0])
    new_path = _patch_path(lines[1])
    if old_path != new_path:
        raise PatchError("Patch 只能修改一个已有文件，且不能新建或删除文件")

    hunks: list[tuple[int, int, list[str]]] = []
    index = 2
    while index < len(lines):
        header_index = index
        match = _HUNK_RE.match(lines[index])
        if not match:
            index += 1
            continue
        old_start = int(match.group(1))
        old_count = int(match.group(2) or "1")
        body: list[str] = []
        index += 1
        while index < len(lines) and not lines[index].startswith("@@ "):
            line = lines[index]
            if line.startswith((" ", "+", "-", "\\")):
                body.append(line)
            else:
                raise PatchError("Patch 包含无法识别的 hunk 内容")
            index += 1
        actual_old = sum(1 for line in body if line.startswith((" ", "-")))
        actual_new = sum(1 for line in body if line.startswith((" ", "+")))
        if actual_old != old_count:
            if not repair_counts:
                raise PatchError(f"Patch 原文件行数不匹配：期望 {old_count}，实际 {actual_old}")
        new_count = int(match.group(4) or "1")
        if actual_new != new_count:
            if not repair_counts:
                raise PatchError(f"Patch 新文件行数不匹配：期望 {new_count}，实际 {actual_new}")
        if repair_counts and (actual_old != old_count or actual_new != new_count):
            lines[header_index] = _rewrite_hunk_header(lines[header_index], match, actual_old, actual_new)
            old_count = actual_old
        hunks.append((old_start, old_count, body))

    if not hunks:
        raise PatchError("Patch 不包含任何修改 hunk")
    return old_path, hunks


def _parse_patch(patch: str, *, repair_counts: bool = False) -> tuple[Path, list[tuple[int, int, list[str]]]]:
    return _parse_patch_lines(_clean_patch(patch), repair_counts=repair_counts)


def _repair_patch_counts(patch: str) -> str:
    """Normalize hunk counts and return a clean, header-first unified diff."""
    lines = _clean_patch(patch)
    _parse_patch_lines(lines, repair_counts=True)
    normalized = "\n".join(lines) + "\n"
    _parse_patch(normalized)
    return normalized


def _apply_unified_patch_to_text(
    content: str, patch: str, expected_file: str | None = None
) -> tuple[str, str]:
    """Apply an already normalized unified patch after verifying its context."""
    relative_path, hunks = _parse_patch(patch)
    if expected_file is not None and relative_path != safe_relative_path(expected_file):
        raise PatchError(f"Patch 目标文件不是审查问题对应的文件：{relative_path}")

    line_ending = "\r\n" if "\r\n" in content else "\n"
    normalized_content = content.replace("\r\n", "\n").replace("\r", "\n")
    original = normalized_content.splitlines()
    result: list[str] = []
    cursor = 0
    for old_start, _old_count, body in hunks:
        target = old_start - 1
        if target < cursor or target > len(original):
            raise PatchError("Patch hunk 的行号超出原文件范围")
        result.extend(original[cursor:target])
        for line in body:
            marker, value = line[:1], line[1:]
            if marker == "\\":
                continue
            if marker == " ":
                if cursor >= len(original) or original[cursor] != value:
                    raise PatchError("Patch 上下文与原文件不一致，已拒绝应用")
                result.append(value)
                cursor += 1
            elif marker == "-":
                if cursor >= len(original) or original[cursor] != value:
                    raise PatchError("Patch 删除内容与原文件不一致，已拒绝应用")
                cursor += 1
            elif marker == "+":
                result.append(value)
    result.extend(original[cursor:])
    ending = "\n" if normalized_content.endswith("\n") else ""
    updated = "\n".join(result) + ending
    return updated.replace("\n", line_ending), str(relative_path).replace("\\", "/")


def normalize_unified_patch(
    patch: str, content: str, expected_file: str | None = None
) -> str:
    """Repair safe hunk-count errors and validate the patch against source content."""
    normalized_patch = _repair_patch_counts(patch)
    _apply_unified_patch_to_text(content, normalized_patch, expected_file)
    return normalized_patch


def apply_unified_patch_to_text(content: str, patch: str, expected_file: str | None = None) -> tuple[str, str]:
    """Apply a single-file unified diff after repairing and verifying it."""
    normalized_patch = _repair_patch_counts(patch)
    return _apply_unified_patch_to_text(content, normalized_patch, expected_file)


def _zip_workspace(root: Path) -> bytes:
    buffer = io.BytesIO()
    ignored = {".git", ".venv", "venv", "node_modules", "__pycache__"}
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(root.rglob("*")):
            if path.is_file() and not any(part in ignored for part in path.parts):
                archive.write(path, path.relative_to(root).as_posix())
    return buffer.getvalue()


def apply_patch_to_copy(project_dir: str | Path, patch: str, expected_file: str | None = None) -> PatchApplication:
    """Apply a patch to a temporary copy and validate changed Python syntax."""
    source_root = Path(project_dir).resolve()
    if not source_root.is_dir():
        raise PatchError(f"项目目录不存在：{source_root}")
    normalized_patch = _repair_patch_counts(patch)
    parsed_file, _hunks = _parse_patch(normalized_patch)
    if expected_file is not None and parsed_file != safe_relative_path(expected_file):
        raise PatchError(f"Patch 目标文件不是审查问题对应的文件：{parsed_file}")
    target = (source_root / parsed_file).resolve()
    if source_root not in target.parents or not target.is_file():
        raise PatchError(f"Patch 目标文件不存在：{parsed_file}")
    original = target.read_bytes().decode("utf-8")
    updated, changed_file = _apply_unified_patch_to_text(original, normalized_patch, expected_file)

    staged_root = Path(tempfile.mkdtemp(prefix="codereview-agent-patched-"))
    try:
        shutil.copytree(
            source_root,
            staged_root,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", ".venv", "venv", "node_modules", "__pycache__"),
        )
        staged_target = staged_root / parsed_file
        with staged_target.open("w", encoding="utf-8", newline="") as handle:
            handle.write(updated)
        if staged_target.suffix.lower() == ".py":
            try:
                ast.parse(updated, filename=changed_file)
            except SyntaxError as exc:
                raise PatchError(f"Patch 应用后 Python 语法检查失败：{exc.msg}") from exc
        return PatchApplication(
            workspace=staged_root,
            changed_file=changed_file,
            zip_bytes=_zip_workspace(staged_root),
        )
    except Exception:
        shutil.rmtree(staged_root, ignore_errors=True)
        raise
