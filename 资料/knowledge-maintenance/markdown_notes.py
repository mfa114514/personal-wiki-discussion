"""Parse local Markdown without treating code or existing link labels as mentions."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

import yaml
from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.dollarmath.index import math_block_dollar


def normalized(value: str) -> str:
    return unicodedata.normalize("NFC", value).casefold()


def display_title(stem: str) -> str:
    return re.sub(r"^[ab]?\d+(?:\.\d+)*[.、\s]+", "", stem).strip() or stem


def wiki_rule(state, silent: bool) -> bool:
    start = state.pos
    embed = state.src.startswith("![[", start)
    opener = 3 if embed else 2
    if not embed and not state.src.startswith("[[", start):
        return False
    end = state.src.find("]]", start + opener, state.posMax)
    if end < 0:
        return False
    body = state.src[start + opener:end]
    if "\n" in body or "[[" in body or not body.strip():
        return False
    parts = re.split(r"(?<!\\)\|", body, maxsplit=1)
    if not silent:
        token = state.push("wiki", "", 0)
        token.content = body
        token.meta = {
            "target": parts[0].strip(),
            "label": parts[1] if len(parts) > 1 else parts[0],
            "embed": embed,
            "offset": start,
        }
    state.pos = end + 2
    return True


def parser() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": True}).enable("table").use(dollarmath_plugin)
    # Obsidian allows display math directly after a paragraph. Make it a
    # paragraph terminator, so a standalone '=' inside math is not a heading.
    md.block.ruler.at("math_block", math_block_dollar(True, lambda value: value, True), {"alt": ["paragraph", "reference", "blockquote"]})
    md.inline.ruler.before("link", "wiki", wiki_rule)
    return md


def _string_list(value, name: str, warnings: list[str]) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        warnings.append(f"{name} 使用单个字符串；已兼容读取，未修改原文件。")
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(dict.fromkeys(value))
    warnings.append(f"{name} 格式无法识别，未作为匹配词使用。")
    return []


def parse_note(raw: bytes, relative_path: str) -> dict:
    text = raw.decode("utf-8-sig")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.splitlines(keepends=True)
    body = text
    metadata = {}
    warnings = []
    if lines and lines[0].strip() == "---":
        closing = next((i for i in range(1, len(lines)) if lines[i].strip() in {"---", "..."}), None)
        if closing is None:
            warnings.append("开头有 YAML 分隔符，但没有结束分隔符；按正文解析。")
        else:
            try:
                data = yaml.safe_load("".join(lines[1:closing]))
                if data is not None and not isinstance(data, dict):
                    warnings.append("YAML 属性不是键值结构，未用作页面属性。")
                else:
                    metadata = data or {}
            except yaml.YAMLError:
                warnings.append("YAML 属性解析失败；正文仍继续解析。")
            # Keep line numbers equal to the original source.
            body = "\n" * (closing + 1) + "".join(lines[closing + 1:])

    aliases = _string_list(metadata.get("aliases"), "aliases", warnings)
    tags = _string_list(metadata.get("tags"), "tags", warnings)
    title = metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        title = display_title(Path(relative_path).stem)

    tokens = parser().parse(body)
    headings = []
    segments = []
    links = []
    heading = ""
    for index, block in enumerate(tokens):
        if block.type != "inline":
            continue
        start_line = (block.map or [0])[0] + 1
        is_heading = index > 0 and tokens[index - 1].type == "heading_open"
        if is_heading:
            heading = "".join(("$" + child.content + "$") if child.type == "math_inline" else child.content for child in block.children or [] if child.type in {"text", "code_inline", "wiki", "math_inline"})
            headings.append({"text": heading, "line": start_line, "level": int(tokens[index - 1].tag[1:])})
        depth = 0
        cursor = 0
        for child in block.children or []:
            if child.type == "link_open":
                depth += 1
                links.append({"kind": "markdown", "target": child.attrGet("href") or "", "line": start_line, "heading": heading, "embed": False})
            elif child.type == "link_close":
                depth -= 1
            elif child.type == "image":
                links.append({"kind": "markdown", "target": child.attrGet("src") or "", "line": start_line, "heading": heading, "embed": True})
            elif child.type == "wiki":
                offset = child.meta["offset"]
                links.append({"kind": "wiki", "target": child.meta["target"], "label": child.meta["label"], "line": start_line + block.content[:offset].count("\n"), "heading": heading, "embed": child.meta["embed"]})
            elif child.type == "text" and depth == 0 and child.content.strip():
                offset = block.content.find(child.content, cursor)
                if offset < 0:
                    offset = cursor
                cursor = offset + len(child.content)
                # Inline code, HTML and link labels never enter these segments.
                segments.append({"text": child.content, "line": start_line + block.content[:offset].count("\n"), "heading": heading, "is_heading": is_heading})
    for segment in segments:
        for tag in re.findall(r"(?<![\w/#])#([\w/-]+)", segment["text"]):
            if not tag.isdigit():
                tags.append(tag)
    return {
        "path": relative_path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "title": title,
        "aliases": aliases,
        "tags": sorted(set(tags)),
        "headings": headings,
        "segments": segments,
        "links": links,
        "warnings": warnings,
    }


def title_terms(note: dict) -> list[dict]:
    """Inferred title fragments are suggestions, never formal aliases or links."""
    explicit = [{"text": note["title"], "origin": "title"}]
    explicit += [{"text": alias, "origin": "alias"} for alias in note["aliases"]]
    stem_title = display_title(Path(note["path"]).stem)
    if stem_title != note["title"]:
        explicit.append({"text": stem_title, "origin": "filename"})
    fragments = re.split(r"[与、，,:：]|\s+(?=[A-Za-z])", stem_title)
    for fragment in fragments:
        fragment = fragment.strip(" \"“”‘’")
        if 3 <= len(fragment) <= 32 and not any(word in fragment for word in ("计划", "总结", "框架", "统一", "如何", "完整", "限制")):
            explicit.append({"text": fragment, "origin": "inferred_title_fragment"})
    seen = set()
    results = []
    for term in explicit:
        key = normalized(term["text"])
        if 3 <= len(term["text"]) <= 64 and key not in seen:
            seen.add(key)
            results.append(term)
    return results
