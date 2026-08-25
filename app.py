from __future__ import annotations

import io
import json
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

from codereview_agent.agent import CodeReviewAgent
from codereview_agent.config import Settings
from codereview_agent.models import ReviewReport
from codereview_agent.patcher import PatchError, apply_patch_to_copy


st.set_page_config(page_title="CodeReviewAgent", page_icon="🔍", layout="wide")

SUPPORTED_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_TOTAL_UPLOAD_BYTES = 100 * 1024 * 1024
SEVERITY_LABELS = {
    "critical": "严重",
    "high": "高",
    "medium": "中",
    "low": "低",
    "info": "提示",
}


def _safe_relative_path(filename: str) -> Path:
    normalized = filename.replace("\\", "/")
    candidate = Path(normalized)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"不安全的文件路径：{filename}")
    parts = [part for part in candidate.parts if part not in ("", ".")]
    if not parts:
        raise ValueError(f"无效的文件路径：{filename}")
    return Path(*parts)


def _safe_destination(root: Path, relative: Path) -> Path:
    root = root.resolve()
    destination = (root / relative).resolve()
    if destination != root and root not in destination.parents:
        raise ValueError(f"文件路径超出工作区：{relative}")
    return destination


def _write_uploaded_file(root: Path, filename: str, content: bytes) -> None:
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"文件超过 25 MB 限制：{filename}")
    relative = _safe_relative_path(filename)
    if relative.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"暂不支持的文件类型：{filename}")
    destination = _safe_destination(root, relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)


def _extract_zip(root: Path, content: bytes) -> int:
    extracted = 0
    total_size = 0
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for item in archive.infolist():
            if item.is_dir():
                continue
            relative = _safe_relative_path(item.filename)
            if relative.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            if item.file_size > MAX_UPLOAD_BYTES:
                raise ValueError(f"压缩包内文件超过 25 MB 限制：{item.filename}")
            total_size += item.file_size
            if total_size > MAX_TOTAL_UPLOAD_BYTES:
                raise ValueError("压缩包内源代码总大小超过 100 MB 限制")
            _write_uploaded_file(root, str(relative), archive.read(item))
            extracted += 1
    return extracted


def materialize_uploads(uploaded_files) -> tuple[Path, int]:
    root = Path(tempfile.mkdtemp(prefix="codereview-agent-"))
    count = 0
    for uploaded in uploaded_files:
        content = uploaded.getvalue()
        if len(content) > MAX_UPLOAD_BYTES:
            raise ValueError(f"上传文件超过 25 MB 限制：{uploaded.name}")
        if uploaded.name.lower().endswith(".zip"):
            count += _extract_zip(root, content)
        else:
            _write_uploaded_file(root, uploaded.name, content)
            count += 1
    return root, count


def _read_snippet(root: Path | None, relative_file: str, line: int | None) -> str | None:
    if root is None:
        return None
    try:
        path = _safe_destination(root, _safe_relative_path(relative_file))
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    if not lines:
        return ""
    center = max(1, min(line or 1, len(lines)))
    start = max(1, center - 3)
    end = min(len(lines), center + 3)
    return "\n".join(f"{index:>4} | {lines[index - 1]}" for index in range(start, end + 1))


def _report_markdown(report: ReviewReport) -> str:
    lines = [
        "# CodeReviewAgent 审查报告",
        "",
        f"**评分：** {report.score}/100",
        "",
        "## 总结",
        "",
        report.summary,
        "",
        "## 问题列表",
        "",
    ]
    if not report.issues:
        lines.append("未发现问题。")
    for issue in report.issues:
        location = f"{issue.file}:{issue.line}" if issue.line else issue.file
        lines.extend(
            [
                f"### [{SEVERITY_LABELS.get(issue.severity, issue.severity)}] {issue.title}",
                f"- **位置：** `{location}`",
                f"- **类别：** {issue.category}",
                f"- **说明：** {issue.explanation}",
                f"- **建议：** {issue.suggestion}",
                "",
            ]
        )
    if report.strengths:
        lines.extend(["## 做得好的地方", ""])
        lines.extend(f"- {strength}" for strength in report.strengths)
    return "\n".join(lines) + "\n"


