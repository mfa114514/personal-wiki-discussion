"""This trial reads MAC and previews mentions pointing to the existing entry."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from urllib.parse import quote

TASK = Path(__file__).resolve().parent
sys.path.insert(0, str(TASK.parents[1]))

from analyze import MARKER, note_link, require_process_destination, write_owned
from concepts import _matches
from markdown_notes import parse_note


def preview() -> dict:
    require_process_destination(TASK)
    config = json.loads((TASK / "config.json").read_text(encoding="utf-8"))
    vault = (TASK / config["vault"]).resolve()
    source = vault / config["source"]
    entry = vault / "词条/InfoNCE.md"
    entry_hash = hashlib.sha256(entry.read_bytes()).hexdigest()
    mentions = []
    existing = Counter()
    manifest = {}
    originals = {}
    raw_count = 0
    # The existing page supplies the name. No dependency on the 13-item
    # extraction selection, and no inferred aliases in this bounded trial.
    title = entry.stem
    for path in sorted(source.rglob("*.md")):
        raw = path.read_bytes()
        relative = path.relative_to(vault).as_posix()
        manifest[relative] = hashlib.sha256(raw).hexdigest()
        originals[relative] = raw.decode("utf-8-sig").splitlines()
        raw_count += len(list(_matches(raw.decode("utf-8-sig"), title)))
        note = parse_note(raw, relative)
        for link in note["links"]:
            destination = link["target"].partition("#")[0].removesuffix(".md")
            if link["kind"] == "wiki" and destination in {title, "词条/" + title}:
                existing[relative] += 1
        for segment in note["segments"]:
            for match in _matches(segment["text"], title):
                line = segment["line"] + segment["text"][:match.start()].count("\n")
                if match.group().casefold() not in originals[relative][line - 1].casefold():
                    raise ValueError(f"解析位置与原文不一致：{relative}:{line}")
                mentions.append({
                    "source": relative, "line": line,
                    "is_heading": segment["is_heading"],
                    "heading": segment["heading"],
                    "excerpt": segment["text"][max(0, match.start() - 40):match.end() + 85].replace("\n", " "),
                })

    paths = sorted({item["source"] for item in mentions})
    prose = Counter(item["source"] for item in mentions if not item["is_heading"])
    headings = Counter(item["source"] for item in mentions if item["is_heading"])
    lines = [MARKER, "# InfoNCE：新词条回查预览", "",
        "这次从已经存在的 InfoNCE 词条出发，查找 MAC 旧材料中的未链接提及。它检验的是回查和补标机会，不是在重新选择这批材料应该引出哪些核心词条。", "",
        "这是只读预览；源笔记、正式词条和 13 项文末列表没有改动。这里只匹配 InfoNCE 这个明确名称，没有推断或添加别名，也没有扫描全库。", "",
        f"范围：{config['source']}，共 {len(manifest)} 个 Markdown 文件。已有目标：{note_link(entry.relative_to(vault).as_posix(), 'InfoNCE 词条')}。", "",
        f"解析找到 **{len(mentions)} 处未链接提及，分布在 {len(paths)} 个文件**：正文 {sum(prose.values())} 处，标题 {sum(headings.values())} 处。已有显式 Wiki Link {sum(existing.values())} 处。原始文本搜索有 {raw_count} 次命中，包含数学内容和已有链接，不能直接作为补链数量。", "",
        "正文和标题均列出，尚未决定重复出现时标注几次。一个文件已有文末链接，也不会因此跳过其正文提及。代码、数学内容和已有链接标签不进入这些候选。", "",
        "## 文件分布", "",
        "| 文件 | 正文提及 | 标题提及 | 已有链接 |",
        "| --- | ---: | ---: | ---: |"]
    for relative in paths:
        # A Wikilink alias uses '|', which conflicts with Markdown table cells.
        href = quote(Path(os.path.relpath(vault / relative, TASK)).as_posix())
        label = PurePosixPath(relative).stem.replace("]", "\\]")
        lines.append(f"| [{label}]({href}) | {prose[relative]} | {headings[relative]} | {existing[relative]} |")

    lines.extend(["", "## 三处具体补链预览", "",
        "下面只展示可讨论的文本变化，不会执行它们。已有链接的文件和未有链接的文件都可以继续补正文链接。", ""])
    examples = (("03. 表示空间的几何结构.md", 481),
                ("07. 无负样本学习、表示坍缩、自蒸馏.md", 3),
                ("06. 对比学习与InfoNCE.md", 485))
    for filename, number in examples:
        relative = next(path for path in paths if PurePosixPath(path).name == filename)
        item = next((item for item in mentions if item["source"] == relative and item["line"] == number and not item["is_heading"]), None)
        if item is None:
            raise ValueError(f"已选预览位置发生变化：{filename}:{number}")
        before = originals[relative][number - 1]
        after = before.replace(title, f"[[{title}]]", 1)
        lines.extend([f"### {filename}，第 {number} 行", "",
            f"来源：{note_link(relative, filename, item['heading'])}", "",
            "```text", "原文：" + before, "预览：" + after, "```", ""])

    lines.extend(["## 全部未链接位置", "",
        "这些是文字提及，不表示材料之间已确认语义关系。标题位置单列为候选，不默认改写标题。段落中的重复出现也全部保留，方便讨论标注频度。", ""])
    for relative in paths:
        lines.extend(["### " + PurePosixPath(relative).stem, "", note_link(relative, "打开原文"), ""])
        for item in mentions:
            if item["source"] != relative:
                continue
            kind = "标题" if item["is_heading"] else "正文"
            lines.append(f"- 第 {item['line']} 行（{kind}）：{item['excerpt']}")
        lines.append("")

    current = {path.relative_to(vault).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in source.rglob("*.md")}
    if current != manifest or hashlib.sha256(entry.read_bytes()).hexdigest() != entry_hash:
        raise ValueError("材料或词条在预览期间发生变化，请重新运行。")
    lines.extend(["## 本轮限制与下一步", "",
        "这是单词条、单组材料的回查实验，不是日常自动补链器。现有日常分析仍依赖手选词条清单；全库词条目录、别名歧义、重叠名称和自动应用尚未接入。", "",
        "接下来讨论正文补链的重复频度及标题处理，再决定是否在一篇材料中试用。已有词条的明确名称可以逐步承担机械补链；新概念发现、别名判断及内容讲解仍需另行判断。", "",
        "预览生成前后，本轮全部材料及词条内容哈希一致；只写入任务目录中的这份报告。", ""])
    write_owned(TASK / "InfoNCE回查预览.md", "\n".join(lines))
    return {"files_read": len(manifest), "files_with_mentions": len(paths),
            "unlinked_mentions": len(mentions), "prose": sum(prose.values()),
            "headings": sum(headings.values()), "existing_links": sum(existing.values()),
            "source_unchanged": True}


if __name__ == "__main__":
    print(json.dumps(preview(), ensure_ascii=True))
