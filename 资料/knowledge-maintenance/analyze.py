"""Read a selected part of a vault; write only owned, rebuildable task outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from markdown_notes import display_title, normalized, parse_note
from concepts import classify_concept_edges, discover_concepts

GENERATOR = "knowledge-maintenance-v1"
MARKER = "<!-- knowledge-maintenance:generated -->"
VERSION = 2


def within(path: Path, parent: Path) -> bool:
    return path.resolve().is_relative_to(parent.resolve())


def require_process_destination(path: Path) -> None:
    reserved = Path(__file__).resolve().parent / "output"
    if within(path, reserved):
        raise ValueError("output 是用户点名收录的成果目录；自动过程文件请放在 tasks 等目录。")


def write_owned(path: Path, content: str) -> None:
    require_process_destination(path)
    if path.exists():
        old = path.read_text(encoding="utf-8")
        owned = old.startswith(MARKER) if path.suffix == ".md" else json.loads(old).get("generator") == GENERATOR
        if not owned:
            raise ValueError(f"拒绝覆盖未标记为工具产物的文件：{path}")
        if old == content:
            return
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(content, encoding="utf-8", newline="\n")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def json_text(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def note_link(path: str, label: str | None = None, heading: str = "") -> str:
    if any(character in heading for character in ("$", "\\", "|", "\n", "]")):
        heading = ""  # Open the real file rather than emit an uncertain math anchor.
    target = path.removesuffix(".md") + ("#" + heading if heading else "")
    safe_label = (label or display_title(PurePosixPath(path).stem)).replace("|", "／").replace("]", "）").replace("\n", " ")
    return f"[[{target}|{safe_label}]]"


def resolve_link(link: dict, source: str, files: list[str], nodes: dict, vault: Path) -> dict:
    raw = link["target"]
    url = urlsplit(raw)
    edge = {"source": source, **link}
    if url.scheme or raw.startswith("//"):
        return {**edge, "status": "external", "resolved": None}
    if link["kind"] == "wiki":
        file_part, _, anchor = raw.partition("#")
        file_part = unquote(file_part).replace("\\", "/")
        # A dot in a note title (e.g. '1.3 logit') is not a file extension.
        options = [file_part] if file_part.lower().endswith(".md") else [file_part + ".md", file_part]
        if not file_part:
            candidates = [source]
        else:
            local = [str(PurePosixPath(source).parent / item) for item in options]
            candidates = [p for p in files if normalized(p) in {normalized(x) for x in local}]
            if not candidates:
                candidates = [p for p in files if normalized(p) in {normalized(x.lstrip("/")) for x in options}]
            if not candidates and "/" not in file_part:
                candidates = [p for p in files if normalized(PurePosixPath(p).name) in {normalized(x) for x in options}]
        unresolved_status = "unresolved_in_scope"
    else:
        file_part, anchor = unquote(url.path), unquote(url.fragment)
        destination = (vault / source).parent / file_part if file_part else vault / source
        if file_part.startswith("/"):
            destination = vault / file_part.lstrip("/")
        if not within(destination, vault):
            return {**edge, "status": "outside_vault", "resolved": None}
        relative = destination.resolve().relative_to(vault.resolve()).as_posix()
        options = [relative] if relative.lower().endswith(".md") else [relative, relative + ".md"]
        candidates = [p for p in files if normalized(p) in {normalized(x) for x in options}]
        if not candidates:
            existing = next((item for item in options if (vault / item).is_file()), None)
            if existing:
                return {**edge, "status": "outside_analysis_scope", "resolved": existing, "anchor": anchor, "anchor_status": "not_checked"}
        unresolved_status = "missing_local_file"
    if len(candidates) > 1:
        return {**edge, "status": "ambiguous", "resolved": None, "candidates": candidates}
    if not candidates:
        return {**edge, "status": unresolved_status, "resolved": None}
    target = candidates[0]
    anchor_status = "none"
    if anchor:
        if anchor.startswith("^") or "#" in anchor:
            anchor_status = "not_checked"
        elif target not in nodes:
            anchor_status = "not_checked"
        else:
            headings = {normalized(h["text"]) for h in nodes[target]["headings"]}
            github_slugs = {re.sub(r"[^\w\- ]", "", h).replace(" ", "-") for h in headings}
            anchor_status = "found" if normalized(anchor) in headings | github_slugs else "not_found"
    return {**edge, "status": "resolved", "resolved": target, "anchor": anchor, "anchor_status": anchor_status}


def role(note: dict) -> str:
    stem = PurePosixPath(note["path"]).stem
    if "计划" in stem or "prompt" in stem.casefold():
        return "planning"
    if "总结" in stem:
        return "summary"
    return "lesson"


def markdown_inventory(vault: Path, tool_directory: Path) -> list[str]:
    """Check actual concept-page names without reading the whole vault's content."""
    ignored = {".git", ".obsidian", ".trash", ".venv", ".codex", ".agents", ".idea", "node_modules", "__pycache__"}
    files = []
    for root, directories, names in os.walk(vault, followlinks=False):
        base = Path(root)
        directories[:] = [name for name in directories if name not in ignored and not (base / name).is_symlink() and (base / name).resolve() != tool_directory.resolve()]
        for name in names:
            path = base / name
            if path.suffix.lower() == ".md" and not path.is_symlink():
                files.append(path.relative_to(vault).as_posix())
    return sorted(files)


