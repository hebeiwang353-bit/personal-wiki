# MemoryOS · 项目计划文档

> 让所有 AI 工具永久认识你的本地个人记忆操作系统

**版本**：v0.1 规划稿  
**日期**：2026-04-27  
**目标平台**：macOS + Windows  
**分发渠道**：GitHub 开源 + OpenClaw 插件市场

---

## 一、产品定位

### 解决的问题
用户使用多个 AI 工具（OpenClaw、QClaw、EasyClaw、Claude Code、网页版 AI 等），每次都要重新介绍自己，AI 不了解用户的职业、习惯、正在做的项目，导致回答质量低、沟通成本高。

### 解决方案
在用户本地运行一个**个人记忆中间层**：
1. 读取用户电脑文件，自动建立结构化个人知识库（Wiki）
2. 以 MCP Server 形式接入所有兼容工具（OpenClaw 等）
3. 以本地 API 代理形式接入所有其他 AI 工具（不限后端模型）
4. 每次对话自动注入个人上下文，无需用户任何操作

### 核心理念
- **本地优先**：所有数据存在用户自己电脑，不上传任何私人文件到 MemoryOS 服务器
- **模型无关**：兼容 Claude、OpenAI、DeepSeek、Ollama 等任意后端
- **零操作**：配置一次，永久生效，用户无感知

---

## 二、用户完整使用流程

```
① 在 OpenClaw 插件市场搜索 "MemoryOS" → 点击安装
         ↓
② 安装脚本自动完成：
   - 下载 MemoryOS 到本地
   - 安装 Python 依赖
   - 注册系统服务（开机自启）
   - 向 OpenClaw 注册 MCP Server
         ↓
③ 首次对话触发引导（通过 MCP 在对话框内完成）：
   "你好！我是 MemoryOS，你的个人记忆助手。
    我需要读取你的电脑文件来了解你。
    请先输入你的 API Key（用于分析文件，仅存本地）：[输入框]
    
    扫描时机：
    [现在开始]  [今晚定时]（用户输入时间）  [跳过，稍后设置]"
         ↓
④ 后台静默扫描 → 建立 Wiki → 启动代理服务
         ↓
⑤ 用户正常使用任意 AI 工具，自动带上个人上下文
         ↓
⑥ 每周定时增量扫描，Wiki 自动更新
```

---

## 三、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户电脑                              │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ OpenClaw │    │  QClaw   │    │ EasyClaw │  ...         │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘              │
│       │ MCP            │ API代理        │ API代理             │
│       ▼                ▼               ▼                    │
│  ┌─────────────────────────────────────────┐               │
│  │           MemoryOS Core                 │               │
│  │                                         │               │
│  │  ┌─────────────┐   ┌─────────────────┐  │               │
│  │  │ MCP Server  │   │  通用 API 代理   │  │               │
│  │  │  :port MCP  │   │  localhost:8765  │  │               │
│  │  └──────┬──────┘   └────────┬────────┘  │               │
│  │         │                   │            │               │
│  │         └─────────┬─────────┘            │               │
│  │                   ▼                      │               │
│  │         ┌──────────────────┐             │               │
│  │         │  Context Builder │             │               │
│  │         │  从Wiki提取上下文  │             │               │
│  │         └────────┬─────────┘             │               │
│  │                  │                       │               │
│  │         ┌────────▼─────────┐             │               │
│  │         │   Wiki 知识库    │             │               │
│  │         │  (Markdown文件)  │             │               │
│  │         └────────┬─────────┘             │               │
│  │                  │                       │               │
│  │         ┌────────▼─────────┐             │               │
│  │         │   扫描 & 分析引擎  │             │               │
│  │         │ Scanner→Extractor │             │               │
│  │         │ →Embedder→Claude  │             │               │
│  │         └──────────────────┘             │               │
│  └─────────────────────────────────────────┘               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                           │
              转发到真实 AI 服务（带注入上下文）
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
  api.anthropic.com   api.deepseek.com  localhost:11434
     (Claude)           (DeepSeek)         (Ollama)
```

---

## 四、模块详细设计

### 4.1 Wiki 知识库层（Karpathy 风格）

**存储格式**：Markdown 文件，存于 `~/.memoryos/wiki/`

```
~/.memoryos/
  wiki/
    index.md          ← 所有页面目录 + 导航
    me.md             ← 用户核心画像（职业、习惯、知识结构）
    projects/         ← 正在进行的项目
      project_A.md
      project_B.md
    interests/        ← 兴趣领域知识图谱
    tools/            ← 常用工具链
    log.md            ← 追加式操作日志（摄入/查询/更新记录）
  chroma_db/          ← 向量数据库（ChromaDB 持久化）
  config.toml         ← 用户配置
  .env                ← API Keys（加密存储）
