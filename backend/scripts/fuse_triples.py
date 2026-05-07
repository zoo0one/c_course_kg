#!/usr/bin/env python3
"""
融合文本规则抽取、代码 AST 抽取与人工标注金标准，生成统一三元组与 RDF 导出。
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent.parent
TEXT_FILE = ROOT / "data" / "extracted" / "rule_based_triples.jsonl"
CODE_FILE = ROOT / "data" / "extracted" / "code_ast_triples.jsonl"
GOLD_FILE = ROOT / "data" / "gold" / "kp_text_gold.jsonl"
KPS_FILE = ROOT / "data" / "export" / "kps.csv"
OUT_FILE = ROOT / "data" / "extracted" / "fused_triples.jsonl"
CSV_FILE = ROOT / "data" / "export" / "fused_relations.csv"
TTL_FILE = ROOT / "data" / "export" / "fused_rdf.ttl"
REPORT_FILE = ROOT / "data" / "extracted" / "fused_report.json"
BASE_URI = "http://example.org/c-course-kg/"

REL_MAP = {
    "PREREQUISITE": "prerequisiteOf",
    "RELATED": "relatedTo",
    "ALIAS": "aliasOf",
    "MENTIONS_KP": "mentions",
    "GOLD_LABEL": "goldMentions",
    "IMPLEMENTS_KP": "implements",
    "BELONGS_TO_CHAPTER": "belongsToChapter",
}

BAD_ALIAS_TOKENS = {
    "void", "int", "char", "float", "double", "return", "main", "printf", "scanf",
    "strlen", "malloc", "free", "if", "for", "while", "switch",
}
BAD_ALIAS_EVIDENCE_MARKERS = ("main(", "printf(", "scanf(", "strlen(", "return(", "while(", "for(", "switch(", "putchar(")


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def normalize(text: str) -> str:
    text = (text or "").strip().lower().replace("（", "(").replace("）", ")")
    return re.sub(r"\s+", "", text)


def slug(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff\-\.]+", "_", (text or "").strip()).strip("_") or "unknown"


def load_kps() -> Dict[str, str]:
    index: Dict[str, str] = {}
    with KPS_FILE.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            kp_id = (row.get("kp_id") or "").strip()
            name = (row.get("name") or "").strip()
            if not kp_id or not name:
                continue
            index[normalize(name)] = kp_id
            for alias in (row.get("aliases") or "").split(";"):
                alias = alias.strip()
                if alias:
                    index[normalize(alias)] = kp_id
    return index


def resolve_kp_id(name: str | None, index: Dict[str, str]) -> str | None:
    key = normalize(name or "")
    if not key:
        return None
    if key in index:
        return index[key]
    for k, v in index.items():
        if key in k or k in key:
            return v
    return None


def node_id(prefix: str, value: str) -> str:
    return f"{prefix}_{slug(value)}"


def add_entity(entities: Dict[str, Dict[str, str]], entity_id: str, entity_type: str, entity_name: str) -> None:
    entities[entity_id] = {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "entity_name": entity_name,
    }


def is_valid_alias(alias: str, evidence: str) -> bool:
    alias = (alias or "").strip()
    if len(alias) < 2 or len(alias) > 30:
        return False
    if alias.lower() in BAD_ALIAS_TOKENS:
        return False
    if re.fullmatch(r"[0-9\W_]+", alias):
        return False
    if any(marker in (evidence or "") for marker in BAD_ALIAS_EVIDENCE_MARKERS):
        return False
    if re.search(r"[(){};,]", alias):
        return False
    return True


def convert_text(rows: Iterable[Dict[str, Any]], kp_idx: Dict[str, str]) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, str]]]:
    fused: List[Dict[str, Any]] = []
    entities: Dict[str, Dict[str, str]] = {}
    for row in rows:
        pred = row.get("predicate", "")
        sec = str(row.get("section_key") or row.get("subject_id") or "UNKNOWN")
        sec_id = node_id("SEC", sec)
        add_entity(entities, sec_id, "Section", sec)

        if pred == "MENTIONS_KP":
            obj_id = row.get("object_id") or resolve_kp_id(row.get("object_name"), kp_idx)
            if not obj_id:
                continue
            fused.append({
                "subject_id": sec_id, "subject_type": "Section", "subject_name": sec,
                "predicate": pred,
                "object_id": obj_id, "object_type": "KnowledgePoint", "object_name": row.get("object_name", ""),
                "source": row.get("source", "text_rule"), "evidence": row.get("evidence", ""),
                "section_key": sec, "confidence": 0.75,
            })
        elif pred == "PREREQUISITE":
            sub_id = row.get("subject_id") or resolve_kp_id(row.get("subject_name"), kp_idx)
            obj_id = row.get("object_id") or resolve_kp_id(row.get("object_name"), kp_idx)
            if not sub_id or not obj_id or sub_id == obj_id:
                continue
            fused.append({
                "subject_id": sub_id, "subject_type": "KnowledgePoint", "subject_name": row.get("subject_name", ""),
                "predicate": pred,
                "object_id": obj_id, "object_type": "KnowledgePoint", "object_name": row.get("object_name", ""),
                "source": row.get("source", "text_rule"), "evidence": row.get("evidence", ""),
                "section_key": sec, "confidence": 0.82,
            })
        elif pred == "ALIAS":
            kp_id = row.get("subject_id") or resolve_kp_id(row.get("subject_name"), kp_idx)
            alias = str(row.get("object_name") or "")
            evidence = str(row.get("evidence") or "")
            if not kp_id or not alias or not is_valid_alias(alias, evidence):
                continue
            alias_id = node_id("ALIAS", f"{kp_id}_{alias}")
            add_entity(entities, alias_id, "Alias", alias)
            fused.append({
                "subject_id": alias_id, "subject_type": "Alias", "subject_name": alias,
                "predicate": pred,
                "object_id": kp_id, "object_type": "KnowledgePoint", "object_name": row.get("subject_name", ""),
                "source": row.get("source", "text_rule"), "evidence": evidence,
                "section_key": sec, "confidence": 0.88,
            })
    return fused, entities


def convert_code(rows: Iterable[Dict[str, Any]], kp_idx: Dict[str, str]) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, str]]]:
    fused: List[Dict[str, Any]] = []
    entities: Dict[str, Dict[str, str]] = {}
    for row in rows:
        code_name = str(row.get("subject_name") or row.get("subject_id") or "unknown_code")
        code_id = node_id("CODE", str(row.get("subject_id") or code_name))
        add_entity(entities, code_id, "CodeExample", code_name)
        kp_name = str(row.get("mapped_kp") or row.get("object_name") or "")
        kp_id = resolve_kp_id(kp_name, kp_idx)
        if not kp_id:
            continue
        fused.append({
            "subject_id": code_id, "subject_type": "CodeExample", "subject_name": code_name,
            "predicate": "IMPLEMENTS_KP",
            "object_id": kp_id, "object_type": "KnowledgePoint", "object_name": kp_name,
            "source": row.get("source", "code_ast"), "evidence": row.get("evidence", ""),
            "section_key": "", "file_path": row.get("file_path", ""),
            "pattern_name": row.get("object_name", ""), "confidence": 0.9,
        })
    return fused, entities


def convert_gold(rows: Iterable[Dict[str, Any]], kp_idx: Dict[str, str]) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, str]]]:
    fused: List[Dict[str, Any]] = []
    entities: Dict[str, Dict[str, str]] = {}
    for row in rows:
        sample_id = str(row.get("sample_id") or "")
        if not sample_id:
            continue
        sec = f"{row.get('chapter_id', '')}_{row.get('section', '')}"
        add_entity(entities, sample_id, "GoldSample", sample_id)
        for kp_name in row.get("knowledge_points", []) or []:
            kp_id = resolve_kp_id(str(kp_name), kp_idx)
            if kp_id:
                fused.append({
                    "subject_id": sample_id, "subject_type": "GoldSample", "subject_name": sample_id,
                    "predicate": "GOLD_LABEL",
                    "object_id": kp_id, "object_type": "KnowledgePoint", "object_name": kp_name,
                    "source": "gold_manual", "evidence": row.get("text_fragment", ""),
                    "section_key": sec, "question": row.get("question", ""), "confidence": 1.0,
                })
        for rel in row.get("relation_hints", []) or []:
            rel_type = str(rel.get("type") or "").strip().upper()
            target = str(rel.get("target") or "").strip()
            if not rel_type or not target:
                continue
            if rel_type == "BELONGS_TO_CHAPTER":
                add_entity(entities, target, "Chapter", target)
                fused.append({
                    "subject_id": sample_id, "subject_type": "GoldSample", "subject_name": sample_id,
                    "predicate": rel_type,
                    "object_id": target, "object_type": "Chapter", "object_name": target,
                    "source": "gold_manual", "evidence": row.get("text_fragment", ""),
                    "section_key": sec, "confidence": 1.0,
                })
            else:
                kp_id = resolve_kp_id(target, kp_idx)
                if kp_id:
                    fused.append({
                        "subject_id": sample_id, "subject_type": "GoldSample", "subject_name": sample_id,
                        "predicate": rel_type,
                        "object_id": kp_id, "object_type": "KnowledgePoint", "object_name": target,
                        "source": "gold_manual", "evidence": row.get("text_fragment", ""),
                        "section_key": sec, "confidence": 1.0,
                    })
    return fused, entities


def dedup(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    uniq: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for row in rows:
        key = (row.get("subject_id"), row.get("predicate"), row.get("object_id"), row.get("source"), row.get("section_key"))
        uniq[key] = row
    return sorted(uniq.values(), key=lambda x: (str(x.get("subject_id")), str(x.get("predicate")), str(x.get("object_id"))))


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    fields = ["subject_id", "subject_type", "subject_name", "predicate", "object_id", "object_type", "object_name", "source", "confidence", "section_key", "file_path", "pattern_name", "question", "evidence"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def literal(text: Any) -> str:
    s = str(text or "").replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{s}"'


def entity_uri(entity_id: str) -> str:
    return f"<{BASE_URI}{quote(entity_id)}>"


def write_ttl(path: Path, rows: Iterable[Dict[str, Any]], entities: Dict[str, Dict[str, str]]) -> None:
    lines = [
        "@prefix ckg: <http://example.org/c-course-kg/ontology/> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "",
    ]
    for entity in sorted(entities.values(), key=lambda x: x["entity_id"]):
        lines.extend([
            f"{entity_uri(entity['entity_id'])} a ckg:{entity['entity_type']} ;",
            f"    rdfs:label {literal(entity['entity_name'])} .",
            "",
        ])
    for row in rows:
        pred = REL_MAP.get(str(row.get("predicate")), str(row.get("predicate", "relatedTo")).lower())
        lines.append(f"{entity_uri(str(row['subject_id']))} ckg:{pred} {entity_uri(str(row['object_id']))} .")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    kp_idx = load_kps()
    text_rows = load_jsonl(TEXT_FILE)
    code_rows = load_jsonl(CODE_FILE)
    gold_rows = load_jsonl(GOLD_FILE)

    text_fused, text_entities = convert_text(text_rows, kp_idx)
    code_fused, code_entities = convert_code(code_rows, kp_idx)
    gold_fused, gold_entities = convert_gold(gold_rows, kp_idx)

    fused = dedup(text_fused + code_fused + gold_fused)
    entities = {**text_entities, **code_entities, **gold_entities}

    write_jsonl(OUT_FILE, fused)
    write_csv(CSV_FILE, fused)
    write_ttl(TTL_FILE, fused, entities)

    stats = Counter()
    for row in fused:
        stats[f"predicate_{row['predicate']}"] += 1
        stats[f"source_{row['source']}"] += 1

    REPORT_FILE.write_text(json.dumps({
        "text_rows": len(text_rows),
        "code_rows": len(code_rows),
        "gold_rows": len(gold_rows),
        "fused_rows": len(fused),
        "entity_rows": len(entities),
        "stats": dict(stats),
        "outputs": {"jsonl": str(OUT_FILE), "csv": str(CSV_FILE), "ttl": str(TTL_FILE)},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Done. fused={len(fused)} entities={len(entities)} out={OUT_FILE}")


if __name__ == "__main__":
    main()
