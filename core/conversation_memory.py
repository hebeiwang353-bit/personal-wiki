"""
三层对话记忆系统
  - 原始日志  conversations/YYYY-MM-DD.jsonl  — 每次对话完整记录
  - 短期记忆  memory/short_term.json          — 过去24小时提炼的事实，注入每次对话
  - 长期记忆  memory/long_term.md             — 项目进度/关键决策，每日扫描合并更新
"""

import asyncio
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

MEMORYOS_HOME = Path(os.environ.get("MEMORYOS_HOME", Path.home() / ".memoryos"))
CONV_DIR   = MEMORYOS_HOME / "conversations"
MEM_DIR    = MEMORYOS_HOME / "memory"
SHORT_FILE = MEM_DIR / "short_term.json"
LONG_FILE  = MEM_DIR / "long_term.md"

# ── 提示词 ────────────────────────────────────────────────────

_EXTRACT_PROMPT = """\
从以下AI对话中，提炼最多3条值得记住的关键信息（决策、结论、涉及的文件/功能名、下一步计划）。
如果是闲聊或没有实质内容，返回空列表。
只返回JSON数组，每项一句话中文，不要其他文字。

用户：{user}
AI：{assistant}"""

_CONSOLIDATE_PROMPT = """\
根据以下近期对话摘要，更新项目进度记忆文档。
保留已有重要信息，补充新进展，删除明显过时的内容。
格式：Markdown，按项目名分组，每个项目包含：当前状态、最近进展、待办事项。
总字数控制在600字以内。

【已有长期记忆】
{existing}

【近期对话摘要（最近7天）】
{recent_facts}"""


# ── 厂商配置（与 proxy 保持一致）────────────────────────────────

_PROVIDER_URLS: dict[str, str] = {
    "deepseek":  "https://api.deepseek.com/v1",
    "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "moonshot":  "https://api.moonshot.cn/v1",
    "zhipu":     "https://open.bigmodel.cn/api/paas/v4",
    "doubao":    "https://ark.cn-beijing.volces.com/api/v3",
    "openai":    "https://api.openai.com/v1",
    "groq":      "https://api.groq.com/openai/v1",
    "mistral":   "https://api.mistral.ai/v1",
    "gemini":    "https://generativelanguage.googleapis.com/v1beta/openai",
    "grok":      "https://api.x.ai/v1",
    "minimax":   "https://api.minimax.chat/v1",
    "stepfun":   "https://api.stepfun.com/v1",
    "ernie":     "https://qianfan.baidubce.com/v2",
}

_PROVIDER_MODELS: dict[str, str] = {
    "deepseek":  "deepseek-chat",
    "dashscope": "qwen-turbo",
    "moonshot":  "moonshot-v1-8k",
    "zhipu":     "glm-4-flash",
    "doubao":    "doubao-lite-4k",
    "openai":    "gpt-4o-mini",
    "groq":      "llama-3.1-8b-instant",
    "mistral":   "mistral-small-latest",
    "gemini":    "gemini-2.0-flash",
    "grok":      "grok-3-mini",
    "minimax":   "MiniMax-Text-01",
    "stepfun":   "step-1-flash",
    "ernie":     "ernie-lite-8k",
}


# ── 工具名检测 ────────────────────────────────────────────────

def detect_tool_name(model: str, user_agent: str = "") -> str:
    """从 model 名和 User-Agent 推断发起请求的 AI 工具名称。"""
    ua = user_agent.lower()
    for kw, name in [
        ("cursor", "Cursor"), ("continue", "Continue.dev"),
        ("cline", "Cline"), ("claude", "Claude Desktop"),
        ("chatbox", "Chatbox"), ("cherry", "Cherry Studio"),
    ]:
        if kw in ua:
            return name

    m = model.lower()
    for kw, name in [
        ("claude", "Claude"), ("gpt", "OpenAI"), ("o1-", "OpenAI"), ("o3-", "OpenAI"),
        ("deepseek", "DeepSeek"), ("qwen", "通义"), ("moonshot", "Kimi"),
        ("kimi", "Kimi"), ("glm", "智谱"), ("doubao", "豆包"),
        ("gemini", "Gemini"), ("grok", "Grok"), ("mistral", "Mistral"),
    ]:
        if kw in m:
            return name
    return model.split("/")[-1][:20] if model else "AI"


# ── 短期记忆读写 ──────────────────────────────────────────────

def _load_short_term() -> list[dict]:
    if not SHORT_FILE.exists():
        return []
    try:
        entries = json.loads(SHORT_FILE.read_text(encoding="utf-8"))
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        return [e for e in entries if isinstance(e, dict) and e.get("time", "") >= cutoff]
    except Exception:
        return []


