#!/usr/bin/env python3
"""
基于课程语料的规则+词典知识抽取。

功能：
1. 从 data/corpus/sections.jsonl 中识别课程关键词
2. 生成候选知识点命中结果
3. 抽取先修关系、同义关系、代码关联线索
4. 输出结构化三元组到 data/extracted/rule_based_triples.jsonl

用法：
  python -m backend.scripts.extract_text_rules
  python -m backend.scripts.extract_text_rules --chapter CH04
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS_FILE = ROOT / "data" / "corpus" / "sections.jsonl"
KPS_FILE = ROOT / "data" / "export" / "kps.csv"
OUT_DIR = ROOT / "data" / "extracted"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "rule_based_triples.jsonl"
REPORT_FILE = OUT_DIR / "rule_based_report.json"

PREREQ_PATTERNS = [
    re.compile(r"(?P<src>[\u4e00-\u9fa5A-Za-z0-9_\-]{2,20})是(?P<dst>[\u4e00-\u9fa5A-Za-z0-9_\-]{2,20})的前提"),
    re.compile(r"先掌握(?P<src>[\u4e00-\u9fa5A-Za-z0-9_\-]{2,20}).{0,24}?再学习(?P<dst>[\u4e00-\u9fa5A-Za-z0-9_\-]{2,20})"),
    re.compile(r"理解(?P<src>[\u4e00-\u9fa5A-Za-z0-9_\-]{2,20})是(?P<dst>[\u4e00-\u9fa5A-Za-z0-9_\-]{2,20})的基础"),
    re.compile(r"(?P<src>[\u4e00-\u9fa5A-Za-z0-9_\-]{2,20})是学习(?P<dst>[\u4e00-\u9fa5A-Za-z0-9_\-]{2,20})的基础"),
]

ALIAS_PATTERNS = [
    re.compile(r"(?P<name>[\u4e00-\u9fa5]{2,16})\((?P<alias>[A-Za-z][A-Za-z0-9_\-]{1,20})\)"),
    re.compile(r"(?P<name>[\u4e00-\u9fa5]{2,16})又称(?P<alias>[\u4e00-\u9fa5A-Za-z0-9_\-]{2,16})"),
    re.compile(r"(?P<name>[\u4e00-\u9fa5]{2,16}),?简称(?P<alias>[\u4e00-\u9fa5A-Za-z0-9_\-]{2,12})"),
]

CODE_HINTS = {
    "for (": "for语句",
    "for(": "for语句",
    "while (": "while语句",
    "while(": "while语句",
    "do {": "do-while语句",
    "do{": "do-while语句",
    "switch (": "switch语句",
    "switch(": "switch语句",
    "printf(": "格式化输入输出",
    "scanf(": "格式化输入输出",
    "malloc(": "动态内存分配",
    "free(": "动态内存分配",
    "struct ": "结构体定义",
    "typedef ": "typedef",
    "#include": "预处理指令",
}

ALIAS_BLOCKLIST = {
    "void", "main", "printf", "scanf", "malloc", "free", "strlen", "return", "char", "int",
    "float", "double", "programming", "program", "ascii",
}

EVIDENCE_BLOCKLIST = (
    "main(", "printf(", "scanf(", "malloc(", "free(", "strlen(", "return(",
    "for(", "for (", "while(", "while (", "switch(", "switch (", "putchar(",
)

TEXT_NOISE_WORDS = {
    "程序", "语句", "结构", "表达式", "函数", "变量", "整数", "字符", "浮点数", "循环", "条件",
    "学习", "理解", "掌握", "使用", "实现", "进行", "通过", "可以", "需要", "基础", "前提",
}


def load_seed_kps() -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    lines = KPS_FILE.read_text(encoding="utf-8").splitlines()
    header = [x.strip() for x in lines[0].split(",")]
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < len(header):
            continue
        rows.append(dict(zip(header, parts)))
    return rows


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip().lower())


def split_sentences(text: str) -> List[str]:
    parts = re.split(r"[。！？；\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def is_valid_alias(alias: str, evidence: str) -> bool:
    alias = (alias or "").strip()
    normalized = normalize(alias)
    if len(alias) < 2 or len(alias) > 20:
        return False
    if normalized in ALIAS_BLOCKLIST:
        return False
    if re.fullmatch(r"[0-9\W_]+", alias):
        return False
    if re.search(r"[{};,]", alias):
        return False
    if any(marker in evidence for marker in EVIDENCE_BLOCKLIST):
        return False
    if alias.lower() == alias and re.fullmatch(r"[a-z_\-]+", alias) and len(alias) <= 5:
        return False
    return True


def is_reasonable_text_span(text: str) -> bool:
    text = (text or "").strip()
    if len(text) < 2 or len(text) > 20:
        return False
    if any(ch in text for ch in "(){}[];,:#%*/\\\""):
        return False
    if text in TEXT_NOISE_WORDS:
        return False
    return True


def iter_sections(chapter: str | None) -> Iterable[Dict[str, Any]]:
    lines = CORPUS_FILE.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        if chapter and row.get("chapter_id") != chapter:
            continue
        yield row


def build_term_index(seed_kps: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    term_index: Dict[str, Dict[str, str]] = {}
    for kp in seed_kps:
        name = kp.get("name", "")
        if name:
            term_index[name] = kp
        aliases = kp.get("aliases", "")
        for alias in aliases.split(";"):
            alias = alias.strip()
            if alias:
                term_index[alias] = kp
    return term_index


def match_kps(text: str, term_index: Dict[str, Dict[str, str]]) -> List[Dict[str, str]]:
    hits: List[Dict[str, str]] = []
    for term, kp in term_index.items():
        if len(term) < 2:
            continue
        if term in text:
            hits.append({
                "kp_id": kp.get("kp_id", ""),
                "name": kp.get("name", ""),
                "term": term,
                "chapter_id": kp.get("chapter_id", ""),
            })
    dedup: Dict[str, Dict[str, str]] = {}
    for hit in hits:
        previous = dedup.get(hit["kp_id"])
        if previous is None or len(hit["term"]) > len(previous["term"]):
            dedup[hit["kp_id"]] = hit
    return list(dedup.values())


def resolve_kp(name: str, term_index: Dict[str, Dict[str, str]]) -> Dict[str, str] | None:
    target = normalize(name)
    if not target:
        return None
    exact = None
    partial = None
    for term, kp in term_index.items():
        norm_term = normalize(term)
        if norm_term == target:
            exact = kp
            break
        if len(target) >= 3 and (target in norm_term or norm_term in target):
            partial = partial or kp
    return exact or partial


def extract_prerequisites(text: str, term_index: Dict[str, Dict[str, str]], section_key: str) -> List[Dict[str, Any]]:
    triples: List[Dict[str, Any]] = []
    for sentence in split_sentences(text):
        if "前提" not in sentence and "基础" not in sentence and "先掌握" not in sentence:
            continue
        for pattern in PREREQ_PATTERNS:
            for match in pattern.finditer(sentence):
                src_name = match.group("src").strip()
                dst_name = match.group("dst").strip()
                if not is_reasonable_text_span(src_name) or not is_reasonable_text_span(dst_name):
                    continue
                src = resolve_kp(src_name, term_index)
                dst = resolve_kp(dst_name, term_index)
                if not src or not dst:
                    continue
                if src.get("kp_id") == dst.get("kp_id"):
                    continue
                triples.append({
                    "subject_id": src.get("kp_id"),
                    "subject_name": src.get("name"),
                    "predicate": "PREREQUISITE",
                    "object_id": dst.get("kp_id"),
                    "object_name": dst.get("name"),
                    "evidence": match.group(0),
                    "source": "text_rule",
                    "section_key": section_key,
                })
    return triples


def extract_aliases(text: str, term_index: Dict[str, Dict[str, str]], section_key: str) -> List[Dict[str, Any]]:
    triples: List[Dict[str, Any]] = []
    for sentence in split_sentences(text):
        for pattern in ALIAS_PATTERNS:
            for match in pattern.finditer(sentence):
                name = match.group("name").strip()
                alias = match.group("alias").strip()
                if not is_reasonable_text_span(name):
                    continue
                if not is_valid_alias(alias, match.group(0)):
                    continue
                kp = resolve_kp(name, term_index)
                if not kp:
                    continue
                if normalize(alias) == normalize(kp.get("name", "")):
                    continue
                triples.append({
                    "subject_id": kp.get("kp_id"),
                    "subject_name": kp.get("name"),
                    "predicate": "ALIAS",
                    "object_id": None,
                    "object_name": alias,
                    "evidence": match.group(0),
                    "source": "text_rule",
                    "section_key": section_key,
                })
    return triples


def extract_code_links(code_blocks: List[str], section_hits: List[Dict[str, str]], section_key: str) -> List[Dict[str, Any]]:
    triples: List[Dict[str, Any]] = []
    for code in code_blocks:
        linked_names = set()
        for hint, kp_name in CODE_HINTS.items():
            if hint in code:
                linked_names.add(kp_name)
        if not linked_names:
            continue
        for kp_name in sorted(linked_names):
            triples.append({
                "subject_id": section_key,
                "subject_name": section_key,
                "predicate": "MENTIONS_CODE_KP",
                "object_id": None,
                "object_name": kp_name,
                "evidence": code[:160],
                "source": "code_hint",
                "section_key": section_key,
            })
    return triples


def build_contains_triples(section_hits: List[Dict[str, str]], section_key: str) -> List[Dict[str, Any]]:
    triples: List[Dict[str, Any]] = []
    for hit in section_hits:
        triples.append({
            "subject_id": section_key,
            "subject_name": section_key,
            "predicate": "MENTIONS_KP",
            "object_id": hit["kp_id"],
            "object_name": hit["name"],
            "evidence": hit["term"],
            "source": "term_match",
            "section_key": section_key,
        })
    return triples


def dedup_triples(triples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    uniq: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for triple in triples:
        key = (
            triple.get("subject_id"),
            triple.get("predicate"),
            triple.get("object_id"),
            triple.get("object_name"),
            triple.get("section_key"),
        )
        uniq[key] = triple
    return list(uniq.values())


def main() -> None:
    parser = argparse.ArgumentParser(description="规则抽取课程知识三元组")
    parser.add_argument("--chapter", help="只处理某个章节，如 CH04")
    args = parser.parse_args()

    seed_kps = load_seed_kps()
    term_index = build_term_index(seed_kps)

    triples: List[Dict[str, Any]] = []
    stats = Counter()

    for row in iter_sections(args.chapter):
        section_key = f"{row.get('chapter_id')}_{row.get('section')}"
        text = f"{row.get('title', '')}\n{row.get('text', '')}"
        code_blocks = row.get("code_blocks", []) or []

        section_hits = match_kps(text, term_index)
        prerequisite_triples = extract_prerequisites(text, term_index, section_key)
        alias_triples = extract_aliases(text, term_index, section_key)
        code_triples = extract_code_links(code_blocks, section_hits, section_key)

        triples.extend(build_contains_triples(section_hits, section_key))
        triples.extend(prerequisite_triples)
        triples.extend(alias_triples)
        triples.extend(code_triples)

        stats["sections"] += 1
        stats["kp_hits"] += len(section_hits)
        stats["code_blocks"] += len(code_blocks)
        stats["prerequisite_hits"] += len(prerequisite_triples)
        stats["alias_hits"] += len(alias_triples)
        stats["code_hint_hits"] += len(code_triples)

    triples = dedup_triples(triples)
    for triple in triples:
        stats[f"predicate_{triple['predicate']}"] += 1

    with OUT_FILE.open("w", encoding="utf-8") as f:
        for triple in triples:
            f.write(json.dumps(triple, ensure_ascii=False) + "\n")

    REPORT_FILE.write_text(
        json.dumps(
            {
                "chapter": args.chapter or "ALL",
                "triples_total": len(triples),
                "stats": dict(stats),
                "output": str(OUT_FILE),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Done. sections={stats['sections']} triples={len(triples)} output={OUT_FILE}")


if __name__ == "__main__":
    main()
