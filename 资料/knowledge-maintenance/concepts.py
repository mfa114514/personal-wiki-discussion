"""Concept identities and evidence are separate from course-file identities."""
from __future__ import annotations

import re
from pathlib import PurePosixPath

from markdown_notes import normalized


def _matches(text: str, form: str):
    prefix = r"(?<![A-Za-z0-9_])" if re.match(r"^[A-Za-z0-9]", form) else ""
    suffix = r"(?![A-Za-z0-9_])" if re.search(r"[A-Za-z0-9]$", form) else ""
    return re.finditer(prefix + re.escape(form) + suffix, text, re.IGNORECASE)


def discover_concepts(selection: dict, nodes: dict, vault_markdown: list[str]) -> dict:
    source = selection["source"]
    if source not in nodes:
        raise ValueError("词条提取的来源文件没有被解析。")
    result = {}
    for item in selection["concepts"]:
        title = item["title"]
        evidence = []
        for path, note in nodes.items():
            for segment in note["segments"]:
                if segment["heading"] == "相关词条":
                    continue  # A generated footer must not support its own extraction.
                match = next((m for form in item["forms"] for m in _matches(segment["text"], form)), None)
                if match:
                    evidence.append({"source": path, "line": segment["line"] + segment["text"][:match.start()].count("\n"), "heading": segment["heading"], "quote": segment["text"][max(0,match.start()-35):match.end()+80].replace("\n", " "), "evidence_type": "text_mention"})
        source_evidence = [e for e in evidence if e["source"] == source]
        if item.get("reviewed_heading"):
            heading = next((h for h in nodes[source]["headings"] if h["text"] == item["reviewed_heading"]), None)
            if not heading:
                raise ValueError(f"经阅读判断的词条 {title} 的来源章节已经变化。")
            source_evidence.append({"source": source, "line": heading["line"], "heading": heading["text"], "quote": heading["text"], "evidence_type": "AI_reviewed_section_and_formula"})
        if not source_evidence:
            raise ValueError(f"词条 {title} 没有找到提取依据，拒绝生成无依据词条。")
        targets = [p for p in vault_markdown if normalized(PurePosixPath(p).stem) == normalized(title)]
        status = "has_page" if len(targets) == 1 else "ambiguous_page" if targets else "pending_explanation"
        result[title] = {"id": title, "title": title, "kind": "concept", "group": item["group"], "surface_forms": item["forms"], "status": status, "page_candidates": targets, "extraction_source": source, "extraction_evidence": source_evidence[:2], "mentioned_in": sorted({e["source"] for e in evidence}), "mentions": evidence, "selection_method": selection["selection_method"], "note": item.get("note", "")}
    return result


def classify_concept_edges(edges: list[dict], concepts: dict) -> list[dict]:
    by_name = {normalized(name): item for name, item in concepts.items()}
    results = []
    for edge in edges:
        copy = dict(edge)
        target = edge["target"].partition("#")[0].removesuffix(".md")
        concept = by_name.get(normalized(target)) if edge["kind"] == "wiki" else None
        if concept:
            copy["target_kind"] = "concept"
            copy["concept_id"] = concept["id"]
            if edge["status"] == "unresolved_in_scope":
                if concept["status"] == "pending_explanation":
                    copy["status"] = "pending_concept"
                elif concept["status"] == "ambiguous_page":
                    copy["status"] = "ambiguous"
                    copy["candidates"] = concept["page_candidates"]
                else:
                    copy["status"] = "concept_page_outside_scope"
                    copy["resolved"] = concept["page_candidates"][0]
                    copy["anchor_status"] = "not_checked" if "#" in edge["target"] else "none"
        results.append(copy)
    return results
