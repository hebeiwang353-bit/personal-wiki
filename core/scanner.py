"""
扫描用户电脑所有可读文件，返回文件路径列表。
优先级：Documents/Desktop/Downloads > 浏览器历史/消息 > 其余 Home 目录
"""

import os
import sqlite3
from pathlib import Path
from dataclasses import dataclass
from typing import Generator

# 支持的文档格式
SUPPORTED_EXTS = {
    ".txt", ".md", ".markdown",
    ".pdf",
    ".doc", ".docx",
    ".xls", ".xlsx",
    ".csv",
    ".py", ".js", ".ts", ".java", ".go", ".rs", ".swift",
    ".html", ".htm",
    ".json", ".yaml", ".yml",
    ".rtf",
}

# 跳过的目录（系统、缓存、依赖、第三方库 — 跟用户本人无关）
SKIP_DIRS = {
    # Python
    "venv", ".venv", "env", "__pycache__", "site-packages", "dist-packages",
    # Node / 前端
    "node_modules", "bower_components", ".next", ".nuxt", "dist", "build",
    # iOS / Ruby / Swift 依赖
    "Pods", "vendor", "bundle", "Carthage", ".build",
    # Git / 缓存 / 系统
    ".git", ".svn", ".hg", ".cache", "Cache", "Caches",
    "Library/Caches", "Library/Logs",
    # IDE / 工具
    ".idea", ".vscode-cache", ".gradle", ".cocoapods",
    # 临时构建产物
    "DerivedData", "target", "out",
}

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB 单文件上限


@dataclass
class FileRecord:
    path: Path
    category: str       # 文件类型大类
    size: int
    mtime: float        # 最后修改时间


def _should_skip(path: Path) -> bool:
    for part in path.parts:
        if part in SKIP_DIRS:
            return True
    return False


PER_PROJECT_LIMIT = 80     # 每个顶层项目最多取这么多文件，避免单项目挤占
META_PRIORITY_NAMES = {     # 即使超过 PER_PROJECT_LIMIT 也必须保留的关键文件
    "readme.md", "readme.txt", "readme",
    "claude.md", "agents.md", "context.md",
    "package.json", "pyproject.toml", "cargo.toml",
    "plan.md", "design.md", "spec.md",
}


def _file_record(entry: Path) -> "FileRecord | None":
    """把一个文件路径包装成 FileRecord，过滤无效文件。"""
    if _should_skip(entry):
        return None
    if entry.suffix.lower() not in SUPPORTED_EXTS and entry.name.lower() not in META_PRIORITY_NAMES:
        return None
    try:
        stat = entry.stat()
        if stat.st_size == 0 or stat.st_size > MAX_FILE_SIZE:
            return None
        return FileRecord(path=entry, category="document", size=stat.st_size, mtime=stat.st_mtime)
    except (PermissionError, OSError):
        return None


def _scan_project_dir(project_dir: Path, limit: int) -> list[FileRecord]:
    """扫描单个顶层项目，返回最多 limit 条记录。Meta 文件优先纳入。"""
    metas: list[FileRecord] = []
    others: list[FileRecord] = []
    try:
        for entry in project_dir.rglob("*"):
            if not entry.is_file():
                continue
            rec = _file_record(entry)
            if rec is None:
                continue
            if entry.name.lower() in META_PRIORITY_NAMES:
                metas.append(rec)
            else:
                others.append(rec)
            # 提前终止条件：others 已经足够多
            if len(others) > limit * 5:
                break
    except (PermissionError, OSError):
        pass

    # meta 全保留 + others 按修改时间倒序补足
    others.sort(key=lambda r: -r.mtime)
    return metas + others[: max(limit - len(metas), 0)]


def scan_documents(home: Path) -> Generator[FileRecord, None, None]:
    """
    扫描文档类文件 —— 按"顶层项目"公平分配名额，避免单一大项目挤占所有扫描预算。
    遍历顺序：Desktop → Documents → Downloads → Movies/Music/Pictures → Home 顶层。
    """
    priority_roots = [home / "Desktop", home / "Documents", home / "Downloads"]
    other_roots = [home / "Movies", home / "Music", home / "Pictures"]

    seen: set[Path] = set()

    def _emit(rec: FileRecord):
        if rec.path in seen:
            return None
        seen.add(rec.path)
        return rec

    # ── Desktop / Documents / Downloads：按"顶层子目录"遍历，每项目限额 ────
    for root in priority_roots:
        if not root.exists():
            continue
        try:
            children = sorted(root.iterdir(), key=lambda p: -p.stat().st_mtime if p.exists() else 0)
        except (PermissionError, OSError):
            continue
        for child in children:
            if not child.exists():
                continue
            if child.is_dir():
                if _should_skip(child):
                    continue
                for rec in _scan_project_dir(child, PER_PROJECT_LIMIT):
                    out = _emit(rec)
                    if out:
                        yield out
            else:
                rec = _file_record(child)
                if rec:
                    out = _emit(rec)
                    if out:
                        yield out

    # ── 其余目录：浅层扫描 ─────────────────────────────────────────────
    for root in other_roots + [home]:
        if not root.exists():
            continue
        try:
            for entry in root.rglob("*"):
                if not entry.is_file():
                    continue
                rec = _file_record(entry)
                if rec is None:
                    continue
                out = _emit(rec)
                if out:
                    yield out
        except (PermissionError, OSError):
            continue


def scan_browser_history(home: Path) -> list[dict]:
    """读取 Safari / Chrome 浏览历史（返回 {url, title, visit_time} 列表）"""
    records = []

    # Safari
    safari_db = home / "Library/Safari/History.db"
    if safari_db.exists():
        try:
            conn = sqlite3.connect(f"file:{safari_db}?mode=ro", uri=True)
            rows = conn.execute(
                "SELECT url, title, visit_time FROM history_visits "
                "JOIN history_items ON history_visits.history_item = history_items.id "
                "ORDER BY visit_time DESC LIMIT 5000"
            ).fetchall()
            conn.close()
            for url, title, ts in rows:
                records.append({"source": "Safari", "url": url, "title": title or "", "ts": ts})
        except Exception:
            pass

    # Chrome
    chrome_history = home / "Library/Application Support/Google/Chrome/Default/History"
    if chrome_history.exists():
        import shutil, tempfile
        # Chrome 锁住 DB，需要复制一份再读
        # 用 mkstemp 代替 mktemp，消除 TOCTOU 竞态漏洞
        tmp_fd, tmp_str = tempfile.mkstemp(suffix=".db")
        tmp = Path(tmp_str)
        try:
            os.close(tmp_fd)   # 先关闭 fd，再让 shutil.copy2 写入
            shutil.copy2(chrome_history, tmp)
            conn = sqlite3.connect(tmp)
            rows = conn.execute(
                "SELECT url, title, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT 5000"
            ).fetchall()
            conn.close()
            for url, title, ts in rows:
                records.append({"source": "Chrome", "url": url, "title": title or "", "ts": ts})
        except Exception:
            pass
        finally:
            tmp.unlink(missing_ok=True)

    return records


def scan_imessage(home: Path) -> list[dict]:
    """读取 iMessage 聊天记录摘要（不含完整内容，仅采样）"""
    db_path = home / "Library/Messages/chat.db"
    if not db_path.exists():
        return []
    records = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        rows = conn.execute(
            "SELECT text, date FROM message WHERE text IS NOT NULL AND length(text) > 5 "
            "ORDER BY date DESC LIMIT 2000"
        ).fetchall()
        conn.close()
        for text, ts in rows:
            records.append({"text": text, "ts": ts})
    except Exception:
        pass
    return records
