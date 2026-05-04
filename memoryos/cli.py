"""
memoryos CLI — 入口命令
用法：
  memoryos install    一键安装（创建目录、注册 MCP、定时任务、代理自启）
  memoryos scan       立即扫描更新记忆库
  memoryos status     查看当前 Wiki 状态
  memoryos proxy      启动 API 代理（前台）
  memoryos web        启动 Web UI（前台）
  memoryos schedule   查看/修改定时扫描时间
"""

import os
import sys
import platform
import subprocess
import json
import argparse
from pathlib import Path

# ── 基础路径（pip install 后也能正确找到）──────────────────────
# memoryos/cli.py → memoryos/ → 项目根
PKG_DIR  = Path(__file__).parent           # site-packages/memoryos/
ROOT     = PKG_DIR.parent                  # site-packages/  (或开发模式下的项目根)
MEMORYOS_HOME = Path(os.environ.get("MEMORYOS_HOME", Path.home() / ".memoryos"))
WIKI_DIR = MEMORYOS_HOME / "wiki"
ENV_FILE = MEMORYOS_HOME / ".env"
VENV_DIR = MEMORYOS_HOME / "venv"         # bootstrap 安装的 venv（如有）

IS_WIN   = platform.system() == "Windows"
IS_MAC   = platform.system() == "Darwin"
IS_LINUX = platform.system() == "Linux"

GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
CYAN   = "\033[36m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET} {msg}")
def info(msg): print(f"    {msg}")
def step(msg): print(f"\n{CYAN}▶{RESET} {msg}")
def err(msg):  print(f"  {RED}✗{RESET} {msg}")


# ── .env 模板内容（内嵌，避免依赖外部文件）───────────────────────
ENV_TEMPLATE = """\
# ════════════════════════════════════════
# MemoryOS 配置  —  填入你的 API Key
# ════════════════════════════════════════

# 选你正在用的厂商（任选其一）：
#   openai / anthropic / deepseek / dashscope（通义）
#   zhipu（GLM）/ moonshot（Kimi）/ doubao（豆包）
#   ernie（文心）/ gemini / grok / mistral / groq
#   minimax / stepfun / ollama / lmstudio / custom

AI_PROVIDER=deepseek
AI_API_KEY=sk-xxxxxxxxxxxxxxxx

# 可选：指定模型（留空则用厂商默认）
# AI_MODEL=deepseek-chat

# 可选：自定义 OpenAI 兼容服务
# AI_PROVIDER=custom
# AI_BASE_URL=https://your-service.com/v1
# AI_MODEL=your-model
"""

ME_TEMPLATE = """\
# 关于我

## 用户自述

（在这里写下你的核心身份、主要项目、沟通偏好。这一节永远不会被自动覆盖。）

"""

INDEX_TEMPLATE = """\
# Wiki 索引

## 核心页面
- [关于我](me.md)

## 项目

## 兴趣领域

## 工具链
"""


# ══════════════════════════════════════════════════════════════
#  install 命令
# ══════════════════════════════════════════════════════════════

def cmd_install():
    """一键安装：创建目录、写配置、注册 MCP、定时任务、代理自启"""
    print(f"""
{CYAN}╔══════════════════════════════════════╗
║      MemoryOS 安装程序               ║
║  让所有 AI 工具永久认识你            ║
╚══════════════════════════════════════╝{RESET}
平台：{platform.system()} {platform.machine()}
""")

    # 1. 创建目录结构
    step("初始化 Wiki 知识库...")
    for d in [WIKI_DIR, WIKI_DIR/"projects", WIKI_DIR/"interests", WIKI_DIR/"tools"]:
        d.mkdir(parents=True, exist_ok=True)

    if not (WIKI_DIR / "me.md").exists():
        (WIKI_DIR / "me.md").write_text(ME_TEMPLATE, encoding="utf-8")
        (WIKI_DIR / "index.md").write_text(INDEX_TEMPLATE, encoding="utf-8")
        from datetime import datetime
        (WIKI_DIR / "log.md").write_text(
            f"# 操作日志\n\n{datetime.now().strftime('%Y-%m-%d')} 初始化 Wiki\n",
            encoding="utf-8"
        )
    ok(f"Wiki 目录：{WIKI_DIR}")

    # 2. 写 .env 模板
    step("准备配置文件...")
    if not ENV_FILE.exists():
        MEMORYOS_HOME.mkdir(parents=True, exist_ok=True)
        ENV_FILE.write_text(ENV_TEMPLATE, encoding="utf-8")
        if not IS_WIN:
            ENV_FILE.chmod(0o600)
        warn(f"请编辑 {ENV_FILE}，填入 AI_PROVIDER 和 AI_API_KEY")
    else:
        ok(f"配置文件已存在：{ENV_FILE}")

    # 3. 注册代理开机自启
    step("注册代理开机自启...")
    _register_proxy_autostart()

    # 4. 注册 MCP Server（Claude Desktop / Cursor / Windsurf / LM Studio / Cline / Trae）
    step("注册 MCP Server 到 AI 工具...")
    registered = _register_mcp()

    # 5. 自动配置代理类工具（Chatbox / Aider / Zed / Codex / Jan 等）
    step("自动配置其他 AI 工具...")
    print()
    proxy_configured = _configure_proxy_tools()

    # 6. 设定每日 11:00 定时扫描
    step("设定每日 11:00 自动扫描...")
    _register_daily_scan()

    # 7. 交互式设置 API Key + 首次扫描
    _interactive_setup()


