# 接入指南 · INTEGRATIONS

把 MemoryOS 接入到你正在用的 AI 工具。每个工具有具体步骤、配置代码、验证方法。

---

## 接入原理（30 秒理解）

MemoryOS 提供两种接入协议：

| 协议 | 端口 | 适合工具 |
|------|------|---------|
| **MCP（stdio）** | 无端口，子进程 | Claude Code、Cursor、Cline、Continue 等 IDE 工具 |
| **HTTP 代理** | `localhost:8765` | OpenClaw、QClaw、Cherry Studio 等 GUI 客户端 |

工具如果支持 MCP，**优先用 MCP**——更深度、能调用 query_wiki / update_wiki 工具。  
工具不支持 MCP，**用 HTTP 代理**——把 base_url 改成 `localhost:8765/v1`。

确保代理已启动：

```bash
PYTHONPATH=. python proxy/proxy_server.py
# 健康检查：curl http://localhost:8765/health
```

---

## 工具清单

| # | 工具 | 推荐协议 | 章节 |
|---|------|---------|------|
| 1 | Claude Code (CLI) | MCP | [跳转](#1-claude-code) |
| 2 | Claude Desktop | MCP | [跳转](#2-claude-desktop) |
| 3 | Cursor | MCP + 代理 | [跳转](#3-cursor) |
| 4 | Codex CLI | 代理 | [跳转](#4-codex-cli) |
| 5 | Cline (VSCode 插件) | 代理 | [跳转](#5-cline-vscode-插件) |
| 6 | Continue.dev | MCP / 代理 | [跳转](#6-continuedev) |
| 7 | OpenClaw | MCP / 代理 | [跳转](#7-openclaw) |
| 8 | QClaw | 代理 | [跳转](#8-qclaw) |
| 9 | Hermes | 代理 | [跳转](#9-hermes) |
| 10 | Cherry Studio | 代理 | [跳转](#10-cherry-studio) |
| 11 | Chatbox | 代理 | [跳转](#11-chatbox) |
| 12 | Ollama 本地工具 | 代理 | [跳转](#12-ollama--任意本地-gui) |

---

## 1. Claude Code

**协议**：MCP

### 自动配置（推荐）

`install.sh` 已自动注册到 `~/.claude.json`。安装完成后重启 Claude Code 即可。

### 手动配置

编辑 `~/.claude.json`：

```json
{
  "mcpServers": {
    "memoryos": {
      "command": "/Users/YOU/.memoryos/venv/bin/python",
      "args": ["/Users/YOU/.memoryos/src/memoryos_mcp/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/Users/YOU/.memoryos/src",
        "MEMORYOS_HOME": "/Users/YOU/.memoryos"
      }
    }
  }
}
```

### 验证

在 Claude Code 中输入：
```
调用 get_wiki_status
```

应该返回 Wiki 状态、页面列表、最近操作记录。

---

## 2. Claude Desktop

**协议**：MCP

### 配置位置

- macOS：`~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows：`%APPDATA%\Claude\claude_desktop_config.json`

### 配置内容

跟 Claude Code 完全相同：

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

完全退出 Claude Desktop 后重启（Cmd+Q，不是关窗口）。

---

## 3. Cursor

**两种接入方式都支持**，根据你的版本选：

### 方式 A：MCP（Cursor 0.40+）

编辑 `~/.cursor/mcp.json`：

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

重启 Cursor，`Settings → MCP` 中应该看到 `memoryos`。

### 方式 B：API 代理

`Settings → Models → OpenAI API Key` 处：

```
API Key:   sk-你的真实key
Base URL:  http://localhost:8765/v1
```

启用 GPT 之外的模型（`Settings → Models → Add Model`），添加：

```
deepseek-chat
qwen-plus
glm-4-flash
```

---

## 4. Codex CLI

**协议**：API 代理

### 配置

Codex CLI 通过环境变量读取 OpenAI 配置：

```bash
export OPENAI_API_KEY=sk-你的真实key
export OPENAI_BASE_URL=http://localhost:8765/v1
codex
```

或写入 `~/.codex/config.toml`：

```toml
[provider]
base_url = "http://localhost:8765/v1"
api_key = "sk-你的真实key"
```

### 验证

```bash
codex "我是谁？最近在做什么？"
```

应该返回基于你 Wiki 的个性化回答。

---

## 5. Cline (VSCode 插件)

**协议**：API 代理

### 配置

VSCode → Cline 设置面板：

| 字段 | 值 |
|------|-----|
| API Provider | `OpenAI Compatible` |
| Base URL | `http://localhost:8765/v1` |
| API Key | 你的真实 key（DeepSeek / OpenAI / 其他） |
| Model ID | `deepseek-chat` 或其他你想用的 model |

代理会自动按 model 名路由：
- `deepseek-*` → DeepSeek
- `gpt-*` → OpenAI
- `qwen-*` → 通义千问

---

## 6. Continue.dev

**协议**：MCP（推荐）或 API 代理

### MCP 方式

编辑 `~/.continue/config.json`：

```json
{
  "experimental": {
    "modelContextProtocolServer": {
      "transport": {
        "type": "stdio",
        "command": "/path/to/memoryos/venv/bin/python",
        "args": ["/path/to/memoryos/memoryos_mcp/mcp_server.py"],
        "env": {
          "PYTHONPATH": "/path/to/memoryos"
        }
      }
    }
  }
}
```

### API 代理方式

```json
{
  "models": [{
    "title": "DeepSeek (via MemoryOS)",
    "provider": "openai",
    "model": "deepseek-chat",
    "apiBase": "http://localhost:8765/v1",
    "apiKey": "sk-你的真实key"
  }]
}
```

---

## 7. OpenClaw

**两种方式都支持。**

### 方式 A：MCP

`Settings → MCP Servers → Add`：

```json
{
  "memoryos": {
    "command": "/path/to/memoryos/venv/bin/python",
    "args": ["/path/to/memoryos/memoryos_mcp/mcp_server.py"]
  }
}
```

### 方式 B：API 代理

`Settings → API Provider`：
- API Type: `OpenAI Compatible`
- API URL: `http://localhost:8765/v1`
- API Key: 你的真实 key
- Model: 任意你想用的（`claude-haiku-4-5` / `deepseek-chat` / `qwen-plus` 等）

---

## 8. QClaw

**协议**：API 代理

`设置 → API` 中：

| 字段 | 值 |
|------|-----|
| API 类型 | OpenAI 兼容 |
| API 地址 | `http://localhost:8765/v1` |
| API 密钥 | 你的真实 key |
| 模型名 | `deepseek-chat`（或其他） |

---

## 9. Hermes

**协议**：API 代理

Hermes 默认调用 Claude API。改成走代理：

`Settings → Anthropic API`：

```
API URL: http://localhost:8765
API Key: 你的真实 sk-ant-key
```

注意 Hermes 用的是 Anthropic 原生格式，所以路径是 `/v1/messages`，不是 `/v1/chat/completions`。  
代理会自动识别并转发到 `api.anthropic.com`。

---

## 10. Cherry Studio

**协议**：API 代理

`设置 → 模型服务 → 添加`：

| 字段 | 值 |
|------|-----|
| 服务商类型 | OpenAI |
| API 主机 | `http://localhost:8765/v1` |
| API 密钥 | 你的真实 key |
| 模型 | 添加你想用的（`deepseek-chat`、`qwen-plus`、`glm-4-flash` 等） |

---

## 11. Chatbox

**协议**：API 代理

`设置 → 模型`：

```
Model Provider:  OpenAI API
API Host:        http://localhost:8765/v1
API Key:         你的真实 key
Model:           deepseek-chat (或其他)
```

---

## 12. Ollama + 任意本地 GUI

如果你用 Ollama 跑本地模型，且通过某个 GUI 调用它：

### 让 GUI 走 MemoryOS 代理

把 GUI 里的 Ollama 地址：
```
http://localhost:11434
```
改成：
```
http://localhost:8765
```

代理会识别 `qwen-*` / `llama-*` / `phi-*` / `gemma-*` 等本地模型前缀，自动转发到 Ollama。

### 或显式指定 model

如果你的模型名不在自动路由列表中，可在启动代理时指定上游：

```bash
PYTHONPATH=. python proxy/proxy_server.py --upstream http://localhost:11434
```

---

## 网页版 AI（Claude.ai / ChatGPT / DeepSeek Chat 等）

网页版没法直接接入代理。两种兜底方案：

### 兜底方案 1：复制上下文卡

在浏览器 Bookmarklet 或终端运行：

```bash
curl http://localhost:8765/health  # 确认代理在线
curl -s "http://localhost:8766/api/page/me.md" | python3 -c "import sys,json;print(json.load(sys.stdin)['content'])"
```

把输出粘贴到网页 AI 的「自定义指令 / 系统提示」字段。

### 兜底方案 2：浏览器插件（开发中）

未来 Phase 2 会做浏览器插件，自动注入到所有网页 AI 工具。

---

## 故障排查

### Q: 代理启动失败，端口被占用

```bash
lsof -i :8765
kill -9 <PID>
```

### Q: MCP 工具显示已连接但调用失败

检查 Python 路径和 PYTHONPATH 是否正确。`~/.claude.json` 里写绝对路径。

### Q: 国内厂商 API 报 401

确认两点：
1. `.env` 里 `AI_API_KEY` 是真实的 key（去对应厂商后台获取）
2. `AI_PROVIDER` 名字拼对了（参考 `.env.example` 列表）

### Q: 想换厂商，旧 Wiki 还能用吗？

能。Wiki 是 Markdown，跟厂商无关。改 `.env` 里的 `AI_PROVIDER` 重启代理就行。

---

## 测试每个接入是否成功

最简单的测试：在工具里问一句你的真实主项目，看看 AI 是否回答得出来。

例如：

> 我最近主要在做什么项目？技术栈是什么？

如果接入成功，AI 会从 Wiki 拉到准确答案。如果没接入成功，AI 会说「我没有这个信息」或瞎编。
