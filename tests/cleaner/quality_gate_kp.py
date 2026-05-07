#!/usr/bin/env python3
"""
AI 抽取知识点质量闸门（仅测试目录使用）

输入：data/extracted/kp_candidates_clean.jsonl
输出：
  - tests/cleaner/output/kp_gate_pass.jsonl
  - tests/cleaner/output/kp_gate_reject.jsonl
  - tests/cleaner/output/kp_gate_report.json

用法：
  python3 tests/cleaner/quality_gate_kp.py
  python3 tests/cleaner/quality_gate_kp.py --min-score 65
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.scripts.course_schema import KNOWLEDGE_POINTS
INPUT_FILE = ROOT / "data" / "extracted" / "kp_candidates_clean.jsonl"
OUT_DIR = ROOT / "tests" / "cleaner" / "output"
PASS_FILE = OUT_DIR / "kp_gate_pass.jsonl"
REJECT_FILE = OUT_DIR / "kp_gate_reject.jsonl"
REPORT_FILE = OUT_DIR / "kp_gate_report.json"

ALLOWED_CATEGORIES = {"syntax", "datatype", "control", "function", "memory", "algorithm", "other"}

# 过泛词（命中则扣分/拒绝）
GENERIC_PATTERNS = [
    r"^循环结构$",
    r"^条件判断$",
    r"^算法优化$",
    r"^处理.*方法$",
    r"^程序解析$",
    r"^基础概念$",
    r"^使用.*实现.*$",
    r"^.*实现要点$",
    r"^.*使用场景$",
    r"^.*执行流程$",
    r"^.*的作用$",
    r"^.*的执行流程$",
    r"^.*的使用场景$",
    r"^.*的实现要点$",
    r"^函数定义和调用$",
    r"^项的计算与符号变化$",
]

# C 语义锚点（命中加分）
C_ANCHORS = [
    "if", "else", "switch", "case", "for", "while", "do-while",
    "printf", "scanf", "malloc", "free", "fopen", "fclose",
    "指针", "数组", "函数", "结构体", "文件", "递归", "位运算",
]

METHOD_PATTERNS = [
    r"^.*算法$",
    r"^.*判断$",
    r"^.*求解$",
    r"^.*计算$",
    r"^.*检测$",
    r"^.*统计$",
]


def normalize_name(name: str) -> str:
    s = (name or "").strip()
    s = s.replace("（", "(").replace("）", ")")
    s = re.sub(r"\s+", "", s)
    return s


def simple_similarity(a: str, b: str) -> float:
    a_set = set(a.lower())
    b_set = set(b.lower())
    if not a_set or not b_set:
        return 0.0
    return len(a_set & b_set) / len(a_set | b_set)


def load_seed_names() -> List[str]:
    return [normalize_name(kp.get("name", "")) for kp in KNOWLEDGE_POINTS if kp.get("name")]


def hits_generic(name: str) -> bool:
    normalized = normalize_name(name)
    return any(re.match(p, normalized) for p in GENERIC_PATTERNS)


def calc_score(rec: Dict, seed_names: List[str]) -> Tuple[int, List[str], str | None]:
    score = 100
    reasons: List[str] = []
    hard_reject: str | None = None

    name = normalize_name(rec.get("name", ""))
    category = (rec.get("category") or "other").strip()
    summary = (rec.get("summary") or "").strip()
    description = (rec.get("description") or "").strip()
    code_example = (rec.get("code_example") or "").strip()

    if not name:
        hard_reject = "empty_name"
        score = 0
        reasons.append("名称为空")
        return score, reasons, hard_reject

    if category not in ALLOWED_CATEGORIES:
        score -= 25
        reasons.append(f"类别异常: {category}")

    if hits_generic(name):
        score -= 35
        reasons.append("命中过泛词")

    if len(summary) < 12:
        score -= 10
        reasons.append("summary过短")

    if len(description) < 40:
        score -= 20
        reasons.append("description过短")

    if not code_example:
        score -= 8
        reasons.append("缺少代码示例")

    if category == "other":
        score -= 20
        reasons.append("category=other")

    name_lower = name.lower()
    if any(anchor in name_lower or anchor in description for anchor in C_ANCHORS):
        score += 8

    if rec.get("candidate_type") == "MethodPattern":
        score -= 25
        reasons.append("candidate_type=MethodPattern")

    if rec.get("duplicate_of"):
        score -= 20
        reasons.append(f"duplicate_of={rec.get('duplicate_of')}")

    near_dup = 0.0
    for seed_name in seed_names:
        near_dup = max(near_dup, simple_similarity(name, seed_name))
    if near_dup >= 0.85:
        score -= 25
        reasons.append(f"疑似与seed重复({near_dup:.2f})")

    score = max(0, min(100, score))

    # 硬拒绝条件
    if len(description) < 20:
        hard_reject = "description_too_short"
    elif hits_generic(name):
        hard_reject = "generic_name"
    elif rec.get("duplicate_of"):
        hard_reject = "duplicate_of_seed"
    elif rec.get("candidate_type") == "MethodPattern":
        hard_reject = "method_pattern"
    elif hits_generic(name) and category == "other":
        hard_reject = "generic_and_other"

    return score, reasons, hard_reject


def load_records(path: Path) -> List[Dict]:
    if not path.exists():
        raise FileNotFoundError(f"输入文件不存在: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def save_jsonl(path: Path, rows: List[Dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="KP 质量闸门")
    parser.add_argument("--min-score", type=int, default=65, help="通过阈值，默认 65")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    records = load_records(INPUT_FILE)
    seed_names = load_seed_names()

    passed: List[Dict] = []
    rejected: List[Dict] = []

    for rec in records:
        score, reasons, hard_reject = calc_score(rec, seed_names)
        item = dict(rec)
        item["quality_score"] = score
        item["quality_reasons"] = reasons
        item["quality_hard_reject"] = hard_reject

        if hard_reject or score < args.min_score:
            rejected.append(item)
        else:
            passed.append(item)

    save_jsonl(PASS_FILE, passed)
    save_jsonl(REJECT_FILE, rejected)

    report = {
        "input_total": len(records),
        "passed_total": len(passed),
        "rejected_total": len(rejected),
        "pass_rate": round(len(passed) / len(records), 4) if records else 0,
        "min_score": args.min_score,
        "pass_file": str(PASS_FILE),
        "reject_file": str(REJECT_FILE),
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("质量闸门完成")
    print(f"  输入: {len(records)}")
    print(f"  通过: {len(passed)}")
    print(f"  拒绝: {len(rejected)}")
    print(f"  报告: {REPORT_FILE}")


if __name__ == "__main__":
    main()
