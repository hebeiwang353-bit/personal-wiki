"""
运行前估算费用，让用户决定是否继续。
"""

import tiktoken

EMBED_PRICE_PER_M = 0.02      # OpenAI text-embedding-3-small, $0.02/M tokens
CLAUDE_INPUT_PRICE_PER_M = 3.0   # Claude Sonnet 4.6, $3/M tokens
CLAUDE_OUTPUT_PRICE_PER_M = 15.0

_enc = None


def _get_enc():
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding("cl100k_base")
    return _enc


def count_tokens(text: str) -> int:
    return len(_get_enc().encode(text, disallowed_special=()))


def estimate(
    extracted_items: list[dict],
    n_claude_samples: int,
    avg_sample_chars: int = 4000,
) -> dict:
    """
    extracted_items: [{"text": str}, ...]
    返回费用明细 dict
    """
    # Embedding 费用：全量文本
    total_embed_tokens = sum(count_tokens(item["text"]) for item in extracted_items)
    embed_cost = total_embed_tokens / 1_000_000 * EMBED_PRICE_PER_M

    # Claude 费用：只分析采样后的文档
    claude_input_tokens = n_claude_samples * (avg_sample_chars // 3)  # 约 3 字/token（中英混合）
    claude_output_tokens = n_claude_samples * 200   # 每批输出约 200 token
    claude_cost = (
        claude_input_tokens / 1_000_000 * CLAUDE_INPUT_PRICE_PER_M
        + claude_output_tokens / 1_000_000 * CLAUDE_OUTPUT_PRICE_PER_M
    )

    return {
        "文件数量": len(extracted_items),
        "Embedding token 数": total_embed_tokens,
        "Embedding 费用($)": round(embed_cost, 3),
        "Claude 分析样本数": n_claude_samples,
        "Claude 输入 token 数": claude_input_tokens,
        "Claude 费用($)": round(claude_cost, 3),
        "总费用($)": round(embed_cost + claude_cost, 3),
        "总费用(人民币)": round((embed_cost + claude_cost) * 7.2, 2),
    }
