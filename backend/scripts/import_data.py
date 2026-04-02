"""导入知识图谱数据到 Neo4j"""
import os
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "export"

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
    "CREATE INDEX kp_name_index IF NOT EXISTS FOR (k:KnowledgePoint) ON (k.name)",
]

CHAPTERS_CYPHER = """
UNWIND $rows AS row
MERGE (c:Chapter {chapter_id: row.chapter_id})
SET c.title = row.title, c.order = toInteger(row.order)
"""

KPS_CYPHER = """
UNWIND $rows AS row
MERGE (k:KnowledgePoint {kp_id: row.kp_id})
SET k.name = row.name, k.chapter_id = row.chapter_id,
    k.section = row.section, k.aliases = row.aliases, k.source = row.source
"""

CONTAINS_CYPHER = """
UNWIND $rows AS row
MATCH (c:Chapter {chapter_id: row.chapter_id})
MATCH (k:KnowledgePoint {kp_id: row.kp_id})
MERGE (c)-[:CONTAINS]->(k)
"""

PREREQUISITE_CYPHER = """
UNWIND $rows AS row
MATCH (a:KnowledgePoint {kp_id: row.source_kp_id})
MATCH (b:KnowledgePoint {kp_id: row.target_kp_id})
MERGE (a)-[r:PREREQUISITE]->(b)
SET r.description = row.description
"""

RELATED_CYPHER = """
UNWIND $rows AS row
MATCH (a:KnowledgePoint {kp_id: row.source_kp_id})
MATCH (b:KnowledgePoint {kp_id: row.target_kp_id})
MERGE (a)-[r:RELATED]->(b)
SET r.description = row.description
"""

EXTENDS_CYPHER = """
UNWIND $rows AS row
MATCH (a:KnowledgePoint {kp_id: row.source_kp_id})
MATCH (b:KnowledgePoint {kp_id: row.target_kp_id})
MERGE (a)-[r:EXTENDS]->(b)
SET r.description = row.description
"""

KP_CONTAINS_CYPHER = """
UNWIND $rows AS row
MATCH (a:KnowledgePoint {kp_id: row.source_kp_id})
MATCH (b:KnowledgePoint {kp_id: row.target_kp_id})
MERGE (a)-[r:CONTAINS]->(b)
SET r.description = row.description
"""


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


def main() -> None:
    chapters_df = pd.read_csv(DATA_DIR / "chapters.csv")
    kps_df = pd.read_csv(DATA_DIR / "kps.csv")
    contains_df = pd.read_csv(DATA_DIR / "contains_edges.csv")

    relations_df = None
    relations_path = DATA_DIR / "relations.csv"
    if relations_path.exists():
        relations_df = pd.read_csv(relations_path, comment="#")
        relations_df = relations_df.dropna(subset=["source_kp_id", "target_kp_id"])
        print(f"发现关系数据: {len(relations_df)} 条")

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    for stmt in SCHEMA_CYPHERS:
        _run(driver, stmt)

    # 导入章节
    chapters_df["chapter_id"] = chapters_df["chapter_id"].astype(str)
    chapters_df["title"] = chapters_df["title"].astype(str)
    for batch in _chunked(_to_records(chapters_df)):
        _run(driver, CHAPTERS_CYPHER, {"rows": batch})
    print(f"章节: {len(chapters_df)} 条")

    # 导入知识点
    for col in ["kp_id", "name", "chapter_id", "section", "aliases", "source"]:
        kps_df[col] = kps_df[col].apply(_normalize)
    for batch in _chunked(_to_records(kps_df)):
        _run(driver, KPS_CYPHER, {"rows": batch})
    print(f"知识点: {len(kps_df)} 条")

    # 导入章节-知识点关系
    contains_df["chapter_id"] = contains_df["chapter_id"].apply(_normalize)
    contains_df["kp_id"] = contains_df["kp_id"].apply(_normalize)
    for batch in _chunked(_to_records(contains_df), 2000):
        _run(driver, CONTAINS_CYPHER, {"rows": batch})
    print(f"章节包含关系: {len(contains_df)} 条")

    # 导入知识点关系
    n_rel = 0
    if relations_df is not None and not relations_df.empty:
        for col in ["source_kp_id", "target_kp_id", "relation_type", "description"]:
            if col not in relations_df.columns:
                relations_df[col] = ""
            relations_df[col] = relations_df[col].apply(_normalize)

        for rel_type, cypher in [
            ("PREREQUISITE", PREREQUISITE_CYPHER),
            ("RELATED", RELATED_CYPHER),
            ("EXTENDS", EXTENDS_CYPHER),
            ("CONTAINS", KP_CONTAINS_CYPHER),
        ]:
            subset = relations_df[relations_df["relation_type"] == rel_type]
            if subset.empty:
                continue
            for batch in _chunked(_to_records(subset)):
                _run(driver, cypher, {"rows": batch})
            n_rel += len(subset)
            print(f"  {rel_type}: {len(subset)} 条")

    driver.close()
    print(f"\n导入完成: {len(chapters_df)} 章节, {len(kps_df)} 知识点, {len(contains_df)} 章节包含关系, {n_rel} 知识点关系")
    print(f"数据库: {NEO4J_DATABASE} ({NEO4J_URI})")


if __name__ == "__main__":
    main()