def _patch_state_key(issue) -> str:
    return f"{issue.file}:{issue.line}:{issue.title}"


def _render_patch_controls(issue, root: Path | None, settings: Settings, agent: CodeReviewAgent) -> None:
    if root is None:
        return
    state_key = _patch_state_key(issue)
    patches = st.session_state.setdefault("patches", {})
    applications = st.session_state.setdefault("patch_applications", {})

    if not settings.api_key:
        st.caption("配置 OPENAI_API_KEY 后可以生成自动修复 Patch。")
        return

    if st.button("生成修复 Patch", key=f"generate-patch-{state_key}"):
        try:
            with st.spinner("正在生成修复 Patch……"):
                patches[state_key] = agent.generate_patch(root, issue)
            applications.pop(state_key, None)
        except Exception as exc:  # noqa: BLE001 - surface provider errors in the UI
            st.error(f"Patch 生成失败：{type(exc).__name__}: {exc}")

    patch_response = patches.get(state_key)
    if patch_response is None:
        return
    if not patch_response.patch.strip():
        st.warning(f"模型未生成可安全应用的 Patch：{patch_response.summary}")
        return

    st.markdown(f"**Patch 说明：** {patch_response.summary}")
    st.code(patch_response.patch, language="diff")
    if patch_response.verification:
        st.caption("模型建议验证：" + "；".join(patch_response.verification))
    if st.button("验证 Patch 并生成修复版 ZIP", key=f"apply-patch-{state_key}"):
        try:
            with st.spinner("正在临时应用 Patch 并验证……"):
                applications[state_key] = apply_patch_to_copy(
                    root,
                    patch_response.patch,
                    expected_file=issue.file,
                )
            st.success("Patch 已在临时副本中通过验证，原始代码未被覆盖。")
        except (PatchError, OSError) as exc:
            st.error(f"Patch 验证失败：{exc}")

    application = applications.get(state_key)
    if application:
        st.download_button(
            "下载修复版 ZIP",
            data=application.zip_bytes,
            file_name="code-review-patched.zip",
            mime="application/zip",
            key=f"download-patched-{state_key}",
        )


def _render_issue(issue, index: int, root: Path | None, settings: Settings, agent: CodeReviewAgent) -> None:
    severity = SEVERITY_LABELS.get(issue.severity, issue.severity)
    location = f"{issue.file}:{issue.line}" if issue.line else issue.file
    with st.expander(f"{index}. [{severity}] {issue.title}  ·  {location}", expanded=index == 1):
        st.write(issue.explanation)
        st.markdown(f"**修复建议：** {issue.suggestion}")
        st.caption(f"类别：{issue.category}　严重程度：{issue.severity}")
        snippet = _read_snippet(root, issue.file, issue.line)
        if snippet:
            st.code(snippet, language=Path(issue.file).suffix.lstrip(".") or "text")
        _render_patch_controls(issue, root, settings, agent)


def _render_report(report: ReviewReport, root: Path | None, settings: Settings, agent: CodeReviewAgent) -> None:
    st.subheader("审查结果")
    metric_columns = st.columns(4)
    metric_columns[0].metric("综合评分", f"{report.score}/100")
    metric_columns[1].metric("发现问题", len(report.issues))
    metric_columns[2].metric("审查文件", report.metadata.get("files_reviewed", "-"))
    metric_columns[3].metric("运行模式", "离线" if report.metadata.get("mode") == "offline" else "LLM")
    st.progress(report.score / 100, text=f"代码质量评分：{report.score}/100")

    st.info(report.summary)
    if report.strengths:
        with st.expander("做得好的地方", expanded=False):
            for strength in report.strengths:
                st.success(strength)

    st.subheader("问题列表")
    severities = sorted({issue.severity for issue in report.issues})
    selected = st.multiselect(
        "按严重程度筛选",
        options=severities,
        default=severities,
        format_func=lambda value: f"{SEVERITY_LABELS.get(value, value)} ({value})",
    )
    visible_issues = [issue for issue in report.issues if issue.severity in selected]
    if not visible_issues:
        st.success("当前筛选条件下没有问题。")
    else:
        for index, issue in enumerate(visible_issues, start=1):
            _render_issue(issue, index, root, settings, agent)

    st.subheader("下载报告")
    download_columns = st.columns(2)
    download_columns[0].download_button(
        "下载 Markdown 报告",
        data=_report_markdown(report),
        file_name="code-review-report.md",
        mime="text/markdown",
    )
    download_columns[1].download_button(
        "下载 JSON 报告",
        data=json.dumps(report.model_dump(), ensure_ascii=False, indent=2),
        file_name="code-review-report.json",
        mime="application/json",
        )


