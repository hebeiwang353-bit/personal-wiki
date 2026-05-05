<div align="center">

# 🧠 MemoryOS

### 让所有 AI 工具永久认识你的本地个人记忆系统

[![PyPI](https://img.shields.io/pypi/v/memoryos-personal?color=blue&label=pip)](https://pypi.org/project/memoryos-personal/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)]()
[![AI Tools](https://img.shields.io/badge/AI%20工具-30%2B-green.svg)]()

</div>

---

> **每打开一个新 AI 软件，都要重新自我介绍一遍？**  
> MemoryOS 在你电脑本地建立一个结构化个人记忆库，一次配置，让 Claude / Cursor / OpenClaw / Cherry Studio 等 **30+ 工具永久认识你**。

```
你的电脑文件 ──→ 扫描分析 ──→ 本地 Wiki 知识库
                                     │
                              自动注入个人上下文
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
         Claude Code             Cursor              OpenClaw / Hermes
        （MCP 协议）           （MCP 协议）            （HTTP 代理）
```

![MemoryOS 主面板](docs/screenshots/01-home.png)

> Web 管理面板：57 个 Wiki 页面，1194 token 个人上下文，每次对话自动注入。

<details>
<summary><b>📸 更多截图（点击展开）</b></summary>

### 个人画像页（me.md）
`## 用户自述` 节由你手动维护、**永不被自动覆盖**；`## 自动分析` 节由扫描后自动重写。

![me.md 页面](docs/screenshots/02-me-page.png)

### 项目档案（自动生成）
每个项目自动生成 300-400 字的结构化档案：项目目标、技术栈、当前进度、关键文件。

![项目页](docs/screenshots/03-project-page.png)

### 编辑模式
任何页面都可以直接在 Web UI 编辑，`Cmd+S` 保存。

![编辑模式](docs/screenshots/04-edit-mode.png)

### 立即扫描
点击「立即扫描」按钮，弹窗实时显示扫描进度。

![扫描进行中](docs/screenshots/05-scan-modal.png)

</details>

---

## ⚡ 一键安装

### 🍎 macOS / 🐧 Linux

```bash
curl -sSL https://raw.githubusercontent.com/hebeiwang353-bit/personal-wiki/main/bootstrap.sh | bash
```

### 🪟 Windows（PowerShell 管理员模式）

```powershell
irm https://raw.githubusercontent.com/hebeiwang353-bit/personal-wiki/main/bootstrap.ps1 | iex
```

> 如提示执行策略错误，先运行：`Set-ExecutionPolicy Bypass -Scope Process`

### 📦 已有 Python 3.10+（三平台通用）

```bash
pip install memoryos-personal
memoryos install
```

> 引导脚本自动完成：检测 Python → 安装依赖 → 注册 MCP → 配置 API Key → 首次扫描。全程约 5 分钟。

---

## 🦅 OpenClaw / QClaw 用户专属安装

> MemoryOS 会自动检测 OpenClaw 并写入 MCP 配置，**无需任何手动操作**。

**macOS / Linux：**
```bash
curl -sSL https://raw.githubusercontent.com/hebeiwang353-bit/personal-wiki/main/bootstrap.sh | bash
```

**Windows：**
```powershell
irm https://raw.githubusercontent.com/hebeiwang353-bit/personal-wiki/main/bootstrap.ps1 | iex
```

**已有 Python 直接安装：**
```bash
pip install memoryos-personal && memoryos install
```

安装完成后，**重启 OpenClaw / QClaw**，MemoryOS 出现在 MCP 工具列表即表示成功。

效果：OpenClaw 每次对话都会自动携带你的个人画像、近期项目、沟通偏好，无需任何额外操作。

---

## 🪶 Hermes 用户专属安装

> MemoryOS 自动检测并写入 Hermes 的 `~/.hermes/config.yaml` MCP 配置。

**macOS / Linux：**
```bash
curl -sSL https://raw.githubusercontent.com/hebeiwang353-bit/personal-wiki/main/bootstrap.sh | bash
```

**Windows：**
```powershell
irm https://raw.githubusercontent.com/hebeiwang353-bit/personal-wiki/main/bootstrap.ps1 | iex
```

**已有 Python 直接安装：**
```bash
pip install memoryos-personal && memoryos install
```

安装完成后，**重启 Hermes**，在 MCP 工具列表中看到 `memoryos` 即表示成功。

效果：Hermes 每次对话都会自动加载你的 Wiki 知识库上下文，AI 从此"认识"你。

---

## 🔑 配置 API Key（必做，仅需一次）

安装后编辑配置文件：

| 系统 | 配置文件路径 |
|------|------------|
| macOS / Linux | `~/.memoryos/.env` |
| Windows | `%USERPROFILE%\.memoryos\.env` |

填入你的 AI 服务商信息：

```env
AI_PROVIDER=deepseek        # 推荐：¥0.1/百万 token
AI_API_KEY=sk-xxxxxxxxxxxxxxxx
```

支持的厂商关键词：

| 类型 | 关键词 |
|------|--------|
| 国际 | `openai` · `anthropic` · `gemini` · `grok` · `mistral` · `groq` |
| 国内 | `deepseek` · `dashscope`（通义）· `zhipu`（GLM）· `moonshot`（Kimi）· `doubao`（豆包）· `ernie`（文心）· `minimax` · `stepfun` |
| 本地 | `ollama` · `lmstudio`（数据完全不出网） |
| 自定义 | `custom`（任何 OpenAI 兼容服务，配合 `AI_BASE_URL`） |

---

## 🚀 第一次扫描

```bash
memoryos scan
```

约 2-5 分钟完成，之后**每天 11:00 自动更新**，无需任何操作。

建一次 90GB 文件库的画像成本约 **¥3-5**（DeepSeek），此后每日增量扫描接近免费。

---

## 🛠 支持的 AI 工具（30+）

| 工具 | 接入方式 | 自动配置 |
|------|---------|---------|
| **Claude Code** | MCP | ✅ 自动 |
| **Claude Desktop** | MCP | ✅ 自动 |
| **Cursor** | MCP | ✅ 自动 |
| **Windsurf** | MCP | ✅ 自动 |
| **Cline / RooCline** | MCP | ✅ 自动 |
| **Continue.dev** | MCP | ✅ 自动 |
| **LM Studio** | MCP | ✅ 自动 |
| **Trae** | MCP | ✅ 自动 |
| **OpenClaw / QClaw** | MCP | ✅ 自动 |
| **Hermes** | MCP | ✅ 自动 |
| **Cherry Studio** | MCP | ✅ 自动（URL Scheme） |
| **Chatbox** | HTTP 代理 | ✅ 自动 |
| **Jan** | HTTP 代理 | ✅ 自动 |
| **Aider** | HTTP 代理 | ✅ 自动 |
| **Zed** | HTTP 代理 | ✅ 自动 |
| **Codex CLI** | HTTP 代理 | ✅ 自动 |
| **LobeChat** | HTTP 代理 | ✅ 自动 |
| **SiYuan** | HTTP 代理 | ✅ 自动 |
| **Witsy** | HTTP 代理 | ✅ 自动 |
| **Bob 翻译** | HTTP 代理 | ✅ 自动 |
| 任何 OpenAI 兼容工具 | HTTP 代理 | 手动改 API 地址为 `http://localhost:8765/v1` |

---

## 🏗 架构原理

```
┌─────────────────────────────────────────────────────────────────┐
│                           你的电脑                               │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Claude  │  │  Cursor  │  │ OpenClaw │  │  Hermes  │  ...  │
│  │   Code   │  │          │  │  /QClaw  │  │          │       │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘       │
│       │ MCP         │ MCP         │ HTTP代理      │ MCP         │
│       └─────────────┴──────┬──────┴───────────────┘            │
│                            ▼                                    │
│        ┌───────────────────────────────────────────┐           │
│        │    MemoryOS 核心层                         │           │
│        │  ┌──────────────┐  ┌─────────────────┐   │           │
│        │  │  MCP Server  │  │  HTTP 代理 :8765 │   │           │
│        │  │  stdio 协议  │  │  OpenAI/Claude   │   │           │
│        │  └──────┬───────┘  └────────┬────────┘   │           │
│        │         └────────┬───────────┘            │           │
│        │                  ▼                         │           │
│        │  ┌─────────────────────────────────────┐  │           │
│        │  │   Wiki 知识库 ~/.memoryos/wiki/      │  │           │
│        │  │   me.md · projects/ · interests/    │  │           │
│        │  └─────────────────────────────────────┘  │           │
│        └───────────────────────────────────────────┘           │
│                            │ 转发到真实 AI 服务                  │
└────────────────────────────┼────────────────────────────────────┘
             ┌───────────────┼───────────────┐
             ▼               ▼               ▼
        DeepSeek         Anthropic        OpenAI  ...
```

**三层接入协议：**
- **MCP**：Claude Code / Cursor / OpenClaw / Hermes 等 IDE 类工具，通过 stdio JSON-RPC 直接调用
- **HTTP 代理**：GUI 类工具（Chatbox / Cherry Studio 等），把 API Base URL 改为 `localhost:8765` 即可透明注入
- **Web UI**：`localhost:8766`，可视化浏览/编辑 Wiki，手动触发扫描

---

## 📂 Wiki 结构

```
~/.memoryos/
├── .env                   API Key 配置
├── wiki/
│   ├── index.md           导航目录
│   ├── me.md              ← 核心画像（用户自述 + 自动分析）
│   ├── projects/          正在做的项目（自动生成详细页面）
│   ├── interests/         兴趣领域
│   ├── tools/             常用工具链
│   └── log.md             操作日志
├── chroma_db/             本地向量数据库
└── memory/                对话记忆层
    ├── short_term.json    近期对话摘要
    └── long_term.md       长期项目进度
```

`me.md` 中 `## 用户自述` 节**永远不会被自动覆盖**，建议在这里写：
- 你的真实身份、职业、主技术栈
- 当前最重要的项目
- 希望 AI 用什么风格回答你

---

## 🔒 隐私说明

| 数据类型 | 是否离开本机 |
|---------|------------|
| 文件原文 | ❌ 永不上传 |
| 文件提取的文本片段 | ⚠️ 扫描时发给你配置的 AI 服务（建画像用，一次性） |
| 浏览器历史标题 | ⚠️ 扫描时发给你配置的 AI 服务（前 150 条） |
| 生成的 Wiki | ❌ 永久存于本地 |
| 每次对话注入的上下文 | ⚠️ ≤1500 token 随请求发给 AI |

**MemoryOS 没有任何自己的服务器**。  
想要数据完全不出本机：将 `AI_PROVIDER` 设为 `ollama`（需本地安装 Ollama）。

---

## 📋 命令速查

```bash
# 安装与配置
memoryos install              # 一键安装 / 重新配置
memoryos config               # 重新设置 API Key（不重装）

# 扫描
memoryos scan                 # 立即扫描，更新记忆库
memoryos scan --max-files 5000  # 深度全量扫描

# 查看状态
memoryos status               # 查看 Wiki 状态、工具连接、Token 数

# 服务
memoryos proxy                # 前台启动 HTTP 代理（localhost:8765）
memoryos web                  # 前台启动 Web UI（localhost:8766）

# 定时任务
memoryos schedule --set 22:00   # 修改定时扫描时间
memoryos schedule --status      # 查看定时状态
memoryos schedule --remove      # 移除定时任务
```

---

## 🗺 路线图

### ✅ Phase 1（已完成）
- 文件扫描 + 提取（PDF / Word / Excel / HTML / 代码等 20+ 格式）
- 浏览器历史分析（Safari / Chrome）
- 智能采样（meta 文件优先 + 目录多样性）
- Wiki 自动维护（用户自述节保留 + 自动分析节覆盖）
- MCP Server（4 个工具）
- 通用 HTTP 代理（OpenAI + Anthropic 双格式 + 流式）
- BM25 + jieba 中文相关性排序
- Web UI（浏览 / 编辑 / 扫描 / 定时）
- 16+ AI 厂商一键切换
- 三平台支持（macOS / Windows / Linux）
- **OpenClaw / QClaw / Hermes MCP 自动配置**
- **API Key 自动验证 + 错误重试流程**

### 🔧 Phase 2（进行中）
- [ ] Ollama 本地模型完整支持（数据完全不出网）
- [ ] 浏览器插件（自动注入网页版 AI）
- [ ] OpenClaw 插件市场上架
- [ ] Wiki 矛盾检测与质量审计

### 🌟 Phase 3
- [ ] 多人 / 多角色支持（家庭 / 团队场景）
- [ ] Wiki 可视化知识图谱
- [ ] 一键导出 Notion / Obsidian / PDF

---

## 🤝 贡献

欢迎 Issue 和 PR。建议先开 Issue 讨论方向再动手。

## 📄 License

[MIT](LICENSE) © 2026 王贺北 (Wang Hebei)

---

## 致谢

- 知识库设计灵感来自 [Andrej Karpathy 的 LLM Wiki 思路](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- MCP 协议来自 [Anthropic](https://modelcontextprotocol.io/)
