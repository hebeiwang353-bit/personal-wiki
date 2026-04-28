"""
用 AI 分析文件批次，输出结构化用户画像片段，并写入 Wiki。
后端通过 core.provider 模块统一接入，支持所有主流厂商。
"""

import json
from core.provider import call_chat


def _call(prompt: str, max_tokens: int = 2000) -> str:
    """统一调用入口，对接 provider 抽象层。"""
    return call_chat(prompt, max_tokens=max_tokens)


# ── 批次分析 ──────────────────────────────────────────────────

def analyze_batch(batch: list[dict]) -> dict:
    """batch: [{"path": str, "text": str}, ...]"""
    docs_block = ""
    for i, item in enumerate(batch, 1):
        docs_block += f"\n\n---文件{i}: {item['path']}---\n{item['text']}"

    prompt = f"""你是一名用户行为分析师。以下是用户电脑中的部分文件内容。
请仔细阅读，提炼出关于这个用户的信息，输出 JSON 格式：

{{
  "职业/角色": "判断用户的职业或主要角色",
  "专业领域": ["领域1", "领域2"],
  "工作内容": ["具体工作事项"],
  "兴趣爱好": ["兴趣1"],
  "常用工具": ["工具/软件1"],
  "工作习惯": ["习惯描述1"],
  "知识水平": "对某些领域的掌握程度描述",
  "近期项目": ["正在做的事情"],
  "关键词": ["高频出现的重要词汇"]
}}

只输出 JSON，不要有其他文字。如果某个字段信息不足，填空列表或空字符串。

用户文件内容：{docs_block}"""

    return _parse_json(_call(prompt, 2000))


def merge_profiles(fragments: list[dict]) -> dict:
    """把多个分析片段合并成最终用户画像。浏览历史会被明确降权。"""
    file_fragments = [f for f in fragments if "浏览行为分析" not in f]
    browser_fragments = [f["浏览行为分析"] for f in fragments if "浏览行为分析" in f]

    file_json = json.dumps(file_fragments, ensure_ascii=False, indent=2)
    browser_json = json.dumps(browser_fragments, ensure_ascii=False, indent=2) if browser_fragments else ""

    prompt = f"""以下是对用户电脑文件的分析结果（**主要依据**）。
请综合所有片段，生成一份完整、准确的用户画像，输出 JSON：

【主要依据 · 文件内容分析】
{file_json}

"""
    if browser_json:
        prompt += f"""【次要参考 · 浏览器历史】
注意：浏览历史只反映用户的临时关注点和好奇心，**不要让它主导职业判断**。
仅用作"兴趣爱好"和"近期热点关注"的辅助信息。
{browser_json}

"""
    prompt += """请综合判断（以文件内容为主），输出 JSON：

{
  "姓名": "如果能推断出则填写，否则留空",
  "职业": "最可能的职业（以文件内容为准，不要被浏览历史误导）",
  "专业领域": ["主要领域"],
  "工作内容": ["核心工作事项"],
  "兴趣爱好": ["爱好"],
  "常用工具": ["工具/软件"],
  "工作习惯": ["习惯"],
  "知识结构": {
    "精通": ["领域"],
    "熟悉": ["领域"],
    "了解": ["领域"]
  },
  "近期项目": ["项目描述"],
  "行为特征": ["特征描述"],
  "高频关键词": ["词"],
  "画像总结": "2-3句话的综合描述"
}

只输出 JSON，不要任何其他文字。"""

    return _parse_json(_call(prompt, 3000))


def analyze_browser_history(records: list[dict]) -> dict:
    """分析浏览历史，提炼用户的关注点和习惯（限量降权）"""
    titles = [r["title"] for r in records if r.get("title")][:150]
    titles_text = "\n".join(titles)

    prompt = f"""以下是用户的浏览器历史记录标题列表。
请分析用户的网络行为习惯和关注领域，输出 JSON：

{{
  "主要关注领域": ["领域1"],
  "常用网站类型": ["类型描述"],
  "学习/工作相关": ["主题"],
  "娱乐/生活相关": ["主题"],
  "近期热点关注": ["话题"]
}}

只输出 JSON。

浏览标题：
{titles_text}"""

    return _parse_json(_call(prompt, 1500))


def determine_affected_pages(new_content_summary: str, existing_pages: list[str]) -> list[str]:
    """增量更新时，判断哪些 Wiki 页面需要更新（最多10个）。"""
    pages_list = "\n".join(f"- {p}" for p in existing_pages)
    prompt = f"""用户有以下 Wiki 页面：
{pages_list}

新加入的文件内容摘要：
{new_content_summary[:2000]}

请判断哪些页面需要根据这些新信息更新，返回 JSON 列表（最多10个页面路径）：
["me.md", "projects/xxx.md"]

只输出 JSON 数组。"""

    result = _parse_json(_call(prompt, 500))
    return result if isinstance(result, list) else ["me.md"]


def generate_project_page(project_name: str, related_files: list[dict]) -> str:
    """根据项目名 + 相关文件内容，生成项目 Wiki 页面的 Markdown 正文。"""
    if not related_files:
        return f"# {project_name}\n\n（暂无相关文件信息，待后续扫描补充）\n"

    blocks = []
    for f in related_files[:6]:
        text = f["text"][:1500]
        blocks.append(f"--- 文件: {f['path']} ---\n{text}")
    files_text = "\n\n".join(blocks)

    prompt = f"""你正在为用户的本地知识库写一篇项目页面。
项目名称：{project_name}

以下是该项目相关的文件内容：
{files_text}

请基于这些文件，写一篇结构化的项目页面，使用以下 Markdown 模板：

# {project_name}

## 项目目标
（1-2 句话说明这个项目要解决什么问题、面向什么用户）

## 技术栈
- 列出涉及的技术、框架、工具

## 当前进度
（基于文件内容判断项目处于什么阶段：初步规划/原型开发/已上线/暂停 等）

## 关键文件
- 列出 2-4 个最重要的文件路径（从上面给的相关文件中挑选）

## 备注
（任何值得记录的信息：踩坑、决策、待办等。如果文件里没有相关信息，可省略此节）

要求：
- 内容必须基于上面提供的文件内容，不要编造
- 如果某节信息不足，写"（信息不足）"或省略整节
- 整体长度控制在 200-400 字
- 只输出 Markdown，不要其他文字"""

    return _call(prompt, 800).strip()


def update_wiki_page(page_name: str, current_content: str, new_info: str) -> str:
    """增量更新单个 Wiki 页面，把 new_info 融合进 current_content。"""
    prompt = f"""你正在维护一个 Markdown Wiki 页面。
请将新信息融合进现有内容，保持原有结构，去除重复，补充新内容。
不要删除用户手动编辑的内容。只输出更新后的 Markdown，不要有其他文字。

页面名称：{page_name}

现有内容：
{current_content}

新信息：
{new_info}"""

    return _call(prompt, 2000).strip()


def _parse_json(text: str) -> dict | list:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text.strip())
    except Exception:
        return {"raw": text}