```

**三种操作模式**（参考 Karpathy）：
- `ingest`：新文件扫描 → 更新相关 Wiki 页面（增量，不全量重写）
- `query`：在 Wiki 内检索并合成答案
- `inspect`：定期检查矛盾、空白、过时信息

**Wiki 更新策略**：
- 新文件进来时，Claude 判断影响哪些页面（最多 10 个）
- 只更新受影响页面，其余不动
- 每次更新追加一条 log.md 记录

---

### 4.2 MCP Server（OpenClaw 等 MCP 兼容工具接入）

**功能**：
- 暴露工具（Tools）和资源（Resources）给 MCP 客户端
- 首次运行触发 onboarding 流程
- 提供 `get_user_context` 工具：返回压缩后的个人上下文
- 提供 `query_wiki` 工具：在 Wiki 中检索特定信息

**MCP Tools 定义**：
```json
{
  "tools": [
    {
      "name": "get_user_context",
      "description": "获取用户个人上下文，在每次对话开始时自动调用",
      "returns": "压缩的用户画像 markdown，约500-1500 token"
    },
    {
      "name": "query_wiki",
      "description": "在用户知识库中检索特定信息",
      "parameters": { "query": "string" }
    },
    {
      "name": "update_wiki",
      "description": "将对话中产生的重要信息写回 Wiki",
      "parameters": { "content": "string", "page": "string" }
    }
  ]
}
```

---

### 4.3 通用 API 代理（非 MCP 工具接入）

**监听端口**：`localhost:8765`

**支持格式**：
- `POST /v1/chat/completions`（OpenAI 格式）← 覆盖 Ollama、DeepSeek、大多数工具
- `POST /v1/messages`（Anthropic 格式）← 覆盖 Claude 专用工具

**处理流程**：
```
收到请求
  → 识别格式（OpenAI / Anthropic）
  → 读取 Wiki 生成压缩上下文（< 1500 token）
  → 注入为 system prompt 开头
  → 流式转发到真实上游（保持 SSE 流）
  → 返回给客户端
```

**上游路由配置**（`config.toml`）：
```toml
[proxy]
port = 8765
context_max_tokens = 1500

# 默认上游（用户可修改）
[[upstreams]]
name = "claude"
format = "anthropic"
target = "https://api.anthropic.com"

[[upstreams]]
name = "deepseek"
format = "openai"
target = "https://api.deepseek.com"

[[upstreams]]
name = "ollama"
format = "openai"
target = "http://localhost:11434"

[[upstreams]]
name = "openai"
format = "openai"
target = "https://api.openai.com"
```

---

### 4.4 首次引导流程（Onboarding）

触发条件：`~/.memoryos/wiki/` 不存在或为空

**引导步骤**（通过 MCP 对话框交互）：

```
Step 1: 欢迎 + 权限说明
  → 说明会读取哪些文件、数据存哪里、不上传到任何服务器

Step 2: API Key 配置
  → 询问使用哪个 AI 服务（Claude / DeepSeek / Ollama 本地）
  → 输入对应 API Key
  → 加密保存到 ~/.memoryos/.env

Step 3: 扫描时机选择
  → [现在开始扫描]
  → [设定定时]（用户输入如 "22:00"）
  → [跳过，稍后设置]

Step 4: 代理配置引导
  → 展示如何把其他 AI 工具的 API 地址改为 localhost:8765
  → 提供各主流工具的图文教程链接

Step 5: 完成
  → 告知用户 Wiki 建好后会通知（系统通知）
```

---

### 4.5 定时调度器（Scheduler）

**跨平台实现**：
- macOS：写入 `~/Library/LaunchAgents/com.memoryos.scanner.plist`（LaunchAgent）
- Windows：调用 `schtasks` 写入任务计划程序

**调度策略**：
- 首次扫描：用户指定时间（或立即）
- 后续增量扫描：每周固定时间（默认周日 22:00，可配置）
- 增量逻辑：只处理 `mtime > 上次扫描时间` 的文件

---

### 4.6 Context Builder（上下文压缩器）

**目标**：从 Wiki 提取最相关的内容，压缩到 1500 token 以内

**策略**：
1. 始终包含 `me.md` 核心画像（~500 token）
2. 根据当前对话内容，从 Wiki 检索最相关的 2-3 个页面（~800 token）
3. 追加最近 log.md 的最新 5 条记录（~200 token）

**输出格式**（注入为 system prompt 开头）：
```markdown
<user_context>
## 关于用户
[me.md 内容]

## 相关背景
[检索到的相关 Wiki 页面片段]

## 最近动态
[log.md 最新记录]
</user_context>

