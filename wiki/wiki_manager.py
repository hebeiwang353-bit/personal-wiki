"""
Wiki 知识库管理器 —— 负责所有页面的增删改查和日志追加。

存储位置：~/.memoryos/wiki/
结构：
  index.md          所有页面目录
  me.md             用户核心画像
  projects/         项目页
  interests/        兴趣领域
  tools/            工具链
  log.md            追加式操作日志
"""

import json
from datetime import datetime
from pathlib import Path


WIKI_ROOT = Path.home() / ".memoryos" / "wiki"

# 启动时必须存在的页面
CORE_PAGES = {
    "me.md": "# 关于我\n\n（待建立）\n",
    "log.md": f"# 操作日志\n\n{datetime.now().strftime('%Y-%m-%d')} 初始化 Wiki\n",
    "index.md": "# Wiki 索引\n\n## 核心页面\n- [关于我](me.md)\n\n## 项目\n\n## 兴趣领域\n\n## 工具链\n",
}


# ── 初始化 ────────────────────────────────────────────────────

def init_wiki(root: Path = WIKI_ROOT) -> Path:
    """创建 Wiki 目录结构，已存在则跳过。返回根路径。"""
    root.mkdir(parents=True, exist_ok=True)
    (root / "projects").mkdir(exist_ok=True)
    (root / "interests").mkdir(exist_ok=True)
    (root / "tools").mkdir(exist_ok=True)

    for name, default_content in CORE_PAGES.items():
        page = root / name
        if not page.exists():
            page.write_text(default_content, encoding="utf-8")

    return root


# ── 页面读写 ──────────────────────────────────────────────────

def get_page(name: str, root: Path = WIKI_ROOT) -> str | None:
    """读取页面内容，不存在返回 None。name 可含子目录，如 'projects/app.md'"""
    path = root / name
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def update_page(name: str, content: str, root: Path = WIKI_ROOT) -> Path:
    """写入或覆盖页面内容，自动创建父目录。"""
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _update_index(name, root)
    return path


def delete_page(name: str, root: Path = WIKI_ROOT) -> bool:
    path = root / name
    if path.exists():
        path.unlink()
        return True
    return False


def list_pages(root: Path = WIKI_ROOT) -> list[str]:
    """返回所有 .md 页面的相对路径列表（相对于 root）"""
    if not root.exists():
        return []
    return sorted(
        str(p.relative_to(root))
        for p in root.rglob("*.md")
    )


def get_all_content(root: Path = WIKI_ROOT, exclude: list[str] | None = None) -> dict[str, str]:
    """返回 {相对路径: 内容} 字典，用于 context builder 汇总。"""
    exclude_set = set(exclude or ["log.md"])
    result = {}
    for rel in list_pages(root):
        if rel in exclude_set:
            continue
        content = get_page(rel, root)
        if content and content.strip() and content.strip() != "（待建立）":
            result[rel] = content
    return result


# ── 日志 ─────────────────────────────────────────────────────

def append_log(entry: str, root: Path = WIKI_ROOT):
    """向 log.md 追加一条带时间戳的记录。"""
    log_path = root / "log.md"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"\n- **{ts}** {entry}"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)


def recent_logs(n: int = 10, root: Path = WIKI_ROOT) -> str:
    """返回 log.md 最后 n 条记录。"""
    log_path = root / "log.md"
    if not log_path.exists():
        return ""
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.startswith("- **")]
    return "\n".join(lines[-n:])


# ── 索引维护 ──────────────────────────────────────────────────

def _update_index(name: str, root: Path):
    """把新页面添加到 index.md 对应分类中（已存在则跳过）。"""
    index_path = root / "index.md"
    content = index_path.read_text(encoding="utf-8") if index_path.exists() else ""

    link = f"- [{Path(name).stem}]({name})"
    if link in content:
        return

    # 按目录归类插入
    if name.startswith("projects/"):
        section = "## 项目"
    elif name.startswith("interests/"):
        section = "## 兴趣领域"
    elif name.startswith("tools/"):
        section = "## 工具链"
    else:
        section = "## 核心页面"

    if section in content:
        content = content.replace(section, f"{section}\n{link}", 1)
    else:
        content += f"\n{section}\n{link}\n"

    index_path.write_text(content, encoding="utf-8")


