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

MEMORYOS_HOME = Path(os.environ.get("MEMORYOS_HOME", Path.home() / ".memoryos"))
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
            "编辑 `~/.memoryos/.env`（Windows：`%USERPROFILE%\\.memoryos\\.env`），填入：",
            "",
            "```",
            "AI_PROVIDER=deepseek    # 或 openai / anthropic / moonshot / qwen 等",
            "AI_API_KEY=sk-xxxxxxxx",
            "```",
            "",
            "支持 16+ 个厂商，完整列表见 `.env.example`。",
            "",
            "配置完成后，重新开始对话，我会继续引导你。",
        ]
    else:
        lines += [
            "## API Key ✓ 已配置",
            "",
            "## 开始扫描文件（运行一次即可）",
            "",
            "**macOS / Linux：**",
            "```bash",
            f"~/.memoryos/venv/bin/python {ROOT}/main.py --max-files 2000 --no-embed --skip-confirm",
            "```",
            "",
            "**Windows（PowerShell）：**",
            "```powershell",
            r'& "$env:USERPROFILE\.memoryos\venv\Scripts\python.exe" '
            + f'"{ROOT}\\main.py" --max-files 2000 --no-embed --skip-confirm',
            "```",
            "",
            "约 2-5 分钟，扫完后所有 AI 工具将自动认识你 ✨",
            "",
            "---",
            "",
            "之后每天 11:00 自动更新记忆库（安装时已设定定时任务）。",
            "如需让更多 AI 工具接入，把它们的 API 地址改为 `http://localhost:8765/v1` 即可。",
        ]

    return "\n".join(lines)


def save_api_key(key: str, provider: str = "deepseek"):
    """把 AI_PROVIDER + AI_API_KEY 写入 ~/.memoryos/.env"""
    MEMORYOS_HOME.mkdir(parents=True, exist_ok=True)
    env_content = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""

    lines = [l for l in env_content.splitlines()
             if not l.startswith("AI_PROVIDER=") and not l.startswith("AI_API_KEY=")]
    lines.append(f"AI_PROVIDER={provider}")
    lines.append(f"AI_API_KEY={key}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        ENV_FILE.chmod(0o600)
    except Exception:
        pass  # Windows 不支持 chmod，忽略


def _check_api_key() -> bool:
    """检查是否已配置 AI_API_KEY（新格式）或任意旧格式 Key。"""
    if ENV_FILE.exists():
        content = ENV_FILE.read_text(encoding="utf-8")
        for line in content.splitlines():
            # 新格式
            if line.startswith("AI_API_KEY=") and len(line) > len("AI_API_KEY=") + 4:
                return True
            # 兼容旧格式
            for old in ("ANTHROPIC_API_KEY=", "OPENAI_API_KEY=", "DEEPSEEK_API_KEY="):
                if line.startswith(old) and len(line) > len(old) + 4:
                    return True
    return bool(os.environ.get("AI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))
