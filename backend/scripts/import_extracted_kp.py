#!/usr/bin/env python3
"""
将 AI 抽取的新知识点导入 Neo4j

只导入 duplicate_of 为 null 的新知识点（seed KP 已由 seed_course.py 导入）。
同时尝试根据 prerequisites/related 字段建立关系。

用法:
  venv/bin/python backend/scripts/import_extracted_kp.py           # 正式导入
  venv/bin/python backend/scripts/import_extracted_kp.py --dry-run  # 预览，不写 Neo4j
"""
import argparse
import json
import os
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=ROOT / ".env")

IN_FILE = ROOT / "data" / "extracted" / "kp_candidates_clean.jsonl"

NEO4J_URI      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# AI 抽取的 KP 从 KP9000 开始编号，避免与 seed（最大到 KP1106）冲突
KP_ID_START = 9000

# Cypher
MERGE_KP = """
UNWIND $rows AS row
MERGE (k:KnowledgePoint {kp_id: row.kp_id})
SET k.name        = row.name,
    k.chapter_id  = row.chapter_id,
    k.section     = row.section,
    k.aliases     = row.aliases,
    k.category    = row.category,
    k.summary     = row.summary,
    k.description = row.description,
    k.code_example = row.code_example,
    k.source      = 'ai_extracted',
    k.reviewed    = false
"""

MERGE_CHAPTER_CONTAINS = """
UNWIND $rows AS row
MATCH (c:Chapter {chapter_id: row.chapter_id})
MATCH (k:KnowledgePoint {kp_id: row.kp_id})
MERGE (c)-[:CONTAINS]->(k)
"""

MERGE_PREREQUISITE = """
UNWIND $rows AS row
MATCH (a:KnowledgePoint) WHERE a.kp_id = row.src OR a.name = row.src
MATCH (b:KnowledgePoint) WHERE b.kp_id = row.dst OR b.name = row.dst
MERGE (a)-[:PREREQUISITE]->(b)
"""

MERGE_RELATED = """
UNWIND $rows AS row
MATCH (a:KnowledgePoint) WHERE a.kp_id = row.src OR a.name = row.src
MATCH (b:KnowledgePoint) WHERE b.kp_id = row.dst OR b.name = row.dst
MERGE (a)-[:RELATED]->(b)
"""


def load_new_kps() -> List[Dict]:
    records = [json.loads(line) for line in IN_FILE.read_text(encoding="utf-8").splitlines()]
    new_kps = [r for r in records if not r.get("duplicate_of")]
    return new_kps


def assign_kp_ids(kps: List[Dict]) -> List[Dict]:
    """给每个新 KP 分配唯一 kp_id（KP9001, KP9002, ...）"""
    for i, kp in enumerate(kps):
        kp["kp_id"] = f"KP{KP_ID_START + i + 1:04d}"
    return kps


def build_relation_rows(kps: List[Dict]) -> tuple:
    """从 prerequisites/related 字段提取关系行。"""
    prereq_rows = []
    related_rows = []

    for kp in kps:
        src = kp["kp_id"]
        for prereq_name in kp.get("prerequisites", []):
            prereq_name = prereq_name.strip()
            if prereq_name:
                # 用名称，Neo4j 查询时会做名称匹配
                prereq_rows.append({"src": prereq_name, "dst": src})
        for rel_name in kp.get("related", []):
            rel_name = rel_name.strip()
            if rel_name:
                related_rows.append({"src": src, "dst": rel_name})

    return prereq_rows, related_rows


def run_cypher(driver, cypher: str, params: dict, database: str):
    with driver.session(database=database) as s:
        result = s.run(cypher, params)
        summary = result.consume()
        return summary


def main():
    parser = argparse.ArgumentParser(description="导入 AI 抽取的知识点到 Neo4j")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不写数据库")
    args = parser.parse_args()

    # 加载新 KP
    new_kps = load_new_kps()
    print(f"待导入新 KP: {len(new_kps)} 个")

    # 分配 ID
    new_kps = assign_kp_ids(new_kps)

    # 构建关系
    prereq_rows, related_rows = build_relation_rows(new_kps)
    print(f"先修关系: {len(prereq_rows)} 条")
    print(f"相关关系: {len(related_rows)} 条")

    if args.dry_run:
        print("\n=== DRY RUN - 预览前20条新KP ===")
        for kp in new_kps[:20]:
            print(f"  {kp['kp_id']} [{kp['chapter_id']} {kp['section']:8}] "
                  f"{kp['name'][:30]:30} [{kp['category']}]")
        print("\n=== 先修关系（前10条）===")
        for r in prereq_rows[:10]:
            print(f"  {r['dst']} PREREQUISITE← {r['src']}")
        print("\n干运行完成，未写入数据库")
        return

    # 正式导入
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("ERROR: 请安装 neo4j driver: venv/bin/pip install neo4j")
        return

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        # 1. 导入 KP 节点
        kp_rows = [{
            "kp_id":        kp["kp_id"],
            "name":         kp["name"],
            "chapter_id":   kp["chapter_id"],
            "section":      kp.get("section", ""),
            "aliases":      kp.get("aliases", ""),
            "category":     kp.get("category", "other"),
            "summary":      kp.get("summary", ""),
            "description":  kp.get("description", ""),
            "code_example": kp.get("code_example", ""),
        } for kp in new_kps]

        run_cypher(driver, MERGE_KP, {"rows": kp_rows}, NEO4J_DATABASE)
        print(f"✓ 导入 {len(kp_rows)} 个 KP 节点")

        # 2. 建立 Chapter -CONTAINS-> KP 关系
        run_cypher(driver, MERGE_CHAPTER_CONTAINS, {"rows": kp_rows}, NEO4J_DATABASE)
        print(f"✓ 建立 {len(kp_rows)} 条章节包含关系")

        # 3. 建立先修关系（按名称匹配，允许找不到时静默跳过）
        if prereq_rows:
            run_cypher(driver, MERGE_PREREQUISITE, {"rows": prereq_rows}, NEO4J_DATABASE)
            print(f"✓ 建立先修关系（尝试 {len(prereq_rows)} 条）")

        # 4. 建立相关关系
        if related_rows:
            run_cypher(driver, MERGE_RELATED, {"rows": related_rows}, NEO4J_DATABASE)
            print(f"✓ 建立相关关系（尝试 {len(related_rows)} 条）")

    finally:
        driver.close()

    print("\n导入完成！")
    print(f"  新增 KP: {len(new_kps)} 个（ID: KP{KP_ID_START+1:04d} ~ KP{KP_ID_START+len(new_kps):04d}）")
    print(f"  数据库: {NEO4J_DATABASE} ({NEO4J_URI})")


if __name__ == "__main__":
    main()
