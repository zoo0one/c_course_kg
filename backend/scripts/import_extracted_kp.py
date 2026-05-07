#!/usr/bin/env python3
"""
将 AI 抽取的新知识点导入 Neo4j

默认导入经过质量闸门的通过文件：tests/cleaner/output/kp_gate_pass.jsonl
也可通过 --input 指定文件。

用法:
  venv/bin/python backend/scripts/import_extracted_kp.py --dry-run
  venv/bin/python backend/scripts/import_extracted_kp.py
  venv/bin/python backend/scripts/import_extracted_kp.py --input data/extracted/kp_candidates_clean.jsonl
"""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=ROOT / ".env")

DEFAULT_IN_FILE = ROOT / "tests" / "cleaner" / "output" / "kp_gate_pass.jsonl"
FALLBACK_IN_FILE = ROOT / "data" / "extracted" / "kp_candidates_clean.jsonl"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

KP_ID_START = 9000

MERGE_KP = """
UNWIND $rows AS row
MERGE (k:KnowledgePoint {kp_id: row.kp_id})
SET k.name         = row.name,
    k.chapter_id   = row.chapter_id,
    k.section      = row.section,
    k.aliases      = row.aliases,
    k.category     = row.category,
    k.summary      = row.summary,
    k.description  = row.description,
    k.code_example = row.code_example,
    k.source       = 'ai_extracted',
    k.reviewed     = false
"""

MERGE_CHAPTER_CONTAINS = """
UNWIND $rows AS row
MATCH (c:Chapter {chapter_id: row.chapter_id})
MATCH (k:KnowledgePoint {kp_id: row.kp_id})
MERGE (c)-[:CONTAINS]->(k)
"""

MERGE_PREREQUISITE = """
UNWIND $rows AS row
MATCH (a:KnowledgePoint {kp_id: row.src})
MATCH (b:KnowledgePoint {kp_id: row.dst})
MERGE (a)-[:PREREQUISITE]->(b)
"""

MERGE_RELATED = """
UNWIND $rows AS row
MATCH (a:KnowledgePoint {kp_id: row.src})
MATCH (b:KnowledgePoint {kp_id: row.dst})
MERGE (a)-[:RELATED]->(b)
"""


def normalize_name(name: str) -> str:
    s = (name or "").strip().lower()
    s = s.replace("（", "(").replace("）", ")")
    s = re.sub(r"\s+", "", s)
    return s


def choose_input_file(input_arg: str | None) -> Path:
    if input_arg:
        return Path(input_arg)
    if DEFAULT_IN_FILE.exists():
        return DEFAULT_IN_FILE
    return FALLBACK_IN_FILE


