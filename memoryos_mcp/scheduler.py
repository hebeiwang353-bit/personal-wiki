"""
定时扫描任务管理器 —— Mac (LaunchAgent) + Windows (Task Scheduler)
用法：
  python -m memoryos_mcp.scheduler --set "22:00"    设定每天定时扫描
  python -m memoryos_mcp.scheduler --status         查看当前定时状态
  python -m memoryos_mcp.scheduler --remove         移除定时任务
  python -m memoryos_mcp.scheduler --run-now        立即触发一次扫描
"""

import argparse
import platform
import subprocess
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
PYTHON = str(ROOT / "venv" / ("Scripts/python.exe" if platform.system() == "Windows" else "bin/python"))
MAIN_SCRIPT = str(ROOT / "main.py")

# ── macOS LaunchAgent ─────────────────────────────────────────

PLIST_PATH = Path.home() / "Library/LaunchAgents/com.memoryos.scanner.plist"
PLIST_LABEL = "com.memoryos.scanner"


def _plist_content(hour: int, minute: int) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{PYTHON}</string>
        <string>{MAIN_SCRIPT}</string>
        <string>--max-files</string>
        <string>5000</string>
        <string>--skip-confirm</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>{minute}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{Path.home()}/.memoryos/scan.log</string>
    <key>StandardErrorPath</key>
    <string>{Path.home()}/.memoryos/scan_error.log</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>"""


def _set_mac(hour: int, minute: int):
    # 先卸载旧的（如果存在）
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)

    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(_plist_content(hour, minute), encoding="utf-8")

    result = subprocess.run(["launchctl", "load", str(PLIST_PATH)], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"注册失败：{result.stderr}")
        return False

    print(f"✓ 定时扫描已设定：每天 {hour:02d}:{minute:02d}")
    print(f"  日志：~/.memoryos/scan.log")
    return True


def _status_mac() -> str:
    if not PLIST_PATH.exists():
        return "未设定定时扫描"
    content = PLIST_PATH.read_text(encoding="utf-8")
    hour = _extract_plist_int(content, "Hour")
    minute = _extract_plist_int(content, "Minute")
    result = subprocess.run(
        ["launchctl", "list", PLIST_LABEL], capture_output=True, text=True
    )
    running = "已注册" if result.returncode == 0 else "已配置但未注册"
    return f"定时扫描：每天 {hour:02d}:{minute:02d}（{running}）"


def _remove_mac():
    if not PLIST_PATH.exists():
        print("无定时任务。")
        return
    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], capture_output=True)
    PLIST_PATH.unlink()
    print("✓ 已移除定时扫描任务")


def _extract_plist_int(content: str, key: str) -> int:
    import re
    m = re.search(rf"<key>{key}</key>\s*<integer>(\d+)</integer>", content)
    return int(m.group(1)) if m else 0


# ── Windows Task Scheduler ────────────────────────────────────

TASK_NAME = "MemoryOS_Scanner"


def _set_windows(hour: int, minute: int):
    time_str = f"{hour:02d}:{minute:02d}"
    cmd = [
        "schtasks", "/Create", "/F",
        "/TN", TASK_NAME,
        "/TR", f'"{PYTHON}" "{MAIN_SCRIPT}" --max-files 5000 --skip-confirm',
        "/SC", "DAILY",
        "/ST", time_str,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    if result.returncode != 0:
        print(f"注册失败：{result.stderr}")
        return False
    print(f"✓ 定时扫描已设定：每天 {hour:02d}:{minute:02d}")
    return True


def _status_windows() -> str:
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"],
        capture_output=True, text=True, encoding="gbk", errors="ignore"
    )
    if result.returncode != 0:
        return "未设定定时扫描"
    for line in result.stdout.splitlines():
        if "下次运行时间" in line or "Next Run Time" in line:
            return f"定时扫描已配置。{line.strip()}"
    return "定时扫描已配置"


def _remove_windows():
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("✓ 已移除定时扫描任务")
    else:
        print("无定时任务或移除失败")


# ── 公共接口 ──────────────────────────────────────────────────

def parse_time(time_str: str) -> tuple[int, int]:
    """解析 'HH:MM' 格式，返回 (hour, minute)"""
    try:
        t = datetime.strptime(time_str.strip(), "%H:%M")
        return t.hour, t.minute
    except ValueError:
        raise ValueError(f"时间格式错误：{time_str}，请使用 HH:MM 格式，如 22:00")


def set_schedule(time_str: str) -> bool:
    hour, minute = parse_time(time_str)
    system = platform.system()
    if system == "Darwin":
        return _set_mac(hour, minute)
    elif system == "Windows":
        return _set_windows(hour, minute)
    else:
        print(f"暂不支持 {system}，请手动设置 cron：")
        print(f"  {minute} {hour} * * * {PYTHON} {MAIN_SCRIPT} --max-files 5000 --skip-confirm")
        return False


def get_status() -> str:
    system = platform.system()
    if system == "Darwin":
        return _status_mac()
    elif system == "Windows":
        return _status_windows()
    return "请通过 crontab -l 查看定时任务"


def remove_schedule():
    system = platform.system()
    if system == "Darwin":
        _remove_mac()
    elif system == "Windows":
        _remove_windows()
    else:
        print("请手动编辑 crontab -e 移除任务")


def run_now():
    """立即在后台触发一次扫描"""
    import subprocess
    print("正在启动扫描...")
    subprocess.Popen(
        [PYTHON, MAIN_SCRIPT, "--max-files", "5000", "--skip-confirm"],
        stdout=open(Path.home() / ".memoryos/scan.log", "a"),
        stderr=subprocess.STDOUT,
    )
    print(f"✓ 扫描已在后台启动，日志：~/.memoryos/scan.log")


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MemoryOS 定时扫描管理")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--set", metavar="HH:MM", help='设定每日扫描时间，如 "22:00"')
    group.add_argument("--status", action="store_true", help="查看当前定时状态")
    group.add_argument("--remove", action="store_true", help="移除定时任务")
    group.add_argument("--run-now", action="store_true", help="立即触发一次扫描")
    args = parser.parse_args()

    if args.set:
        set_schedule(args.set)
    elif args.status:
        print(get_status())
    elif args.remove:
        remove_schedule()
    elif args.run_now:
        run_now()
