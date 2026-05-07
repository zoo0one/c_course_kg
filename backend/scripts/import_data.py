#!/usr/bin/env python3
"""
将课程知识图谱抽取结果导入 Neo4j。

支持导入：
1. 课程骨架 CSV（章节、知识点、显式关系）
2. 融合后的结构化三元组（章节片段/代码样例/人工标注）

用法：
  python -m backend.scripts.import_data
  python -m backend.scripts.import_data --skip-fused
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "export"
FUSED_FILE = DATA_DIR / "fused_relations.csv"

load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


def _require_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing env var: {key}. Check {PROJECT_ROOT / '.env'}")
    return val


NEO4J_URI = _require_env("NEO4J_URI")
NEO4J_USER = _require_env("NEO4J_USER")
NEO4J_PASSWORD = _require_env("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

SCHEMA_CYPHERS = [
    "CREATE CONSTRAINT chapter_id_unique IF NOT EXISTS FOR (c:Chapter) REQUIRE c.chapter_id IS UNIQUE",
    "CREATE CONSTRAINT kp_id_unique IF NOT EXISTS FOR (k:KnowledgePoint) REQUIRE k.kp_id IS UNIQUE",
    "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE",
    "CREATE INDEX kp_name_index IF NOT EXISTS FOR (k:KnowledgePoint) ON (k.name)",
]

CHAPTERS_CYPHER = """
UNWIND $rows AS row
MERGE (c:Chapter:Entity {chapter_id: row.chapter_id})
SET c.title = row.title, c.order = toInteger(row.order), c.entity_id = row.chapter_id
"""

KPS_CYPHER = """
UNWIND $rows AS row
MERGE (k:KnowledgePoint:Entity {kp_id: row.kp_id})
SET k.name = row.name, k.chapter_id = row.chapter_id,
    k.section = row.section, k.aliases = row.aliases, k.source = row.source,
    k.entity_id = row.kp_id
"""

CONTAINS_CYPHER = """
UNWIND $rows AS row
MATCH (c:Chapter {chapter_id: row.chapter_id})
MATCH (k:KnowledgePoint {kp_id: row.kp_id})
MERGE (c)-[:CONTAINS]->(k)
"""

RELATION_CYPHERS = {
    "PREREQUISITE": """
    UNWIND $rows AS row
    MATCH (a:KnowledgePoint {kp_id: row.source_kp_id})
    MATCH (b:KnowledgePoint {kp_id: row.target_kp_id})
    MERGE (a)-[r:PREREQUISITE]->(b)
    SET r.description = row.description
    """,
    "RELATED": """
    UNWIND $rows AS row
    MATCH (a:KnowledgePoint {kp_id: row.source_kp_id})
    MATCH (b:KnowledgePoint {kp_id: row.target_kp_id})
    MERGE (a)-[r:RELATED]->(b)
    SET r.description = row.description
    """,
    "EXTENDS": """
    UNWIND $rows AS row
    MATCH (a:KnowledgePoint {kp_id: row.source_kp_id})
    MATCH (b:KnowledgePoint {kp_id: row.target_kp_id})
    MERGE (a)-[r:EXTENDS]->(b)
    SET r.description = row.description
    """,
    "CONTAINS": """
    UNWIND $rows AS row
    MATCH (a:KnowledgePoint {kp_id: row.source_kp_id})
    MATCH (b:KnowledgePoint {kp_id: row.target_kp_id})
    MERGE (a)-[r:CONTAINS]->(b)
    SET r.description = row.description
    """,
}

UPSERT_ENTITY_CYPHER = """
UNWIND $rows AS row
MERGE (e:Entity {entity_id: row.entity_id})
SET e.name = row.name,
    e.entity_type = row.entity_type,
    e.source = row.source,
    e.section_key = row.section_key,
    e.file_path = row.file_path,
    e.question = row.question
