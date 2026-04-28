#!/usr/bin/env python3
"""
MemoryOS MCP Server
支持 OpenClaw / Claude Code / Claude Desktop 等 MCP 兼容工具。

Tools 暴露：
  - get_user_context   每次对话自动注入个人上下文
  - query_wiki         在 Wiki 中检索特定信息
  - update_wiki        把对话中的重要信息写回 Wiki
  - get_wiki_status    查看 Wiki 建立状态

启动方式：python mcp_server.py
"""

import sys
import json
import asyncio
from pathlib import Path

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from mcp.server import FastMCP
from wiki.wiki_manager import (
    WIKI_ROOT, init_wiki, get_page, update_page,
    get_all_content, list_pages, append_log, recent_logs,
)
from wiki.context_builder import build_context, context_token_count
from memoryos_mcp.onboarding import needs_onboarding, run_onboarding_text

app = FastMCP(
    name="MemoryOS",
    instructions=(
        "MemoryOS 是用户的本地个人记忆系统。"
        "在每次对话开始时，请调用 get_user_context 获取用户背景，"
        "让你的回答更加贴近用户实际情况。"
    ),
)


# ── Tool 1: 获取用户上下文 ────────────────────────────────────

@app.tool()
def get_user_context(query: str = "") -> str:
    """
    获取用户个人上下文。
    在每次对话开始时调用，将用户画像注入到当前对话。
    query: 当前问题（可选），用于返回更相关的上下文片段。
    """
    if needs_onboarding():
        return run_onboarding_text()

    ctx = build_context(query=query or None)
    if not ctx:
        return (
            "MemoryOS：用户知识库尚未建立。\n"
            "请告诉用户运行扫描命令：\n"
            "`python main.py --max-files 100`"
        )
    token_count = context_token_count()
    return f"{ctx}\n\n<!-- MemoryOS: {token_count} tokens -->"


# ── Tool 2: 查询 Wiki ─────────────────────────────────────────

@app.tool()
def query_wiki(query: str) -> str:
    """
    在用户 Wiki 知识库中检索与 query 相关的信息。
    用于需要查找用户历史项目、技能、习惯等具体信息时。
    """
    if not WIKI_ROOT.exists():
        return "Wiki 尚未建立。"

    all_pages = get_all_content()
    if not all_pages:
        return "Wiki 为空。"

    q_words = set(query.lower().split())
    results = []
    for path, content in all_pages.items():
        score = sum(1 for w in q_words if w in content.lower())
        if score > 0:
            results.append((score, path, content))

    if not results:
        return f"Wiki 中未找到与「{query}」相关的内容。"

    results.sort(key=lambda x: -x[0])
    output = f"## Wiki 检索结果：{query}\n\n"
    for _, path, content in results[:3]:
        preview = content[:800]
        output += f"### {path}\n{preview}\n\n"

    append_log(f"查询 Wiki：{query}")
    return output


# ── Tool 3: 更新 Wiki ─────────────────────────────────────────

@app.tool()
def update_wiki(page: str, content: str) -> str:
    """
    将对话中产生的重要信息写入 Wiki 页面。
    page: 页面路径，如 'me.md' 或 'projects/myapp.md'
    content: 要写入的 Markdown 内容
    """
    if not page.endswith(".md"):
        page = page + ".md"

    # 安全检查：不允许写到 Wiki 目录外
    target = (WIKI_ROOT / page).resolve()
    if not str(target).startswith(str(WIKI_ROOT.resolve())):
        return "错误：不允许写入 Wiki 目录之外的文件。"

    existing = get_page(page) or ""
    if existing and content in existing:
        return f"内容已存在于 {page}，无需更新。"

    if existing:
        # 追加到页面末尾
        new_content = existing.rstrip() + "\n\n" + content
    else:
        new_content = f"# {Path(page).stem}\n\n{content}"

    update_page(page, new_content)
    append_log(f"更新页面 {page}（来自对话）")
    return f"✓ 已写入 {page}"


# ── Tool 4: Wiki 状态 ─────────────────────────────────────────

@app.tool()
def get_wiki_status() -> str:
    """查看用户 Wiki 的建立状态和页面列表。"""
    if not WIKI_ROOT.exists():
        return "Wiki 尚未建立。请先运行文件扫描。"

    pages = list_pages()
    logs = recent_logs(5)
    me = get_page("me.md") or ""
    summary_line = next(
        (l for l in me.splitlines() if "综合描述" in l or "画像总结" in l),
        "（画像未建立）"
    )

    status = (
        f"## MemoryOS Wiki 状态\n\n"
        f"- 位置：`{WIKI_ROOT}`\n"
        f"- 页面数：{len(pages)}\n"
        f"- 上下文：约 {context_token_count()} tokens\n\n"
        f"**用户摘要**：{summary_line}\n\n"
        f"**页面列表**：\n" + "\n".join(f"  - {p}" for p in pages) + "\n\n"
        f"**最近操作**：\n{logs}"
    )
    return status


# ── 入口 ─────────────────────────────────────────────────────

if __name__ == "__main__":
    init_wiki()
    app.run(transport="stdio")
