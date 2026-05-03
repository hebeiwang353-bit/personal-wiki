#!/usr/bin/env python3
"""
MemoryOS Web UI · 本地可视化界面
启动：python web/server.py
访问：http://localhost:8766
"""

import os
import sys
import json
import platform
import subprocess
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from wiki.wiki_manager import (
    WIKI_ROOT, get_page, update_page, list_pages,
    recent_logs, append_log, init_wiki,
)
from wiki.context_builder import context_token_count
from memoryos_mcp.scheduler import get_status as scheduler_status, set_schedule, run_now

PORT = 8766
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="MemoryOS Web UI", docs_url=None, redoc_url=None)


# ── HTML 主页面 ───────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


# ── API ───────────────────────────────────────────────────────

@app.get("/api/status")
async def api_status():
    """Wiki 状态总览"""
    init_wiki()
    pages = list_pages()
    me = get_page("me.md") or ""
    summary = ""
    for line in me.splitlines():
        if "综合描述" in line:
            summary = line.split("：", 1)[-1].strip().rstrip("*").strip()
            break
    return {
        "wiki_root": str(WIKI_ROOT),
        "page_count": len(pages),
        "context_tokens": context_token_count(),
        "summary": summary,
        "schedule": scheduler_status(),
        "recent_logs": recent_logs(10),
    }


@app.get("/api/pages")
async def api_pages():
    """返回页面树（按目录分组）"""
    init_wiki()
    pages = list_pages()
    tree = {"core": [], "projects": [], "interests": [], "tools": [], "other": []}
    for p in pages:
        if p.startswith("projects/"):
            tree["projects"].append(p)
        elif p.startswith("interests/"):
            tree["interests"].append(p)
        elif p.startswith("tools/"):
            tree["tools"].append(p)
        elif p in ("me.md", "index.md", "log.md"):
            tree["core"].append(p)
        else:
            tree["other"].append(p)
    return tree


@app.get("/api/page/{path:path}")
async def api_page_get(path: str):
    """读取单个页面"""
    if ".." in path or path.startswith("/"):
        raise HTTPException(400, "非法路径")
    content = get_page(path)
    if content is None:
        raise HTTPException(404, f"页面不存在: {path}")
    return {"path": path, "content": content}


class PageUpdate(BaseModel):
    content: str


@app.put("/api/page/{path:path}")
async def api_page_put(path: str, body: PageUpdate):
    """保存页面内容"""
    if ".." in path or path.startswith("/"):
        raise HTTPException(400, "非法路径")
    if not path.endswith(".md"):
        raise HTTPException(400, "只能编辑 .md 文件")
    update_page(path, body.content)
    append_log(f"通过 Web UI 编辑了 {path}")
    return {"ok": True, "path": path}


def _find_python() -> str:
    """跨平台找到当前环境的 Python 可执行文件路径。"""
    # 1. 优先用与当前进程相同的 Python（最可靠）
    if sys.executable:
        return sys.executable
    # 2. 备用：在 venv 目录里找（兼容不同安装位置）
    is_win = platform.system() == "Windows"
    candidates = [
        ROOT / "venv" / ("Scripts/python.exe" if is_win else "bin/python"),
        Path(os.environ.get("MEMORYOS_HOME", Path.home() / ".memoryos"))
        / "venv" / ("Scripts/python.exe" if is_win else "bin/python"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return "python"  # 最后回退到 PATH 里的 python


@app.post("/api/scan")
async def api_scan(max_files: int = 2000):
    """在后台触发一次扫描"""
    main_py = str(ROOT / "main.py")
    venv_python = _find_python()
    log_path = WIKI_ROOT.parent / "scan.log"
    log_file = open(log_path, "a", encoding="utf-8")

    # 继承当前进程环境变量，追加 PYTHONPATH 和 MEMORYOS_HOME
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env.setdefault("MEMORYOS_HOME", str(WIKI_ROOT.parent))

    proc = subprocess.Popen(
        [venv_python, main_py, "--max-files", str(max_files), "--no-embed", "--skip-confirm"],
        cwd=str(ROOT),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    append_log(f"通过 Web UI 启动扫描（PID: {proc.pid}, max_files={max_files}）")
    return {"ok": True, "pid": proc.pid, "log_path": str(log_path)}


@app.get("/api/scan/log")
async def api_scan_log(lines: int = 50):
    """读取扫描日志最后 N 行"""
    log_path = WIKI_ROOT.parent / "scan.log"
    if not log_path.exists():
        return {"lines": []}
    with open(log_path, "rb") as f:
        # 简单读最后 N 行
        all_lines = f.read().decode("utf-8", errors="ignore").splitlines()
    return {"lines": all_lines[-lines:]}


class ScheduleUpdate(BaseModel):
    time: str   # HH:MM


@app.post("/api/schedule")
async def api_schedule_set(body: ScheduleUpdate):
    """设置每日定时扫描"""
    ok = set_schedule(body.time)
    return {"ok": ok, "status": scheduler_status()}


# ── 静态资源 ──────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    print(f"MemoryOS Web UI 启动")
    print(f"  访问：http://localhost:{PORT}")
    print(f"  Wiki：{WIKI_ROOT}")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