def _save_short_term(entries: list[dict]):
    MEM_DIR.mkdir(parents=True, exist_ok=True)
    SHORT_FILE.write_text(
        json.dumps(entries[-60:], ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_short_term_context() -> str:
    """返回过去24小时对话摘要，格式化为可注入的 Markdown 段落。"""
    entries = _load_short_term()
    if not entries:
        return ""

    lines = []
    for e in entries[-20:]:
        t = e.get("time", "")[:16].replace("T", " ")
        tool = e.get("tool", "AI")
        facts = e.get("facts", [])
        if facts:
            lines.append(f"- {t} [{tool}] " + "；".join(facts))

    if not lines:
        return ""
    return "## 近期对话记录（过去24小时）\n" + "\n".join(lines)


def get_long_term_context() -> str:
    """返回长期记忆（项目进度）内容。"""
    if not LONG_FILE.exists():
        return ""
    content = LONG_FILE.read_text(encoding="utf-8").strip()
    return f"## 项目进度记忆\n{content}" if content else ""


# ── 原始对话日志 ──────────────────────────────────────────────

def _save_raw(tool: str, model: str, user_msg: str, assistant_msg: str):
    CONV_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    record = {
        "time":      datetime.now(timezone.utc).isoformat(),
        "tool":      tool,
        "model":     model,
        "user":      user_msg[:3000],
        "assistant": assistant_msg[:3000],
    }
    log_file = CONV_DIR / f"{today}.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── AI 客户端（异步）─────────────────────────────────────────

async def _call_ai(prompt: str, max_tokens: int = 300, timeout: int = 30) -> str:
    """调用配置的 AI 厂商提取信息，出错返回空字符串。"""
    try:
        from dotenv import load_dotenv
        load_dotenv(MEMORYOS_HOME / ".env")

        provider = os.environ.get("AI_PROVIDER", "deepseek")
        api_key  = os.environ.get("AI_API_KEY", "")

        if not api_key or "xxxxxxx" in api_key:
            return ""

        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            model  = os.environ.get("AI_MODEL", "claude-haiku-4-5-20251001")
            loop   = asyncio.get_event_loop()
            msg    = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: client.messages.create(
                    model=model, max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}]
                )),
                timeout=timeout,
            )
            return msg.content[0].text.strip()

        if provider == "ollama":
            base_url = "http://localhost:11434/v1"
            model    = os.environ.get("AI_MODEL", "llama3.2")
            key      = "ollama"
        else:
            base_url = os.environ.get("AI_BASE_URL") or _PROVIDER_URLS.get(provider, "https://api.openai.com/v1")
            model    = os.environ.get("AI_MODEL") or _PROVIDER_MODELS.get(provider, "gpt-4o-mini")
            key      = api_key

        import openai
        client = openai.AsyncOpenAI(base_url=base_url, api_key=key)
        resp = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0,
            ),
            timeout=timeout,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""


# ── 核心：记录一次对话交换 ────────────────────────────────────

async def record_exchange(tool: str, model: str, user_msg: str, assistant_msg: str):
    """
    在后台异步执行：保存原始日志 → 提炼事实 → 更新短期记忆。
    调用方用 asyncio.create_task() 触发，不阻塞响应。
    """
    if not user_msg.strip() or not assistant_msg.strip():
        return

    _save_raw(tool, model, user_msg, assistant_msg)

    prompt  = _EXTRACT_PROMPT.format(user=user_msg[:600], assistant=assistant_msg[:600])
    raw_out = await _call_ai(prompt, max_tokens=250, timeout=25)
    if not raw_out:
        return

    try:
        m = re.search(r"\[.*?\]", raw_out, re.DOTALL)
        facts = json.loads(m.group()) if m else []
        facts = [f for f in facts if isinstance(f, str) and f.strip()][:3]
    except Exception:
        facts = []

    if not facts:
        return

    entries = _load_short_term()
    entries.append({
        "time":  datetime.now(timezone.utc).isoformat(),
        "tool":  tool,
        "model": model,
        "facts": facts,
    })
    _save_short_term(entries)


# ── 核心：每日合并到长期记忆 ─────────────────────────────────

async def consolidate_to_long_term():
    """
    把短期记忆中的事实合并进长期记忆（项目进度文档）。
    每日扫描时调用一次。
    """
    entries = _load_short_term()
    # 也读取过去7天的 short_term（历史文件暂未持久化，仅用已加载的）
    if not entries:
        return

    fact_lines = [
        f"- [{e['time'][:10]}][{e['tool']}] " + "；".join(e.get("facts", []))
        for e in entries if e.get("facts")
    ]
    if not fact_lines:
        return

    existing = LONG_FILE.read_text(encoding="utf-8").strip() if LONG_FILE.exists() else "（暂无）"
    prompt   = _CONSOLIDATE_PROMPT.format(
        existing=existing[:1500],
        recent_facts="\n".join(fact_lines[:60])
    )

    result = await _call_ai(prompt, max_tokens=900, timeout=60)
    if result:
        MEM_DIR.mkdir(parents=True, exist_ok=True)
        LONG_FILE.write_text(result, encoding="utf-8")
