"""一键将课程骨架（章节 + 知识点 + 关系）导入 Neo4j。

用法：
    python3 -m backend.scripts.seed_course
    # 或
    python3 backend/scripts/seed_course.py

选项：
    --clear   导入前清空数据库（谨慎使用）
    --dry-run 只打印统计，不写库
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 确保项目根在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.neo4j import neo4j_client  # noqa: E402
from backend.scripts.course_schema import CHAPTERS, KNOWLEDGE_POINTS, EXAMPLES, RELATIONS  # noqa: E402


def apply_constraints() -> None:
    """应用约束与索引（幂等）"""
    stmts = [
        "CREATE CONSTRAINT chapter_id_unique IF NOT EXISTS FOR (c:Chapter) REQUIRE c.chapter_id IS UNIQUE",
        "CREATE CONSTRAINT kp_id_unique IF NOT EXISTS FOR (k:KnowledgePoint) REQUIRE k.kp_id IS UNIQUE",
        "CREATE CONSTRAINT example_id_unique IF NOT EXISTS FOR (e:Example) REQUIRE e.example_id IS UNIQUE",
        "CREATE INDEX kp_name_idx IF NOT EXISTS FOR (k:KnowledgePoint) ON (k.name)",
        "CREATE INDEX kp_chapter_idx IF NOT EXISTS FOR (k:KnowledgePoint) ON (k.chapter_id)",
        "CREATE INDEX example_chapter_idx IF NOT EXISTS FOR (e:Example) ON (e.chapter_id)",
    ]
    for s in stmts:
        try:
            neo4j_client.run(s)
        except Exception as e:
            print(f"  [warn] constraint/index: {e}")


def clear_db() -> None:
    neo4j_client.run("MATCH (n) DETACH DELETE n")
    print("  数据库已清空")


def seed_chapters() -> int:
    neo4j_client.run(
        """
        UNWIND $rows AS row
        MERGE (c:Chapter {chapter_id: row.chapter_id})
        SET c.title = row.title,
            c.order = toInteger(row.order),
            c.description = row.description
        """,
        {"rows": CHAPTERS},
    )
    return len(CHAPTERS)


def seed_kps() -> int:
    neo4j_client.run(
        """
        UNWIND $rows AS row
        MERGE (k:KnowledgePoint {kp_id: row.kp_id})
        SET k.name      = row.name,
            k.chapter_id = row.chapter_id,
            k.section   = row.section,
            k.category  = row.category,
            k.aliases   = row.aliases,
            k.source    = row.source,
            k.reviewed  = row.reviewed,
            k.source_book = row.source_book,
            k.source_page = row.source_page,
            k.source_pages = row.source_pages,
            k.role      = row.role,
            k.level     = row.level,
            k.main_chain_order = row.main_chain_order,
            k.importance = row.importance
        """,
        {"rows": KNOWLEDGE_POINTS},
    )
    # CONTAINS 关系
    neo4j_client.run(
        """
        UNWIND $rows AS row
        MATCH (c:Chapter {chapter_id: row.chapter_id})
        MATCH (k:KnowledgePoint {kp_id: row.kp_id})
        MERGE (c)-[:CONTAINS]->(k)
        """,
        {"rows": KNOWLEDGE_POINTS},
    )
    return len(KNOWLEDGE_POINTS)


def seed_examples() -> int:
    neo4j_client.run(
        """
        UNWIND $rows AS row
        MERGE (e:Example {example_id: row.example_id})
        SET e.name = row.name,
            e.chapter_id = row.chapter_id,
            e.section = row.section,
            e.scene = row.scene,
            e.difficulty = row.difficulty,
            e.target_kp_id = row.target_kp_id,
            e.source = row.source,
            e.reviewed = row.reviewed
        """,
        {"rows": EXAMPLES},
    )
    return len(EXAMPLES)


def seed_relations() -> int:
    prereqs = [r for r in RELATIONS if r["relation_type"] == "PREREQUISITE"]
    related = [r for r in RELATIONS if r["relation_type"] == "RELATED"]
    extends = [r for r in RELATIONS if r["relation_type"] == "EXTENDS"]
    example_of = [r for r in RELATIONS if r["relation_type"] == "EXAMPLE_OF"]

    if prereqs:
        neo4j_client.run(
            """
            UNWIND $rows AS row
            MATCH (a:KnowledgePoint {kp_id: row.source})
            MATCH (b:KnowledgePoint {kp_id: row.target})
            MERGE (a)-[r:PREREQUISITE]->(b)
            SET r.description = row.description
            """,
            {"rows": prereqs},
        )
    if related:
        neo4j_client.run(
            """
            UNWIND $rows AS row
            MATCH (a:KnowledgePoint {kp_id: row.source})
            MATCH (b:KnowledgePoint {kp_id: row.target})
            MERGE (a)-[r:RELATED]->(b)
            SET r.description = row.description
            """,
            {"rows": related},
        )
    if extends:
        neo4j_client.run(
            """
            UNWIND $rows AS row
            MATCH (a:KnowledgePoint {kp_id: row.source})
            MATCH (b:KnowledgePoint {kp_id: row.target})
            MERGE (a)-[r:EXTENDS]->(b)
            SET r.description = row.description
            """,
            {"rows": extends},
        )
    if example_of:
        neo4j_client.run(
            """
            UNWIND $rows AS row
            MATCH (a:Example {example_id: row.source})
            MATCH (b:KnowledgePoint {kp_id: row.target})
            MERGE (a)-[r:EXAMPLE_OF]->(b)
            SET r.description = row.description
            """,
            {"rows": example_of},
        )
    return len(RELATIONS)


def main() -> None:
    parser = argparse.ArgumentParser(description="导入C语言课程骨架到 Neo4j")
    parser.add_argument("--clear", action="store_true", help="导入前清空数据库")
    parser.add_argument("--dry-run", action="store_true", help="只打印统计，不写库")
    args = parser.parse_args()

    print("=" * 50)
    print("C语言课程知识图谱 · 骨架导入")
    print("=" * 50)
    print(f"  章节:   {len(CHAPTERS)}")
    print(f"  知识点: {len(KNOWLEDGE_POINTS)}")
    print(f"  示例:   {len(EXAMPLES)}")
    print(f"  关系:   {len(RELATIONS)}")

    if args.dry_run:
        print("[dry-run] 跳过写库")
        return

    print("\n[1/4] 应用约束与索引...")
    apply_constraints()

    if args.clear:
        print("[1.5] 清空数据库...")
        clear_db()

    print("[2/4] 导入章节...")
    n = seed_chapters()
    print(f"  写入 {n} 个章节")

    print("[3/5] 导入知识点...")
    n = seed_kps()
    print(f"  写入 {n} 个知识点 + CONTAINS 关系")

    print("[4/5] 导入示例节点...")
    n = seed_examples()
    print(f"  写入 {n} 个示例节点")

    print("[5/5] 导入先修/相关关系...")
    n = seed_relations()
    print(f"  写入 {n} 条关系")

    # 验证
    stats = neo4j_client.run(
        """
        MATCH (c:Chapter) WITH count(c) AS ch
        MATCH (k:KnowledgePoint) WITH ch, count(k) AS kp
        MATCH ()-[r]->() WITH ch, kp, count(r) AS rel
        RETURN ch, kp, rel
        """
    )
    if stats:
        s = stats[0]
        print(f"\n[验证] Neo4j 当前: 章节={s['ch']}, 知识点={s['kp']}, 关系={s['rel']}")

    print("\n完成。")


if __name__ == "__main__":
    main()
