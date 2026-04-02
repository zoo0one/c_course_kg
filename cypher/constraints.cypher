// ============================================================
// C 语言课程知识图谱 - Neo4j 约束与索引
// ============================================================

// ── Chapter ──────────────────────────────────────────────────
CREATE CONSTRAINT chapter_chapter_id_unique IF NOT EXISTS
FOR (c:Chapter) REQUIRE c.chapter_id IS UNIQUE;

// ── KnowledgePoint ───────────────────────────────────────────
CREATE CONSTRAINT kp_kp_id_unique IF NOT EXISTS
FOR (k:KnowledgePoint) REQUIRE k.kp_id IS UNIQUE;

// ── Exercise（习题）────────────────────────────────────────────
CREATE CONSTRAINT exercise_id_unique IF NOT EXISTS
FOR (e:Exercise) REQUIRE e.exercise_id IS UNIQUE;

// ── ExampleCode（示例代码）──────────────────────────────────────
CREATE CONSTRAINT code_id_unique IF NOT EXISTS
FOR (c:ExampleCode) REQUIRE c.code_id IS UNIQUE;

// ── Resource（教学资源）─────────────────────────────────────────
CREATE CONSTRAINT resource_res_id_unique IF NOT EXISTS
FOR (r:Resource) REQUIRE r.res_id IS UNIQUE;

CREATE CONSTRAINT resource_res_id_exists IF NOT EXISTS
FOR (r:Resource) REQUIRE r.res_id IS NOT NULL;

// ── AssessmentPoint（考核点）────────────────────────────────────
CREATE CONSTRAINT assessment_id_unique IF NOT EXISTS
FOR (a:AssessmentPoint) REQUIRE a.assessment_id IS UNIQUE;

// ============================================================
// 索引（加速常见查询）
// ============================================================

// 章节：层级查询
CREATE INDEX chapter_parent_id_idx IF NOT EXISTS
FOR (c:Chapter) ON (c.parent_id);

CREATE INDEX chapter_order_idx IF NOT EXISTS
FOR (c:Chapter) ON (c.order);

// 知识点：名称搜索、分类过滤
CREATE INDEX kp_name_idx IF NOT EXISTS
FOR (k:KnowledgePoint) ON (k.name);

CREATE INDEX kp_chapter_id_idx IF NOT EXISTS
FOR (k:KnowledgePoint) ON (k.chapter_id);

CREATE INDEX kp_category_idx IF NOT EXISTS
FOR (k:KnowledgePoint) ON (k.category);

CREATE INDEX kp_source_idx IF NOT EXISTS
FOR (k:KnowledgePoint) ON (k.source);

CREATE INDEX kp_reviewed_idx IF NOT EXISTS
FOR (k:KnowledgePoint) ON (k.reviewed);

// 习题：所属章节、难度
CREATE INDEX exercise_chapter_id_idx IF NOT EXISTS
FOR (e:Exercise) ON (e.chapter_id);

CREATE INDEX exercise_difficulty_idx IF NOT EXISTS
FOR (e:Exercise) ON (e.difficulty);

// 示例代码：所属章节
CREATE INDEX code_chapter_id_idx IF NOT EXISTS
FOR (c:ExampleCode) ON (c.chapter_id);

// 教学资源：归属章节
CREATE INDEX resource_chapter_id_idx IF NOT EXISTS
FOR (r:Resource) ON (r.chapter_id);
