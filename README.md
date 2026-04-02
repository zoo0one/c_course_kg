# 📚 C 语言课程知识图谱系统（c_course_kg）

一个面向课程学习场景的知识图谱系统：
- 后端：`FastAPI + Neo4j`
- 前端：`React + TypeScript + Cytoscape`
- AI：支持本地 `Ollama` 或 OpenAI 兼容接口
- 管理端：支持 PDF 上传 → 抽取 → 审核 → 入库

适合作为毕业设计的**可演示、可扩展、可复现**项目骨架。

---

## 目录

- [1. 项目能力概览](#1-项目能力概览)
- [2. 技术栈](#2-技术栈)
- [3. 真实目录结构（按当前代码校正）](#3-真实目录结构按当前代码校正)
- [4. 运行前准备](#4-运行前准备)
- [5. 安装与启动](#5-安装与启动)
- [6. 数据导入与构建流程](#6-数据导入与构建流程)
- [7. 管理端 PDF 抽取流程](#7-管理端-pdf-抽取流程)
- [8. API 总览（按路由全量校正）](#8-api-总览按路由全量校正)
- [9. 前端功能说明](#9-前端功能说明)
- [10. 常见问题排查](#10-常见问题排查)
- [11. 开发建议（毕业设计场景）](#11-开发建议毕业设计场景)

---

## 1. 项目能力概览

本项目围绕 C 语言课程构建知识图谱，核心能力包括：

1. **图谱存储与查询**
   - Chapter / KnowledgePoint 节点
   - `CONTAINS` / `PREREQUISITE` / `RELATED` / `EXTENDS` 关系
2. **图谱可视化**
   - 图节点与关系边交互展示
   - 节点点击查看先修、后继、相关知识点
3. **AI 学习助手**
   - 普通问答（`POST /api/ai/chat`）
   - 流式回答（`GET /api/ai/chat/stream`，SSE）
4. **管理后台数据闭环**
   - 上传 PDF
   - 自动抽取（含 OCR 回退 + 清洗）
   - 审核队列
   - 一键应用到 Neo4j
5. **多种导入方式**
   - 内置课程骨架导入（`seed_course.py`）
   - CSV 批量导入（`import_data.py`）

---

## 2. 技术栈

### 后端
- Python 3.11+
- FastAPI
- Neo4j Python Driver
- Pydantic v2
- Requests
- PyMuPDF / Pillow / pytesseract

### 前端
- React 18 + TypeScript
- Vite
- Ant Design 5
- Cytoscape.js
- Zustand
- TailwindCSS（已集成）

### 数据与脚本
- Pandas
- 章节/语料处理脚本（`backend/scripts`）

---

## 3. 真实目录结构（按当前代码校正）

```text
c_course_kg/
├── backend/
│   ├── app.py                          # FastAPI 入口
│   ├── db/
│   │   └── neo4j.py                    # Neo4j 客户端
│   ├── models/
│   │   └── schemas.py                  # Pydantic 输出模型
│   ├── routers/
│   │   ├── graph.py                    # 图谱查询接口
│   │   ├── ai.py                       # AI 接口（含流式）
│   │   └── admin.py                    # 管理端上传/抽取/审核
│   ├── services/
│   │   ├── ai.py                       # Ollama/OpenAI 兼容封装
│   │   └── text_cleaner.py             # PDF 文本清洗管道
│   └── scripts/
│       ├── seed_course.py              # 内置课程骨架导入
│       ├── import_data.py              # CSV 导入 Neo4j
│       ├── corpus_builder.py           # 语料切分
│       └── course_schema.py            # 课程骨架数据
├── frontend/
│   ├── src/
│   │   ├── components/                 # Graph/AIChat/Admin/Layout/pages
│   │   ├── services/                   # api.ts / store.ts
│   │   ├── styles/
│   │   ├── types/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts                  # /api 代理到 127.0.0.1:8000
│   └── README.md
├── cypher/
│   └── constraints.cypher
├── data/
│   ├── corpus/
│   ├── export/
│   ├── extracted/
│   ├── raw/
│   └── uploads/
├── tests/
├── requirements.txt
├── .env.example
├── start.sh                            # 一键启动后端+前端
├── STARTUP_GUIDE.md
└── README.md
```

---

## 4. 运行前准备

请确保以下环境已安装：

- Python 3.11+
- Node.js 18+
- Neo4j（本地或远程）

可选（使用本地 AI 时）：
- Ollama

### 4.1 配置环境变量

在项目根目录执行：

```bash
cp .env.example .env
```

关键配置项：

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j

AI_PROVIDER=ollama
AI_TIMEOUT=120

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b

# 或在线兼容接口
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_FALLBACK_MODELS=
```

---

## 5. 安装与启动

### 方式 A：一键启动（推荐）

```bash
chmod +x start.sh
./start.sh
```

脚本会：
- 自动创建/使用 `venv`
- 安装 Python 依赖
- 启动后端（`8000`）
- 启动前端（`3000`）

访问地址：
- 前端：`http://localhost:3000`
- 后端：`http://localhost:8000`
- 文档：`http://localhost:8000/docs`

### 方式 B：手动启动

#### 1）后端

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
```

#### 2）前端（新终端）

```bash
cd frontend
npm install
npm run dev
```

---

## 6. 数据导入与构建流程

本项目推荐三种路径：

### 路径 1：快速演示（最省事）

导入内置课程骨架：

```bash
source venv/bin/activate
python -m backend.scripts.seed_course
```

常用参数：
- `--clear`：导入前清空库
- `--dry-run`：仅打印统计

### 路径 2：CSV 批量导入（你已有结构化数据）

准备以下文件到 `data/export/`：
- `chapters.csv`
- `kps.csv`
- `contains_edges.csv`
- `relations.csv`（可选）

执行：

```bash
source venv/bin/activate
python -m backend.scripts.import_data
```

### 路径 3：从文本清洗/语料处理开始

语料切分脚本：

```bash
source venv/bin/activate
python -m backend.scripts.corpus_builder
```

输出到：
- `data/corpus/sections.jsonl`
- `data/corpus/chapters.json`

---

## 7. 管理端 PDF 抽取流程

对应前端管理员页面 + `admin` 路由：

1. 上传 PDF：`POST /api/admin/upload-pdf`
2. 开始抽取：`POST /api/admin/extract/{job_id}/start`
3. 查看状态：`GET /api/admin/extract/{job_id}/status`
4. 预览结果：`GET /api/admin/extract/{job_id}/preview`
5. 加入审核：`POST /api/admin/extract/{job_id}/to-review`
6. 审核通过：`POST /api/admin/review/{review_id}/approve`
7. 应用入库：`POST /api/admin/apply-reviewed`

抽取过程特性：
- 文本层为空时自动 OCR 回退
- 内置清洗管道（编码、噪声、章节识别、代码块保护等）
- 支持重试与抽取日志落盘（`data/uploads/jobs/...`）

---

## 8. API 总览（按路由全量校正）

### 8.1 图谱相关（`backend/routers/graph.py`）

- `GET /api/health`
- `GET /api/stats`
- `GET /api/chapters`
- `GET /api/chapters/{chapter_id}`
- `GET /api/kps/search?q=...`
- `GET /api/kps/{kp_id}`
- `GET /api/kps/{kp_id}/prerequisites`
- `GET /api/kps/{kp_id}/successors`
- `GET /api/kps/{kp_id}/related`
- `GET /api/graph`

### 8.2 AI 相关（`backend/routers/ai.py`）

- `GET /api/ai/health`
- `POST /api/ai/chat`
- `GET /api/ai/chat/stream`
- `POST /api/ai/explain`
- `POST /api/ai/recommend-path`
- `POST /api/ai/code-review`

### 8.3 管理端（`backend/routers/admin.py`）

- `POST /api/admin/upload-pdf`
- `POST /api/admin/extract/{job_id}/start`
- `GET /api/admin/extract/{job_id}/status`
- `GET /api/admin/extract/{job_id}/preview`
- `POST /api/admin/extract/{job_id}/to-review`
- `POST /api/admin/parse-upload`
- `POST /api/admin/confirm-import`
- `GET /api/admin/review`
- `POST /api/admin/review/{review_id}/approve`
- `POST /api/admin/review/batch/approve-all`
- `POST /api/admin/review/{review_id}/reject`
- `POST /api/admin/apply-reviewed`
- `POST /api/admin/kps`
- `PUT /api/admin/kps/{kp_id}`
- `DELETE /api/admin/kps/{kp_id}`

---

## 9. 前端功能说明

- 首页统计与快速入口（图谱 / AI / 管理）
- 图谱页面：
  - 节点点击弹出知识点详情
  - 图例切换
  - 按章节筛选
- AI 抽屉聊天：
  - 检测 AI 健康状态
  - 支持流式输出
- 管理员页面：
  - 数据上传
  - 审核队列
  - 知识点编辑

---

## 10. 常见问题排查

### Q1：后端启动后直接报 Neo4j 连接失败
- 检查 Neo4j 服务是否启动
- 检查 `.env` 中 `NEO4J_URI/USER/PASSWORD`

### Q2：前端提示无法连接后端
- 检查 `http://localhost:8000/api/health`
- 确认后端在 `8000` 端口运行
- 前端通过 Vite 代理请求 `/api`

### Q3：AI 显示未连接
- `AI_PROVIDER=ollama` 时确认执行了 `ollama serve`
- `AI_PROVIDER=openai` 时确认 `OPENAI_API_KEY` 正确

### Q4：图谱为空
- 先执行一次 `seed_course` 或 `import_data`
- 再刷新前端页面

### Q5：PDF 抽取结果为空
- 管理端可查看 `extract/{job_id}/preview`
- 检查扫描页范围环境变量：
  - `MAX_SCAN_PAGES`
  - `EXTRACT_CHAPTER_MODE`
  - `EXTRACT_PAGE_START`
  - `EXTRACT_PAGE_END`

---

## 11. 开发建议（毕业设计场景）

1. **演示前固定数据集**：用 `seed_course --clear` 保证稳定演示。  
2. **准备两套 AI 方案**：本地 Ollama + 在线接口兜底。  
3. **答辩展示链路建议**：
   - 先展示图谱浏览
   - 再展示 AI 问答
   - 最后展示管理端 PDF 抽取与审核闭环

---

如果你希望，我可以下一步再给你补一版「**答辩展示 README（PPT 配套版）**」，会把“演示话术、页面截图位、指标表格模板”也一起写好。