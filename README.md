# MemoryOS

> 让所有 AI 工具永久认识你的本地个人记忆系统

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey.svg)]()

---

## 解决什么问题

你是不是已经厌倦了——

- 每打开一个新的 AI 软件（OpenClaw、QClaw、ChatGPT、Claude.ai…）都要从头自我介绍
- "我是谁、我做什么工作、我在做什么项目"重复一万遍
- 一个软件刚教会，换一个又什么都不知道
- 想让 AI 真正了解你的工作背景，但不愿意把所有文件上传到云端

**MemoryOS 是干什么的**：在你电脑本地建立一个**结构化个人记忆库**，然后通过三种方式让所有 AI 工具自动用上它——你只需要配置一次，永久生效。

```
你的电脑文件 → MemoryOS 扫描分析 → 本地 Wiki 知识库
                                        ↓ 自动注入
                                   所有 AI 工具
                  (OpenClaw / Claude Code / 网页 AI / Ollama / DeepSeek …)
```

---

## 核心特性

- 🔒 **完全本地**：所有数据存在 `~/.memoryos/`，不上传到任何服务器（除了你自己用的 AI API）
- 🤖 **模型无关**：兼容 Claude / OpenAI / DeepSeek / Ollama / Qwen 等任意后端
- 🧩 **三种接入方式**：MCP Server（Claude Code 等）+ HTTP 代理（任意 OpenAI 兼容工具）+ Web UI（手动管理）
- 📝 **可读可改的 Wiki**：知识库是 Markdown 格式，你随时能看、能改、能版本管理
- 🔄 **增量更新**：扫描时只分析有变化的文件，一次建库，每周维护
- 💰 **成本极低**：建一次 90GB 文件的画像约 ¥3-5（一次性）

---

## 工作原理（30 秒理解）

```
┌─────────────────────────────────────────────────────────────┐
│                        你的电脑                              │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ OpenClaw │    │  QClaw   │    │  其他工具 │              │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘              │
│       │                │               │                    │
│       │ MCP            │ HTTP 代理     │ HTTP 代理            │
│       ▼                ▼               ▼                    │
│  ┌─────────────────────────────────────────┐               │
│  │         MemoryOS · localhost:8765       │               │
│  │  自动注入个人上下文 → 转发到真实 AI 服务 │               │
│  └────────────────┬────────────────────────┘               │
│                   ▼                                         │
│  ┌──────────────────────────────────────┐                  │
│  │  Wiki 知识库（Markdown）              │                  │
│  │  ├── me.md                           │                  │
│  │  ├── projects/                       │                  │
│  │  ├── interests/                      │                  │
│  │  └── tools/                          │                  │
│  └──────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 1. 安装（macOS）

```bash
git clone https://github.com/hebeiwang353-bit/personal-wiki.git
cd personal-wiki
bash install.sh
```

### 1. 安装（Windows）

```powershell
git clone https://github.com/hebeiwang353-bit/personal-wiki.git
cd personal-wiki
.\install.ps1
```

### 2. 配置 API Key

在 `.env` 文件中填入你使用的 AI 服务的 Key（任选其一）：

```bash
# Claude（推荐质量最高）
ANTHROPIC_API_KEY=sk-ant-xxxxx

# OpenAI
OPENAI_API_KEY=sk-xxxxx

