#!/usr/bin/env python3
"""
知识点后处理：category 归一化 + 名称去重 + 泛化项过滤

输入:  data/extracted/kp_candidates.jsonl
输出:  data/extracted/kp_candidates_clean.jsonl
"""
import json
import re
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent.parent
IN_FILE = ROOT / "data" / "extracted" / "kp_candidates.jsonl"
OUT_FILE = ROOT / "data" / "extracted" / "kp_candidates_clean.jsonl"

CAT_MAP = {
    "syntax": "syntax",
    "datatype": "datatype",
    "control": "control",
    "function": "function",
    "memory": "memory",
    "algorithm": "algorithm",
    "other": "other",
    "算法": "algorithm",
    "其他": "other",
    "指针操作": "memory",
    "数据结构": "datatype",
    "函数调用": "function",
    "文件操作": "syntax",
    "syntax/datatype": "datatype",
    "control/function": "function",
    "memory/variable/lifetime": "memory",
    "memory/distribution": "memory",
    "memory/algorithm": "memory",
    "function/input_output": "function",
    "datatype/input_output": "datatype",
    "operator/other": "syntax",
    "expression": "syntax",
    "input/output": "syntax",
    "array": "datatype",
    "operation": "syntax",
    "assignment": "syntax",
    "file操作": "syntax",
    "declaration": "syntax",
    "output": "syntax",
    "static variables": "memory",
    "characterManipulation": "syntax",
    "operator": "syntax",
    "string": "datatype",
    "runtime": "memory",
    "character": "datatype",
    "file": "syntax",
    "variable": "datatype",
}

GENERIC_PATTERNS = [
    r"^循环结构$",
    r"^条件判断$",
    r"^算法优化$",
    r"^程序解析$",
    r"^基础概念$",
    r"^处理.*方法$",
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

METHOD_PATTERNS = [
    r"^.*算法$",
    r"^.*判断$",
    r"^.*求解$",
    r"^.*计算$",
    r"^.*检测$",
    r"^.*统计$",
]

CONCEPT_KEYWORDS = (
    "语句", "函数", "指针", "数组", "结构体", "文件", "运算符", "表达式", "内存", "类型", "排序", "sqrt"
)


def is_generic_name(name: str) -> bool:
    return any(re.match(p, name) for p in GENERIC_PATTERNS)


def classify_candidate_type(name: str, category: str) -> str:
    if any(re.match(p, name) for p in METHOD_PATTERNS):
        return "MethodPattern"
    if category == "algorithm" and not any(keyword in name for keyword in CONCEPT_KEYWORDS):
        return "MethodPattern"
    return "KnowledgePoint"


def normalize_category(cat: str) -> str:
    cat = cat.strip()
    if cat in CAT_MAP:
        return CAT_MAP[cat]
    cat_lower = cat.lower()
    if "memory" in cat_lower or "pointer" in cat_lower or "指针" in cat_lower:
        return "memory"
    if "algorithm" in cat_lower or "算法" in cat_lower or "sort" in cat_lower:
        return "algorithm"
    if "function" in cat_lower or "函数" in cat_lower:
        return "function"
    if "control" in cat_lower or "loop" in cat_lower or "循环" in cat_lower:
        return "control"
    if "type" in cat_lower or "data" in cat_lower or "数据" in cat_lower:
        return "datatype"
    if "file" in cat_lower or "文件" in cat_lower:
        return "syntax"
    return "other"


def normalize_name(name: str) -> str:
    name = name.strip()
    name = re.sub(r"\s+", "", name)
    return name.replace("（", "(").replace("）", ")")


def name_similarity(a: str, b: str) -> float:
    a_set = set(a.lower())
    b_set = set(b.lower())
    if not a_set or not b_set:
        return 0.0
    return len(a_set & b_set) / len(a_set | b_set)


def dedup_within_section(records: List[Dict]) -> List[Dict]:
    seen_names: Dict[str, str] = {}
    kept = []
    for rec in records:
        name = normalize_name(rec["name"])
        section_key = rec["_section_key"]
        if name in seen_names:
            continue
        is_dup = False
        for seen_name, seen_sec in seen_names.items():
            if seen_sec == section_key and name_similarity(name, seen_name) > 0.75:
                is_dup = True
                break
        if not is_dup:
            seen_names[name] = section_key
            rec["name"] = name
            kept.append(rec)
    return kept


def main():
    records = [json.loads(line) for line in IN_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"输入: {len(records)} 条")

    for rec in records:
        rec["category"] = normalize_category(rec.get("category", "other"))
        rec["name"] = normalize_name(rec.get("name", ""))
        rec["candidate_type"] = classify_candidate_type(rec["name"], rec["category"])
        aliases = rec.get("aliases", "")
        if isinstance(aliases, list):
            aliases = ",".join(str(x).strip() for x in aliases if str(x).strip())
        else:
            aliases = str(aliases).strip()
        rec["aliases"] = aliases

    filtered = [
        rec for rec in records
        if rec.get("name")
        and not is_generic_name(rec["name"])
        and len((rec.get("description") or "").strip()) >= 30
        and not rec.get("duplicate_of")
        and rec.get("candidate_type") == "KnowledgePoint"
    ]

    cleaned = dedup_within_section(filtered)
    print(f"去重后: {len(cleaned)} 条（移除 {len(filtered) - len(cleaned)} 条重复）")

    from collections import Counter
    new_kps = [r for r in cleaned if not r.get("duplicate_of")]
    dup_kps = [r for r in cleaned if r.get("duplicate_of")]
    print(f"  新KP: {len(new_kps)}，与seed重复: {len(dup_kps)}")

    by_cat = Counter(r["category"] for r in new_kps)
    by_type = Counter(r.get("candidate_type", "KnowledgePoint") for r in cleaned)
    print("\n各类别分布（新KP）:")
    for cat, cnt in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {cnt}")
    print("\n候选类型分布:")
    for typ, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {typ}: {cnt}")

    with OUT_FILE.open("w", encoding="utf-8") as f:
        for rec in cleaned:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"\n输出: {OUT_FILE}")
    print(f"  新KP总计: {len(new_kps)} 个可导入图谱")


if __name__ == "__main__":
    main()
