#!/usr/bin/env python3
"""
MemoryOS 通用 API 代理
监听 localhost:8765，拦截所有 AI 请求，自动注入个人上下文。

支持格式：
  POST /v1/chat/completions   OpenAI 兼容（Ollama / DeepSeek / Qwen 等）
  POST /v1/messages           Anthropic / Claude 格式

用法：
  python proxy/proxy_server.py
  python proxy/proxy_server.py --port 8765 --upstream https://api.deepseek.com
"""

import argparse
import asyncio
import json
import sys
import tomllib
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
import aiohttp

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from wiki.context_builder import build_context, build_system_prompt
from core.conversation_memory import record_exchange, detect_tool_name

# ── 配置加载 ──────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "proxy": {"port": 8765, "context_max_tokens": 1500},
    "upstreams": [
        {"name": "claude",   "format": "anthropic", "target": "https://api.anthropic.com"},
        {"name": "openai",   "format": "openai",    "target": "https://api.openai.com"},
        {"name": "deepseek", "format": "openai",    "target": "https://api.deepseek.com"},
        {"name": "ollama",   "format": "openai",    "target": "http://localhost:11434"},
    ],
}

CONFIG_FILE = ROOT / "proxy" / "config.toml"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            return tomllib.load(f)
    return DEFAULT_CONFIG


# ── FastAPI 应用 ──────────────────────────────────────────────

app = FastAPI(title="MemoryOS Proxy", docs_url=None, redoc_url=None)
_config = load_config()
_upstream_url: str = ""   # 命令行可覆盖


# model 名前缀 → 上游服务地址（后缀路径会自动追加）
# 顺序：先匹配更具体的前缀，再匹配通用前缀
MODEL_ROUTES: list[tuple[str, str]] = [
    # ── Anthropic ──
    ("claude", "https://api.anthropic.com"),

    # ── OpenAI 系列（gpt-、o1-、o3-、text-、dall-） ──
    ("gpt", "https://api.openai.com"),
    ("o1", "https://api.openai.com"),
    ("o3", "https://api.openai.com"),
    ("o4", "https://api.openai.com"),
    ("text-", "https://api.openai.com"),
    ("dall-e", "https://api.openai.com"),
    ("davinci", "https://api.openai.com"),

    # ── DeepSeek ──
    ("deepseek", "https://api.deepseek.com"),

    # ── 国内厂商 ──
    ("qwen", "https://dashscope.aliyuncs.com/compatible-mode"),  # 通义千问云端
    ("qwq", "https://dashscope.aliyuncs.com/compatible-mode"),
    ("glm", "https://open.bigmodel.cn/api/paas/v4"),              # 智谱
    ("chatglm", "https://open.bigmodel.cn/api/paas/v4"),
    ("moonshot", "https://api.moonshot.cn"),                       # Kimi
    ("kimi", "https://api.moonshot.cn"),
    ("doubao", "https://ark.cn-beijing.volces.com/api/v3"),       # 字节豆包
    ("ernie", "https://qianfan.baidubce.com/v2"),                  # 文心一言
    ("minimax", "https://api.minimax.chat"),
    ("step-", "https://api.stepfun.com"),                          # 阶跃星辰
    ("abab", "https://api.minimax.chat"),

    # ── 海外厂商 ──
    ("grok", "https://api.x.ai"),
    ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai"),
    ("mistral", "https://api.mistral.ai"),
    ("mixtral", "https://api.mistral.ai"),
    ("llama-3", "https://api.groq.com/openai"),  # 默认走 Groq，本地用户可用 --upstream 覆盖

    # ── 本地 Ollama 常见模型（如果想走云端 Groq 加 --upstream）──
    ("llama", "http://localhost:11434"),
    ("phi", "http://localhost:11434"),
    ("gemma", "http://localhost:11434"),
    ("yi:", "http://localhost:11434"),
    ("internlm", "http://localhost:11434"),
]


def get_upstream(path: str, model: str = "") -> str:
    """
    根据请求路径 + model 字段智能选择上游。
    优先级：命令行 --upstream > model 名前缀匹配 > 路径默认值
    """
    if _upstream_url:
        return _upstream_url.rstrip("/")

    model_lower = model.lower()
    if model_lower:
        # Ollama 模型名标准格式带冒号（如 qwen2.5:7b、llama3.2:1b）
        # 优先识别为本地 Ollama
        if ":" in model_lower and not model_lower.startswith("step-"):
            return "http://localhost:11434"

        for prefix, target in MODEL_ROUTES:
            if model_lower.startswith(prefix):
                return target.rstrip("/")

    # 路径默认
    if "/messages" in path:
        for u in _config.get("upstreams", []):
            if u["format"] == "anthropic":
                return u["target"].rstrip("/")
    for u in _config.get("upstreams", []):
        if u["name"] == "openai":
            return u["target"].rstrip("/")
    return "https://api.openai.com"


# ── OpenAI 格式注入 ───────────────────────────────────────────

def inject_openai(body: dict, query: str) -> dict:
    """向 OpenAI 格式请求注入 system prompt。"""
    messages = body.get("messages", [])
    ctx = build_context(query=query)
    if not ctx:
        return body

    # 查找已有 system 消息
    system_idx = next((i for i, m in enumerate(messages) if m.get("role") == "system"), None)

    if system_idx is not None:
        original = messages[system_idx].get("content", "")
        messages[system_idx]["content"] = f"{ctx}\n\n{original}"
    else:
        messages.insert(0, {"role": "system", "content": ctx})

    body["messages"] = messages
    return body


# ── Anthropic 格式注入 ────────────────────────────────────────