[原始 system prompt 继续...]
```

---

## 五、分发与安装

### 5.1 OpenClaw 插件市场

**插件描述文件**（`memoryos.plugin.json`）：
```json
{
  "name": "MemoryOS",
  "version": "0.1.0",
  "description": "让所有 AI 工具永久认识你的本地个人记忆系统",
  "author": "王贺北",
  "github": "https://github.com/xxx/memoryos",
  "install": {
    "type": "script",
    "mac": "install.sh",
    "windows": "install.ps1"
  },
  "mcp": {
    "command": "python",
    "args": ["~/.memoryos/mcp/mcp_server.py"]
  }
}
```

### 5.2 安装脚本做的事（install.sh / install.ps1）

```
1. 检查 Python 3.10+ 是否存在，没有则提示安装
2. 创建 ~/.memoryos/ 目录结构
3. 下载 MemoryOS 代码到 ~/.memoryos/
4. 创建 venv 并安装依赖
5. 写入系统服务（开机自启动代理 + MCP Server）
6. 向 OpenClaw 注册 MCP Server（修改 OpenClaw 配置文件）
7. 打开浏览器展示"安装成功"页面
```

### 5.3 GitHub 仓库结构

```
memoryos/
  README.md           ← 产品介绍 + 安装说明
  PLAN.md             ← 本文档
  install.sh          ← macOS/Linux 安装脚本
  install.ps1         ← Windows 安装脚本
  memoryos.plugin.json ← OpenClaw 插件描述
  requirements.txt    ← Python 依赖
  core/
    scanner.py
    extractor.py
    embedder.py
    clusterer.py
    analyzer.py
    cost_estimator.py
  wiki/
    __init__.py
    wiki_manager.py   ← Wiki 页面增删改查
    context_builder.py ← 压缩上下文生成
  proxy/
    proxy_server.py   ← 通用 API 代理
    config.toml       ← 默认配置模板
  mcp/
    mcp_server.py     ← MCP Server 入口
    onboarding.py     ← 首次引导
    scheduler.py      ← 定时任务管理
  services/
    autostart_mac.py  ← macOS LaunchAgent 管理
    autostart_win.py  ← Windows 任务计划程序管理
```

---

## 六、开发顺序

| 阶段 | 模块 | 优先级 | 估计工作量 |
|------|------|--------|-----------|
| P0 | Wiki 层（wiki_manager.py + 页面结构） | 🔴 必须 | 1天 |
| P0 | Context Builder（上下文压缩） | 🔴 必须 | 0.5天 |
| P1 | MCP Server 基础框架 | 🔴 必须 | 1天 |
| P1 | Onboarding 引导流程 | 🔴 必须 | 1天 |
| P1 | 定时调度器（Mac + Win） | 🔴 必须 | 1天 |
| P2 | 通用 API 代理（OpenAI + Anthropic 格式） | 🟡 重要 | 1.5天 |
| P2 | 流式响应支持（SSE） | 🟡 重要 | 0.5天 |
| P3 | 安装脚本（install.sh + install.ps1） | 🟡 重要 | 1天 |
| P3 | OpenClaw 插件描述文件 | 🟡 重要 | 0.5天 |
| P4 | Wiki Inspect（矛盾检测） | 🟢 可选 | 1天 |
| P4 | 系统通知（扫描完成提醒） | 🟢 可选 | 0.5天 |

**编程开始顺序**：
```
① wiki_manager.py + 页面结构设计
② context_builder.py
③ 更新 analyzer.py 输出到 Wiki（而非 profile.json）
④ mcp_server.py 基础框架
⑤ onboarding.py
⑥ scheduler.py（Mac + Win 双实现）
⑦ proxy_server.py（通用代理）
⑧ install.sh + install.ps1
```

---

## 七、关键技术决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 知识库格式 | Markdown Wiki（非向量DB直存） | 人可读、LLM可读、可版本管理 |
| Embedding | OpenAI text-embedding-3-small | 便宜（$0.02/M）、质量好 |
| 分析模型 | 用户自己的 API Key | 成本由用户承担，MemoryOS 不中转 |
| 数据存储位置 | ~/.memoryos/（用户Home） | 跨平台统一，用户可见可控 |
| 代理端口 | 8765 | 避免与常用端口冲突 |
| Wiki 更新策略 | 增量（只改受影响页面） | 成本低，不覆盖用户手动编辑 |
| 上下文长度 | ≤ 1500 token | 不过度占用模型上下文窗口 |
| API Key 存储 | 本地 .env 文件 | 简单可靠，不涉及远程服务 |

---

## 八、未来版本规划（v0.2+）

- **浏览器插件**：自动注入上下文到 Claude.ai、ChatGPT 等网页
- **Wiki Query 命令行**：`memoryos query "我最近在做什么"`
- **多用户支持**：家庭/团队场景，每人独立 Wiki
- **Wiki 可视化**：本地 Web UI 展示知识图谱
- **导出**：一键导出 Wiki 为 PDF / Notion / Obsidian 格式
