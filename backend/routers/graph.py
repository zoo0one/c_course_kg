"""图谱和知识点相关路由"""
from fastapi import APIRouter, Query, HTTPException
from typing import List

from backend.db.neo4j import neo4j_client
from backend.models.schemas import ChapterOut, KnowledgePointOut, ChapterDetailOut

router = APIRouter(tags=["graph"])


@router.get("/health")
def health():
    rows = neo4j_client.run("RETURN 1 AS ok")
    return {"ok": rows[0]["ok"] if rows else 0}


@router.get("/stats")
def get_stats():
    rows = neo4j_client.run("""
        MATCH (k:KnowledgePoint) WITH COUNT(k) AS total_kps
        MATCH (c:Chapter) WITH total_kps, COUNT(c) AS total_chapters
        MATCH ()-[r]->() WITH total_kps, total_chapters, COUNT(r) AS total_relations
        RETURN {
            total_kps: total_kps,
            total_chapters: total_chapters,
            total_relations: total_relations,
            total_segments: 0
        } AS stats
    """)
    if rows:
        return rows[0]["stats"]
    return {"total_kps": 0, "total_chapters": 0, "total_relations": 0, "total_segments": 0}


@router.get("/chapters", response_model=List[ChapterOut])
def list_chapters():
    return neo4j_client.run("""
        MATCH (c:Chapter)
        RETURN c.chapter_id AS chapter_id, c.title AS title, c.order AS order
        ORDER BY c.order
    """)


@router.get("/chapters/{chapter_id}", response_model=ChapterDetailOut)
def get_chapter_detail(chapter_id: str):
    chapter_rows = neo4j_client.run(
        "MATCH (c:Chapter {chapter_id: $chapter_id}) RETURN c.chapter_id AS chapter_id, c.title AS title, c.order AS order",
        {"chapter_id": chapter_id},
    )
    if not chapter_rows:
        raise HTTPException(status_code=404, detail="Chapter not found")
    kp_rows = neo4j_client.run(
        """
        MATCH (c:Chapter {chapter_id: $chapter_id})-[:CONTAINS]->(k:KnowledgePoint)
        RETURN k.kp_id AS kp_id, k.name AS name, k.chapter_id AS chapter_id,
               k.section AS section, k.aliases AS aliases, k.source AS source
        ORDER BY k.section
        """,
        {"chapter_id": chapter_id},
    )
    return {"chapter": chapter_rows[0], "kps": kp_rows}


@router.get("/kps/search", response_model=List[KnowledgePointOut])
def search_kps(q: str = Query(..., min_length=1)):
    return neo4j_client.run(
        """
        MATCH (k:KnowledgePoint)
        WHERE k.name CONTAINS $q OR coalesce(k.aliases, "") CONTAINS $q
        RETURN k.kp_id AS kp_id, k.name AS name, k.chapter_id AS chapter_id,
               k.section AS section, k.aliases AS aliases, k.source AS source
        ORDER BY k.chapter_id, k.section LIMIT 50
        """,
        {"q": q},
    )


@router.get("/kps/{kp_id}", response_model=KnowledgePointOut)
def get_kp_detail(kp_id: str):
    rows = neo4j_client.run(
        "MATCH (k:KnowledgePoint {kp_id: $kp_id}) RETURN k.kp_id AS kp_id, k.name AS name, k.chapter_id AS chapter_id, k.section AS section, k.aliases AS aliases, k.source AS source",
        {"kp_id": kp_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Knowledge point not found")
    return rows[0]


@router.get("/kps/{kp_id}/prerequisites", response_model=List[KnowledgePointOut])
def get_prerequisites(kp_id: str):
    return neo4j_client.run(
        """
        MATCH (k:KnowledgePoint {kp_id: $kp_id})-[:PREREQUISITE]->(prereq:KnowledgePoint)
        RETURN prereq.kp_id AS kp_id, prereq.name AS name, prereq.chapter_id AS chapter_id,
               prereq.section AS section, prereq.aliases AS aliases, prereq.source AS source
        """,
        {"kp_id": kp_id},
    )


@router.get("/kps/{kp_id}/successors", response_model=List[KnowledgePointOut])
def get_successors(kp_id: str):
    return neo4j_client.run(
        """
        MATCH (k:KnowledgePoint {kp_id: $kp_id})<-[:PREREQUISITE]-(succ:KnowledgePoint)
        RETURN succ.kp_id AS kp_id, succ.name AS name, succ.chapter_id AS chapter_id,
               succ.section AS section, succ.aliases AS aliases, succ.source AS source
        """,
        {"kp_id": kp_id},
    )


@router.get("/kps/{kp_id}/related", response_model=List[KnowledgePointOut])
def get_related(kp_id: str):
    return neo4j_client.run(
        """
        MATCH (k:KnowledgePoint {kp_id: $kp_id})-[:RELATED]-(related:KnowledgePoint)
        RETURN related.kp_id AS kp_id, related.name AS name, related.chapter_id AS chapter_id,
               related.section AS section, related.aliases AS aliases, related.source AS source
        LIMIT 10
        """,
        {"kp_id": kp_id},
    )


@router.get("/graph")
def get_graph():
    nodes = neo4j_client.run("""
        MATCH (n) WHERE n:KnowledgePoint OR n:Chapter
        RETURN {
            id: COALESCE(n.kp_id, n.chapter_id),
            label: COALESCE(n.name, n.title),
            type: CASE WHEN n:KnowledgePoint THEN 'knowledge_point' ELSE 'chapter' END,
            data: properties(n)
        } AS node LIMIT 500
    """)
    edges = neo4j_client.run("""
        MATCH (a)-[r]->(b)
        WHERE (a:KnowledgePoint OR a:Chapter) AND (b:KnowledgePoint OR b:Chapter)
        RETURN {
            id: id(r),
            source: COALESCE(a.kp_id, a.chapter_id),
            target: COALESCE(b.kp_id, b.chapter_id),
            label: type(r),
            type: type(r)
        } AS edge LIMIT 1000
    """)
    return {
        "nodes": [n["node"] for n in nodes],
        "edges": [e["edge"] for e in edges],
    }
