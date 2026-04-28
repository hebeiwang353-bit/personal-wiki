"""
从 Wiki 提取并压缩个人上下文，注入到 AI 对话的 system prompt 中。
目标：≤ 1500 token，始终包含核心画像 + 相关页面 + 最近日志。
"""

from pathlib import Path

import tiktoken

from wiki.wiki_manager import (
    WIKI_ROOT, get_page, get_all_content, recent_logs, list_pages
)

MAX_TOKENS = 1500
_enc = None


def _tokenize(text: str) -> int:
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding("cl100k_base")
    return len(_enc.encode(text, disallowed_special=()))


def build_context(
    query: str | None = None,
    max_tokens: int = MAX_TOKENS,
    root: Path = WIKI_ROOT,
) -> str:
    """
    生成注入用的上下文字符串。
    query：当前对话问题（用于语义相关性排序，可为 None）
    返回格式：
      <user_context>
      ## 关于用户
      ...
      ## 相关背景
      ...
      ## 最近动态
      ...
      </user_context>
    """
    if not root.exists() or not list_pages(root):
        return ""

    budget = max_tokens
    sections: list[str] = []

    # ── 1. 核心画像（me.md）始终包含 ─────────────────────────────
    me = get_page("me.md", root) or ""
    me = _trim_to_tokens(me, int(budget * 0.45))
    if me.strip() and me.strip() != "（待建立）":
        sections.append(f"## 关于用户\n{me}")
        budget -= _tokenize(me)

    # ── 2. 相关页面（按 query 或按修改时间排序）───────────────────
    all_pages = get_all_content(root, exclude=["me.md", "log.md", "index.md"])

    if query and all_pages:
        ranked = _rank_by_relevance(query, all_pages)
    else:
        # 无 query 时取 projects/ 页面（最常相关）
        ranked = sorted(
            all_pages.items(),
            key=lambda kv: (0 if kv[0].startswith("projects/") else 1, kv[0])
        )

    related_parts: list[str] = []
    for rel_path, content in ranked[:5]:
        trimmed = _trim_to_tokens(content, int(budget * 0.4 / max(len(ranked[:5]), 1)))
        if trimmed.strip():
            related_parts.append(f"### {Path(rel_path).stem}\n{trimmed}")
            budget -= _tokenize(trimmed)
        if budget <= 100:
            break

    if related_parts:
        sections.append("## 相关背景\n" + "\n\n".join(related_parts))

    # ── 3. 最近日志（最后 8 条）─────────────────────────────────
    logs = recent_logs(8, root)
    if logs and budget > 80:
        logs = _trim_to_tokens(logs, min(200, budget))
        sections.append(f"## 最近动态\n{logs}")

    if not sections:
        return ""

    body = "\n\n".join(sections)
    return f"<user_context>\n{body}\n</user_context>"


def build_system_prompt(original_system: str, query: str | None = None, root: Path = WIKI_ROOT) -> str:
    """把用户上下文前置到原始 system prompt 中。"""
    ctx = build_context(query=query, root=root)
    if not ctx:
        return original_system
    if original_system:
        return f"{ctx}\n\n{original_system}"
    return ctx


# ── 工具函数 ─────────────────────────────────────────────────

def _trim_to_tokens(text: str, max_tok: int) -> str:
    """把文本截断到不超过 max_tok token。"""
    if max_tok <= 0:
        return ""
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding("cl100k_base")
    tokens = _enc.encode(text, disallowed_special=())
    if len(tokens) <= max_tok:
        return text
    return _enc.decode(tokens[:max_tok]) + "…"


def _tokenize_zh(text: str) -> list[str]:
    """中英文混合分词（用 jieba），过滤空白和单字符停用词。"""
    import jieba
    import re
    tokens = []
    for tok in jieba.cut_for_search(text.lower()):
        tok = tok.strip()
        if not tok or len(tok) < 2 and not re.match(r"[a-z0-9]", tok):
            continue
        tokens.append(tok)
    return tokens


def _rank_by_relevance(query: str, pages: dict[str, str]) -> list[tuple[str, str]]:
    """
    用 BM25 + jieba 中文分词做语义相关性排序。
    比简单关键词匹配准很多，且无需调用任何 API。
    """
    from rank_bm25 import BM25Okapi

    if not query.strip() or not pages:
        return list(pages.items())

    paths = list(pages.keys())
    contents = [pages[p] for p in paths]

    # 对每个页面分词
    corpus_tokens = [_tokenize_zh(c) for c in contents]
    query_tokens = _tokenize_zh(query)

    if not any(corpus_tokens) or not query_tokens:
        return list(pages.items())

    bm25 = BM25Okapi(corpus_tokens)
    scores = bm25.get_scores(query_tokens)

    # projects/ 页面加权（业务规则：项目页比兴趣页更可能被询问）
    boosted = []
    for i, path in enumerate(paths):
        boost = 1.5 if path.startswith("projects/") else 1.0
        boosted.append((scores[i] * boost, path, contents[i]))

    boosted.sort(key=lambda x: -x[0])
    return [(p, c) for _, p, c in boosted]


def context_token_count(root: Path = WIKI_ROOT) -> int:
    """返回当前上下文的 token 数（用于调试）。"""
    return _tokenize(build_context(root=root))
