"""
首次使用引导流程。
通过 MCP 对话框与用户交互，完成：
  1. 欢迎说明
  2. API Key 配置
  3. 扫描时机选择（立即 / 定时 / 跳过）
  4. 代理配置引导
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

MEMORYOS_HOME = Path.home() / ".memoryos"
ENV_FILE = MEMORYOS_HOME / ".env"
WIKI_ROOT = MEMORYOS_HOME / "wiki"


def needs_onboarding() -> bool:
    """Wiki 不存在或为空 → 需要引导。"""
    if not WIKI_ROOT.exists():
        return True
    md_files = list(WIKI_ROOT.rglob("*.md"))
    if not md_files:
        return True
    me = WIKI_ROOT / "me.md"
    if me.exists():
        content = me.read_text(encoding="utf-8").strip()
        if content == "（待建立）" or len(content) < 20:
            return True
    return False


def run_onboarding_text() -> str:
    """
    返回引导文本，在 MCP 对话中展示给用户。
    这是第一步：欢迎 + 说明。
    后续步骤通过 update_wiki / 用户手动配置完成。
    """
    api_configured = _check_api_key()

    lines = [
        "# 👋 欢迎使用 MemoryOS",
        "",
        "我是你的**本地个人记忆助手**，可以帮你：",
        "- 读取电脑文件，自动建立专属知识库",
        "- 让所有 AI 工具永久认识你",
        "- 每次对话自动带上你的背景，无需重复介绍",
        "",
        "**你的数据完全存储在本地**（`~/.memoryos/`），不上传到任何服务器。",
        "",
        "---",
        "",
    ]

    if not api_configured:
        lines += [
            "## 第一步：配置 API Key",
            "",
            "请在终端运行以下命令配置你的 API Key：",
            "",
            "```bash",
            "# 进入 MemoryOS 目录",
            f"cd {ROOT}",
            "",
            "# 复制配置模板",
            "cp .env.example .env",
            "",
            "# 编辑 .env，填入你的 Key（任选其一）",
            "# ANTHROPIC_API_KEY=sk-ant-xxxx   (推荐，用于 Claude)",
            "# OPENAI_API_KEY=sk-xxxx           (用于 GPT 系列)",
            "# DEEPSEEK_API_KEY=sk-xxxx         (DeepSeek，更便宜)",
            "```",
            "",
            "配置完成后，重新开始对话，我会继续引导你。",
        ]
    else:
        lines += [
            "## API Key ✓ 已配置",
            "",
            "## 第二步：开始扫描文件",
            "",
            "请选择扫描时机，在终端运行对应命令：",
            "",
            "**立即开始（推荐）**",
            "```bash",
            f"cd {ROOT} && source venv/bin/activate",
            "python main.py --max-files 200",
            "```",
            "",
            "**设定定时扫描（例如今晚 22:00）**",
            "```bash",
            f"cd {ROOT} && source venv/bin/activate",
            'python -m memoryos_mcp.scheduler --set "22:00"',
            "```",
            "",
            "扫描完成后，所有 AI 工具将自动认识你 ✨",
            "",
            "---",
            "",
            "## 第三步：配置其他 AI 工具（可选）",
            "",
            "如需让 **QClaw / EasyClaw / Ollama** 等工具也认识你：",
            "把这些工具的 API 地址改为 `http://localhost:8765`",
            "",
            "然后启动代理：",
            "```bash",
            "python proxy/proxy_server.py",
            "```",
        ]

    return "\n".join(lines)


def save_api_key(key: str, provider: str = "anthropic"):
    """把 API Key 写入 ~/.memoryos/.env"""
    MEMORYOS_HOME.mkdir(parents=True, exist_ok=True)
    env_content = ENV_FILE.read_text() if ENV_FILE.exists() else ""

    key_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
    }
    env_var = key_map.get(provider, "ANTHROPIC_API_KEY")

    lines = [l for l in env_content.splitlines() if not l.startswith(env_var)]
    lines.append(f"{env_var}={key}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ENV_FILE.chmod(0o600)


def _check_api_key() -> bool:
    """检查是否已配置任意 API Key。"""
    if ENV_FILE.exists():
        content = ENV_FILE.read_text()
        for key_name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
            for line in content.splitlines():
                if line.startswith(f"{key_name}=") and len(line) > len(key_name) + 5:
                    return True
    for key_name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        if os.environ.get(key_name):
            return True
    return False