# DeepSeek（最便宜，OpenAI 兼容）
DEEPSEEK_API_KEY=sk-xxxxx
```

### 3. 第一次扫描

```bash
source venv/bin/activate
PYTHONPATH=. python main.py --max-files 500 --no-embed --skip-confirm
```

约 1-3 分钟，扫描完后 Wiki 就建好了。

### 4. 查看效果

打开 Web UI：

```bash
PYTHONPATH=. python web/server.py
# 访问 http://localhost:8766
```

---

## 三种接入方式

### A. Claude Code / Claude Desktop（MCP 协议）

编辑 `~/.claude.json`（或 Claude Desktop 配置文件），加入：

```json
{
  "mcpServers": {
    "memoryos": {
      "command": "/path/to/memoryos/venv/bin/python",
      "args": ["/path/to/memoryos/memoryos_mcp/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/path/to/memoryos"
      }
    }
  }
}
```

重启 Claude Code，它就永久认识你了。

### B. 其他 AI 工具（HTTP 代理）

启动代理：

```bash
PYTHONPATH=. python proxy/proxy_server.py
```

把任意 AI 工具的 API 地址改为：

```
http://localhost:8765/v1
```

代理会自动按 model 名路由：
- `claude-*` → api.anthropic.com
- `gpt-*` → api.openai.com
- `deepseek-*` → api.deepseek.com
- `qwen-*`, `llama-*` 等 → localhost:11434 (Ollama)

### C. 手动管理（Web UI）

```bash
PYTHONPATH=. python web/server.py
```

访问 http://localhost:8766，可以：
- 浏览所有 Wiki 页面
- 编辑「用户自述」节（永不被自动覆盖）
- 立即触发扫描或设定每日定时

---

## Wiki 结构

```
~/.memoryos/wiki/
├── index.md             导航目录
├── me.md                ← 核心画像（含用户自述节 + 自动分析节）
├── projects/            正在做的项目
│   ├── 北哥App.md
│   └── 储能项目.md
├── interests/           兴趣领域
├── tools/               常用工具链
└── log.md               操作日志
```

`me.md` 中的 `## 用户自述` 节是**手动维护、永不被自动覆盖**的。建议在这里写：
- 你的真实身份和职业
- 主项目和技术栈
- 沟通偏好（让 AI 用什么语气回答你）

---

## 隐私说明

| 数据 | 是否上传 | 说明 |
|------|---------|------|
| 文件原文 | ❌ 不上传 | 仅本地读取 |
| 提取的文本片段 | ⚠️ 上传到你配置的 AI 服务 | 用于建立画像（仅扫描时） |
| 浏览器历史 | ⚠️ 上传到你配置的 AI 服务 | 仅前 150 条标题 |
| 生成的 Wiki | ❌ 不上传 | 永久存于本地 |
| 每次对话上下文 | ⚠️ 上传到你配置的 AI 服务 | ≤1500 token，由代理自动注入 |

**MemoryOS 本身不会把任何数据发到 MemoryOS 服务器**——这个项目根本没有自己的服务器。

如果你完全不想任何文件内容离开本机，可以使用本地 Ollama 模型作为分析后端（待支持）。

---

## 命令速查

```bash
# 立即扫描（默认 500 文件，跳过 Embedding）
PYTHONPATH=. python main.py --max-files 500 --no-embed --skip-confirm

# 设定每天定时扫描
PYTHONPATH=. python -m memoryos_mcp.scheduler --set "22:00"

# 查看定时状态
PYTHONPATH=. python -m memoryos_mcp.scheduler --status

# 启动代理
PYTHONPATH=. python proxy/proxy_server.py

# 启动 Web UI
PYTHONPATH=. python web/server.py
```

---

## 路线图

- [x] 文件扫描 + 提取（PDF/Word/Excel/HTML/代码 等 20+ 格式）
- [x] 浏览器历史分析（Safari/Chrome）
- [x] 智能采样（meta 文件优先 + 目录多样性）
- [x] Wiki 自动维护（用户自述节保留 + 自动分析节覆盖）
- [x] MCP Server（4 个工具）
- [x] 通用 HTTP 代理（OpenAI + Anthropic 双格式 + 流式）
- [x] BM25 + jieba 中文相关性排序
- [x] Web UI（浏览/编辑/扫描/定时）
- [x] 跨平台定时任务（macOS LaunchAgent + Windows Task Scheduler）
- [ ] Ollama 本地模型作为分析后端（数据完全不出网）
- [ ] 浏览器插件（自动注入网页版 AI）
- [ ] OpenClaw 插件市场上架
- [ ] Wiki 矛盾检测与质量审计
- [ ] 多人 / 多角色支持

---

## 贡献

欢迎 Issue 和 PR。建议先开 Issue 讨论方向再动手。

## License

[MIT](LICENSE) © 2026 王贺北 (Wang Hebei)

---

## 致谢

- 知识库设计灵感来自 [Andrej Karpathy 的 LLM Wiki 思路](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- MCP 协议来自 [Anthropic](https://modelcontextprotocol.io/)
