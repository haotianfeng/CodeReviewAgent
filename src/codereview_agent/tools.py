from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go"}
IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}


@dataclass(frozen=True)
class SourceFile:
    path: str
    extension: str
    content: str


def collect_source_files(project_dir: Path, max_files: int = 30, max_chars: int = 50_000) -> list[SourceFile]:
    """Read a bounded, deterministic set of source files from a project."""
    project_dir = project_dir.resolve()
    if not project_dir.is_dir():
        raise NotADirectoryError(f"Project directory does not exist: {project_dir}")

    result: list[SourceFile] = []
    total_chars = 0
    candidates = sorted(
        path
        for path in project_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and not any(part in IGNORED_DIRS for part in path.parts)
    )

    for path in candidates[:max_files]:
        remaining = max_chars - total_chars
        if remaining <= 0:
            break
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        content = content[:remaining]
        result.append(SourceFile(path=str(path.relative_to(project_dir)), extension=path.suffix.lower(), content=content))
        total_chars += len(content)
    return result


def run_python_static_checks(files: list[SourceFile]) -> list[dict[str, object]]:
    """Small deterministic checks that work even without an LLM/API key."""
    findings: list[dict[str, object]] = []
    for source in files:
        if source.extension != ".py":
            continue
        try:
            tree = ast.parse(source.content, filename=source.path)
        except SyntaxError as exc:
            findings.append(
                {
                    "category": "bug",
                    "severity": "high",
                    "file": source.path,
                    "line": exc.lineno,
                    "title": "Python syntax error",
                    "explanation": exc.msg,
                    "suggestion": "Fix the syntax error before running or reviewing this module.",
                }
            )
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                findings.append(
                    {
                        "category": "maintainability",
                        "severity": "medium",
                        "file": source.path,
                        "line": node.lineno,
                        "title": "Bare except catches every exception",
                        "explanation": "A bare except can hide KeyboardInterrupt, SystemExit, and unexpected failures.",
                        "suggestion": "Catch the narrowest expected exception type and log the failure context.",
                    }
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                findings.append(
                    {
                        "category": "security",
                        "severity": "high",
                        "file": source.path,
                        "line": node.lineno,
                        "title": "Dynamic code execution is unsafe",
                        "explanation": f"{node.func.id} can execute attacker-controlled code when its input is not fully trusted.",
                        "suggestion": "Replace dynamic evaluation with a safe parser or an explicit allowlist of operations.",
                    }
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"run", "call", "Popen", "check_call", "check_output"}:
                    uses_shell = any(
                        keyword.arg == "shell"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                        for keyword in node.keywords
                    )
                    if uses_shell:
                        findings.append(
                            {
                                "category": "security",
                                "severity": "high",
                                "file": source.path,
                                "line": node.lineno,
                                "title": "Subprocess uses shell=True",
                                "explanation": "Passing shell=True can turn untrusted command input into shell injection.",
                                "suggestion": "Pass an argument list with shell=False and validate each argument.",
                            }
                        )
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defaults = [*node.args.defaults, *(item for item in node.args.kw_defaults if item is not None)]
                if any(isinstance(default, (ast.List, ast.Dict, ast.Set)) for default in defaults):
                    findings.append(
                        {
                            "category": "bug",
                            "severity": "medium",
                            "file": source.path,
                            "line": node.lineno,
                            "title": "Mutable default argument",
                            "explanation": "A list, dictionary, or set default is shared across function calls and can retain stale state.",
                            "suggestion": "Use None as the default and create a new mutable value inside the function.",
                        }
                    )
    return findings
