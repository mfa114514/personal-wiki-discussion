"""Prepare and apply a bounded, append-only concept-footer edit to one course."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path

from analyze import GENERATOR, json_text, require_process_destination, within, write_owned
from concepts import discover_concepts
from markdown_notes import parse_note

def footer_for(selection: dict) -> str:
    groups = {}
    seen = set()
    for item in selection["concepts"]:
        title = item["title"]
        if title in seen or any(character in title for character in "\n\r|[]#"):
            raise ValueError("词条名重复或不能直接用于 Wiki Link。")
        seen.add(title)
        groups.setdefault(item["group"], []).append(f"[[{title}]]")
    rows = ["## 相关词条", ""]
    rows.extend(f"- {group}：{' · '.join(links)}" for group, links in groups.items())
    return "\n".join(rows)


def prepare(config_path: Path) -> dict:
    config_path = config_path.resolve()
    task = config_path.parent
    require_process_destination(task)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    vault = (task / config["vault"]).resolve()
    selection = json.loads((task / config["concept_selection"]).read_text(encoding="utf-8"))
    source = (vault / selection["source"]).resolve()
    allowed_source = (vault / config["source"]).resolve()
    if not within(source, allowed_source) or within(task, allowed_source) or not source.is_file():
        raise ValueError("本轮源文件必须位于已指定材料范围，且与产物分开。")
    before = source.read_bytes()
    text = before.decode("utf-8-sig")
    note = parse_note(before, selection["source"])
    if any(heading["text"] == "相关词条" for heading in note["headings"]):
        raise ValueError("原文已含相关词条区，本命令不自动覆盖；需重新讨论该区修改。")
    discover_concepts(selection, {selection["source"]: note}, [])
    footer = footer_for(selection)
    newline = "\r\n" if b"\r\n" in before else "\n"
    suffix = ("\n\n" + footer + "\n").replace("\n", newline).encode("utf-8")
    after = before + suffix
    backup = task / "source-before.txt"
    if backup.exists() and backup.read_bytes() != before:
        raise ValueError("已保存的修改前副本与当前原文不同，拒绝覆盖副本。")
    if not backup.exists():
        backup.write_bytes(before)
    diff_lines = difflib.unified_diff(text.splitlines(keepends=True), after.decode("utf-8-sig").splitlines(keepends=True), fromfile=selection["source"], tofile=selection["source"], n=4)
    diff = "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in diff_lines)
    (task / "链接预览.diff").write_text(diff, encoding="utf-8", newline="\n")
    plan = {"generator": GENERATOR, "source": selection["source"], "before_sha256": hashlib.sha256(before).hexdigest(), "after_sha256": hashlib.sha256(after).hexdigest(), "append_text": suffix.decode("utf-8"), "concepts": [item["title"] for item in selection["concepts"]], "original_bytes_preserved_as_prefix": True, "applied": False}
    write_owned(task / "link-edit.json", json_text(plan))
    return plan


def apply_preview(config_path: Path) -> dict:
    config_path = config_path.resolve()
    task = config_path.parent
    require_process_destination(task)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    vault = (task / config["vault"]).resolve()
    plan_path = task / "link-edit.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("generator") != GENERATOR:
        raise ValueError("编辑预览不是本工具的产物。")
    source = (vault / plan["source"]).resolve()
    require_process_destination(source)
    if not within(source, (vault / config["source"]).resolve()):
        raise ValueError("预览目标位于本轮范围之外。")
    before = source.read_bytes()
    digest = hashlib.sha256(before).hexdigest()
    if plan.get("applied") and digest == plan["after_sha256"]:
        return plan
    if digest != plan["before_sha256"] or (task / "source-before.txt").read_bytes() != before:
        raise ValueError("原文自预览后发生变化，拒绝应用过时预览。")
    suffix = plan["append_text"].encode("utf-8")
    after = before + suffix
    if hashlib.sha256(after).hexdigest() != plan["after_sha256"]:
        raise ValueError("预览内容与预期哈希不同。")
    # The requested edit is append-only. Preserve all original bytes and ACLs.
    with source.open("r+b") as handle:
        if hashlib.sha256(handle.read()).hexdigest() != plan["before_sha256"]:
            raise ValueError("应用时原文已变化。")
        handle.write(suffix)
        handle.flush()
    actual = source.read_bytes()
    if actual != after or not actual.startswith(before):
        raise RuntimeError("追加后校验失败；修改前副本已保留。")
    plan["applied"] = True
    write_owned(plan_path, json_text(plan))
    return plan


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="应用已经生成、哈希一致的单篇追加预览。")
    args = parser.parse_args()
    outcome = apply_preview(args.config) if args.apply else prepare(args.config)
    print(json.dumps({"source": outcome["source"], "concept_count": len(outcome["concepts"]), "applied": outcome["applied"]}, ensure_ascii=True))
