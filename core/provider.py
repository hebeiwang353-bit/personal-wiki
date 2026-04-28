"""
AI Provider 抽象层 —— 统一所有大模型厂商的接入。

支持三种来源：
1. 预设厂商（providers.toml）：用户只填 AI_PROVIDER 和 AI_API_KEY
2. 自定义 OpenAI 兼容服务：用户填 AI_BASE_URL + AI_MODEL + AI_API_KEY
3. 完全自定义：可同时覆盖预设的 model / base_url

环境变量优先级：
  AI_PROVIDER     选定预设（默认 openai）
  AI_API_KEY      API 密钥（必填）
  AI_BASE_URL     覆盖预设的 base_url（可选）
  AI_MODEL        覆盖预设的 default_model（可选）
"""

import os
import sys
import tomllib
from pathlib import Path
from typing import Any

PROVIDERS_FILE = Path(__file__).parent / "providers.toml"


def _load_providers() -> dict[str, dict]:
    """加载预设厂商配置。"""
    if not PROVIDERS_FILE.exists():
        return {}
    with open(PROVIDERS_FILE, "rb") as f:
        return tomllib.load(f)


_PROVIDERS = _load_providers()


def list_providers() -> list[dict]:
    """返回所有可用厂商的简表，给 CLI / Web UI 用。"""
    return [
        {
            "key": k,
            "name": v.get("display_name", k),
            "default_model": v.get("default_model", ""),
            "format": v.get("format", "openai"),
            "note": v.get("note", ""),
        }
        for k, v in _PROVIDERS.items()
    ]


def get_provider_config(provider_key: str | None = None) -> dict:
    """
    返回当前使用的 provider 配置（合并 .env 覆盖）。
    返回字段：base_url, model, format, api_key, key
    """
    key = (provider_key or os.environ.get("AI_PROVIDER") or "openai").lower()

    if key not in _PROVIDERS:
        # 未知 provider 视为 custom
        key = "custom"

    preset = _PROVIDERS[key].copy()

    base_url = os.environ.get("AI_BASE_URL") or preset.get("base_url", "")
    model = os.environ.get("AI_MODEL") or preset.get("default_model", "")
    api_key = os.environ.get("AI_API_KEY", "")

    # 兼容部分早期变量名
    if not api_key:
        api_key = (
            os.environ.get("OPENAI_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("DEEPSEEK_API_KEY")
            or ""
        )

    if not base_url:
        raise ValueError(
            f"Provider '{key}' 的 base_url 为空。"
            f"请在 .env 设置 AI_BASE_URL，或选择已预设的 AI_PROVIDER。"
        )
    if not api_key:
        raise ValueError("缺少 AI_API_KEY，请在 .env 中设置。")
    if not model:
        raise ValueError(
            f"Provider '{key}' 缺少 model。请在 .env 设置 AI_MODEL。"
        )

    return {
        "key": key,
        "base_url": base_url,
        "model": model,
        "format": preset.get("format", "openai"),
        "api_key": api_key,
        "display_name": preset.get("display_name", key),
    }


def get_client():
    """
    返回 (client, model, format) 三元组：
      client: SDK 客户端实例（OpenAI 或 Anthropic）
      model:  模型名
      format: "openai" 或 "anthropic"
    """
    cfg = get_provider_config()

    if cfg["format"] == "anthropic":
        from anthropic import Anthropic
        client = Anthropic(api_key=cfg["api_key"], base_url=cfg["base_url"])
    else:
        # 所有 OpenAI 兼容服务（包括本地 Ollama / LM Studio）
        from openai import OpenAI
        client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])

    return client, cfg["model"], cfg["format"]


def call_chat(prompt: str, max_tokens: int = 2000, system: str | None = None) -> str:
    """
    统一的 chat 调用入口。屏蔽 OpenAI/Anthropic 协议差异。
    返回纯文本回复。
    """
    client, model, fmt = get_client()

    if fmt == "anthropic":
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        resp = client.messages.create(**kwargs)
        return resp.content[0].text if resp.content else ""
    else:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )
        return resp.choices[0].message.content or ""


def get_current_provider_info() -> str:
    """返回当前 provider 的简短描述（用于 CLI 启动时打印）。"""
    try:
        cfg = get_provider_config()
        return f"{cfg['display_name']} · {cfg['model']}"
    except ValueError as e:
        return f"未配置 ({e})"