def load_records(path: Path) -> List[Dict]:
    if not path.exists():
        raise FileNotFoundError(f"输入文件不存在: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def load_new_kps(path: Path) -> List[Dict]:
    records = load_records(path)
    return [
        r for r in records
        if not r.get("duplicate_of") and r.get("candidate_type", "KnowledgePoint") == "KnowledgePoint"
    ]


def assign_kp_ids(kps: List[Dict]) -> List[Dict]:
    for i, kp in enumerate(kps):
        kp["kp_id"] = f"KP{KP_ID_START + i + 1:04d}"
    return kps


def build_name_index_for_existing(driver, database: str) -> Dict[str, str]:
    query = "MATCH (k:KnowledgePoint) RETURN k.kp_id AS kp_id, k.name AS name"
    idx: Dict[str, str] = {}
    with driver.session(database=database) as s:
        result = s.run(query)
        for row in result:
            kp_id = row.get("kp_id")
            name = row.get("name")
            if kp_id and name:
                idx[normalize_name(name)] = kp_id
    return idx


def build_name_index_for_new(kps: List[Dict]) -> Dict[str, str]:
    idx: Dict[str, str] = {}
    for kp in kps:
        n = normalize_name(kp.get("name", ""))
        if n:
            idx[n] = kp["kp_id"]
    return idx


def build_relation_rows(
    kps: List[Dict],
    existing_name_to_id: Dict[str, str],
    new_name_to_id: Dict[str, str],
) -> Tuple[List[Dict], List[Dict], int, int]:
    prereq_rows: List[Dict] = []
    related_rows: List[Dict] = []
    missed_prereq = 0
    missed_related = 0

    def resolve_name(name: str) -> str | None:
        n = normalize_name(name)
        if not n:
            return None
        if n in new_name_to_id:
            return new_name_to_id[n]
        return existing_name_to_id.get(n)

    for kp in kps:
        dst = kp["kp_id"]

        for prereq_name in kp.get("prerequisites", []):
            src_id = resolve_name(str(prereq_name))
            if src_id:
                prereq_rows.append({"src": src_id, "dst": dst})
            else:
                missed_prereq += 1

        for rel_name in kp.get("related", []):
            rel_id = resolve_name(str(rel_name))
            if rel_id:
                related_rows.append({"src": dst, "dst": rel_id})
            else:
                missed_related += 1

    return prereq_rows, related_rows, missed_prereq, missed_related


def run_cypher(driver, cypher: str, params: dict, database: str):
    with driver.session(database=database) as s:
        result = s.run(cypher, params)
        return result.consume()


def main() -> None:
    parser = argparse.ArgumentParser(description="导入 AI 抽取知识点到 Neo4j")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不写数据库")
    parser.add_argument("--input", help="输入 jsonl 文件路径")
    args = parser.parse_args()

    input_file = choose_input_file(args.input)
    new_kps = load_new_kps(input_file)
    print(f"输入文件: {input_file}")
    print(f"待导入新 KP: {len(new_kps)} 个")

    new_kps = assign_kp_ids(new_kps)

    if args.dry_run:
        print("\n=== DRY RUN - 新KP预览（前20条）===")
        for kp in new_kps[:20]:
            print(
                f"  {kp['kp_id']} [{kp.get('chapter_id','')} {kp.get('section',''):8}] "
                f"{kp.get('name','')[:30]:30} [{kp.get('category','other')}]"
            )
        print("\n干运行完成，未写数据库")
        return

    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("ERROR: 请安装 neo4j driver: venv/bin/pip install neo4j")
        return

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        existing_name_to_id = build_name_index_for_existing(driver, NEO4J_DATABASE)
        new_name_to_id = build_name_index_for_new(new_kps)

        prereq_rows, related_rows, missed_prereq, missed_related = build_relation_rows(
            new_kps, existing_name_to_id, new_name_to_id
        )

        kp_rows = [
            {
                "kp_id": kp["kp_id"],
                "name": kp.get("name", ""),
                "chapter_id": kp.get("chapter_id", ""),
                "section": kp.get("section", ""),
                "aliases": kp.get("aliases", ""),
                "category": kp.get("category", "other"),
                "summary": kp.get("summary", ""),
                "description": kp.get("description", ""),
                "code_example": kp.get("code_example", ""),
            }
            for kp in new_kps
        ]

        run_cypher(driver, MERGE_KP, {"rows": kp_rows}, NEO4J_DATABASE)
        print(f"✓ 导入 {len(kp_rows)} 个 KP 节点")

        run_cypher(driver, MERGE_CHAPTER_CONTAINS, {"rows": kp_rows}, NEO4J_DATABASE)
        print(f"✓ 建立 {len(kp_rows)} 条章节包含关系")

        if prereq_rows:
            run_cypher(driver, MERGE_PREREQUISITE, {"rows": prereq_rows}, NEO4J_DATABASE)
        if related_rows:
            run_cypher(driver, MERGE_RELATED, {"rows": related_rows}, NEO4J_DATABASE)

        print(f"✓ 建立先修关系: {len(prereq_rows)} 条（未命中 {missed_prereq}）")
        print(f"✓ 建立相关关系: {len(related_rows)} 条（未命中 {missed_related}）")

    finally:
        driver.close()

    print("\n导入完成！")
    print(f"  数据库: {NEO4J_DATABASE} ({NEO4J_URI})")


if __name__ == "__main__":
    main()