def _require_demo_access(settings: Settings) -> None:
    if not settings.demo_access_password or st.session_state.get("demo_authenticated"):
        return

    st.title("🔒 CodeReviewAgent Demo")
    st.caption("此在线 Demo 需要访问密码。")
    with st.form("demo-access-form"):
        password = st.text_input("访问密码", type="password")
        submitted = st.form_submit_button("进入 Demo", type="primary")
    if submitted and password == settings.demo_access_password:
        st.session_state["demo_authenticated"] = True
        return
    if submitted:
        st.error("访问密码不正确。")
    else:
        st.info("请输入 Demo 访问密码。")
    st.stop()


def main() -> None:
    settings = Settings.from_env(Path(".env"))
    agent = CodeReviewAgent(settings)
    _require_demo_access(settings)

    st.title("🔍 CodeReviewAgent")
    st.caption("上传代码项目，获得结构化的 Bug、安全、性能和可维护性审查结果。")

    with st.sidebar:
        st.header("审查配置")
        offline_mode = st.checkbox(
            "离线模式",
            value=not bool(settings.api_key),
            help="离线模式只运行当前已实现的确定性 Python 检查，不调用模型 API。",
        )
        st.text_input("模型", value=settings.model, disabled=True)
        st.text_input("Base URL", value=settings.base_url or "OpenAI 默认地址", disabled=True)
        st.divider()
        st.caption("上传限制：单个文件最大 25 MB；支持 ZIP、Python、JavaScript、TypeScript、Java 和 Go。")

    uploaded_files = st.file_uploader(
        "上传代码文件或 ZIP 项目",
        type=["zip", "py", "js", "jsx", "ts", "tsx", "java", "go"],
        accept_multiple_files=True,
        help="可以上传多个源文件，也可以上传一个 ZIP 压缩包。",
    )

    if uploaded_files:
        st.caption("已选择：" + "、".join(uploaded.name for uploaded in uploaded_files))

    review_count = int(st.session_state.get("review_count", 0))
    review_limit_reached = review_count >= settings.max_reviews_per_session
    if review_limit_reached:
        st.warning("当前会话已达到审查次数上限。")
    if st.button(
        "开始审查",
        type="primary",
        disabled=not uploaded_files or review_limit_reached,
        use_container_width=True,
    ):
        try:
            with st.spinner("正在准备代码并运行审查……"):
                workspace, file_count = materialize_uploads(uploaded_files)
                if file_count == 0:
                    raise ValueError("上传内容中没有找到支持的源代码文件。")
                report = agent.review(workspace, dry_run=offline_mode)
            st.session_state["report"] = report
            st.session_state["workspace"] = workspace
            st.session_state["patches"] = {}
            st.session_state["patch_applications"] = {}
            st.session_state["review_count"] = review_count + 1
            st.success(f"审查完成，共处理 {file_count} 个源代码文件。")
        except (ValueError, OSError, zipfile.BadZipFile) as exc:
            st.error(f"审查失败：{exc}")
        except Exception as exc:  # noqa: BLE001 - surface provider errors in the UI
            st.error(f"审查失败：{type(exc).__name__}: {exc}")

    report = st.session_state.get("report")
    if report:
        st.divider()
        _render_report(report, st.session_state.get("workspace"), settings, agent)
    else:
        st.divider()
        st.info("请上传代码文件，然后点击“开始审查”。")


if __name__ == "__main__":
    main()