"""

FUSED_REL_CYPHER = """
UNWIND $rows AS row
MATCH (s:Entity {entity_id: row.subject_id})
MATCH (o:Entity {entity_id: row.object_id})
MERGE (s)-[rel:FUSED_RELATION {predicate: row.predicate, object_id: row.object_id, source: row.source}]->(o)
SET rel.confidence = toFloat(row.confidence),
    rel.evidence = row.evidence,
    rel.section_key = row.section_key,
    rel.file_path = row.file_path,
    rel.pattern_name = row.pattern_name,
    rel.question = row.question
"""


SPECIAL_ENTITY_TYPES = {"KnowledgePoint", "Chapter"}


def _normalize(x: Any) -> str:
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    return str(x)


def _to_records(df: pd.DataFrame) -> list[dict]:
    records = df.to_dict("records")
    for r in records:
        for k, v in list(r.items()):
            if isinstance(v, float) and pd.isna(v):
                r[k] = ""
            elif v is None:
                r[k] = ""
    return records


def _chunked(items: list[dict], size: int = 1000):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _run(driver, cypher: str, params: dict | None = None) -> None:
    with driver.session(database=NEO4J_DATABASE) as s:
        s.run(cypher, params or {}).consume()


def _run_one(driver, cypher: str) -> None:
    with driver.session(database=NEO4J_DATABASE) as s:
        s.run(cypher).consume()


def load_fused_rows() -> list[dict]:
    if not FUSED_FILE.exists():
        return []
    with FUSED_FILE.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key in list(row.keys()):
            row[key] = _normalize(row.get(key))
    return rows


def build_entity_rows(fused_rows: list[dict], kps_df: pd.DataFrame, chapters_df: pd.DataFrame) -> list[dict]:
    entities: dict[str, dict] = {}

    for row in chapters_df.to_dict("records"):
        chapter_id = _normalize(row.get("chapter_id"))
        if chapter_id:
            entities[chapter_id] = {
                "entity_id": chapter_id,
                "name": _normalize(row.get("title")) or chapter_id,
                "entity_type": "Chapter",
                "source": "seed",
                "section_key": "",
                "file_path": "",
                "question": "",
            }

    for row in kps_df.to_dict("records"):
        kp_id = _normalize(row.get("kp_id"))
        if kp_id:
            entities[kp_id] = {
                "entity_id": kp_id,
                "name": _normalize(row.get("name")) or kp_id,
                "entity_type": "KnowledgePoint",
                "source": _normalize(row.get("source")) or "seed",
                "section_key": f"{_normalize(row.get('chapter_id'))}_{_normalize(row.get('section'))}",
                "file_path": "",
                "question": "",
            }

    for row in fused_rows:
        for side in ("subject", "object"):
            entity_id = _normalize(row.get(f"{side}_id"))
            entity_type = _normalize(row.get(f"{side}_type")) or "Entity"
            if not entity_id or entity_type in SPECIAL_ENTITY_TYPES:
                continue
            entities[entity_id] = {
                "entity_id": entity_id,
                "name": _normalize(row.get(f"{side}_name")) or entity_id,
                "entity_type": entity_type,
                "source": _normalize(row.get("source")),
                "section_key": _normalize(row.get("section_key")),
                "file_path": _normalize(row.get("file_path")),
                "question": _normalize(row.get("question")),
            }
    return list(entities.values())


def import_base_graph(driver) -> tuple[int, int, int, int]:
    chapters_df = pd.read_csv(DATA_DIR / "chapters.csv")
    kps_df = pd.read_csv(DATA_DIR / "kps.csv")
    contains_df = pd.read_csv(DATA_DIR / "contains_edges.csv")

    relations_path = DATA_DIR / "relations.csv"
    relations_df = pd.read_csv(relations_path, comment="#") if relations_path.exists() else pd.DataFrame()
    if not relations_df.empty:
        relations_df = relations_df.dropna(subset=["source_kp_id", "target_kp_id"])

    chapters_df["chapter_id"] = chapters_df["chapter_id"].astype(str)
    chapters_df["title"] = chapters_df["title"].astype(str)
    for batch in _chunked(_to_records(chapters_df)):
        _run(driver, CHAPTERS_CYPHER, {"rows": batch})

    for col in ["kp_id", "name", "chapter_id", "section", "aliases", "source"]:
        kps_df[col] = kps_df[col].apply(_normalize)
    for batch in _chunked(_to_records(kps_df)):
        _run(driver, KPS_CYPHER, {"rows": batch})

    contains_df["chapter_id"] = contains_df["chapter_id"].apply(_normalize)
    contains_df["kp_id"] = contains_df["kp_id"].apply(_normalize)
    for batch in _chunked(_to_records(contains_df), 2000):
        _run(driver, CONTAINS_CYPHER, {"rows": batch})

    n_rel = 0
    if not relations_df.empty:
        for col in ["source_kp_id", "target_kp_id", "relation_type", "description"]:
            if col not in relations_df.columns:
                relations_df[col] = ""
            relations_df[col] = relations_df[col].apply(_normalize)
        for rel_type, cypher in RELATION_CYPHERS.items():
            subset = relations_df[relations_df["relation_type"] == rel_type]
            if subset.empty:
                continue
            for batch in _chunked(_to_records(subset)):
                _run(driver, cypher, {"rows": batch})
            n_rel += len(subset)

    return len(chapters_df), len(kps_df), len(contains_df), n_rel


def import_fused_graph(driver) -> tuple[int, int]:
    fused_rows = load_fused_rows()
    if not fused_rows:
        return 0, 0

    chapters_df = pd.read_csv(DATA_DIR / "chapters.csv")
    kps_df = pd.read_csv(DATA_DIR / "kps.csv")
    entity_rows = build_entity_rows(fused_rows, kps_df, chapters_df)

    for row in entity_rows:
        row["entity_type"] = row["entity_type"] or "Entity"
    generic_entities = [r for r in entity_rows if r["entity_type"] not in SPECIAL_ENTITY_TYPES]

    if generic_entities:
        try:
            for batch in _chunked(generic_entities):
                _run(driver, UPSERT_ENTITY_CYPHER, {"rows": batch})
        except Exception as exc:
            raise RuntimeError(
                "导入融合实体失败，请检查 Neo4j 连接、约束状态或节点写权限。"
            ) from exc

    fused_edge_rows = [
        {
            "subject_id": _normalize(r.get("subject_id")),
            "object_id": _normalize(r.get("object_id")),
            "predicate": _normalize(r.get("predicate")) or "RELATED",
            "source": _normalize(r.get("source")),
            "confidence": _normalize(r.get("confidence")) or "0",
            "evidence": _normalize(r.get("evidence")),
            "section_key": _normalize(r.get("section_key")),
            "file_path": _normalize(r.get("file_path")),
            "pattern_name": _normalize(r.get("pattern_name")),
            "question": _normalize(r.get("question")),
        }
        for r in fused_rows
        if _normalize(r.get("subject_id")) and _normalize(r.get("object_id"))
    ]
    for batch in _chunked(fused_edge_rows):
        _run(driver, FUSED_REL_CYPHER, {"rows": batch})
    return len(generic_entities), len(fused_edge_rows)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="导入课程知识图谱数据到 Neo4j")
    parser.add_argument("--skip-fused", action="store_true", help="只导入课程骨架 CSV，不导入融合三元组")
    args = parser.parse_args()

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    for stmt in SCHEMA_CYPHERS:
        _run_one(driver, stmt)

    base_stats = import_base_graph(driver)
    print(f"基础图谱导入完成: 章节={base_stats[0]}, 知识点={base_stats[1]}, 章节包含={base_stats[2]}, 显式关系={base_stats[3]}")

    if args.skip_fused:
        driver.close()
        print("已跳过融合三元组导入")
        return

    entity_count, fused_rel_count = import_fused_graph(driver)
    driver.close()
    print(f"融合图谱导入完成: 新增实体={entity_count}, 新增融合关系={fused_rel_count}")
    print(f"数据库: {NEO4J_DATABASE} ({NEO4J_URI})")


if __name__ == "__main__":
    main()
