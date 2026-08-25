# CodeReviewAgent

CodeReviewAgent 是一个基于 Python、Streamlit 和大语言模型的智能代码审查工具。用户可以上传代码文件或 ZIP 项目，系统会运行确定性的 Python 检查，并调用 OpenCode Go 的 GPT-5.6 Luna 生成结构化审查报告。

## 当前功能

- 支持 Python、JavaScript、TypeScript、Java 和 Go 源代码
- 支持单个文件、多个文件和 ZIP 项目上传
- 自动忽略虚拟环境、依赖目录、构建产物和 `.git` 目录
- Python AST 确定性检查
- LLM 辅助的 Bug、安全、性能、风格和可维护性审查
- 输出评分、问题严重程度、文件位置、问题说明和修复建议
- 在页面中查看问题附近的代码片段
- 下载 Markdown 和 JSON 格式的审查报告
- 针对单个问题生成 Unified Diff 修复 Patch
- 在临时副本中校验 Patch、执行 Python 语法检查并下载修复版 ZIP
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

编辑 `.env`，填入你自己的 OpenCode Go API Key：

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

1. 上传代码文件或 ZIP 项目。
2. 确认左侧的模型和 Base URL。
3. 没有 API Key 时使用“离线模式”；配置 API Key 后取消勾选离线模式。
4. 点击“开始审查”。
5. 查看评分、问题详情和代码片段。
6. 在问题详情中点击“生成修复 Patch”，查看模型建议的 Diff。
7. 点击“验证 Patch 并生成修复版 ZIP”，下载经过临时副本验证的结果。
8. 下载 Markdown 或 JSON 报告。

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

## 部署到 Render

当前项目可以部署为 Streamlit Web Service。

### 1. 推送到 GitHub

如果项目目录还没有 Git 仓库，先在项目根目录执行：

```powershell
git init
git remote add origin 你的GitHub仓库地址
```

确认 `.env` 不在 Git 暂存区，然后提交项目代码：

```powershell
git add .
git commit -m "Deploy CodeReviewAgent Streamlit app"
git push
```

`.gitignore` 已忽略 `.env`、`.venv`、测试缓存、构建产物和审查输出文件。

### 2. 创建 Render Web Service

在 Render 中连接 GitHub 仓库，使用以下配置：

```text
Build Command: pip install -r requirements.txt
Start Command: streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```

也可以在 Render 中选择仓库里的 `render.yaml`，使用 Blueprint 自动读取上述服务配置。

### 3. 添加环境变量

在 Render 的 Environment 页面添加：

```text
OPENAI_API_KEY=你的OpenCode Go API Key
OPENAI_BASE_URL=https://opencode.ai/zen/go/v1
CODE_REVIEW_MODEL=gpt-5.6-luna
CODE_REVIEW_MAX_FILES=30
CODE_REVIEW_MAX_CHARS=50000
DEMO_ACCESS_PASSWORD=建议设置一个单独的Demo密码
DEMO_MAX_REVIEWS_PER_SESSION=10
```

部署完成后，使用 Render 提供的公网 URL 访问页面。Render 中的环境变量会被项目自动读取，不需要上传 `.env` 文件。

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
- 当前应用没有用户登录、权限管理和 API 调用限流，不适合直接用于敏感代码或无保护的生产环境。
- 公网 Demo 应设置 API 用量限制或访问保护，避免公开 Key 被滥用。

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

确认当前目录存在 `.env`，并且其中的 `OPENAI_API_KEY` 不是占位符。修改 `.env` 后重新启动 Streamlit。

### 出现模型或接口错误

确认以下配置一致：

```env
OPENAI_BASE_URL=https://opencode.ai/zen/go/v1
CODE_REVIEW_MODEL=gpt-5.6-luna
```

同时确认 OpenCode Go API Key 有效且账户仍有可用额度。
