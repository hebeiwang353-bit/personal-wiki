#!/usr/bin/env python3
"""
桌面理解 — 分层用户画像系统
流程：扫描 → 提取 → Embedding(全量) → 聚类采样 → Claude分析 → 画像
"""

import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm

from core.scanner import scan_documents, scan_browser_history
from core.extractor import extract
from core.embedder import embed_and_store, total_stored, get_all_embeddings, already_embedded
from core.clusterer import cluster_and_sample, estimate_clusters
from core.analyzer import analyze_batch, merge_profiles, analyze_browser_history, determine_affected_pages, update_wiki_page
from core.cost_estimator import estimate as cost_estimate
from wiki.wiki_manager import init_wiki, write_profile_to_wiki, append_log, WIKI_ROOT
from wiki.context_builder import build_context

console = Console()
CLAUDE_BATCH_SIZE = 5


def _project_root(path_str: str) -> str:
    """识别一个文件所属的"顶层项目"——以 Desktop/Documents/Downloads 下的第一级目录为准。"""
    p = Path(path_str)
    parts = p.parts
    for anchor in ("Desktop", "Documents", "Downloads"):
        if anchor in parts:
            i = parts.index(anchor)
            if i + 1 < len(parts):
                return f"{anchor}/{parts[i+1]}"
    return str(p.parent)


def _simple_sample(items: list[dict], target: int = 50) -> list[dict]:
    """
    无 Embedding 时的智能采样：
    1) 必采项目自描述文件（README/CLAUDE.md/context.md/package.json）
    2) **每个顶层项目最多 3 个文件**（核心约束），避免单项目挤占
    3) 在 2 的约束下，优先 meta 文件 → 再按修改时间补足
    """
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

    # 按"顶层项目"分组
    by_project: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        by_project[_project_root(it["path"])].append(it)

    # 每个项目内部排序：meta 文件优先，其次按修改时间倒序
    def _priority(it):
        is_meta = Path(it["path"]).name.lower() in META_NAMES
        return (0 if is_meta else 1, -it.get("mtime", 0))

    for proj in by_project:
        by_project[proj].sort(key=_priority)

    # 轮转：每个项目轮流取 1 个，直到达到 target，每个项目最多 8 个
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
            break  # 全部项目都满或耗尽

    return selected


