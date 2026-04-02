#!/usr/bin/env python3
"""
知识点后处理：category 归一化 + 名称去重

输入:  data/extracted/kp_candidates.jsonl
输出:  data/extracted/kp_candidates_clean.jsonl
"""
import json
import re
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent.parent
IN_FILE  = ROOT / "data" / "extracted" / "kp_candidates.jsonl"
OUT_FILE = ROOT / "data" / "extracted" / "kp_candidates_clean.jsonl"

# ── category 归一化映射 ────────────────────────────────────
CAT_MAP = {
    # 标准类别直接保留
    "syntax": "syntax",
    "datatype": "datatype",
    "control": "control",
    "function": "function",
    "memory": "memory",
    "algorithm": "algorithm",
    "other": "other",
    # 中文
    "算法": "algorithm",
    "其他": "other",
    "指针操作": "memory",
    "数据结构": "datatype",
    "函数调用": "function",
    "文件操作": "syntax",
    # 混合类别 → 取主类
    "syntax/datatype": "datatype",
    "control/function": "function",
    "memory/variable/lifetime": "memory",
    "memory/distribution": "memory",
    "memory/algorithm": "memory",
    "function/input_output": "function",
    "datatype/input_output": "datatype",
    "operator/other": "syntax",
    # 英文非标准
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


def normalize_category(cat: str) -> str:
    cat = cat.strip()
    if cat in CAT_MAP:
        return CAT_MAP[cat]
    # 模糊匹配
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
    """简单归一化：去除多余空格、统一常见符号。"""
    name = name.strip()
    name = re.sub(r'\s+', '', name)  # 去除内部空格（中文习惯）
    # 统一括号
    name = name.replace('（', '(').replace('）', ')')
    return name


def name_similarity(a: str, b: str) -> float:
    """简单字符串相似度（基于字符集重叠），用于去重判断。"""
    a_set = set(a.lower())
    b_set = set(b.lower())
    if not a_set or not b_set:
        return 0.0
    intersection = a_set & b_set
    union = a_set | b_set
    return len(intersection) / len(union)


def dedup_within_section(records: List[Dict]) -> List[Dict]:
    """
    在同一个 section 内对名称相似度 > 0.75 的 KP 去重，保留第一条。
    同时对全局名称做精确去重。
    """
    seen_names: Dict[str, str] = {}  # normalized_name -> section_key
    kept = []

    for rec in records:
        name = normalize_name(rec["name"])
        section_key = rec["_section_key"]

        # 精确去重（同名）
        if name in seen_names:
            continue

        # 在同 section 内做相似度去重
        is_dup = False
        for seen_name, seen_sec in seen_names.items():
            if seen_sec == section_key:
                sim = name_similarity(name, seen_name)
                if sim > 0.75:
                    is_dup = True
                    break

        if not is_dup:
            seen_names[name] = section_key
            rec["name"] = name  # 用归一化后的名称
            kept.append(rec)

    return kept


def main():
    records = [json.loads(line) for line in IN_FILE.read_text(encoding="utf-8").splitlines()]
    print(f"输入: {len(records)} 条")

    # 1. category 归一化
    for rec in records:
        rec["category"] = normalize_category(rec.get("category", "other"))

    # 2. 去重
    cleaned = dedup_within_section(records)
    print(f"去重后: {len(cleaned)} 条（移除 {len(records) - len(cleaned)} 条重复）")

    # 3. 统计
    from collections import Counter
    new_kps = [r for r in cleaned if not r["duplicate_of"]]
    dup_kps = [r for r in cleaned if r["duplicate_of"]]
    print(f"  新KP: {len(new_kps)}，与seed重复: {len(dup_kps)}")

    by_cat = Counter(r["category"] for r in new_kps)
    print("\n各类别分布（新KP）:")
    for cat, cnt in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {cnt}")

    # 4. 写出
    with OUT_FILE.open("w", encoding="utf-8") as f:
        for rec in cleaned:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"\n输出: {OUT_FILE}")
    print(f"  新KP总计: {len(new_kps)} 个可导入图谱")


if __name__ == "__main__":
    main()
