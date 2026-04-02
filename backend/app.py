"""FastAPI 应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers.graph import router as graph_router
from backend.routers.ai import ai_router
from backend.routers.admin import admin_router

app = FastAPI(
    title="C 语言知识图谱 API",
    description="基于 Neo4j 和 Ollama 的 C 语言知识图谱系统",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graph_router, prefix="/api")
app.include_router(ai_router, prefix="/api")
app.include_router(admin_router, prefix="/api")


@app.get("/")
def root():
    return {"message": "C 语言知识图谱 API", "docs": "/docs"}