# ── 从分析结果批量写入 Wiki ───────────────────────────────────

USER_NOTE_MARKER = "## 用户自述"   # 用户手动编辑节的标识，自动更新时永不覆盖


def _extract_user_note(content: str) -> str:
    """从 me.md 中提取 ## 用户自述 节（含标题），无则返回空串。"""
    if USER_NOTE_MARKER not in content:
        return ""
    parts = content.split(USER_NOTE_MARKER, 1)
    after = parts[1]
    # 找下一个二级标题（## 开头的行）作为终止
    next_h2 = after.find("\n## ")
    section_body = after if next_h2 == -1 else after[:next_h2]
    return f"{USER_NOTE_MARKER}{section_body}"


AUTO_SECTION_MARKER = "## 自动分析"   # 自动写入的内容统一放这个二级标题下


def write_profile_to_wiki(profile: dict, root: Path = WIKI_ROOT):
    """
    把 analyzer.merge_profiles() 的输出结构化写入 Wiki 各页面。
    - 保留用户手动编辑的 "## 用户自述" 节（永不覆盖）
    - 所有自动生成内容统一放在 "## 自动分析" 节下（每次完整替换）
    """
    # 提取已有的用户自述节（用户写的，要保留）
    existing_me = get_page("me.md", root) or ""
    user_note = _extract_user_note(existing_me)

    # 重建 me.md
    lines = ["# 关于我\n"]
    if user_note:
        lines.append(user_note.rstrip() + "\n")

    # ── 自动分析节（每次完整覆盖） ──
    lines.append(f"\n{AUTO_SECTION_MARKER}\n")
    lines.append(f"> 此节由 MemoryOS 自动维护，每次扫描重写。最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

    # 直接列出关键字段（粗体）
    if profile.get("职业"):
        lines.append(f"\n**职业**：{profile['职业']}")
    if profile.get("画像总结"):
        lines.append(f"\n**综合描述**：{profile['画像总结']}")
    if profile.get("行为特征"):
        v = profile["行为特征"]
        lines.append(f"\n**行为特征**：{', '.join(v) if isinstance(v, list) else v}")
    if profile.get("高频关键词"):
        v = profile["高频关键词"]
        lines.append(f"\n**高频关键词**：{', '.join(v) if isinstance(v, list) else v}\n")

    # ── 知识结构子节 ──
    if profile.get("知识结构") and isinstance(profile["知识结构"], dict):
        lines.append("\n### 知识结构\n")
        for level, items in profile["知识结构"].items():
            txt = ', '.join(items) if isinstance(items, list) else items
            lines.append(f"- **{level}**：{txt}")
        lines.append("")

    # ── 工作内容 / 习惯子节 ──
    if profile.get("工作内容"):
        lines.append("\n### 工作内容\n")
        for w in profile["工作内容"]:
            lines.append(f"- {w}")
    if profile.get("工作习惯"):
        lines.append("\n### 工作习惯\n")
        for h in profile["工作习惯"]:
            lines.append(f"- {h}")

    update_page("me.md", "\n".join(lines).rstrip() + "\n", root)

    # projects/ —— 每个近期项目一个页面
    for proj in profile.get("近期项目", []):
        slug = proj[:20].replace(" ", "_").replace("/", "-")
        path = f"projects/{slug}.md"
        if not get_page(path, root):  # 不覆盖已有页面
            update_page(path, f"# {proj}\n\n（从文件分析自动创建）\n", root)

    # interests/ —— 专业领域 + 兴趣爱好
    domains = profile.get("专业领域", []) + profile.get("兴趣爱好", [])
    for domain in domains[:5]:
        slug = domain[:20].replace(" ", "_")
        path = f"interests/{slug}.md"
        if not get_page(path, root):
            update_page(path, f"# {domain}\n\n（从文件分析自动创建）\n", root)

    # tools/ —— 常用工具
    tools_content = "# 常用工具链\n\n"
    tools = profile.get("常用工具", [])
    if tools:
        tools_content += "\n".join(f"- {t}" for t in tools)
    update_page("tools/toolchain.md", tools_content, root)

    append_log(f"从文件分析写入画像，涉及 {len(list_pages(root))} 个页面", root)