def inject_anthropic(body: dict, query: str) -> dict:
    """向 Anthropic 格式请求注入 system prompt。"""
    ctx = build_context(query=query)
    if not ctx:
        return body

    original_system = body.get("system", "")
    if isinstance(original_system, list):
        # 支持 Anthropic 结构化 system blocks
        body["system"] = [{"type": "text", "text": ctx}] + original_system
    else:
        body["system"] = f"{ctx}\n\n{original_system}" if original_system else ctx

    return body


# ── 提取对话中的 query ────────────────────────────────────────

def extract_query(body: dict, is_anthropic: bool) -> str:
    """从请求体中提取最后一条用户消息作为 query（用于相关上下文匹配）。"""
    try:
        messages = body.get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content[:200]
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            return block.get("text", "")[:200]
    except Exception:
        pass
    return ""


# ── 通用代理核心 ──────────────────────────────────────────────

def _extract_text_from_sse_chunk(chunk_bytes: bytes, is_anthropic: bool) -> str:
    """从 SSE chunk 中提取文本内容（尽力而为，失败返回空串）。"""
    text = ""
    try:
        for line in chunk_bytes.decode("utf-8", errors="ignore").splitlines():
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            data = json.loads(line[6:])
            if is_anthropic:
                # Anthropic SSE: content_block_delta
                if data.get("type") == "content_block_delta":
                    text += data.get("delta", {}).get("text", "")
            else:
                # OpenAI SSE: choices[0].delta.content
                delta = data.get("choices", [{}])[0].get("delta", {})
                text += delta.get("content", "")
    except Exception:
        pass
    return text


def _extract_text_from_response(content: bytes, is_anthropic: bool) -> str:
    """从非流式响应体中提取 assistant 文本。"""
    try:
        data = json.loads(content)
        if is_anthropic:
            blocks = data.get("content", [])
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        else:
            return data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    except Exception:
        return ""


async def _proxy(request: Request, is_anthropic: bool) -> Response:
    body = await request.json()
    query = extract_query(body, is_anthropic)
    model = body.get("model", "")
    tool  = detect_tool_name(model, request.headers.get("user-agent", ""))

    # 注入上下文
    if is_anthropic:
        body = inject_anthropic(body, query)
    else:
        body = inject_openai(body, query)

    upstream   = get_upstream(request.url.path, model=model)
    target_url = upstream + request.url.path

    # 透传所有原始 headers（除 host）
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }

    is_stream = body.get("stream", False)

    if is_stream:
        session = aiohttp.ClientSession()
        try:
            resp = await session.post(
                target_url,
                json=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120),
            )
            resp_headers = {
                k: v for k, v in resp.headers.items()
                if k.lower() not in ("content-encoding", "transfer-encoding", "content-length")
            }

            # 捕获流式响应文本，流结束后触发记忆提炼
            _buf: list[str] = []

            async def stream_gen():
                try:
                    async for chunk in resp.content.iter_chunked(1024):
                        yield chunk
                        txt = _extract_text_from_sse_chunk(chunk, is_anthropic)
                        if txt:
                            _buf.append(txt)
                finally:
                    resp.release()
                    await session.close()
                    assistant_text = "".join(_buf)
                    if assistant_text and query:
                        asyncio.create_task(
                            record_exchange(tool, model, query, assistant_text)
                        )

            return StreamingResponse(
                stream_gen(),
                status_code=resp.status,
                headers=resp_headers,
                media_type=resp.content_type,
            )
        except Exception:
            await session.close()
            raise
    else:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                target_url,
                json=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                resp_headers = {
                    k: v for k, v in resp.headers.items()
                    if k.lower() not in ("content-encoding", "transfer-encoding", "content-length")
                }
                content = await resp.read()
                # 非流式：提炼记忆
                if resp.status == 200 and query:
                    assistant_text = _extract_text_from_response(content, is_anthropic)
                    if assistant_text:
                        asyncio.create_task(
                            record_exchange(tool, model, query, assistant_text)
                        )
                return Response(
                    content=content,
                    status_code=resp.status,
                    headers=resp_headers,
                    media_type=resp.content_type,
                )


# ── 路由 ─────────────────────────────────────────────────────

@app.post("/v1/chat/completions")
async def openai_chat(request: Request):
    """OpenAI 兼容接口（Ollama / DeepSeek / Qwen 等）"""
    return await _proxy(request, is_anthropic=False)


@app.post("/v1/messages")
async def anthropic_messages(request: Request):
    """Anthropic / Claude 接口"""
    return await _proxy(request, is_anthropic=True)


@app.get("/health")
async def health():
    """健康检查"""
    from wiki.wiki_manager import list_pages, WIKI_ROOT
    pages = list_pages() if WIKI_ROOT.exists() else []
    return {
        "status": "ok",
        "wiki_pages": len(pages),
        "upstream": _upstream_url or "auto",
    }


@app.get("/")
async def root():
    return {
        "name": "MemoryOS Proxy",
        "version": "0.1.0",
        "endpoints": ["/v1/chat/completions", "/v1/messages", "/health"],
        "usage": "把你的 AI 工具 API 地址改为 http://localhost:8765",
    }


# ── 入口 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MemoryOS 通用 API 代理")
    parser.add_argument("--port", type=int, default=_config["proxy"]["port"], help="监听端口")
    parser.add_argument("--upstream", default="", help="强制指定上游地址，如 http://localhost:11434")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认仅本地）")
    args = parser.parse_args()

    _upstream_url = args.upstream

    print(f"MemoryOS 代理启动")
    print(f"  监听：http://{args.host}:{args.port}")
    print(f"  上游：{args.upstream or '自动（按请求格式选择）'}")
    print(f"  把 AI 工具的 API 地址改为 http://localhost:{args.port} 即可")
    print()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
