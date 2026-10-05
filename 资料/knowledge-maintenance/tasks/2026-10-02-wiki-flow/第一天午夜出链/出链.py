"""本轮三篇材料的人工选词记录，以及有边界检查的写入和核对。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
RUN = Path(__file__).resolve().parent
WORK = RUN.parent
REPO = WORK / "小知识库"
REVIEW_INDEX = WORK / "第一天午夜审核" / "git-review.index"
GIT = Path(r"D:\system\Git\cmd\git.exe")
sys.path.insert(0, str(WORK.parents[1]))
from markdown_notes import parse_note, parser

# 行号来自白天结束时的 Git 审阅索引。这里保存人工选择，不做关键词全局替换。
# 每项为 (原始行号, 原文显示文字, 独立词条页面名)。同义名称可以共用页面。
SELECTION = {
    "MAC01/1.1 神经网络如何“学习”.md": [
        (4, "神经网络", "神经网络"),
        (26, "训练数据集", "训练集"),
        (36, "向量", "向量"),
        (36, "矩阵", "矩阵"),
        (36, "张量", "张量"),
        (38, "训练样本", "训练样本"),
        (49, "可训练参数", "可训练参数"),
        (63, "线性模型", "线性模型"),
        (97, "优化器", "优化器"),
        (103, "参数", "模型参数"),
        (136, "激活值", "激活值"),
        (156, "反向传播", "反向传播"),
        (164, "状态", "训练状态"),
        (168, "动量", "动量优化"),
        (169, "Adam", "Adam"),
        (171, "学习率调度器", "学习率调度器"),
        (184, "checkpoint", "训练检查点"),
        (200, "损失函数", "损失函数"),
        (214, "回归任务", "回归任务"),
        (214, "均方误差", "均方误差"),
        (253, "经验风险", "经验风险"),
        (253, "经验风险最小化", "经验风险最小化"),
        (277, "前向传播", "前向传播"),
        (311, "PyTorch", "PyTorch"),
        (344, "梯度", "梯度"),
        (383, "学习率", "学习率"),
        (386, "梯度下降", "梯度下降"),
        (388, "AdamW", "AdamW"),
        (405, "平方损失", "平方损失"),
        (436, "学习率", "学习率"),
        (506, "反向传播", "反向传播"),
        (528, "链式法则", "链式法则"),
        (549, "反向传播", "反向传播"),
        (551, "优化器", "优化器"),
        (596, "计算图", "计算图"),
        (599, "自动微分", "自动微分"),
        (600, "reverse-mode automatic differentiation", "反向模式自动微分"),
        (669, "梯度累积", "梯度累积"),
        (675, "训练", "模型训练"),
        (686, "推理", "模型推理"),
        (727, "训练 step", "训练步"),
    ],
    "MAC01/1.2 从一次step到完整训练过程.md": [
        (27, "训练集", "训练集"),
        (37, "sample", "训练样本"),
        (63, "batch", "训练批次"),
        (65, "batch size", "批大小"),
        (71, "前向传播", "前向传播"),
        (77, "张量", "张量"),
        (94, "batch dimension", "批次维"),
        (114, "mini-batch", "小批次"),
        (120, "单样本训练", "单样本训练"),
        (125, "小批量训练", "小批量训练"),
        (130, "全批量训练", "全批量训练"),
        (141, "training step", "训练步"),
        (143, "forward", "前向传播"),
        (143, "backward", "反向传播"),
        (161, "gradient accumulation", "梯度累积"),
        (167, "epoch", "训练轮"),
        (198, "PyTorch", "PyTorch"),
        (256, "batch gradient descent", "全批量梯度下降"),
        (283, "activation", "激活值"),
        (322, "随机抽样", "随机抽样"),
        (342, "stochastic optimization", "随机优化"),
        (348, "SGD", "随机梯度下降"),
        (459, "batch size", "批大小"),
        (459, "超参数", "超参数"),
        (461, "learning rate", "学习率"),
        (497, "shuffle", "训练数据打乱"),
        (528, "时间序列", "时间序列"),
        (529, "自回归", "自回归"),
        (539, "训练循环", "训练循环"),
        (622, "优化器", "优化器"),
        (641, "training set", "训练集"),
        (663, "validation set", "验证集"),
        (675, "checkpoint", "训练检查点"),
        (676, "过拟合", "过拟合"),
        (678, "early stopping", "早停"),
        (693, "test set", "测试集"),
        (712, "data leakage", "数据泄漏"),
        (777, "Dropout", "Dropout"),
        (778, "Batch Normalization", "批归一化"),
        (784, "自动微分", "自动微分"),
    ],
    "MAC01/1.3 logit 概率 交叉熵.md": [
        (17, "神经网络", "神经网络"),
        (29, "向量", "向量"),
        (47, "logit", "Logit"),
        (72, "概率分布", "概率分布"),
        (74, "线性层", "线性层"),
        (103, "二分类", "二分类"),
        (120, "sigmoid", "Sigmoid"),
        (196, "log-odds", "对数几率"),
        (196, "logit", "Logit"),
        (235, "logistic regression", "逻辑回归"),
        (273, "softmax", "Softmax"),
        (284, "指数函数", "指数函数"),
        (363, "概率分布", "概率分布"),
        (369, "softmax", "Softmax"),
        (459, "多分类", "多分类"),
        (482, "指数族概率模型", "指数族概率模型"),
        (482, "极大似然估计", "极大似然估计"),
        (521, "negative log-likelihood", "负对数似然"),
        (591, "cross entropy", "交叉熵"),
        (613, "交叉熵", "交叉熵"),
        (621, "one-hot", "独热编码"),
        (683, "NLL", "负对数似然"),
        (684, "cross entropy", "交叉熵"),
        (703, "条件概率", "条件概率"),
        (710, "maximum likelihood estimation", "极大似然估计"),
        (712, "似然函数", "似然函数"),
        (796, "log-likelihood", "对数似然"),
        (813, "one-hot", "独热编码"),
        (873, "偏导", "偏导数"),
        (940, "梯度下降", "梯度下降"),
        (992, "softmax", "Softmax"),
        (992, "cross entropy", "交叉熵"),
        (998, "二分类", "二分类"),
        (1008, "binary cross entropy", "二元交叉熵"),
        (1038, "Bernoulli distribution", "伯努利分布"),
        (1038, "负对数似然", "负对数似然"),
        (1082, "PyTorch", "PyTorch"),
        (1095, "numerical stability", "数值稳定性"),
        (1110, "浮点数", "浮点数"),
        (1110, "overflow", "浮点上溢"),
        (1112, "softmax", "Softmax"),
        (1132, "log-sum-exp", "LogSumExp"),
    ],
}


def git(*args: str, review: bool = False) -> bytes:
    env = os.environ.copy()
    if review:
        env["GIT_INDEX_FILE"] = str(REVIEW_INDEX)
    else:
        env.pop("GIT_INDEX_FILE", None)
    return subprocess.run(
        [str(GIT), "-c", "core.quotepath=false", *args],
        cwd=REPO, env=env, capture_output=True, check=True,
    ).stdout


def protected_content(raw: bytes) -> list:
    tokens = parser().parse(raw.decode("utf-8-sig").replace("\r\n", "\n"))
    result = []
    for index, token in enumerate(tokens):
        if token.type in {"fence", "code_block", "math_block", "html_block"}:
            result.append((token.type, token.content, token.info, token.map))
        if token.type == "inline":
            if index and tokens[index - 1].type == "heading_open":
                result.append(("heading", token.content, token.map))
            for child in token.children or []:
                if child.type in {"code_inline", "math_inline", "html_inline"}:
                    result.append((child.type, child.content))
    return result


def intended_edit(before: bytes, relative: str) -> bytes:
    text = before.decode("utf-8")
    if "[[" in text:
        raise ValueError(f"本轮基线不应已有 Wiki 链接：{relative}")
    lines = text.splitlines(keepends=True)
    note = parse_note(before, relative)
    eligible = {}
    for segment in note["segments"]:
        if segment["is_heading"]:
            continue
        for offset, part in enumerate(segment["text"].splitlines()):
            eligible.setdefault(segment["line"] + offset, []).append(part)
    edits = {}
    for number, label, target in SELECTION[relative]:
        if any(c in target for c in "|[]#/\\\r\n"):
            raise ValueError(f"终点必须是独立页面名：{target}")
        if not any(label in part for part in eligible.get(number, [])):
            raise ValueError(f"所选文字不在可编辑正文中：{relative}:{number} {label}")
        # 经验风险先于同一行的经验风险最小化；其余所选文字各行只取明确位置。
        start = lines[number - 1].find(label)
        if start < 0:
            raise ValueError(f"原文位置改变：{relative}:{number}")
        if label != "经验风险" and lines[number - 1].count(label) != 1:
            raise ValueError(f"同一行有多个匹配，需重新选择：{relative}:{number} {label}")
        replacement = f"[[{target}]]" if target == label else f"[[{target}|{label}]]"
        edits.setdefault(number - 1, []).append((start, start + len(label), replacement))
    for index, spans in edits.items():
        ordered = sorted(spans)
        if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
            raise ValueError(f"修改位置重叠：{relative}:{index + 1}")
        for start, end, replacement in reversed(ordered):
            lines[index] = lines[index][:start] + replacement + lines[index][end:]
    after = "".join(lines).encode("utf-8")
    restored = re.sub(r"\[\[([^\[\]\r\n]+)\]\]", lambda m: m[1].split("|", 1)[-1], after.decode("utf-8")).encode("utf-8")
    if restored != before:
        raise ValueError(f"去除新增链接后不能恢复原文字节：{relative}")
    if protected_content(before) != protected_content(after):
        raise ValueError(f"标题、公式或代码发生变化：{relative}")
    parsed = parse_note(after, relative)
    expected = [(target, label, number) for number, label, target in SELECTION[relative]]
    actual = [(link["target"], link["label"], link["line"]) for link in parsed["links"] if link["kind"] == "wiki"]
    if sorted(expected) != sorted(actual) or parsed["warnings"]:
        raise ValueError(f"链接解析或数量核对失败：{relative}")
    return after


def snapshot() -> tuple:
    actual_index = REPO / ".git" / "index"
    return (
        git("rev-parse", "HEAD"),
        hashlib.sha256(actual_index.read_bytes()).hexdigest(),
        hashlib.sha256(REVIEW_INDEX.read_bytes()).hexdigest(),
        sorted(p.relative_to(REPO).as_posix() for p in REPO.rglob("*.md") if ".git" not in p.parts),
    )


def main(mode: str) -> None:
    before_state = snapshot()
    paths = git("ls-files", "-z", review=True).decode("utf-8").strip("\0").split("\0")
    baseline = {path: git("show", f":{path}", review=True) for path in paths}
    prepared = {path: intended_edit(baseline[path], path) for path in SELECTION}
    for path in paths:
        current = (REPO / path).read_bytes()
        allowed = {baseline[path], prepared[path]} if path in prepared else {baseline[path]}
        if current not in allowed:
            raise ValueError(f"出现本轮之外的正文变化，请先重新审核：{path}")
    if mode == "preview":
        for path, after in prepared.items():
            print(path)
            lines = after.decode("utf-8").splitlines()
            for number in sorted({row[0] for row in SELECTION[path]}):
                print(f"{number}: {lines[number - 1]}")
        return
    if mode == "apply":
        for path, after in prepared.items():
            source = REPO / path
            current = source.read_bytes()
            if current == after:
                continue
            if current != baseline[path]:
                raise ValueError(f"写入前原文已变化：{path}")
            source.write_bytes(after)
    for path, expected in prepared.items():
        if (REPO / path).read_bytes() != expected:
            raise ValueError(f"尚未应用预期链接，或本轮文件已继续编辑：{path}")
    changed = git("diff", "--name-only", "-z", review=True).decode("utf-8").strip("\0").split("\0")
    if sorted(changed) != sorted(SELECTION):
        raise ValueError("Git 核对得到的正文修改范围不是指定三篇。")
    if git("ls-files", "--others", "--exclude-standard", "-z", review=True):
        raise ValueError("小库有审阅基线以外的新文件。")
    if snapshot() != before_state:
        raise ValueError("HEAD、真实暂存区、审阅索引或 Markdown 文件清单发生变化。")
    diff = git("diff", "--no-ext-diff", "--no-textconv", "--unified=2", review=True)
    if mode == "apply":
        (RUN / "链接修改.diff").write_bytes(diff)
    targets = sorted({row[2] for rows in SELECTION.values() for row in rows})
    result = {
        "git_comparison": "白天结束时的独立 Git 审阅索引 -> 当前正文",
        "files": [
            {"path": path, "links": len(rows), "distinct_targets": len({row[2] for row in rows})}
            for path, rows in SELECTION.items()
        ],
        "total_links": sum(len(rows) for rows in SELECTION.values()),
        "distinct_targets": len(targets),
        "targets": targets,
        "original_bytes_recover_after_unwrapping_links": True,
        "headings_math_code_unchanged": True,
        "other_four_notes_unchanged": True,
        "git_head_and_both_indexes_unchanged": True,
        "markdown_file_list_unchanged": True,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument("mode", choices=["preview", "apply", "check"], nargs="?", default="check")
    main(arguments.parse_args().mode)