def _interactive_setup():
    """交互式引导用户选择厂商、填入 API Key，然后可选立即扫描。"""
    import getpass

    PROVIDERS = [
        # (显示名,              provider key,   提示)
        ("DeepSeek",           "deepseek",     "推荐｜¥0.1/百万 token，速度快"),
        ("通义千问（阿里）",    "dashscope",    "有免费额度"),
        ("Kimi（月之暗面）",    "moonshot",     ""),
        ("豆包（字节跳动）",    "doubao",       ""),
        ("智谱 GLM",           "zhipu",        ""),
        ("OpenAI（GPT-4）",    "openai",       ""),
        ("Anthropic（Claude）","anthropic",    ""),
        ("Gemini（Google）",   "gemini",       ""),
        ("Ollama（本地模型）",  "ollama",       "数据完全不出网，需先装 Ollama"),
        ("其他 OpenAI 兼容服务","custom",      "手动填 AI_BASE_URL"),
    ]

    print(f"""
{CYAN}══════════════════════════════════════════
  设置 API Key（最后一步）
══════════════════════════════════════════{RESET}

  请选择你使用的 AI 服务商：
""")
    for i, (name, _, hint) in enumerate(PROVIDERS, 1):
        hint_str = f"  {YELLOW}←{RESET} {hint}" if hint else ""
        print(f"   {CYAN}{i:2d}.{RESET} {name}{hint_str}")

    print(f"\n   直接按 Enter 跳过（之后手动编辑 {ENV_FILE}）\n")

    # 选择厂商
    while True:
        try:
            raw = input(f"  请输入编号 [1]: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            warn("跳过 API Key 配置，请稍后手动编辑配置文件")
            _print_final_tips()
            return

        if raw == "":
            choice = 1
            break
        if raw.isdigit() and 1 <= int(raw) <= len(PROVIDERS):
            choice = int(raw)
            break
        print(f"  请输入 1-{len(PROVIDERS)} 之间的数字")

    provider_name, provider_key, _ = PROVIDERS[choice - 1]
    print(f"  已选择：{provider_name}\n")

    # 输入 API Key
    if provider_key == "ollama":
        api_key = "ollama"   # ollama 不需要 key
        print(f"  Ollama 无需 API Key，确保 Ollama 服务已在本机运行即可")
    else:
        print(f"  请粘贴 API Key（输入时不显示字符，粘贴后回车）：")
        try:
            api_key = getpass.getpass("  API Key: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            warn("跳过 API Key 配置，请稍后手动编辑配置文件")
            _print_final_tips()
            return

        if not api_key:
            warn("未输入 API Key，跳过配置，请稍后手动编辑配置文件")
            _print_final_tips()
            return

    # 写入 .env
    try:
        MEMORYOS_HOME.mkdir(parents=True, exist_ok=True)
        existing = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ENV_TEMPLATE

        def _replace_line(text, key, value):
            import re
            pattern = rf"^#?\s*{re.escape(key)}\s*=.*$"
            new_line = f"{key}={value}"
            if re.search(pattern, text, re.MULTILINE):
                return re.sub(pattern, new_line, text, flags=re.MULTILINE)
            return text + f"\n{new_line}\n"

        new_env = _replace_line(existing, "AI_PROVIDER", provider_key)
        new_env = _replace_line(new_env,  "AI_API_KEY",  api_key)
        ENV_FILE.write_text(new_env, encoding="utf-8")
        if not IS_WIN:
            ENV_FILE.chmod(0o600)
        ok(f"API Key 已写入 {ENV_FILE}")
    except Exception as e:
        err(f"写入配置失败：{e}")
        _print_final_tips()
        return

    # 询问是否立即扫描
    print(f"""
{CYAN}══════════════════════════════════════════{RESET}
  首次扫描会分析你电脑上的文件和浏览器历史，
  建立个人知识库（约 2-5 分钟，费用约 ¥1-5）。
""")
    try:
        do_scan = input("  现在立即开始首次扫描？(Y/n): ").strip().lower()
    except (KeyboardInterrupt, EOFError):
        do_scan = "n"
        print()

    if do_scan in ("", "y", "yes"):
        print()
        ok("开始首次扫描...")
        cmd_scan()
    else:
        warn("已跳过，稍后运行：memoryos scan")

    _print_final_tips()


def _print_final_tips():
    """打印安装完成的最终提示。"""
    print(f"""
{GREEN}╔══════════════════════════════════════════╗
║         MemoryOS 安装完成！               ║
╚══════════════════════════════════════╝{RESET}

{YELLOW}常用命令：{RESET}
  memoryos scan       立即扫描，更新记忆库
  memoryos status     查看 Wiki 状态
  memoryos web        打开 Web UI（http://localhost:8766）

{YELLOW}之后无需任何操作：{RESET}
  · 每天 11:00 自动扫描更新记忆库
  · 代理服务开机自动启动（localhost:8765）
""")


def _python_exe() -> str:
    """找到当前环境的 Python 可执行文件路径（跨平台）。"""
    return sys.executable or ("python.exe" if IS_WIN else "python3")


def _memoryos_script(name: str) -> str:
    """找到 memoryos-xxx console_script 的绝对路径（pip install 后在 Scripts/bin 目录）。"""
    scripts_dir = Path(sys.executable).parent
    exe_name = f"{name}.exe" if IS_WIN else name
    script_path = scripts_dir / exe_name
    if script_path.exists():
        return str(script_path)
    return name   # 回退：PATH 里找


def _register_proxy_autostart():
    """注册代理服务为开机自启（macOS LaunchAgent / Linux systemd / Windows Task Scheduler）"""
    python = _python_exe()
    proxy_module = "proxy.proxy_server"   # python -m proxy.proxy_server

    if IS_MAC:
        plist_path = Path.home() / "Library/LaunchAgents/com.memoryos.proxy.plist"
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.memoryos.proxy</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>-m</string>
        <string>{proxy_module}</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>MEMORYOS_HOME</key><string>{MEMORYOS_HOME}</string>
        <key>PYTHONPATH</key><string>{ROOT}</string>
    </dict>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>StandardOutPath</key><string>{MEMORYOS_HOME}/proxy.log</string>
    <key>StandardErrorPath</key><string>{MEMORYOS_HOME}/proxy_error.log</string>
</dict>
</plist>"""
        plist_path.write_text(plist_content, encoding="utf-8")
        subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
        r = subprocess.run(["launchctl", "load",   str(plist_path)], capture_output=True)
        if r.returncode == 0:
            ok("代理已注册为 macOS LaunchAgent（开机自启）")
        else:
            warn("LaunchAgent 注册失败，请手动运行：memoryos proxy")

    elif IS_LINUX:
        service_dir = Path.home() / ".config/systemd/user"
        service_dir.mkdir(parents=True, exist_ok=True)
        service_file = service_dir / "memoryos-proxy.service"
        service_file.write_text(f"""[Unit]
Description=MemoryOS Proxy
After=network.target

[Service]
ExecStart={python} -m {proxy_module}
Environment=MEMORYOS_HOME={MEMORYOS_HOME}
Environment=PYTHONPATH={ROOT}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
""", encoding="utf-8")
        for cmd in [
            ["systemctl", "--user", "daemon-reload"],
            ["systemctl", "--user", "enable", "memoryos-proxy"],
            ["systemctl", "--user", "start",  "memoryos-proxy"],
        ]:
            subprocess.run(cmd, capture_output=True)
        ok("代理已注册为 systemd 用户服务（开机自启）")

    elif IS_WIN:
        bat_path = MEMORYOS_HOME / "start_proxy.bat"
        bat_path.write_text(
            f"@echo off\r\nset MEMORYOS_HOME={MEMORYOS_HOME}\r\nset PYTHONPATH={ROOT}\r\n"
            f'"{python}" -m {proxy_module}\r\n',
            encoding="ascii"
        )
        r = subprocess.run(
            ["schtasks", "/Create", "/F",
             "/TN", "MemoryOS_Proxy",
             "/TR", f'cmd.exe /c "{bat_path}"',
             "/SC", "ONLOGON",
             "/RL", "HIGHEST"],
            capture_output=True, text=True
        )
        if r.returncode == 0:
            subprocess.run(["schtasks", "/Run", "/TN", "MemoryOS_Proxy"], capture_output=True)
            ok("代理已注册为 Windows 开机任务并立即启动")
        else:
            warn("Task Scheduler 注册失败（可能需要管理员权限），请手动运行：memoryos proxy")


def _mcp_entry() -> dict:
    """标准 MCP Server 配置条目。"""
    return {
        "command": _python_exe(),
        "args":    ["-m", "memoryos_mcp.mcp_server"],
        "env":     {"MEMORYOS_HOME": str(MEMORYOS_HOME), "PYTHONPATH": str(ROOT)},
    }


def _read_api_key() -> str:
    """从 .env 读取用户已配置的 API Key。"""
    try:
        if ENV_FILE.exists():
            for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
                if line.startswith("AI_API_KEY=") and "xxxxxxx" not in line:
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


def _patch_json(path: Path, patcher, create_if_missing: bool = False) -> bool:
    """读取 JSON → patcher(cfg) → 写回。path 不存在且 create_if_missing=True 时用 {}。"""
    try:
        if not path.exists():
            if not create_if_missing or not path.parent.exists():
                return False
            cfg = {}
        else:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        patcher(cfg)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception:
        return False


def _register_mcp() -> int:
    """向所有支持 MCP 的工具注入 memoryos server，返回成功注册数。

    支持工具：
      Claude Desktop · Claude Code (.claude.json)
      Cursor · Windsurf · LM Studio
      Cline (VS Code) · Roo-Cline (VS Code)
      Trae (ByteDance)
    """
    entry = _mcp_entry()
    appdata = os.environ.get("APPDATA", "")
    home    = Path.home()

    if IS_WIN:
        candidates = [
            Path(appdata) / "Claude/claude_desktop_config.json",
            home / ".claude.json",
            home / ".cursor/mcp.json",
            Path(appdata) / "Cursor/mcp.json",
            # Windsurf
            home / ".codeium/windsurf/mcp_config.json",
            # LM Studio
            home / ".lmstudio/mcp.json",
            # Cline
            Path(appdata) / "Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
            Path(appdata) / "Code/User/globalStorage/rooveterinaryinc.roo-cline/settings/cline_mcp_settings.json",
            # Trae
            Path(appdata) / "Trae/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
        ]
    else:
        candidates = [
            # Claude Desktop
            home / "Library/Application Support/Claude/claude_desktop_config.json",
            home / ".config/Claude/claude_desktop_config.json",
            # Claude Code
            home / ".claude.json",
            # Cursor
            home / ".cursor/mcp.json",
            # Windsurf
            home / ".codeium/windsurf/mcp_config.json",
            # LM Studio
            home / ".lmstudio/mcp.json",
            # Cline (VS Code)
            home / "Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
            home / "Library/Application Support/Code/User/globalStorage/rooveterinaryinc.roo-cline/settings/cline_mcp_settings.json",
            home / ".config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
            # Trae (ByteDance IDE)
            home / "Library/Application Support/Trae/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
            home / "Library/Application Support/Trae User/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json",
        ]

    count = 0
    seen_tools: set[str] = set()

    for cfg_path in candidates:
        if not cfg_path.exists():
            continue
        # 工具名（用父目录推断）
        tool = _guess_tool_from_path(cfg_path)
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg.setdefault("mcpServers", {})["memoryos"] = entry
            cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
            if tool not in seen_tools:
                ok(f"MCP → {tool}")
                seen_tools.add(tool)
            count += 1
        except Exception as e:
            warn(f"MCP 注册失败 ({tool})：{e}")
    return count


def _guess_tool_from_path(p: Path) -> str:
    """从配置文件路径猜测工具名称。"""
    s = str(p).lower()
    for kw, name in [
        ("windsurf", "Windsurf"), ("lmstudio", "LM Studio"),
        ("cursor",   "Cursor"),   ("claude",   "Claude Desktop"),
        ("trae",     "Trae"),     ("roo-cline","Roo-Cline"),
        ("cline",    "Cline"),
    ]:
        if kw in s:
            return name
    return p.parent.name


# ══════════════════════════════════════════════════════════════
#  代理类工具自动配置
# ══════════════════════════════════════════════════════════════

def _configure_proxy_tools() -> list[str]:
    """
    自动配置所有支持自定义 API 地址的桌面工具。
    在各工具配置文件中添加「MemoryOS」渠道，指向 localhost:8765。
    返回成功配置的工具名列表。
    """
    configured: list[str] = []
    api_key = _read_api_key()
    home    = Path.home()
    appdata = os.environ.get("APPDATA", "")

    # ── Chatbox ─────────────────────────────────────────────────
    chatbox_paths = (
        [home / "Library/Application Support/xyz.chatboxapp.app/config.json"] if IS_MAC else
        [Path(appdata) / "xyz.chatboxapp.app/config.json"] if IS_WIN else
        [home / ".config/chatbox/config.json"]
    )
    for p in chatbox_paths:
        def _patch_chatbox(cfg, _k=api_key):
            cfg.setdefault("settings", {}).setdefault("providers", {})["memoryos"] = {
                "id":     "memoryos",
                "name":   "MemoryOS",
                "apiKey": _k,
                "apiHost": "http://localhost:8765",
                "models": [
                    {"id": "deepseek-chat",               "name": "MemoryOS · DeepSeek"},
                    {"id": "gpt-4o",                      "name": "MemoryOS · GPT-4o"},
                    {"id": "claude-sonnet-4-5-20251001",  "name": "MemoryOS · Claude"},
                    {"id": "qwen-plus",                   "name": "MemoryOS · 通义"},
                    {"id": "moonshot-v1-8k",              "name": "MemoryOS · Kimi"},
                ],
            }
        if _patch_json(p, _patch_chatbox):
            ok("代理 → Chatbox（重启 Chatbox 后在渠道列表选择「MemoryOS」）")
            configured.append("Chatbox")
            break

    # ── LobeChat Desktop ────────────────────────────────────────
    lobechat_paths = (
        [home / "Library/Application Support/LobeChat/config.json",
         home / "Library/Application Support/LobeChat/settings.json"] if IS_MAC else
        [Path(appdata) / "LobeChat/config.json"] if IS_WIN else
        [home / ".config/LobeChat/config.json"]
    )
    for p in lobechat_paths:
        def _patch_lobe(cfg, _k=api_key):
            cfg.setdefault("languageModel", {}).setdefault("openai", {}).update({
                "apiKey":  _k,
                "baseURL": "http://localhost:8765/v1",
            })
        if _patch_json(p, _patch_lobe):
            ok("代理 → LobeChat")
            configured.append("LobeChat")
            break

    # ── Jan ─────────────────────────────────────────────────────
    # Jan 用 ~/jan/engines/openai/engines.json 存远程 API 地址
    jan_dirs = [home / "jan", home / "Library/Application Support/Jan/data"]
    for jan_dir in jan_dirs:
        if not jan_dir.exists():
            continue
        engine_dir  = jan_dir / "engines" / "memoryos"
        engine_file = engine_dir / "engines.json"
        engine_dir.mkdir(parents=True, exist_ok=True)
        engine_file.write_text(json.dumps({
            "full_url": "http://localhost:8765/v1/chat/completions",
            "api_key":  api_key or "memoryos",
        }, indent=2), encoding="utf-8")
        # 写一个示例模型文件
        model_dir = jan_dir / "models" / "memoryos-deepseek"
        model_dir.mkdir(parents=True, exist_ok=True)
        (model_dir / "model.json").write_text(json.dumps({
            "id":       "memoryos-deepseek",
            "object":   "model",
            "name":     "MemoryOS (DeepSeek)",
            "version":  "1.0",
            "format":   "api",
            "engine":   "memoryos",
            "parameters": {"stream": True, "max_tokens": 4096, "temperature": 0.7},
        }, indent=2), encoding="utf-8")
        ok("代理 → Jan（在模型列表选择「MemoryOS (DeepSeek)」）")
        configured.append("Jan")
        break

    # ── Aider ───────────────────────────────────────────────────
    aider_conf = home / ".aider.conf.yml"
    try:
        import yaml as _yaml
        existing = {}
        if aider_conf.exists():
            existing = _yaml.safe_load(aider_conf.read_text(encoding="utf-8")) or {}
        existing["openai-api-base"] = "http://localhost:8765/v1"
        if api_key:
            existing["openai-api-key"] = api_key
        aider_conf.write_text(_yaml.dump(existing, allow_unicode=True), encoding="utf-8")
        ok("代理 → Aider")
        configured.append("Aider")
    except ImportError:
        # yaml 不可用时手动写
        try:
            lines = []
            if aider_conf.exists():
                lines = [l for l in aider_conf.read_text().splitlines()
                         if not l.startswith("openai-api-base:") and not l.startswith("openai-api-key:")]
            lines.append(f"openai-api-base: http://localhost:8765/v1")
            if api_key:
                lines.append(f"openai-api-key: {api_key}")
            aider_conf.write_text("\n".join(lines) + "\n", encoding="utf-8")
            ok("代理 → Aider")
            configured.append("Aider")
        except Exception:
            pass
    except Exception:
        pass

    # ── Zed Editor ──────────────────────────────────────────────
    zed_cfg = home / ".config/zed/settings.json"
    if IS_MAC:
        zed_cfg = home / "Library/Application Support/Zed/settings.json"

    def _patch_zed(cfg, _k=api_key):
        lm = cfg.setdefault("language_models", {})
        lm.setdefault("openai", {}).update({
            "api_url": "http://localhost:8765/v1",
            "available_models": [
                {"name": "deepseek-chat",  "max_tokens": 8192, "display_name": "MemoryOS · DeepSeek"},
                {"name": "gpt-4o",         "max_tokens": 8192, "display_name": "MemoryOS · GPT-4o"},
                {"name": "qwen-plus",      "max_tokens": 8192, "display_name": "MemoryOS · 通义"},
            ],
        })
    if _patch_json(zed_cfg, _patch_zed):
        ok("代理 → Zed Editor")
        configured.append("Zed")

    # ── Codex CLI ────────────────────────────────────────────────
    codex_cfg = home / ".codex/config.json"
    def _patch_codex(cfg, _k=api_key):
        cfg["apiBaseUrl"] = "http://localhost:8765/v1"
        if _k:
            cfg["apiKey"] = _k
    if _patch_json(codex_cfg, _patch_codex, create_if_missing=True):
        ok("代理 → Codex CLI")
        configured.append("Codex CLI")

    # ── Continue.dev ─────────────────────────────────────────────
    continue_cfg = home / ".continue/config.json"
    def _patch_continue(cfg, _k=api_key):
        models = cfg.setdefault("models", [])
        if not any(m.get("title") == "MemoryOS" for m in models):
            models.insert(0, {
                "title":       "MemoryOS",
                "provider":    "openai",
                "model":       "deepseek-chat",
                "apiBase":     "http://localhost:8765/v1",
                "apiKey":      _k or "memoryos",
            })
    if _patch_json(continue_cfg, _patch_continue):
        ok("代理 → Continue.dev")
        configured.append("Continue.dev")

    # ── Trae（VS Code fork，额外代理配置）───────────────────────
    trae_settings_paths = (
        [home / "Library/Application Support/Trae/User/settings.json",
         home / "Library/Application Support/Trae User/User/settings.json"] if IS_MAC else
        [Path(appdata) / "Trae/User/settings.json"] if IS_WIN else
        [home / ".config/Trae/User/settings.json"]
    )
    for p in trae_settings_paths:
        def _patch_trae(cfg, _k=api_key):
            cfg.setdefault("trae.ai.customModels", [])
            models = cfg["trae.ai.customModels"]
            if not any(m.get("name") == "MemoryOS" for m in models):
                models.insert(0, {
                    "name":    "MemoryOS",
                    "baseUrl": "http://localhost:8765/v1",
                    "apiKey":  _k or "memoryos",
                    "model":   "deepseek-chat",
                })
        if _patch_json(p, _patch_trae):
            ok("代理 → Trae")
            configured.append("Trae")
            break

    # ── AnythingLLM ──────────────────────────────────────────────
    allm_env_paths = (
        [home / "Library/Application Support/anythingllm-desktop/.env",
         home / "Library/Application Support/anythingllm-desktop/storage/.env"] if IS_MAC else
        [Path(appdata) / "anythingllm-desktop/.env"] if IS_WIN else
        [home / ".config/anythingllm-desktop/.env"]
    )
    for p in allm_env_paths:
        if p.exists():
            try:
                lines = [l for l in p.read_text(encoding="utf-8").splitlines()
                         if not l.startswith("OPEN_AI_API_BASE=")]
                lines.append(f"OPEN_AI_API_BASE=http://localhost:8765/v1")
                p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                ok("代理 → AnythingLLM")
                configured.append("AnythingLLM")
            except Exception:
                pass
            break

    # ── BoltAI (macOS) ───────────────────────────────────────────
    boltai_cfg = home / "Library/Application Support/BoltAI/settings.json"
    def _patch_boltai(cfg, _k=api_key):
        cfg.setdefault("providers", {})["memoryos"] = {
            "name":    "MemoryOS",
            "baseURL": "http://localhost:8765/v1",
            "apiKey":  _k or "memoryos",
        }
    if IS_MAC and _patch_json(boltai_cfg, _patch_boltai):
        ok("代理 → BoltAI")
        configured.append("BoltAI")

    # ── GPT4All ──────────────────────────────────────────────────
    gpt4all_paths = (
        [home / "Library/Application Support/nomic.ai/GPT4All/settings.json"] if IS_MAC else
        [Path(appdata) / "nomic.ai/GPT4All/settings.json"] if IS_WIN else
        [home / ".config/nomic.ai/GPT4All/settings.json"]
    )
    for p in gpt4all_paths:
        def _patch_gpt4all(cfg, _k=api_key):
            cfg["networkGPT4AllUrl"] = "http://localhost:8765/v1"
        if _patch_json(p, _patch_gpt4all):
            ok("代理 → GPT4All")
            configured.append("GPT4All")
            break

    # ══════════════════════════════════════════════════════════════
    #  第三批：长尾工具
    # ══════════════════════════════════════════════════════════════

    # ── PyGPT ────────────────────────────────────────────────────
    pygpt_cfg = home / ".config/pygpt-net/config.json"
    def _patch_pygpt(cfg, _k=api_key):
        cfg.setdefault("api", {}).setdefault("openai", {}).update({
            "api_endpoint": "http://localhost:8765/v1",
            "api_key":      _k or "memoryos",
        })
    if _patch_json(pygpt_cfg, _patch_pygpt):
        ok("代理 → PyGPT")
        configured.append("PyGPT")

    # ── Pot 翻译 ─────────────────────────────────────────────────
    pot_paths = (
        [home / "Library/Application Support/pot/config.json"] if IS_MAC else
        [Path(appdata) / "pot/config.json"] if IS_WIN else
        [home / ".config/pot/config.json"]
    )
    for p in pot_paths:
        def _patch_pot(cfg, _k=api_key):
            cfg.setdefault("translators", {}).setdefault("openai", {}).update({
                "url":     "http://localhost:8765/v1",
                "api_key": _k or "memoryos",
            })
            cfg["custom_openai_url"] = "http://localhost:8765/v1"
            if _k:
                cfg["custom_openai_key"] = _k
        if _patch_json(p, _patch_pot):
            ok("代理 → Pot 翻译")
            configured.append("Pot")
            break

    # ── Bob 翻译（macOS）─────────────────────────────────────────
    bob_cfg = home / "Library/Application Support/bob/configuration.json"
    def _patch_bob(cfg, _k=api_key):
        services = cfg.setdefault("services", [])
        if not any(s.get("identifier") == "memoryos-openai" for s in services):
            services.append({
                "identifier": "memoryos-openai",
                "name":       "MemoryOS",
                "type":       "openai",
                "config": {
                    "apiKey":  _k or "memoryos",
                    "baseURL": "http://localhost:8765/v1",
                    "model":   "deepseek-chat",
                },
            })
    if IS_MAC and _patch_json(bob_cfg, _patch_bob):
        ok("代理 → Bob 翻译")
        configured.append("Bob")

    # ── SiYuan Note ──────────────────────────────────────────────
    siyuan_paths = [
        home / "SiYuan/conf/conf.json",
        home / "Documents/SiYuan/conf/conf.json",
    ]
    for p in siyuan_paths:
        def _patch_siyuan(cfg, _k=api_key):
            cfg.setdefault("ai", {}).setdefault("openAI", {}).update({
                "apiBaseURL": "http://localhost:8765/v1",
                "apiKey":     _k or "memoryos",
            })
        if _patch_json(p, _patch_siyuan):
            ok("代理 → SiYuan Note")
            configured.append("SiYuan")
            break

    # ── Faraday.dev ──────────────────────────────────────────────
    faraday_paths = (
        [home / "Library/Application Support/Faraday/settings.json"] if IS_MAC else
        [Path(appdata) / "Faraday/settings.json"] if IS_WIN else
        [home / ".config/Faraday/settings.json"]
    )
    for p in faraday_paths:
        def _patch_faraday(cfg, _k=api_key):
            cfg.setdefault("providers", {})["memoryos"] = {
                "name":    "MemoryOS",
                "baseURL": "http://localhost:8765/v1",
                "apiKey":  _k or "memoryos",
                "type":    "openai-compatible",
            }
        if _patch_json(p, _patch_faraday):
            ok("代理 → Faraday.dev")
            configured.append("Faraday")
            break

    # ── Macaify（macOS）──────────────────────────────────────────
    macaify_cfg = home / "Library/Application Support/Macaify/config.json"
    def _patch_macaify(cfg, _k=api_key):
        cfg.setdefault("ai", {}).update({
            "baseURL": "http://localhost:8765/v1",
            "apiKey":  _k or "memoryos",
        })
    if IS_MAC and _patch_json(macaify_cfg, _patch_macaify):
        ok("代理 → Macaify")
        configured.append("Macaify")

    # ── Witsy（macOS AI 助手）────────────────────────────────────
    witsy_paths = [
        home / "Library/Application Support/Witsy/settings.json",
        home / "Library/Application Support/com.nbonamy.witsy/settings.json",
    ]
    for p in witsy_paths:
        def _patch_witsy(cfg, _k=api_key):
            cfg.setdefault("engines", {}).setdefault("openai", {}).update({
                "apiKey":  _k or "memoryos",
                "baseURL": "http://localhost:8765/v1",
            })
        if _patch_json(p, _patch_witsy):
            ok("代理 → Witsy")
            configured.append("Witsy")
            break

    # ── Enchanted（macOS Ollama UI）──────────────────────────────
    enchanted_paths = [
        home / "Library/Application Support/Enchanted/settings.json",
        home / "Library/Group Containers/group.com.biggie.enchanted/settings.json",
    ]
    for p in enchanted_paths:
        def _patch_enchanted(cfg, _k=api_key):
            cfg["ollamaUri"] = "http://localhost:8765"
        if _patch_json(p, _patch_enchanted):
            ok("代理 → Enchanted")
            configured.append("Enchanted")
            break

    # ── n8n Desktop ──────────────────────────────────────────────
    n8n_cfg = home / ".n8n/config"
    def _patch_n8n(cfg, _k=api_key):
        cfg.setdefault("nodes", {}).setdefault("openai", {}).update({
            "baseURL": "http://localhost:8765/v1",
        })
    if _patch_json(n8n_cfg, _patch_n8n):
        ok("代理 → n8n")
        configured.append("n8n")

    # ── AutoGen Studio ───────────────────────────────────────────
    autogen_paths = [
        home / ".autogen/settings.json",
        home / ".autogen/config.json",
    ]
    for p in autogen_paths:
        def _patch_autogen(cfg, _k=api_key):
            models = cfg.setdefault("models", [])
            if not any(m.get("model_name") == "memoryos" for m in models):
                models.append({
                    "model_name": "memoryos",
                    "model_type": "OpenAIChatCompletionClient",
                    "base_url":   "http://localhost:8765/v1",
                    "api_key":    _k or "memoryos",
                })
        if _patch_json(p, _patch_autogen):
            ok("代理 → AutoGen Studio")
            configured.append("AutoGen Studio")
            break

    # ── LibreChat（本地部署）─────────────────────────────────────
    librechat_paths = [
        home / "LibreChat/.env",
        Path("/opt/LibreChat/.env"),
        Path.cwd() / "LibreChat/.env",
    ]
    for p in librechat_paths:
        if p.exists():
            try:
                lines = [l for l in p.read_text(encoding="utf-8").splitlines()
                         if not l.startswith("OPENAI_REVERSE_PROXY=")]
                lines.append("OPENAI_REVERSE_PROXY=http://localhost:8765/v1")
                p.write_text("\n".join(lines) + "\n", encoding="utf-8")
                ok("代理 → LibreChat")
                configured.append("LibreChat")
            except Exception:
                pass
            break

    # ── Obsidian（Smart Connections 插件）────────────────────────
    # Obsidian vault 路径不固定，尝试常见位置
    obsidian_vaults: list[Path] = []
    for candidate in [
        home / "Documents", home / "Obsidian", home / "Library/Mobile Documents/iCloud~md~obsidian/Documents",
    ]:
        if candidate.exists():
            obsidian_vaults += [p.parent for p in candidate.rglob(".obsidian/plugins/smart-connections/data.json")]

    for vault_obsidian in obsidian_vaults[:3]:   # 最多处理3个 vault
        plugin_cfg = vault_obsidian / "data.json"
        def _patch_obsidian(cfg, _k=api_key):
            cfg.setdefault("api_key", _k or "memoryos")
            cfg["chat_model_config"] = cfg.get("chat_model_config", {})
            cfg["chat_model_config"].update({
                "model_endpoint": "http://localhost:8765/v1/chat/completions",
                "api_key":        _k or "memoryos",
            })
        if _patch_json(plugin_cfg, _patch_obsidian):
            ok(f"代理 → Obsidian Smart Connections ({vault_obsidian.parent.name})")
            if "Obsidian" not in configured:
                configured.append("Obsidian")

    # ── Raycast AI（macOS）───────────────────────────────────────
    # Raycast 的 AI 插件配置存在 ~/Library/Application Support/com.raycast.macos/extensions/
    raycast_ai_cfg = home / "Library/Application Support/com.raycast.macos/extensions/raycast.ai/preferences.json"
    def _patch_raycast(cfg, _k=api_key):
        cfg.setdefault("openAIAPIKey",  _k or "memoryos")
        cfg["openAIAPIEndpoint"] = "http://localhost:8765/v1"
    if IS_MAC and _patch_json(raycast_ai_cfg, _patch_raycast):
        ok("代理 → Raycast AI")
        configured.append("Raycast")

    # ── 打印需要手动配置的工具说明 ──────────────────────────────
    _print_manual_instructions(configured)

    return configured


def _print_manual_instructions(configured: list[str]):
    """对无法自动配置的工具，打印一次性手动操作说明。"""
    home    = Path.home()
    appdata = os.environ.get("APPDATA", "")
    manual  = []

    _MANUAL_TOOLS = [
        # (工具名, 检测路径列表, 操作说明)
        ("Cherry Studio",
         [home / "Library/Application Support/CherryStudio",
          Path(appdata) / "CherryStudio"],
         "设置 → 模型服务 → 添加 → 选「OpenAI兼容」→ URL 填 http://localhost:8765/v1"),

        ("QClaw / OpenClaw",
         [home / "Library/Application Support/QClaw",
          Path(appdata) / "QClaw"],
         "设置 → API 配置 → 自定义 Base URL → http://localhost:8765/v1"),

        ("OpenCat",
         [home / "Library/Containers/app.opencat.desktop"],
         "设置 → API → Custom API Endpoint → http://localhost:8765/v1"),

        ("Msty",
         [home / "Library/Application Support/MstyStudio",
          Path(appdata) / "MstyStudio"],
         "设置 → AI Providers → Add Provider → Base URL: http://localhost:8765/v1"),

        ("Poe Desktop",
         [home / "Library/Application Support/Poe",
          Path(appdata) / "Poe"],
         "Bot 设置 → Server URL → http://localhost:8765/v1（仅自建 Bot 支持）"),

        ("TypingMind",
         [home / "Library/Application Support/TypingMind"],
         "设置 → AI Backend → Custom Endpoint → http://localhost:8765/v1"),
    ]

    for tool, paths, instruction in _MANUAL_TOOLS:
        if tool in configured:
            continue
        if any(Path(p).exists() for p in paths):
            manual.append((tool, instruction))

    if manual:
        print(f"\n  {YELLOW}以下工具需一次性手动操作（约30秒）：{RESET}")
        for tool, instruction in manual:
            print(f"  {CYAN}○{RESET} {tool}")
            print(f"      {instruction}")
        print()


def _register_daily_scan():
    """设定每日 11:00 自动扫描。"""
    python = _python_exe()
    scan_args = [python, "-m", "__main__", "--max-files", "2000", "--no-embed", "--skip-confirm"]
    # 调用 scheduler 模块
    try:
        sys.path.insert(0, str(ROOT))
        from memoryos_mcp.scheduler import set_schedule
        if set_schedule("11:00"):
            ok("每日 11:00 自动扫描已设定")
            return
    except Exception as e:
        pass
    warn("定时扫描注册失败，请手动运行：memoryos schedule --set 11:00")


def _detect_tools(already_registered: int):
    """检测本机已安装的 AI 工具，给出针对性提示。"""
    proxy_url = "http://localhost:8765/v1"

    def found(app_paths):
        return any(Path(p).exists() for p in app_paths if p)

    if IS_MAC:
        checks = {
            "Claude Code":    ["/usr/local/bin/claude", "/opt/homebrew/bin/claude"],
            "Claude Desktop": ["/Applications/Claude.app"],
            "Cursor":         ["/Applications/Cursor.app", str(Path.home() / ".cursor")],
            "Cherry Studio":  ["/Applications/Cherry Studio.app"],
            "Chatbox":        ["/Applications/Chatbox.app"],
            "OpenClaw":       ["/Applications/OpenClaw.app"],
            "QClaw":          ["/Applications/QClaw.app"],
        }
    elif IS_WIN:
        appdata = os.environ.get("APPDATA", "")
        localappdata = os.environ.get("LOCALAPPDATA", "")
        checks = {
            "Claude Desktop": [f"{appdata}\\Claude"],
            "Cursor":         [f"{localappdata}\\Programs\\cursor", str(Path.home() / ".cursor")],
            "Cherry Studio":  [f"{localappdata}\\Programs\\Cherry Studio", f"{appdata}\\Cherry Studio"],
            "Chatbox":        [f"{appdata}\\Chatbox"],
            "OpenClaw":       [f"{appdata}\\OpenClaw"],
        }
    else:
        checks = {
            "Claude Desktop": [str(Path.home() / ".config/Claude")],
            "Cursor":         [str(Path.home() / ".cursor")],
        }

    mcp_tools  = {"Claude Code", "Claude Desktop", "Cursor", "Continue.dev"}
    proxy_tools = {"Cherry Studio", "Chatbox", "OpenClaw", "QClaw", "Hermes"}

    for tool, paths in checks.items():
        if not found(paths):
            continue
        if tool in mcp_tools:
            if already_registered > 0:
                ok(f"{tool} — MCP 已自动注册，重启后生效")
            else:
                warn(f"{tool} — 请手动在 mcpServers 配置中添加 memoryos")
        elif tool in proxy_tools:
            print(f"  {YELLOW}○{RESET} {tool} — 设置 → API地址 → 改为：{proxy_url}")


# ══════════════════════════════════════════════════════════════
#  scan 命令
# ══════════════════════════════════════════════════════════════

def cmd_scan(max_files: int = 2000):
    """立即扫描文件，更新记忆库。"""
    from dotenv import load_dotenv
    load_dotenv(ENV_FILE)

    env_text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    if not ENV_FILE.exists() or "sk-xxxxxxxxxxxxxxxx" in env_text or "AI_API_KEY=sk-xxx" in env_text:
        err("请先配置 API Key：编辑 " + str(ENV_FILE))
        sys.exit(1)

    print(f"开始扫描（最多 {max_files} 个文件）...")
    env = os.environ.copy()
    env["MEMORYOS_HOME"] = str(MEMORYOS_HOME)
    env["PYTHONPATH"] = str(ROOT)

    # main.py 的位置（pip install 后在 ROOT/main.py）
    main_py = ROOT / "main.py"
    if not main_py.exists():
        err(f"找不到 main.py（{main_py}），可能是安装不完整")
        sys.exit(1)

    subprocess.run(
        [sys.executable, str(main_py),
         "--max-files", str(max_files), "--no-embed", "--skip-confirm"],
        env=env,
        cwd=str(ROOT),
    )


# ══════════════════════════════════════════════════════════════
#  status 命令
# ══════════════════════════════════════════════════════════════

def cmd_status():
    """显示 Wiki 状态和上下文 Token 数。"""
    sys.path.insert(0, str(ROOT))
    from wiki.wiki_manager  import list_pages, recent_logs, WIKI_ROOT
    from wiki.context_builder import context_token_count
    from memoryos_mcp.scheduler import get_status

    pages = list_pages()
    tokens = context_token_count()
    sched  = get_status()
    logs   = recent_logs(5)

    print(f"""
{CYAN}MemoryOS 状态{RESET}
  Wiki 位置：{WIKI_ROOT}
  页面数量：{len(pages)}
  上下文 Token：{tokens}
  定时扫描：{sched}

最近日志：
{logs}
""")


# ══════════════════════════════════════════════════════════════
#  proxy 命令
# ══════════════════════════════════════════════════════════════

def cmd_proxy():
    """在前台启动 API 代理（localhost:8765）。"""
    sys.path.insert(0, str(ROOT))
    from dotenv import load_dotenv
    load_dotenv(ENV_FILE)
    import uvicorn
    from proxy.proxy_server import app
    print(f"MemoryOS 代理启动 → http://localhost:8765")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")


# ══════════════════════════════════════════════════════════════
#  web 命令
# ══════════════════════════════════════════════════════════════

def cmd_web():
    """在前台启动 Web UI（localhost:8766）。"""
    sys.path.insert(0, str(ROOT))
    import uvicorn
    from web.server import app
    print(f"MemoryOS Web UI 启动 → http://localhost:8766")
    uvicorn.run(app, host="127.0.0.1", port=8766, log_level="warning")


# ══════════════════════════════════════════════════════════════
#  schedule 命令
# ══════════════════════════════════════════════════════════════

def cmd_schedule(set_time: str | None, remove: bool, status: bool):
    """管理定时扫描任务。"""
    sys.path.insert(0, str(ROOT))
    from memoryos_mcp.scheduler import set_schedule, get_status, remove_schedule

    if set_time:
        set_schedule(set_time)
    elif remove:
        remove_schedule()
    else:
        print(get_status())


# ══════════════════════════════════════════════════════════════
#  CLI 入口
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        prog="memoryos",
        description="MemoryOS — 让所有 AI 工具永久认识你"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("install",  help="一键安装（首次使用）")

    p_scan = sub.add_parser("scan", help="立即扫描文件，更新记忆库")
    p_scan.add_argument("--max-files", type=int, default=2000, help="最多扫描文件数")

    sub.add_parser("status",  help="查看 Wiki 状态")
    sub.add_parser("proxy",   help="启动 API 代理（前台，localhost:8765）")
    sub.add_parser("web",     help="启动 Web UI（前台，localhost:8766）")

    p_sched = sub.add_parser("schedule", help="管理定时扫描")
    p_sched.add_argument("--set",    metavar="HH:MM", help='设定时间，如 "11:00"')
    p_sched.add_argument("--remove", action="store_true", help="移除定时任务")
    p_sched.add_argument("--status", action="store_true", help="查看状态")

    args = parser.parse_args()

    if args.cmd == "install":
        cmd_install()
    elif args.cmd == "scan":
        cmd_scan(args.max_files)
    elif args.cmd == "status":
        cmd_status()
    elif args.cmd == "proxy":
        cmd_proxy()
    elif args.cmd == "web":
        cmd_web()
    elif args.cmd == "schedule":
        cmd_schedule(
            set_time=getattr(args, "set", None),
            remove=args.remove,
            status=args.status,
        )


if __name__ == "__main__":
    main()
