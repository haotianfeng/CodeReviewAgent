# CodeReviewAgent

CodeReviewAgent 是一个基于 Python、Streamlit 和大语言模型的智能代码审查工具。用户可以上传代码文件或 ZIP 项目，系统会运行确定性的 Python 检查，并调用 OpenCode Go 的 GPT-5.6 Luna 生成结构化审查报告。项目采用 Streamlit 单体架构，不需要额外部署独立后端。

## 当前功能

- 支持 Python、JavaScript、TypeScript、Java 和 Go 源代码
- 支持单个文件、多个文件和 ZIP 项目上传
- 自动忽略虚拟环境、依赖目录、构建产物和 `.git` 目录
- Python AST 确定性检查
- LLM 辅助的 Bug、安全、性能、风格和可维护性审查
- LLM 和离线报告中的自然语言内容统一使用简体中文
- 输出评分、问题严重程度、文件位置、问题说明和修复建议
- 在页面中查看问题附近的代码片段
- 下载 Markdown 和 JSON 格式的审查报告
- 针对单个问题生成 Unified Diff 修复 Patch
- 独立 Patch 工作区：预览 Diff、查看验证建议、下载 `.patch`
- 在临时副本中校验 Patch、执行 Python 语法检查并下载修复版 ZIP
- 页面内配置个人 API Key；密钥只保存在当前会话，并优先于应用级配置
- 支持 CLI 和 Streamlit 页面两种使用方式
- 使用 Responses API 和 Pydantic 结构化输出

## 环境要求

- Windows、macOS 或 Linux
- Python 3.10 及以上
- OpenCode Go API Key（使用 LLM 审查时需要）

## 本地安装

在项目根目录执行：

```powershell
cd D:\CodeReviewAgent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,ui]"
```

如果 PowerShell 阻止激活脚本，可以只在当前终端临时放宽策略：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 配置 OpenCode Go

复制配置模板：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，可以填入本机运行使用的 OpenCode Go API Key：

```env
OPENAI_API_KEY=your_opencode_go_api_key_here
OPENAI_BASE_URL=https://opencode.ai/zen/go/v1
CODE_REVIEW_MODEL=gpt-5.6-luna
CODE_REVIEW_MAX_FILES=30
CODE_REVIEW_MAX_CHARS=50000
DEMO_ACCESS_PASSWORD=
DEMO_MAX_REVIEWS_PER_SESSION=10
```

`.env` 只保存在本机，不要提交到 GitHub。`OPENAI_API_KEY` 中应填写 OpenCode Go API Key，而不是示例占位符。

如果暂时没有 API Key，保留占位符即可，应用会自动使用离线模式，不会把占位符发送给模型服务商。

启动网页后，也可以在“配置你的模型 API Key”区域输入个人 Key。它只保存在当前 Streamlit 会话，不会写入数据库、Cookie、URL、项目文件或 GitHub；个人 Key 会优先于 `.env` 和 Streamlit Secrets 中的应用级 Key。点击“清除 / 退出”可以清理凭据、报告和 Patch 状态。

`DEMO_ACCESS_PASSWORD` 用于保护公开 Demo；本地开发可以留空。`DEMO_MAX_REVIEWS_PER_SESSION` 用于限制单个浏览器会话的审查次数。

## 使用命令行

### 离线审查

离线模式不调用模型，只运行当前的确定性 Python 检查：

```powershell
python -m codereview_agent examples\sample_project --dry-run
```

### LLM 审查

```powershell
python -m codereview_agent examples\sample_project --output outputs\review.json
```

也可以使用已经安装的命令行入口：

```powershell
codereview examples\sample_project --dry-run
```

不要直接运行 `src\codereview_agent\__main__.py`。应使用 `python -m codereview_agent`，这样 Python 能正确识别包的相对导入。

## 启动 Streamlit 页面

```powershell
streamlit run app.py
```

打开浏览器访问：

```text
http://127.0.0.1:8501
```

页面操作流程：

1. 可在页面顶部配置个人 OpenCode Go API Key；没有 Key 时可以直接使用“离线模式”。
2. 上传代码文件或 ZIP 项目。
3. 确认左侧的模型、Base URL 和运行模式，点击“开始审查”。
4. 在“审查结果”工作区查看评分、问题详情和代码片段。
5. 在“Patch 修改预览”工作区选择问题，生成并审阅模型建议的 Diff。
6. 下载 `.patch`，或点击“验证 Patch 并生成修复版 ZIP”。
7. 在“报告下载”工作区下载 Markdown 或 JSON 报告。

Patch 只会应用到临时副本，并且需要用户主动确认；原始上传内容不会被覆盖。

## 运行评估集

评估集位于 `evals/cases/`，每个案例包含输入代码和标准答案。离线评估不消耗 API 额度：

```powershell
python evals\run_eval.py --mode offline --output outputs\offline-eval.json
```