def main():
    parser = argparse.ArgumentParser(description="桌面理解 — 用户画像生成")
    parser.add_argument("--home", default=str(Path.home()), help="用户 Home 目录")
    parser.add_argument("--max-files", type=int, default=5000, help="扫描文件上限")
    parser.add_argument("--n-clusters", type=int, default=0, help="聚类数（0=自动）")
    parser.add_argument("--top-k", type=int, default=2, help="每个簇取几篇代表文档")
    parser.add_argument("--out", default="profile.json", help="输出画像文件路径")
    parser.add_argument("--skip-confirm", action="store_true", help="跳过费用确认")
    parser.add_argument("--no-embed", action="store_true",
                        help="跳过 Embedding，直接随机采样送分析（适用于 DeepSeek 等无 Embedding API 的服务）")
    args = parser.parse_args()

    home = Path(args.home)
    console.print(Panel(
        f"[bold cyan]桌面理解 · 分层用户画像系统[/bold cyan]\n"
        f"扫描目录：{home}\n"
        f"最大文件数：{args.max_files}",
        expand=False
    ))

    # ── 阶段1：扫描文件 ───────────────────────────────────────────
    console.rule("[bold]阶段 1 / 5  扫描文件")
    all_files = []
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as p:
        task = p.add_task("扫描中...", total=None)
        for rec in scan_documents(home):
            all_files.append(rec)
            p.update(task, description=f"已找到 {len(all_files)} 个文件...")
            if len(all_files) >= args.max_files:
                break
    console.print(f"  → 共找到 [green]{len(all_files)}[/green] 个文件")

    # ── 阶段2：提取文本 ───────────────────────────────────────────
    console.rule("[bold]阶段 2 / 5  提取文本")
    extracted = []
    skip_paths = set() if args.no_embed else already_embedded([str(r.path) for r in all_files])
    if not args.no_embed:
        console.print(f"  → ChromaDB 中已有 {len(skip_paths)} 个文件，跳过重复处理")

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

    new_items = [i for i in extracted if i["path"] not in skip_paths]
    console.print(f"  → 提取成功 [green]{len(extracted)}[/green] 个" + (
        f"，其中 [yellow]{len(new_items)}[/yellow] 个需要新建 Embedding" if not args.no_embed else ""
    ))

    if args.no_embed:
        # ── 简化路径：跳过 Embedding，按目录多样性 + 修改时间采样 ────────
        console.rule("[bold]简化模式：跳过 Embedding，直接采样")
        samples = _simple_sample(extracted, target=min(150, len(extracted)))
        console.print(f"  → 采样 [green]{len(samples)}[/green] 篇文档送给分析")
        if not args.skip_confirm:
            console.print(f"  → 预计费用：约 ${len(samples) * 0.001:.3f}")
            if not Confirm.ask("确认继续？"):
                return
    else:
        # ── 标准路径：Embedding + ChromaDB + 聚类 ─────────────────────
        n_clusters = args.n_clusters or estimate_clusters(total_stored() + len(new_items))
        n_samples = n_clusters * args.top_k
        cost = cost_estimate(new_items, n_samples)

        cost_table = Table(title="费用预估（本次新增部分）", show_header=True, header_style="bold yellow")
        cost_table.add_column("项目", style="cyan")
        cost_table.add_column("数值", justify="right")
        for k, v in cost.items():
            cost_table.add_row(k, str(v))
        console.print(cost_table)

        if not args.skip_confirm and new_items:
            if not Confirm.ask("确认继续？"):
                console.print("已取消。")
                return

        console.rule("[bold]阶段 3 / 5  Embedding & 存入 ChromaDB")
        if new_items:
            with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                          BarColumn(), TaskProgressColumn(), console=console) as p:
                task = p.add_task("Embedding 中...", total=len(new_items))
                added = embed_and_store(new_items, progress_cb=lambda n: p.advance(task, n))
            console.print(f"  → 新增 [green]{added}[/green] 条，ChromaDB 总量：[green]{total_stored()}[/green] 条")
        else:
            console.print(f"  → 无新文件，ChromaDB 当前共 [green]{total_stored()}[/green] 条")

        console.rule("[bold]阶段 4 / 5  聚类采样")
        console.print(f"  → 从 {total_stored()} 条文档中，聚 {n_clusters} 个主题，每个取 {args.top_k} 篇代表...")
        paths, embeddings, texts = get_all_embeddings()
        samples = cluster_and_sample(paths, embeddings, texts,
                                      n_clusters=n_clusters,
                                      top_k_per_cluster=args.top_k)
        console.print(f"  → 采样完成，共 [green]{len(samples)}[/green] 篇代表文档送给分析")

    # ── 阶段5：Claude 分析 ────────────────────────────────────────
    console.rule("[bold]阶段 5 / 5  Claude 分析 & 生成画像")

    # 5a. 分析文档
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

    # 5b. 浏览器历史
    browser_records = scan_browser_history(home)
    if browser_records:
        console.print(f"  → 分析浏览历史（{len(browser_records)} 条）...")
        try:
            browser_profile = analyze_browser_history(browser_records)
            fragments.append({"浏览行为分析": browser_profile})
        except Exception as e:
            console.print(f"  [yellow]浏览历史分析失败：{e}[/yellow]")

    # 5c. 合并最终画像
    console.print("  → 合并所有片段，生成最终用户画像...")
    try:
        final_profile = merge_profiles(fragments)
    except Exception as e:
        console.print(f"  [red]合并失败：{e}[/red]")
        final_profile = {"fragments": fragments}

    # ── 写入 Wiki（主输出）────────────────────────────────────────
    console.print("  → 写入 Wiki 知识库...")
    try:
        wiki_root = init_wiki()
        write_profile_to_wiki(final_profile, wiki_root)
        append_log(f"完整扫描完成，分析 {len(extracted)} 个文件，采样 {len(samples)} 篇", wiki_root)
        console.print(f"  → Wiki 框架已写入：[green]{wiki_root}[/green]")
    except Exception as e:
        console.print(f"  [yellow]Wiki 写入失败：{e}，降级保存 JSON[/yellow]")

    # ── 阶段6：填充项目页详细内容 ─────────────────────────────────
    projects = final_profile.get("近期项目", [])
    if projects and not isinstance(projects, str):
        console.rule(f"[bold]阶段 6 · 填充 {len(projects)} 个项目页详细内容")
        from core.analyzer import generate_project_page
        from wiki.wiki_manager import update_page

        with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                      BarColumn(), TaskProgressColumn(), console=console) as p:
            task = p.add_task("填充中...", total=len(projects))
            for proj in projects:
                # 提取项目关键词（取前5个字符）作为搜索关键词
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

        console.print(f"  → [green]{len(projects)}[/green] 个项目页已填充详细内容")

    # 同时保留 JSON 备份
    out_path = Path(args.out)
    out_path.write_text(json.dumps(final_profile, ensure_ascii=False, indent=2), encoding="utf-8")

    console.print(f"\n[bold green]完成！[/bold green]")
    console.print(f"  Wiki：[cyan]{init_wiki()}[/cyan]")
    console.print(f"  JSON 备份：[cyan]{out_path.absolute()}[/cyan]")
    _print_summary(final_profile)


def _print_summary(profile: dict):
    if "raw" in profile:
        console.print(Panel(profile["raw"], title="用户画像"))
        return

    table = Table(title="用户画像摘要", show_header=True, header_style="bold magenta")
    table.add_column("维度", style="cyan", width=18)
    table.add_column("内容")

    skip_keys = {"高频关键词", "fragments"}
    for k, v in profile.items():
        if k in skip_keys:
            continue
        if isinstance(v, list):
            val = "、".join(str(i) for i in v[:6])
        elif isinstance(v, dict):
            val = "  |  ".join(f"{dk}: {', '.join(dv) if isinstance(dv, list) else dv}"
                               for dk, dv in list(v.items())[:3])
        else:
            val = str(v)
        table.add_row(k, val)

    console.print(table)

    summary = profile.get("画像总结", "")
    if summary:
        console.print(Panel(f"[bold]{summary}[/bold]", title="综合描述"))


if __name__ == "__main__":
    main()
