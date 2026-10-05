"""只读核对本轮五篇词条；检查结果只写到本运行目录。"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")
RUN = Path(__file__).resolve().parent
TASK = RUN.parent
PROJECT = TASK.parents[1]
REPO = TASK / "小知识库"
sys.path.insert(0, str(PROJECT))
from markdown_notes import normalized, parse_note, parser

SELECTED = ["模型训练", "损失函数", "反向传播", "小批量训练", "交叉熵"]
INITIAL_COMMIT = "224fc771f170f609415409c150ba78a8ed9c66f0"
REVISION_TREE = "94d5aee3569c70ea566955b8a5258d53dfa8a371"
SUBJECT_REWRITE_TREE = "7446eb0ce1515e02358b09543f8e4ab0494c7b10"
FOUR_REWRITE_TREE = "61abc688bfccd2bdee40fd3872a8b62ad63564e7"
BACKPROP_HASH = "f481a14413b6caa781ce4df4ecaa3ff046021902362fc2b1f6d2435f4f46f8c7"
LAYOUT_BEFORE_BLOB = "31efd4ec06543fb5aa4a5bff1a0da7a94d777ae2"
# 本次保留用户确认暂用的反向传播，只重写其他四篇。
OTHER_PAGE_PATHS = ["词条/模型训练.md", "词条/损失函数.md", "词条/小批量训练.md", "词条/交叉熵.md"]
# 在本轮创建词条前读取七份现有材料；仅用于验证它们没有被改动。
ORIGINAL_HASHES = {
    "DNA01/00. 计划.md": "8f5ef8c83e06ea0d1eac954c609ca811fdf2fba5b61fa1da9e369bcd7a2d10d7",
    "DNA01/01. DNA的基本化学组成.md": "c474f88fe4a659bb789891a1ab839cda1be582d9dfcbffd1b6e008fd70bc3602",
    "MAC01/1.1 神经网络如何“学习”.md": "907f8d75b5bfa8d4804d87736fc3b3aab767f2cf695af987b0e865b3a126606d",
    "MAC01/1.2 从一次step到完整训练过程.md": "93facab0c9a6f3bd6043a35f9a11f977c2aac855a0101f629709c658166135fd",
    "MAC01/1.3 logit 概率 交叉熵.md": "1c8e9eb1f2ddd053808a64b5d24cb17d23cfb7dc439d079eb4a3f3c267d831c4",
    "MAC01/1.4 计算图、链式法则、反向传播.md": "cd9031f5261fd8c9290425f30956a4ed363f96a8156067b6d4aae09233571bcb",
    "MAC01/1.5 自动微分的pytorch机制.md": "a48cd460f995ef1b6f0cf400cb75c5db311f57072ff5d82ec4c63e92eb0e739a",
}
CHECKS = []


def check(name, passed, details=None):
    CHECKS.append({"name": name, "passed": bool(passed), "details": details})


def near(name, actual, expected, tolerance=1e-7):
    check(name, abs(actual - expected) <= tolerance,
          {"actual": actual, "expected": expected, "tolerance": tolerance})


def derivative(function, x, step=1e-6):
    return (function(x + step) - function(x - step)) / (2 * step)


def logsumexp(values):
    maximum = max(values)
    return maximum + math.log(sum(math.exp(value - maximum) for value in values))


def cross_entropy_logits(values, target):
    # 使用移位后的得分直接求损失，避免大的公共偏移造成额外相减。
    shifted = [value - max(values) for value in values]
    return logsumexp(shifted) - sum(q * z for q, z in zip(target, shifted))


def git(arguments, index=None):
    environment = os.environ.copy()
    environment.pop("GIT_INDEX_FILE", None)
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    if index is not None:
        environment["GIT_INDEX_FILE"] = str(index)
    executable = shutil.which("git") or r"D:\system\Git\cmd\git.exe"
    return subprocess.check_output([executable, "-C", str(REPO), *arguments], env=environment)


def zero_paths(output):
    return sorted(item for item in output.decode("utf-8").split("\0") if item)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


# 新稿的例子从原始样本重新计算，不继续检查已撤下的首稿例子。
training_samples = [(0, 0), (1, 2), (2, 4)]
training_loss = lambda w, b: sum((w * x + b - y) ** 2 for x, y in training_samples) / 3
near("线性模型的初始损失", training_loss(0, 0), 20 / 3)
dw = derivative(lambda w: training_loss(w, 0), 0)
db = derivative(lambda b: training_loss(0, b), 0)
near("线性模型权重导数的数值差分", dw, -20 / 3)
near("线性模型偏置导数的数值差分", db, -4)
w, b = -0.1 * dw, -0.1 * db
near("一次更新后的权重", w, 2 / 3)
near("一次更新后的偏置", b, 0.4)
for x, prediction in [(0, 0.4), (1, 16 / 15), (2, 26 / 15)]:
    near(f"更新后的预测 x={x}", w * x + b, prediction)
near("一次更新后的平均损失", training_loss(w, b), 2.056296296296296)
near("精确拟合时的训练损失", training_loss(2, 0), 0)
check("240 个样本、批大小 60、十轮训练的更新数", 240 // 60 * 10 == 40)
constant_targets = [0, 0, 9]
square_loss = lambda c: sum((c - y) ** 2 for y in constant_targets) / 3
absolute_loss = lambda c: sum(abs(c - y) for y in constant_targets) / 3
for c, sq, absolute in [(0, 27, 3), (3, 18, 4), (9, 54, 6)]:
    near(f"常数预测 c={c} 的平方损失", square_loss(c), sq)
    near(f"常数预测 c={c} 的绝对损失", absolute_loss(c), absolute)
near("平方损失在 c=3 的导数", derivative(square_loss, 3), 0)
check("绝对损失在中位数处的左右斜率", derivative(absolute_loss, -1) < 0 < derivative(absolute_loss, 1))
near("正确类别概率 0.51 的损失", -math.log(0.51), 0.673, 0.0005)
near("正确类别概率 0.99 的损失", -math.log(0.99), 0.010, 0.0005)
# 直接从正态密度计算，核对固定方差下的负对数似然表达。
residual, variance = 1.3, 2.5
density = math.exp(-residual ** 2 / (2 * variance)) / math.sqrt(2 * math.pi * variance)
near("固定方差正态模型的负对数似然", -math.log(density),
     residual ** 2 / (2 * variance) + 0.5 * math.log(2 * math.pi * variance))
# 当前反向传播稿：共享隐层、两个输出；用原始模型的数值差分独立核对手推结果。
branch_parameters = [0.5, 0.5, 2.0, 0.0, -1.0, 0.5]  # w, b, v1, c1, v2, c2


def branch_loss(parameters, x=2.0):
    w, b, v1, c1, v2, c2 = parameters
    h = max(0.0, w * x + b)
    outputs = [v1 * h + c1, v2 * h + c2]
    return sum((value - target) ** 2 for value, target in zip(outputs, [4.0, 0.0])) / 2


near("共享隐层示例的前向损失", branch_loss(branch_parameters), 1.0)
for i, (name, expected) in enumerate(zip(["w", "b", "v1", "c1", "v2", "c2"], [-2, -1, -1.5, -1, -1.5, -1])):
    def changed(value, i=i):
        parameters = branch_parameters.copy()
        parameters[i] = value
        return branch_loss(parameters)
    near(f"共享隐层示例的参数导数 {name}", derivative(changed, branch_parameters[i]), expected)
first_branch = lambda h: 0.5 * (2 * h - 4) ** 2
second_branch = lambda h: 0.5 * (-h + 0.5) ** 2
near("第一路对共享隐层的贡献", derivative(first_branch, 1.5), -2)
near("第二路对共享隐层的贡献", derivative(second_branch, 1.5), 1)
near("两路贡献合并后的导数", derivative(lambda h: first_branch(h) + second_branch(h), 1.5), -1)
near("输入的导数", derivative(lambda x: branch_loss(branch_parameters, x), 2.0), -0.5)
inactive = [-0.5, -0.5, *branch_parameters[2:]]
near("ReLU 负输入区域阻断这一路局部导数", derivative(lambda w: branch_loss([w, *inactive[1:]]), inactive[0]), 0)

# 以非方形权重和非线性激活检查矩阵递推：两层、两个输出，避免只在标量情形检查。
network_parameters = [0.3, -0.1, 0.2, -0.2, 0.4, 0.1, 0.15, -0.2, 0.6, -0.3, 0.2, 0.5, 0.1, -0.05]
network_input, network_target = [-0.4, 0.7, 1.2], [0.4, -0.2]


def network_values(parameters):
    w1 = [parameters[:3], parameters[3:6]]
    b1, w2, b2 = parameters[6:8], [parameters[8:10], parameters[10:12]], parameters[12:14]
    hidden = [math.tanh(sum(weight * value for weight, value in zip(row, network_input)) + bias)
              for row, bias in zip(w1, b1)]
    output = [sum(weight * value for weight, value in zip(row, hidden)) + bias for row, bias in zip(w2, b2)]
    return hidden, output, w2


def network_loss(parameters):
    _, output, _ = network_values(parameters)
    return sum((value - target) ** 2 for value, target in zip(output, network_target)) / 2


hidden, output, w2 = network_values(network_parameters)
delta2 = [value - target for value, target in zip(output, network_target)]
delta1 = [sum(w2[j][i] * delta2[j] for j in range(2)) * (1 - hidden[i] ** 2) for i in range(2)]
analytical = ([delta * value for delta in delta1 for value in network_input] + delta1
              + [delta * value for delta in delta2 for value in hidden] + delta2)
numerical = []
for i, initial in enumerate(network_parameters):
    def changed(value, i=i):
        parameters = network_parameters.copy()
        parameters[i] = value
        return network_loss(parameters)
    numerical.append(derivative(changed, initial))
check("多层网络递推的全部权重与偏置导数", all(abs(a - b) < 1e-7 for a, b in zip(analytical, numerical)),
      {"analytical": analytical, "numerical": numerical, "max_error": max(abs(a - b) for a, b in zip(analytical, numerical))})
batch_targets = [0, 2, 4, 6]
batch_loss = lambda w, targets: sum(0.5 * (w - y) ** 2 for y in targets) / len(targets)
w = 0
for i, targets in enumerate([batch_targets[:2], batch_targets[2:]]):
    near(f"第 {i + 1} 批更新前的损失", batch_loss(w, targets), [1, 10.625][i])
    g = derivative(lambda value: batch_loss(value, targets), w)
    near(f"第 {i + 1} 批梯度的数值差分", g, [-1, -4.5][i])
    w -= 0.5 * g
    near(f"第 {i + 1} 批更新后的参数", w, [0.5, 2.75][i])
near("一次全批更新后的参数", -0.5 * derivative(lambda value: batch_loss(value, batch_targets), 0), 1.5)
near("两次小批更新后的完整数据损失", batch_loss(w, batch_targets), 2.53125)
near("完整数据的初始损失", batch_loss(0, batch_targets), 7)
sample_gradients = [-y for y in batch_targets]
pair_means = [sum(pair) / 2 for pair in itertools.combinations(sample_gradients, 2)]
near("固定参数均匀抽样代表整体", sum(pair_means) / len(pair_means), -3)
check("130 个样本的末批、批数与丢弃后的覆盖", (130 % 48, math.ceil(130 / 48), 130 // 48 * 48) == (34, 3, 96))
near("不同批大小的梯度按样本加权", (48 * 2 + 34 * 6) / 82, 3.659, 0.0005)
near("两个批平均等权时的不同结果", (2 + 6) / 2, 4)
gradient_population = [-1, 1]
population_variance = sum(value ** 2 for value in gradient_population) / 2
independent_means = [sum(values) / 3 for values in itertools.product(gradient_population, repeat=3)]
near("独立采样的批平均方差为单样本方差除以批大小",
     sum(value ** 2 for value in independent_means) / len(independent_means), population_variance / 3)
near("交叉熵第一组概率", -math.log(0.7), 0.357, 0.0005)
near("交叉熵第二组概率", -math.log(0.3), 1.204, 0.0005)
near("软目标的完整加权和", -0.75 * math.log(0.6) - 0.25 * math.log(0.4), 0.612, 0.0005)
target_entropy = -sum(q * math.log(q) for q in [0.8, 0.2])
near("匹配时的非零交叉熵", target_entropy, 0.500, 0.0005)
near("均匀预测相对目标熵多出的部分", -math.log(0.5) - target_entropy, 0.193, 0.0005)
near("大得分的稳定交叉熵", cross_entropy_logits([1000, 1001, 999], [0, 1, 0]), 0.408, 0.0005)
near("大得分示例的第二类概率", 1 / (math.exp(-1) + 1 + math.exp(-2)), 0.665, 0.0005)
near("共同平移保持交叉熵不变", cross_entropy_logits([-1, 0, -2], [0, 1, 0]),
     cross_entropy_logits([1000, 1001, 999], [0, 1, 0]))
q, p = [0.25, 0.75], [0.65, 0.35]
near("交叉熵等于熵加 KL 散度", -sum(a * math.log(b) for a, b in zip(q, p)),
     -sum(a * math.log(a) for a in q) + sum(a * math.log(a / b) for a, b in zip(q, p)))
z, q = [0.4, -0.2, 0.8], [0.25, 0.25, 0.5]
probabilities = [math.exp(value - logsumexp(z)) for value in z]
for index in range(3):
    def changed(value, index=index):
        values = z.copy()
        values[index] = value
        return cross_entropy_logits(values, q)
    near(f"Softmax 交叉熵梯度分量 {index}", derivative(changed, z[index]), probabilities[index] - q[index])
for y in [0, 1]:
    p = 0.35
    binary_loss = -y * math.log(p) - (1 - y) * math.log(1 - p)
    near(f"二元与两类分布的交叉熵一致，标签 {y}", binary_loss, -math.log(p if y else 1 - p))

paths = sorted(REPO.rglob("*.md"))
notes = {path.relative_to(REPO).as_posix(): parse_note(path.read_bytes(), path.relative_to(REPO).as_posix()) for path in paths}
expected_new = [f"词条/{name}.md" for name in SELECTED]
check("恰有七份原材料和五篇新词条", set(notes) == set(ORIGINAL_HASHES) | set(expected_new), list(notes))
check("原有七份材料未改动", all(digest(REPO / path) == sha for path, sha in ORIGINAL_HASHES.items()))
# 最新排版调整以前向传播稿的实际 Git 文件为依据，保留当前已有属性。
layout_before_raw = git(["show", LAYOUT_BEFORE_BLOB])
layout_before = parse_note(layout_before_raw, "词条/反向传播.md")
layout_after = notes["词条/反向传播.md"]
layout_after_raw = (REPO / "词条/反向传播.md").read_bytes()
check("排版调整保留既有属性", layout_before_raw.decode("utf-8").replace("\r\n", "\n").split("---", 2)[:2]
      == layout_after_raw.decode("utf-8").replace("\r\n", "\n").split("---", 2)[:2])
check("排版调整保留所有概念链接", [(link["target"], link["label"]) for link in layout_before["links"]]
      == [(link["target"], link["label"]) for link in layout_after["links"]])

check("本次反向传播按用户要求保持原样", digest(REPO / "词条/反向传播.md") == BACKPROP_HASH, BACKPROP_HASH)
def frontmatter(raw):
    return raw.decode("utf-8").replace("\r\n", "\n").split("---", 2)[:2]
check("其余四篇保留既有文首属性", all(frontmatter((REPO / path).read_bytes())
      == frontmatter(git(["show", f"{FOUR_REWRITE_TREE}:{path}"])) for path in OTHER_PAGE_PATHS))
warnings = {path: note["warnings"] for path, note in notes.items() if note["warnings"]}
check("Markdown 与属性解析", not warnings, warnings)
new_notes = {path: notes[path] for path in expected_new}

markdown_links, anchored_concepts, repeated_labels, broken_wiki_syntax, format_issues = [], [], [], [], []
names = {}
for path, note in notes.items():
    for name in {Path(path).stem, note["title"], *note["aliases"]}:
        names.setdefault(normalized(name), set()).add(path)
for path, note in new_notes.items():
    raw = (REPO / path).read_text(encoding="utf-8")
    check(f"{note['title']}正文非空且可解析", bool(note["segments"]) and bool(note["headings"]))
    check(f"{note['title']}别名没有重复或与其他页冲突", len({normalized(alias) for alias in note["aliases"]}) == len(note["aliases"])
          and all(names[normalized(alias)] == {path} for alias in note["aliases"]), note["aliases"])
    lines = raw.splitlines()
    inside_math = False
    for number, line in enumerate(lines):
        if line.strip() != "$$":
            continue
        inside_math = not inside_math
    if inside_math or any(marker in raw for marker in [r"\[", r"\]", r"\(", r"\)"]):
        format_issues.append({"file": path, "problem": "数学定界符不符合当前稿件格式"})
    labels = {link["label"]: link["target"] for link in note["links"] if link["kind"] == "wiki" and link["target"] != note["title"]}
    for segment in note["segments"]:
        if segment["is_heading"]:
            continue
        text = segment["text"]
        if "[[" in text or "]]" in text or "$" in text:
            broken_wiki_syntax.append({"file": path, "line": segment["line"], "text": text})
        matches = [(match.start(), match.end(), label) for label in labels for match in re.finditer(re.escape(label), text)]
        for start, end, label in matches:
            if any(a <= start and end <= b and b - a > end - start for a, b, _ in matches):
                continue
            repeated_labels.append({"file": path, "line": segment["line"], "label": label})
    for link in note["links"]:
        if link["kind"] == "wiki":
            if "#" in link["target"]:
                anchored_concepts.append({"file": path, **link})
            continue
        markdown_links.append({"file": path, **link})
check("本轮暂不包含外部链接或资料链接", not markdown_links and all(heading["text"] != "相关学习材料" for note in new_notes.values() for heading in note["headings"]), markdown_links)
check("正向概念链接均到独立页面", not anchored_concepts, anchored_concepts)
check("已选链接显示词的正文重复标记", not repeated_labels, repeated_labels)
check("正文的 Wiki Link 与行内公式完整解析", not broken_wiki_syntax, broken_wiki_syntax)
check("MathJax 定界符完整", not format_issues, format_issues)
loss_body = (REPO / "词条/损失函数.md").read_text(encoding="utf-8").split("---", 2)[2]
inline_math = [child.content for token in parser().parse(loss_body) for child in token.children or [] if child.type == "math_inline"]
check("绝对误差公式完整解析，竖线未被误识别为表格列", r"\ell(\hat y,y)=|\hat y-y|" in inline_math)
course_paths = list(ORIGINAL_HASHES)[2:5]
course_links = [link for path in course_paths for link in notes[path]["links"] if link["kind"] == "wiki"]
now_resolved = [link for link in course_links if link["target"] in SELECTED]
check("五个词条承接既有课程链接", len(now_resolved) == 11 and set(link["target"] for link in now_resolved) == set(SELECTED)
      and all(names.get(normalized(name)) == {f"词条/{name}.md"} for name in SELECTED), now_resolved)

# 用 Git 比较白天基线；历史审阅索引和真实索引都只读。
review_index = TASK / "第一天午夜审核/git-review.index"
revision_index = RUN / "词条修订起点.index"
subject_index = RUN / "反向传播重写起点.index"
four_index = RUN / "四篇重写起点.index"
real_index = REPO / ".git/index"
indexes = [review_index, revision_index, subject_index, four_index, real_index]
index_hashes = [digest(index) for index in indexes]
changed = zero_paths(git(["diff", "--name-only", "-z"], review_index))
untracked = zero_paths(git(["ls-files", "--others", "--exclude-standard", "-z"], review_index))
head = git(["rev-parse", "HEAD"]).decode().strip()
staged = zero_paths(git(["diff", "--cached", "--name-only", "-z"]))
check("Git 日间基线之后只有三篇既有加链和五篇新增", changed == sorted(course_paths) and untracked == sorted(expected_new), {"previous_link_edits": changed, "new_concept_pages": untracked})
check("Git 没有新增提交或真实暂存", head == INITIAL_COMMIT and not staged, {"head": head, "staged": staged})
revision_changed = zero_paths(git(["diff", "--name-only", "-z"], revision_index))
revision_untracked = zero_paths(git(["ls-files", "--others", "--exclude-standard", "-z"], revision_index))
check("Git 从五篇首稿至当前变化只涉及五篇词条", revision_changed == sorted(expected_new) and not revision_untracked,
      {"changed": revision_changed, "untracked": revision_untracked})
check("首稿 Git 对象仍可恢复", set(zero_paths(git(["ls-tree", "-r", "--name-only", "-z", REVISION_TREE]))) == set(ORIGINAL_HASHES) | set(expected_new), REVISION_TREE)
subject_changed = zero_paths(git(["diff", "--name-only", "-z"], subject_index))
subject_untracked = zero_paths(git(["ls-files", "--others", "--exclude-standard", "-z"], subject_index))
check("Git 从反向传播重写前至当前仅涉及五篇词条", subject_changed == sorted(expected_new) and not subject_untracked,
      {"changed": subject_changed, "untracked": subject_untracked})
four_changed = zero_paths(git(["diff", "--name-only", "-z"], four_index))
four_untracked = zero_paths(git(["ls-files", "--others", "--exclude-standard", "-z"], four_index))
check("Git 本次重写只涉及其他四篇", four_changed == sorted(OTHER_PAGE_PATHS) and not four_untracked,
      {"changed": four_changed, "untracked": four_untracked})
check("四篇重写前的文件树仍可读取", set(zero_paths(git(["ls-tree", "-r", "--name-only", "-z", FOUR_REWRITE_TREE]))) == set(ORIGINAL_HASHES) | set(expected_new), FOUR_REWRITE_TREE)
check("Git 索引保持原样", index_hashes == [digest(index) for index in indexes])

result = {
    "checked_at_local": datetime.now().astimezone().isoformat(),
    "passed": all(item["passed"] for item in CHECKS),
    "checks": CHECKS,
    "pages": [{"path": path, "sha256": note["sha256"], "aliases": note["aliases"],
               "wiki_links": sum(link["kind"] == "wiki" for link in note["links"]),
               "display_math_blocks": sum(line.strip() == "$$" for line in (REPO / path).read_text(encoding="utf-8").splitlines()) // 2} for path, note in new_notes.items()],
    "original_course_links": {"positions": len(course_links), "targets": len(set(link["target"] for link in course_links)),
                              "now_resolved_positions": len(now_resolved)},
    "revision_baseline_tree": REVISION_TREE,
    "subject_rewrite_baseline_tree": SUBJECT_REWRITE_TREE,
    "four_rewrite_baseline_tree": FOUR_REWRITE_TREE,
    "preserved_backprop_sha256": BACKPROP_HASH,
    "layout_before_blob": LAYOUT_BEFORE_BLOB,
    "limits": ["未操作 Obsidian 界面", "别名是否完全同义及解释深度仍需要语义阅读判断", "重复提及检查只复核已选择的显示词，不替代语义阅读", "仅针对本轮文件状态，之后编辑应更新检查依据"],
}
(RUN / "检查结果.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"passed": result["passed"], "checks": len(CHECKS), "failed": [item for item in CHECKS if not item["passed"]],
                  "pages": result["pages"], "original_course_links": result["original_course_links"]}, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["passed"] else 1)
