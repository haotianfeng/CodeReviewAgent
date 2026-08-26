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
                    "title": "Python 语法错误",
                    "explanation": "Python 解析器无法识别此处的语法，请检查该行附近的括号、缩进、冒号和关键字。",
                    "suggestion": "在运行或审查此模块前修复语法错误。",
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
                        "title": "裸 except 捕获了所有异常",
                        "explanation": "裸 except 可能隐藏 KeyboardInterrupt、SystemExit 以及其他未预期的失败。",
                        "suggestion": "捕获范围最小的预期异常类型，并记录失败上下文。",
                    }
                )
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                findings.append(
                    {
                        "category": "security",
                        "severity": "high",
                        "file": source.path,
                        "line": node.lineno,
                        "title": "动态代码执行存在安全风险",
                        "explanation": f"当输入不完全可信时，{node.func.id} 可能执行攻击者控制的代码。",
                        "suggestion": "使用安全解析器或明确的操作白名单替代动态执行。",
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
                                "title": "子进程调用使用了 shell=True",
                                "explanation": "传入 shell=True 可能将不可信命令输入转化为 Shell 注入。",
                                "suggestion": "使用参数列表并设置 shell=False，同时校验每个参数。",
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
                            "title": "函数使用了可变默认参数",
                            "explanation": "列表、字典或集合默认值会在多次函数调用之间共享，并可能保留过期状态。",
                            "suggestion": "使用 None 作为默认值，并在函数内部创建新的可变对象。",
                        }
                    )
    return findings
