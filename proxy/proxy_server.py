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


def get_upstream(path: str, model: str = "") -> str:
    """
    根据请求路径 + model 字段智能选择上游。
    优先级：命令行 --upstream > model 名匹配 > 路径默认值
    """
    if _upstream_url:
        return _upstream_url.rstrip("/")

    # 按 model 名前缀匹配
    model_lower = model.lower()
    if model_lower:
        if model_lower.startswith("deepseek"):
            return "https://api.deepseek.com"
        if model_lower.startswith("claude"):
            return "https://api.anthropic.com"
        if model_lower.startswith(("gpt", "o1", "o3", "text-")):
            return "https://api.openai.com"
        if model_lower.startswith(("qwen", "llama", "mistral", "phi", "gemma")):
            # 本地 Ollama 常见模型
            return "http://localhost:11434"

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

async def _proxy(request: Request, is_anthropic: bool) -> Response:
    body = await request.json()
    query = extract_query(body, is_anthropic)

    # 注入上下文
    if is_anthropic:
        body = inject_anthropic(body, query)
    else:
        body = inject_openai(body, query)

    upstream = get_upstream(request.url.path, model=body.get("model", ""))
    target_url = upstream + request.url.path

    # 透传所有原始 headers（除 host）
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }

    is_stream = body.get("stream", False)

    if is_stream:
        # 流式：手动管理 session 生命周期，确保 generator 跑完再关闭
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

            async def stream_gen():
                try:
                    async for chunk in resp.content.iter_chunked(1024):
                        yield chunk
                finally:
                    resp.release()
                    await session.close()

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
        # 非流式：用 context manager
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
