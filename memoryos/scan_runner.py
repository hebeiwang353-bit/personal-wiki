"""
MemoryOS 扫描执行器 — pip install 后可用的打包版本
由 memoryos/cli.py 的 cmd_scan() 和 scheduler 直接调用。
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path


def run_scan(
    home: Path | None = None,
    max_files: int = 5000,
    n_clusters: int = 0,
    top_k: int = 2,
    out: str = "profile.json",
    skip_confirm: bool = True,
    no_embed: bool = True,
) -> dict:
    """
    完整扫描流程。返回最终画像 dict。
    no_embed=True（默认）跳过 Embedding，适合轻量定时扫描。
    """
    import sys

    # ── 确保 MEMORYOS_HOME 设好 ──────────────────────────────────
    memoryos_home = Path(os.environ.get("MEMORYOS_HOME", Path.home() / ".memoryos"))
    os.environ.setdefault("MEMORYOS_HOME", str(memoryos_home))

    # ── 导入扫描所需模块 ─────────────────────────────────────────
    # 这些包在 pyproject.toml 的 include 列表中，pip install 后可用
    from dotenv import load_dotenv
    load_dotenv(memoryos_home / ".env")

    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.panel import Panel

    console = Console()

    # 延迟导入，确保 env 变量已设好
    from core.scanner import scan_documents, scan_browser_history
    from core.extractor import extract
    from core.analyzer import analyze_batch, merge_profiles, analyze_browser_history
    from wiki.wiki_manager import init_wiki, write_profile_to_wiki, append_log

    if home is None:
        home = Path.home()

    CLAUDE_BATCH_SIZE = 5

    # ── 阶段1：扫描文件 ──────────────────────────────────────────
    console.rule("[bold]扫描文件")
    all_files = []
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        task = p.add_task("扫描中...", total=None)
        for rec in scan_documents(home):
            all_files.append(rec)
            p.update(task, description=f"已找到 {len(all_files)} 个文件...")
            if len(all_files) >= max_files:
                break
    console.print(f"  → 共找到 [green]{len(all_files)}[/green] 个文件")

    # ── 阶段2：提取文本 ──────────────────────────────────────────
    console.rule("[bold]提取文本")
    extracted = []

    if not no_embed:
        from core.embedder import already_embedded
        skip_paths = already_embedded([str(r.path) for r in all_files])
        console.print(f"  → 已有 {len(skip_paths)} 个文件在 ChromaDB 中")
    else:
        skip_paths = set()

    with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                  BarColumn(), TaskProgressColumn(), console=console) as p:
        task = p.add_task("提取中...", total=len(all_files))
        for rec in all_files:
            text = extract(rec.path)
            if text and len(text.strip()) > 80:
                extracted.append({
                    "path": str(rec.path),
                    "text": text,
                    "mtime": rec.mtime,
                    "size": rec.size,
                })
            p.advance(task)

    # ── 阶段3/4：Embedding + 聚类 或 简单采样 ─────────────────────
    if no_embed:
        console.rule("[bold]简化模式：跳过 Embedding，直接采样")
        samples = _simple_sample(extracted, target=min(150, len(extracted)))
        console.print(f"  → 采样 [green]{len(samples)}[/green] 篇文档送给分析")
    else:
        from core.embedder import (
            embed_and_store, total_stored, get_all_embeddings
        )
        from core.clusterer import cluster_and_sample, estimate_clusters
        from core.cost_estimator import estimate as cost_estimate

        new_items = [i for i in extracted if i["path"] not in skip_paths]
        n_clusters_actual = n_clusters or estimate_clusters(total_stored() + len(new_items))
        n_samples = n_clusters_actual * top_k

        if new_items:
            console.rule("[bold]Embedding & 存入 ChromaDB")
            with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                          BarColumn(), TaskProgressColumn(), console=console) as p:
                task = p.add_task("Embedding 中...", total=len(new_items))
                added = embed_and_store(new_items, progress_cb=lambda n: p.advance(task, n))
            console.print(f"  → 新增 [green]{added}[/green] 条")

        console.rule("[bold]聚类采样")
        paths, embeddings, texts = get_all_embeddings()
        samples = cluster_and_sample(
            paths, embeddings, texts,
            n_clusters=n_clusters_actual,
            top_k_per_cluster=top_k,
        )
        console.print(f"  → 采样完成，共 [green]{len(samples)}[/green] 篇代表文档")

    # ── 阶段5：Claude 分析 ────────────────────────────────────────
    console.rule("[bold]Claude 分析 & 生成画像")

    fragments = []
    batches = [samples[i:i+CLAUDE_BATCH_SIZE] for i in range(0, len(samples), CLAUDE_BATCH_SIZE)]
    with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                  BarColumn(), TaskProgressColumn(), console=console) as p:
        task = p.add_task("Claude 分析中...", total=len(batches))
        for i, batch in enumerate(batches):
            try:
                result = analyze_batch(batch)
                fragments.append(result)
            except Exception as e:
                console.print(f"  [yellow]批次 {i+1} 失败：{e}[/yellow]")
            p.update(task, description=f"第 {i+1}/{len(batches)} 批...", advance=1)
            time.sleep(0.3)

    # 浏览器历史
    browser_records = scan_browser_history(home)
    if browser_records:
        console.print(f"  → 分析浏览历史（{len(browser_records)} 条）...")
        try:
            browser_profile = analyze_browser_history(browser_records)
            fragments.append({"浏览行为分析": browser_profile})
        except Exception as e:
            console.print(f"  [yellow]浏览历史分析失败：{e}[/yellow]")

    # 合并画像
    console.print("  → 合并所有片段，生成最终用户画像...")
    try:
        final_profile = merge_profiles(fragments)
    except Exception as e:
        console.print(f"  [red]合并失败：{e}[/red]")
        final_profile = {"fragments": fragments}

    # ── 写入 Wiki ─────────────────────────────────────────────────
    console.print("  → 写入 Wiki 知识库...")
    try:
        wiki_root = init_wiki()
        write_profile_to_wiki(final_profile, wiki_root)
        append_log(
            f"完整扫描完成，分析 {len(extracted)} 个文件，采样 {len(samples)} 篇",
            wiki_root,
        )
        console.print(f"  → Wiki 已写入：[green]{wiki_root}[/green]")
    except Exception as e:
        console.print(f"  [yellow]Wiki 写入失败：{e}[/yellow]")

    # ── 填充项目页 ────────────────────────────────────────────────
    projects = final_profile.get("近期项目", [])
    if projects and not isinstance(projects, str):
        console.rule(f"[bold]填充 {len(projects)} 个项目页")
        from core.analyzer import generate_project_page
        from wiki.wiki_manager import update_page

        with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                      BarColumn(), TaskProgressColumn(), console=console) as p:
            task = p.add_task("填充中...", total=len(projects))
            for proj in projects:
                key = str(proj)[:8].lower()
                related = [
                    f for f in extracted
                    if key in f["path"].lower() or key in f["text"][:500].lower()
                ][:6]
                slug = str(proj)[:20].replace(" ", "_").replace("/", "-")
                page_path = f"projects/{slug}.md"
                try:
                    content = generate_project_page(str(proj), related)
                    update_page(page_path, content, wiki_root)
                except Exception as e:
                    console.print(f"  [yellow]填充 {slug} 失败：{e}[/yellow]")
                p.advance(task)
                time.sleep(0.2)

    # ── JSON 备份 ─────────────────────────────────────────────────
    out_path = memoryos_home / "profile.json"
    out_path.write_text(
        json.dumps(final_profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── 合并对话记忆 ──────────────────────────────────────────────
    try:
        from core.conversation_memory import consolidate_to_long_term
        asyncio.run(consolidate_to_long_term())
    except Exception:
        pass

    console.print(f"\n[bold green]扫描完成！[/bold green]")
    console.print(f"  Wiki：[cyan]{memoryos_home / 'wiki'}[/cyan]")
    console.print(f"  JSON 备份：[cyan]{out_path}[/cyan]")

    return final_profile


# ── 辅助：简单采样（无 Embedding 时使用）──────────────────────────

def _simple_sample(items: list[dict], target: int = 50) -> list[dict]:
    from collections import defaultdict

    META_NAMES = {
        "readme.md", "readme.txt", "readme",
        "claude.md", "agents.md", "cursor.md", "context.md",
        "package.json", "pyproject.toml", "cargo.toml",
        "plan.md", "design.md", "todo.md", "spec.md",
        "notes.md", "ideas.md", "diary.md", "journal.md",
        "resume.md", "resume.pdf", "cv.pdf", "cv.md",
        "prd.md", "requirements.md", "architecture.md",
        "setup.py", "go.mod", "pom.xml", "build.gradle",
        "dockerfile", "docker-compose.yml", "makefile",
    }

    def _project_root(path_str: str) -> str:
        p = Path(path_str)
        parts = p.parts
        for anchor in ("Desktop", "Documents", "Downloads"):
            if anchor in parts:
                i = parts.index(anchor)
                if i + 1 < len(parts):
                    return f"{anchor}/{parts[i+1]}"
        return str(p.parent)

    by_project: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        by_project[_project_root(it["path"])].append(it)

    def _priority(it):
        is_meta = Path(it["path"]).name.lower() in META_NAMES
        return (0 if is_meta else 1, -it.get("mtime", 0))

    for proj in by_project:
        by_project[proj].sort(key=_priority)

    PER_PROJECT_LIMIT = 8
    selected = []
    project_count: dict[str, int] = defaultdict(int)
    projects = list(by_project.keys())
    pi = 0
    rounds_without_pick = 0

    while len(selected) < target:
        if not projects:
            break
        proj = projects[pi % len(projects)]
        if project_count[proj] < PER_PROJECT_LIMIT and by_project[proj]:
            selected.append(by_project[proj].pop(0))
            project_count[proj] += 1
            rounds_without_pick = 0
        else:
            rounds_without_pick += 1
        pi += 1
        if rounds_without_pick > len(projects):
            break

    return selected


# ── 入口（供 scheduler 直接运行）──────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MemoryOS 扫描执行器")
    parser.add_argument("--max-files", type=int, default=5000)
    parser.add_argument("--skip-confirm", action="store_true")
    parser.add_argument("--no-embed", action="store_true")
    args = parser.parse_args()
    run_scan(max_files=args.max_files, skip_confirm=args.skip_confirm, no_embed=args.no_embed)