def run(config_path: Path, force: bool = False) -> dict:
    config_path = config_path.resolve()
    require_process_destination(config_path.parent)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    output = config_path.parent
    vault = (output / config["vault"]).resolve()
    source = (vault / config["source"]).resolve()
    if not source.is_dir() or not within(source, vault):
        raise ValueError("输入目录必须存在并位于知识库内。")
    if within(output, source) or within(source, output):
        raise ValueError("输入与产物目录必须分开，禁止向原始材料目录写入。")
    lock = output / ".analysis.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as error:
        raise RuntimeError("本轮已有运行锁；请先确认是否仍在运行。") from error
    try:
        with handle:
            handle.write(str(os.getpid()))
        fingerprint = hashlib.sha256(Path(__file__).with_name("markdown_notes.py").read_bytes()).hexdigest()
        cache_path = output / "index.json"
        previous = {}
        if cache_path.exists():
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("generator") != GENERATOR:
                raise ValueError("index.json 不是本工具的产物。")
            if not force and cached.get("parser_fingerprint") == fingerprint and cached.get("source") == config["source"]:
                previous = cached.get("notes", {})
        nodes = {}
        hashes = {}
        files = []
        failures = []
        parsed = 0
        for path in sorted(source.rglob("*")):
            if not path.is_file():
                continue
            if path.is_symlink() or not within(path, source):
                raise ValueError(f"输入含指向范围外的文件：{path.name}")
            relative = path.relative_to(vault).as_posix()
            files.append(relative)
            if path.suffix.lower() != ".md":
                continue
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            hashes[relative] = digest
            if previous.get(relative, {}).get("sha256") == digest:
                nodes[relative] = previous[relative]
            else:
                try:
                    nodes[relative] = parse_note(raw, relative)
                    parsed += 1
                except UnicodeError:
                    failures.append({"path": relative, "reason": "不是可读取的 UTF-8 Markdown；未修改原文件。"})
        # Compute relations across all current nodes, including reused nodes.
        edges = [resolve_link(link, path, files, nodes, vault) for path, note in nodes.items() for link in note["links"]]
        concepts = {}
        concept_pages = {}
        concept_page_parsed = 0
        page_cache = cached.get("concept_pages", {}) if previous else {}
        if config.get("concept_selection"):
            selection_path = (output / config["concept_selection"]).resolve()
            if not within(selection_path, output):
                raise ValueError("词条选择文件必须位于本轮任务目录。")
            selection = json.loads(selection_path.read_text(encoding="utf-8"))
            concepts = discover_concepts(selection, {path: note for path, note in nodes.items() if role(note) == "lesson"}, markdown_inventory(vault, Path(__file__).parent))
            for concept in concepts.values():
                if concept["status"] != "has_page":
                    continue
                path = concept["page_candidates"][0]
                if path in nodes:
                    concept_pages[path] = nodes[path]
                    continue
                raw = (vault / path).read_bytes()
                digest = hashlib.sha256(raw).hexdigest()
                if page_cache.get(path, {}).get("sha256") == digest:
                    concept_pages[path] = page_cache[path]
                else:
                    concept_pages[path] = parse_note(raw, path)
                    concept_page_parsed += 1
            all_nodes = {**nodes, **concept_pages}
            all_files = sorted(set(files) | set(concept_pages))
            edges = [resolve_link(link, path, all_files, all_nodes, vault) for path, note in all_nodes.items() for link in note["links"]]
            edges = classify_concept_edges(edges, concepts)
            page_identities = {item["page_candidates"][0]: item["id"] for item in concepts.values() if item["status"] == "has_page"}
            for edge in edges:
                edge["source_kind"] = "concept" if edge["source"] in page_identities else "material"
                if edge["source"] in page_identities:
                    edge["source_concept_id"] = page_identities[edge["source"]]
        backlinks = defaultdict(list)
        for edge in edges:
            if edge.get("resolved") and edge["status"] in {"resolved", "concept_page_outside_scope"}:
                backlinks[edge["resolved"]].append({"source": edge["source"], "line": edge["line"], "heading": edge["heading"]})
        concept_references = [edge for edge in edges if edge.get("target_kind") == "concept"]
        concept_relations = [edge for edge in concept_references if edge["source_kind"] == "concept"]
        changed = {
            "added": sorted(set(nodes) - set(previous)),
            "modified": sorted(p for p in nodes if p in previous and nodes[p]["sha256"] != previous[p]["sha256"]),
            "removed_from_scope": sorted(set(previous) - set(hashes)),
        }
        page_changes = {"added": sorted(set(concept_pages)-set(page_cache)), "modified": sorted(path for path in concept_pages if path in page_cache and concept_pages[path]["sha256"] != page_cache[path]["sha256"]), "removed_from_selection": sorted(set(page_cache)-set(concept_pages))}
        warnings = [{"path": path, "warning": warning} for path, note in {**nodes, **concept_pages}.items() for warning in note["warnings"]]
        stats = {"files": len(files), "markdown": len(nodes), "other_files": len(files)-len(hashes), "parsed": parsed, "reused": len(nodes)-parsed, "concept_pages": len(concept_pages), "concept_pages_parsed": concept_page_parsed, "concept_pages_reused": len(concept_pages)-concept_page_parsed, "explicit_links": len(edges), "concepts": len(concepts), "pending_concepts": sum(c["status"] == "pending_explanation" for c in concepts.values()), "concept_references": len(concept_references), "concept_relations": len(concept_relations), "roles": dict(Counter(role(note) for note in nodes.values()))}
        # Verify the whole source manifest again before advancing the saved state.
        current_md = {p.relative_to(vault).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob("*") if p.is_file() and p.suffix.lower() == ".md"}
        if hashes != current_md:
            raise RuntimeError("扫描期间原材料发生变化；本轮未保存索引，请重跑。")
        if any(hashlib.sha256((vault / path).read_bytes()).hexdigest() != note["sha256"] for path, note in concept_pages.items()):
            raise RuntimeError("扫描期间词条讲解发生变化；本轮未保存索引，请重跑。")
        index = {"generator": GENERATOR, "schema_version": VERSION, "source": config["source"], "parser_fingerprint": fingerprint, "notes": nodes, "files": files, "concept_pages": concept_pages, "links": edges, "backlinks": dict(backlinks), "concepts": concepts, "concept_references": concept_references, "concept_relations": concept_relations, "warnings": warnings, "failures": failures}
        statuses = dict(Counter(e["status"] for e in edges))
        checks = {"generator": GENERATOR, "source": config["source"], "source_hashes": hashes, "concept_page_hashes": {path:note["sha256"] for path,note in concept_pages.items()}, "source_unchanged_during_run": True, "stats": stats, "changes": changed, "concept_page_changes": page_changes, "link_statuses": statuses, "parse_failures": failures, "warnings": warnings, "incremental_method": "content_sha256; no Git history yet", "external_urls_checked": False}
        report = [MARKER, "# MAC：词条提取与引用检查", "", f"本轮范围：`{config['source']}`。检查命令只读原材料及已存在的选定词条页；课程文末链接由单独的已核对预览追加。", "", f"读取 {stats['markdown']} 篇材料及 {len(concept_pages)} 篇词条讲解；已选择 {len(concepts)} 个词条，显式词条引用 {len(concept_references)} 条，其中词条间引用 {len(concept_relations)} 条。", "", "## 本轮词条", "", "本轮检查课程与选定词条之间的引用及词条间引用；这是 MAC 实验的范围，Wiki 中的其他内容仍保留各自的形式与用途。尚无文件的词条是待讲解节点，可先使用链接。", ""]
        for concept in concepts.values():
            status = {"has_page": "已有同名页面", "ambiguous_page": "存在多个同名页面，需辨认", "pending_explanation": "待讲解，目标文件可暂不存在"}[concept["status"]]
            evidence = concept["extraction_evidence"][0]
            evidence_type = "AI 根据章节与公式判断" if evidence["evidence_type"] == "AI_reviewed_section_and_formula" else "原文提及"
            report.extend([f"### {concept['title']}", "", f"状态：{status}。提取依据：{evidence_type}，{note_link(evidence['source'], heading=evidence['heading'])}，约第 {evidence['line']} 行。", "", "> " + evidence["quote"].replace("\n", " "), ""])
            if concept["status"] == "has_page":
                report.extend(["阅读词条：" + note_link(concept["page_candidates"][0], concept["title"]) + "。", ""])
            if concept["note"]:
                report.extend([concept["note"], ""])
        if not concepts:
            report.extend(["本轮尚未提供经过阅读选择的词条清单。", ""])
        report.extend(["## 当前找不到目标的本地引用", ""])
        missing = [edge for edge in edges if edge["status"] == "missing_local_file"]
        for edge in missing:
            report.extend([f"- {note_link(edge['source'], heading=edge['heading'])}：`{edge['target']}`，出处约第 {edge['line']} 行。", ""])
        if not missing:
            report.extend(["当前未发现路径明确但目标不存在的本地引用。", ""])
        report.extend(["## 检查与边界", "", f"本轮材料重新解析 {parsed} 篇，复用 {len(nodes)-parsed} 篇；词条讲解重新解析 {concept_page_parsed} 篇，复用 {len(concept_pages)-concept_page_parsed} 篇。变化识别暂用文件内容哈希；Git 的管理范围仍待共同决定。", "", f"链接状态统计：`{json.dumps(statuses, ensure_ascii=False)}`。解析失败 {len(failures)} 篇，属性提示 {len(warnings)} 条。", "", "词条提取来自本轮 AI 阅读选择，程序核对出处并找出这些词条在课程正文中的其他提及。提及记录不是已确认的词条间语义关系，也不会生成课程间互链。程序排除文末相关词条区，避免生成链接成为自身的提取依据。", "", "同名词条页检查先扫描全库文件名，排除工具和应用内部目录；只有本轮选定词条的唯一同名页会进一步读取和解析。未解析的其他 Wiki Link 只表示本轮范围内未找到目标。外部网址未联网检查；附件只检查引用，不解析其正文。块引用与多层标题引用暂不验证。", "", "完整机器记录在 index.json：concepts 是词条节点，concept_references 是显式词条引用，concept_relations 记录词条讲解中的词条引用并保留原文位置，不自动推断关系类型；notes 是来源内容解析，concept_pages 是已存在词条讲解的解析。来源及词条页哈希、变化和运行统计在 verification.json。派生数据均可重建，实质讲解以普通 Markdown 文件为准。", ""])
        # All read/parse checks complete before publishing any derived result.
        write_owned(output / "检查报告.md", "\n".join(report))
        write_owned(output / "verification.json", json_text(checks))
        write_owned(cache_path, json_text(index))
        return checks
    finally:
        lock.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="只读解析知识库的一组材料，生成本轮机器记录和报告。")
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--rebuild", action="store_true", help="跳过缓存，完整重建。")
    args = ap.parse_args()
    result = run(args.config, args.rebuild)
    print(json.dumps(result["stats"], ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
