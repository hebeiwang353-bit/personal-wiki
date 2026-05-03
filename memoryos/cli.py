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

    # 4. 注册 MCP Server
    step("注册 MCP Server 到 AI 工具...")
    registered = _register_mcp()
    if registered == 0:
        warn("未找到 Claude Desktop / Cursor 配置文件")

    # 5. 设定每日 11:00 定时扫描
    step("设定每日 11:00 自动扫描...")
    _register_daily_scan()

    # 6. 检测已安装的 AI 工具
    step("检测本机 AI 工具...")
    print()
    _detect_tools(registered)

    # 7. 完成
    print(f"""
{GREEN}╔══════════════════════════════════════════╗
║         MemoryOS 安装完成！               ║
╚══════════════════════════════════════╝{RESET}

{YELLOW}唯一必做步骤：{RESET}
  编辑 {ENV_FILE}
  填写 AI_PROVIDER 和 AI_API_KEY

{YELLOW}填好后运行首次扫描（2-5 分钟，费用约 ¥1-5）：{RESET}
  memoryos scan

{YELLOW}之后无需任何操作：{RESET}
  · 每天 11:00 自动扫描更新记忆库
  · 代理服务开机自动启动（localhost:8765）
  · Web UI：memoryos web → http://localhost:8766
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


def _register_mcp() -> int:
    """向 Claude Desktop / Cursor 的配置文件注入 MCP Server，返回成功注册数。"""
    python  = _python_exe()
    mcp_cmd = [python, "-m", "memoryos_mcp.mcp_server"]

    mcp_entry = {
        "command": python,
        "args": ["-m", "memoryos_mcp.mcp_server"],
        "env": {
            "MEMORYOS_HOME": str(MEMORYOS_HOME),
            "PYTHONPATH": str(ROOT),
        }
    }

    if IS_WIN:
        candidates = [
            Path(os.environ.get("APPDATA", "")) / "Claude/claude_desktop_config.json",
            Path.home() / ".claude.json",
            Path.home() / ".cursor/mcp.json",
            Path(os.environ.get("APPDATA", "")) / "Cursor/mcp.json",
        ]
    else:
        candidates = [
            Path.home() / "Library/Application Support/Claude/claude_desktop_config.json",
            Path.home() / ".config/Claude/claude_desktop_config.json",
            Path.home() / ".claude.json",
            Path.home() / ".cursor/mcp.json",
        ]

    count = 0
    for cfg_path in candidates:
        if not cfg_path.exists():
            continue
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            servers = cfg.setdefault("mcpServers", {})
            servers["memoryos"] = mcp_entry
            cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
            ok(f"MCP 已注册到 {cfg_path.name}")
            count += 1
        except Exception as e:
            warn(f"注册 {cfg_path.name} 失败：{e}")
    return count


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

    if not ENV_FILE.exists() or "AI_API_KEY=sk-xxx" in ENV_FILE.read_text():
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
