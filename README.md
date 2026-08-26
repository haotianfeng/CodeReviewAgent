# CodeReviewAgent

CodeReviewAgent 是一个面向个人开发者、学习者和小团队的智能代码审查工具。用户上传代码文件或 ZIP 项目后，可以获得结构化的代码问题分析、中文修复建议和可审阅的自动修复 Patch。

项目采用 Streamlit 单体架构，不需要额外部署独立后端。审查结果通过 OpenCode Go 的大语言模型生成，也可以在不配置 API Key 时使用离线 Python 检查。

## 项目解决的痛点

- **人工审查耗时**：一次性分析多个源代码文件，快速定位潜在 Bug、安全风险、性能问题和可维护性问题。
- **问题难以定位和排序**：每个问题都包含严重程度、文件路径、行号和附近代码片段，便于确定处理优先级。
- **审查建议不够具体**：模型会用简体中文说明问题影响，并给出可以直接执行的修改建议。
- **修复代码存在风险**：用户可以针对单个问题生成 Unified Diff，在页面中预览后再下载或验证；原始代码不会被直接覆盖。
- **使用模型的门槛和隐私顾虑**：支持在页面中输入用户自己的 API Key。Key 只保存在当前浏览器会话中，不写入项目文件、URL、Cookie 或 GitHub；没有 API Key 时也可以使用离线模式。

## 主要功能

- 支持 Python、JavaScript、TypeScript、Java 和 Go 源代码
- 支持单文件、多文件和 ZIP 项目上传
- 使用 Python AST 进行确定性检查，并支持大语言模型辅助审查
- 审查报告、问题说明和修复建议稳定使用简体中文输出
- 展示代码质量评分、问题严重程度、文件位置和相关代码片段
- 为单个问题生成自动修复 Patch，支持 Diff 预览和 `.patch` 文件下载
- 自动校正 Diff hunk 行数，并在生成阶段校验文件路径、上下文和删除内容
- 在临时副本中验证 Patch，并下载修复后的 ZIP 文件
- 支持下载 Markdown 和 JSON 格式的审查报告

## 在线使用

打开 [CodeReviewAgent 在线 Demo](https://codereviewagent-takpb6glskjgdeohnk5rls.streamlit.app/)。

1. 在页面顶部输入自己的 OpenCode Go API Key。
2. 上传代码文件或 ZIP 项目。
3. 点击“开始审查”。
4. 在“审查结果”中查看评分、问题详情、代码片段和中文修复建议。
5. 切换到“Patch 修改预览”，选择一个问题并点击“生成修复 Patch”。
6. 审阅 Diff 后，可以下载 `.patch` 文件，或验证 Patch 并下载修复版 ZIP。
7. 在“报告下载”中导出 Markdown 或 JSON 报告。

如果不输入 API Key，可以勾选“离线模式”使用当前支持的 Python 确定性检查。在线 Demo 是否要求访问密码由 Demo 管理者决定。

## 本地运行

### 环境要求

- Python 3.10 或更高版本
- 使用大语言模型审查和生成 Patch 时，需要 OpenCode Go API Key

### 安装并启动

Windows PowerShell：

```powershell
git clone https://github.com/haotianfeng/CodeReviewAgent.git
cd CodeReviewAgent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,ui]"
streamlit run app.py
```

macOS 或 Linux：

```bash
git clone https://github.com/haotianfeng/CodeReviewAgent.git
cd CodeReviewAgent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,ui]"
streamlit run app.py
```

启动后访问：<http://127.0.0.1:8501>

### 配置模型 API

本地运行时，可以在项目根目录创建 `.env`：

```env
OPENAI_API_KEY=你的_OpenCode_Go_API_Key
OPENAI_BASE_URL=https://opencode.ai/zen/go/v1
CODE_REVIEW_MODEL=gpt-5.6-luna
CODE_REVIEW_MAX_CHARS=100000
```

也可以不配置 `.env`，直接在网页顶部输入个人 API Key。API Key 不要提交到 GitHub，也不要上传包含密钥、密码、Token 或证书的源代码。

## 两种审查模式

### LLM 审查

配置有效 API Key 后，系统会将上传的源代码发送给配置的模型服务商，生成更全面的 Bug、安全、性能、风格和可维护性审查结果，并支持自动生成 Patch。

### 离线审查

不调用模型服务，只运行当前已实现的确定性 Python 检查，例如：

- Python 语法错误
- 裸 `except`
- `eval` 或 `exec` 动态执行
- `subprocess` 使用 `shell=True`
- 可变默认参数

## 数据与安全边界

- 应用只读取上传的源代码，不执行用户上传的代码。
- 使用 LLM 审查时，源代码会发送到配置的模型服务商，请勿上传敏感代码。
- 页面输入的个人 API Key 仅用于当前 Streamlit 会话，点击“清除 / 退出”后会清理会话中的凭据和审查结果。
- 生成的 Patch 只允许针对一个已存在的源文件，并会先在临时副本中校验；原始上传文件不会被修改。
- 单个文件最大 25 MB，ZIP 内源代码总大小最大 100 MB。
- 模型审查和单个 Patch 的源代码字符上限默认为 100,000，可通过 `CODE_REVIEW_MAX_CHARS` 调整。
- 当前网页不提供账号注册、权限管理或跨会话历史记录功能。

## 项目地址

[GitHub 仓库](https://github.com/haotianfeng/CodeReviewAgent)
