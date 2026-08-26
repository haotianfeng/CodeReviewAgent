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
from codereview_agent.session import clear_session_state, normalize_user_api_key


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


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container { max-width: 1180px; padding-top: 2rem; padding-bottom: 3rem; }
        [data-testid="stAppViewContainer"] { background: #f7f9fc; }
        [data-testid="stSidebar"] { background: #101828; }
        [data-testid="stSidebar"] * { color: #eef4ff; }
        [data-testid="stSidebar"] [data-baseweb="select"] * { color: #101828; }
        [data-testid="stSidebar"] .stCaption { color: #a9b8d0; }
        [data-testid="stAppViewContainer"] h4,
        [data-testid="stAppViewContainer"] h3,
        [data-testid="stAppViewContainer"] h2 { color: #152b55 !important; }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] h4 { color: #eef4ff !important; }
        .cr-hero {
            background: linear-gradient(135deg, #152b55 0%, #2463a8 55%, #2e8bc0 100%);
            border-radius: 20px; padding: 2rem 2.2rem; color: white;
            box-shadow: 0 12px 30px rgba(21, 43, 85, .18); margin-bottom: 1.25rem;
        }
        .cr-hero h1 { margin: 0; color: white; font-size: 2.2rem; }
        .cr-hero p { margin: .55rem 0 0; color: #dbeafe; font-size: 1.02rem; }
        .cr-status {
            display: inline-block; margin-top: 1rem; padding: .35rem .75rem;
            border: 1px solid rgba(255,255,255,.32); border-radius: 999px;
            color: #eff6ff; font-size: .84rem;
        }
        .cr-section-title { color: #152b55; margin: .4rem 0 .2rem; }
        [data-testid="stMetric"] {
            background: white; border: 1px solid #e4eaf2; border-radius: 14px;
            padding: .8rem 1rem; box-shadow: 0 4px 14px rgba(16, 24, 40, .04);
        }
        div[data-testid="stButton"] > button[kind="primary"] {
            background: linear-gradient(90deg, #2463a8, #2e8bc0) !important; border: 0;
        }
        [data-testid="stFormSubmitButton"] button {
            background: linear-gradient(90deg, #2463a8, #2e8bc0) !important;
            border: 0 !important; color: white !important;
        }
        .cr-muted { color: #667085; font-size: .9rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def _issue_label(issue, index: int) -> str:
    severity = SEVERITY_LABELS.get(issue.severity, issue.severity)
    location = f"{issue.file}:{issue.line}" if issue.line else issue.file
    return f"{index}. [{severity}] {issue.title} · {location}"


def _render_issue(issue, index: int, root: Path | None) -> None:
    severity = SEVERITY_LABELS.get(issue.severity, issue.severity)
    location = f"{issue.file}:{issue.line}" if issue.line else issue.file
    with st.expander(f"{index}. [{severity}] {issue.title}  ·  {location}", expanded=index == 1):
        st.write(issue.explanation)
        st.markdown(f"**修复建议：** {issue.suggestion}")
        st.caption(f"类别：{issue.category}　严重程度：{issue.severity}")
        snippet = _read_snippet(root, issue.file, issue.line)
        if snippet:
            st.code(snippet, language=Path(issue.file).suffix.lstrip(".") or "text")


def _render_patch_workspace(
    report: ReviewReport,
    root: Path | None,
    settings: Settings,
    agent: CodeReviewAgent,
) -> None:
    """Render an isolated workspace for selecting, reviewing, and applying patches."""
    if root is None:
        st.info("请先完成一次代码审查，再使用 Patch 修改预览。")
        return
    if not report.issues:
        st.success("本次审查没有发现可修复的问题。")
        return

    issue_index = st.selectbox(
        "选择要生成修复 Patch 的问题",
        options=list(range(len(report.issues))),
        format_func=lambda index: _issue_label(report.issues[index], index + 1),
        key="patch_issue_selector",
    )
    issue = report.issues[issue_index]
    state_key = _patch_state_key(issue)
    patches = st.session_state.setdefault("patches", {})
    applications = st.session_state.setdefault("patch_applications", {})

    with st.container(border=True):
        st.markdown(f"#### {_issue_label(issue, issue_index + 1)}")
        detail_columns = st.columns(2)
        detail_columns[0].markdown(f"**问题说明**  \n{issue.explanation}")
        detail_columns[1].markdown(f"**修复建议**  \n{issue.suggestion}")
        st.caption(f"类别：{issue.category}　·　严重程度：{issue.severity}")

    if not settings.api_key:
        st.warning("当前未连接模型 API。请先在上方配置个人 API Key，或继续使用离线审查。")
        return

    if st.button("生成修复 Patch", type="primary", key=f"generate-patch-{state_key}"):
        try:
            with st.spinner("正在生成最小化修复 Patch……"):
                patches[state_key] = agent.generate_patch(root, issue)
            applications.pop(state_key, None)
        except Exception as exc:  # noqa: BLE001 - surface provider errors in the UI
            st.error(f"Patch 生成失败：{type(exc).__name__}: {exc}")

    patch_response = patches.get(state_key)
    if patch_response is None:
        st.info("选择问题后点击上方按钮，模型会为该文件生成一个可审阅的 Unified Diff。")
        return
    if not patch_response.patch.strip():
        st.warning(f"模型未生成可安全应用的 Patch：{patch_response.summary}")
        return

    st.markdown("#### Diff 预览")
    st.code(patch_response.patch, language="diff")
    st.markdown(f"**Patch 说明：** {patch_response.summary}")
    if patch_response.verification:
        st.markdown("**模型建议验证方式：**\n" + "\n".join(f"- {item}" for item in patch_response.verification))

    patch_download, patch_apply = st.columns(2)
    patch_download.download_button(
        "下载 .patch 文件",
        data=patch_response.patch,
        file_name=f"code-review-{issue_index + 1}.patch",
        mime="text/plain",
        key=f"download-patch-{state_key}",
        use_container_width=True,
    )
    if patch_apply.button(
        "验证 Patch 并生成修复版 ZIP",
        key=f"apply-patch-{state_key}",
        use_container_width=True,
    ):
        try:
            with st.spinner("正在临时应用 Patch 并验证……"):
                applications[state_key] = apply_patch_to_copy(
                    root,
                    patch_response.patch,
                    expected_file=issue.file,
                )
        except (PatchError, OSError) as exc:
            st.error(f"Patch 验证失败：{exc}")

    application = applications.get(state_key)
    if application:
        st.success(f"Patch 已在临时副本中通过验证：{application.changed_file}。原始代码未被覆盖。")
        st.download_button(
            "下载修复版 ZIP",
            data=application.zip_bytes,
            file_name="code-review-patched.zip",
            mime="application/zip",
            key=f"download-patched-{state_key}",
            use_container_width=True,
        )


def _render_downloads(report: ReviewReport) -> None:
    st.markdown("#### 导出审查结果")
    st.caption("报告仅包含本次审查结果；修复版代码需要在 Patch 工作区中单独验证和下载。")
    download_columns = st.columns(2)
    download_columns[0].download_button(
        "下载 Markdown 报告",
        data=_report_markdown(report),
        file_name="code-review-report.md",
        mime="text/markdown",
        key="download-report-markdown",
        use_container_width=True,
    )
    download_columns[1].download_button(
        "下载 JSON 报告",
        data=json.dumps(report.model_dump(), ensure_ascii=False, indent=2),
        file_name="code-review-report.json",
        mime="application/json",
        key="download-report-json",
        use_container_width=True,
    )


def _render_report(report: ReviewReport, root: Path | None, settings: Settings, agent: CodeReviewAgent) -> None:
    st.markdown('<h2 class="cr-section-title">审查工作台</h2>', unsafe_allow_html=True)
    metric_columns = st.columns(4)
    metric_columns[0].metric("综合评分", f"{report.score}/100")
    metric_columns[1].metric("发现问题", len(report.issues))
    metric_columns[2].metric("审查文件", report.metadata.get("files_reviewed", "-"))
    metric_columns[3].metric("运行模式", "离线" if report.metadata.get("mode") == "offline" else "LLM")
    st.progress(report.score / 100, text=f"代码质量评分：{report.score}/100")

    review_tab, patch_tab, download_tab = st.tabs(
        ["📊 审查结果", "🛠️ Patch 修改预览", "📥 报告下载"]
    )
    with review_tab:
        st.info(report.summary)
        if report.strengths:
            with st.expander("做得好的地方", expanded=False):
                for strength in report.strengths:
                    st.success(strength)

        st.markdown("#### 问题列表")
        severities = sorted({issue.severity for issue in report.issues})
        selected = st.multiselect(
            "按严重程度筛选",
            options=severities,
            default=severities,
            format_func=lambda value: f"{SEVERITY_LABELS.get(value, value)} ({value})",
            key="severity_filter",
        )
        visible_issues = [issue for issue in report.issues if issue.severity in selected]
        if not visible_issues:
            st.success("当前筛选条件下没有问题。")
        else:
            for index, issue in enumerate(visible_issues, start=1):
                _render_issue(issue, index, root)
    with patch_tab:
        _render_patch_workspace(report, root, settings, agent)
    with download_tab:
        _render_downloads(report)


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


def _render_api_key_panel(settings: Settings) -> None:
    """Let a visitor connect their own provider key for this Streamlit session."""
    session_api_key = normalize_user_api_key(st.session_state.get("user_api_key"))
    if session_api_key:
        with st.container(border=True):
            status_column, action_column = st.columns([3, 1])
            status_column.success("已连接你的 OpenCode Go API Key（仅当前会话）")
            if action_column.button("清除 / 退出", key="clear-user-session", use_container_width=True):
                clear_session_state(st.session_state)
                st.rerun()
        return

    title = "🔑 配置你的模型 API Key"
    expanded = not bool(settings.api_key)
    with st.expander(title, expanded=expanded):
        if settings.api_key:
            st.info("当前应用已配置默认模型 Key。你也可以输入自己的 Key，它只会优先用于当前浏览器会话。")
        else:
            st.info("输入 OpenCode Go API Key 后可使用 LLM 审查和自动 Patch；不输入也可以使用离线模式。")
        with st.form("user-api-key-form", clear_on_submit=True):
            api_key_input = st.text_input(
                "OpenCode Go API Key",
                type="password",
                key="api_key_input",
                autocomplete="new-password",
                help="密钥只保存在当前 Streamlit 会话内，不会写入项目文件、URL、Cookie 或 GitHub。",
            )
            submitted = st.form_submit_button("连接并保存到本次会话", type="primary", use_container_width=True)
        if submitted:
            normalized = normalize_user_api_key(api_key_input)
            if not api_key_input.strip():
                st.error("请输入 API Key，或关闭此区域使用离线模式。")
            elif normalized is None:
                st.error("不能使用示例占位符，请输入有效的 OpenCode Go API Key。")
            else:
                st.session_state["user_api_key"] = normalized
                st.session_state["offline_mode"] = False
                st.rerun()


def main() -> None:
    base_settings = Settings.from_env(Path(".env"))
    _require_demo_access(base_settings)
    _inject_styles()

    user_api_key = normalize_user_api_key(st.session_state.get("user_api_key"))
    settings = base_settings.with_api_key(user_api_key) if user_api_key else base_settings
    if user_api_key:
        run_status = "已连接 · 使用本会话 API Key"
    elif settings.api_key:
        run_status = "已连接 · 使用应用默认配置"
    else:
        run_status = "离线模式 · 未配置模型 API Key"

    st.markdown(
        f"""
        <div class="cr-hero">
            <h1>🔍 CodeReviewAgent</h1>
            <p>上传代码项目，获得结构化的 Bug、安全、性能和可维护性审查结果。</p>
            <span class="cr-status">{run_status}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    _render_api_key_panel(base_settings)
    agent = CodeReviewAgent(settings)

    with st.sidebar:
        st.header("⚙️ 审查配置")
        if user_api_key:
            st.success("本会话 Key 已连接")
        elif settings.api_key:
            st.success("应用默认 Key 已连接")
        else:
            st.warning("未配置 API Key")
        if "offline_mode" not in st.session_state:
            st.session_state["offline_mode"] = not bool(settings.api_key)
        offline_mode = st.checkbox(
            "离线模式",
            key="offline_mode",
            help="离线模式只运行当前已实现的确定性 Python 检查，不调用模型 API。",
        )
        st.text_input("模型", value=settings.model, disabled=True)
        st.text_input("Base URL", value=settings.base_url, disabled=True)
        st.divider()
        st.caption("单文件最大 25 MB；ZIP 内源代码总大小最大 100 MB。")
        st.caption("支持 Python、JavaScript、TypeScript、Java 和 Go。")

    st.markdown("#### 选择要审查的代码")
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
            st.session_state.pop("severity_filter", None)
            st.session_state.pop("patch_issue_selector", None)
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
        st.info("请上传代码文件，然后点击“开始审查”。审查完成后可在 Patch 工作区生成修复建议。")


if __name__ == "__main__":
    main()