如果已配置 API Key，也可以评估 LLM 审查结果：

```powershell
python evals\run_eval.py --mode llm --output outputs\llm-eval.json
```

评估脚本会统计案例通过数、问题识别精确率和召回率。

## 部署到 Streamlit Community Cloud

当前项目可以直接部署为 Streamlit Community Cloud 应用，不需要单独启动 FastAPI 等后端服务。

### 1. 推送到 GitHub

确认 `.env` 不在 Git 暂存区，然后提交并推送项目代码：

```powershell
git add .
git commit -m "Update CodeReviewAgent app"
git push origin master
```

`.gitignore` 已忽略 `.env`、`.venv`、测试缓存、构建产物和审查输出文件。

### 2. 创建 Community Cloud 应用

在 [Streamlit Community Cloud](https://share.streamlit.io/) 中连接 GitHub 仓库，选择：

```text
Repository: haotianfeng/CodeReviewAgent
Branch: master
Main file path: app.py
```

Community Cloud 会根据 `requirements.txt` 自动安装依赖，并在 GitHub 推送后重新部署。

### 3. 添加 Secrets（可选）

在应用的 Advanced settings → Secrets 中使用 TOML 格式。公开 Demo 可以不设置 `OPENAI_API_KEY`，让访问者在网页内输入自己的 Key；如果需要应用级默认 Key，再添加：

```toml
OPENAI_BASE_URL = "https://opencode.ai/zen/go/v1"
CODE_REVIEW_MODEL = "gpt-5.6-luna"
CODE_REVIEW_MAX_FILES = "30"
CODE_REVIEW_MAX_CHARS = "50000"
DEMO_ACCESS_PASSWORD = "建议设置一个单独的 Demo 密码"
DEMO_MAX_REVIEWS_PER_SESSION = "10"
# OPENAI_API_KEY = "仅在你确实需要共享应用级 Key 时填写"
```

部署完成后，使用 Community Cloud 提供的公网 URL 访问页面。应用同时支持 `.env`、系统环境变量和 `st.secrets`，不需要上传 `.env` 文件。

## 项目结构

```text
CodeReviewAgent/
├── app.py                              # Streamlit 页面入口
├── requirements.txt                    # 部署依赖
├── pyproject.toml                      # Python 包和测试配置
├── .env.example                        # 环境变量模板
├── render.yaml                         # Render Blueprint 配置
├── .streamlit/config.toml              # Streamlit 服务配置
├── examples/sample_project/            # 示例代码
├── src/codereview_agent/
│   ├── agent.py                        # Agent 编排
│   ├── cli.py                          # CLI 入口
│   ├── config.py                       # 配置读取
│   ├── llm.py                          # Responses API 调用
│   ├── models.py                       # 审查结果数据模型
│   ├── patcher.py                       # Diff 校验、临时应用和 ZIP 导出
│   ├── prompts.py                      # 审查提示词
│   ├── session.py                      # 会话 Key 与状态清理
│   └── tools.py                        # 文件读取和静态检查
├── evals/                              # 标准案例和评估脚本
└── tests/                              # 单元测试
```

## 测试

```powershell
python -m pytest -q --basetemp .pytest-temp
```

## 安全与数据边界

- 不要上传包含 API Key、密码、Token、证书或个人隐私的代码。
- 上传的源代码会在审查时发送到配置的模型服务商。
- 当前应用不会执行用户上传的代码，只读取源文件并进行文本/AST 分析。
- 单个上传文件最大 25 MB，ZIP 内源代码总大小最大 100 MB。
- 生成的 Patch 只允许修改一个已存在的源文件，并且会先在临时副本中验证。
- 当前应用没有独立账号系统；网页中的 API Key 配置是会话级凭据，不提供账号注册、权限管理或跨会话历史。
- 应用不会显示或记录完整 API Key，但上传代码会发送到配置的模型服务商；不要上传敏感代码。
- 公网 Demo 应设置 `DEMO_ACCESS_PASSWORD` 和审查次数限制；共享应用级 Key 时还应关注额度和滥用风险。

## 常见问题

### 访问不了 localhost

确认 Streamlit 终端仍在运行，并访问：

```text
http://127.0.0.1:8501
```

检查端口：

```powershell
Test-NetConnection 127.0.0.1 -Port 8501
```

### 页面显示离线模式

可以在页面顶部输入个人 API Key，或确认当前目录存在 `.env`，并且其中的 `OPENAI_API_KEY` 不是占位符。修改 `.env` 后重新启动 Streamlit。

### 出现模型或接口错误

确认以下配置一致：

```env
OPENAI_BASE_URL=https://opencode.ai/zen/go/v1
CODE_REVIEW_MODEL=gpt-5.6-luna
```

同时确认 OpenCode Go API Key 有效且账户仍有可用额度。
