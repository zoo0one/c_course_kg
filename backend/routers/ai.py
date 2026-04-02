"""AI 相关路由"""
from fastapi import APIRouter, Body
from typing import Optional, Dict, Any
from pydantic import BaseModel
import json

from backend.db.neo4j import neo4j_client
from backend.services.ai import ai_service
from fastapi.responses import StreamingResponse

ai_router = APIRouter(prefix="/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


@ai_router.get("/health")
def ai_health():
    """检查 AI 服务状态"""
    is_ready = ai_service.is_ready()
    provider = ai_service.provider_name
    model = ai_service.model_name
    msg = (
        "在线 AI 接口可用" if provider == "openai" else "Ollama 服务正常运行"
    ) if is_ready else (
        "请配置 OPENAI_API_KEY 并检查 OPENAI_BASE_URL" if provider == "openai" else "请启动 Ollama 服务: ollama serve"
    )
    return {
        "ready": is_ready,
        "provider": provider,
        "model": model,
        "status": "就绪" if is_ready else "未连接",
        "message": msg,
    }


@ai_router.post("/chat")
def ai_chat(request: ChatRequest):
    """AI 聊天（完整响应）"""
    if not ai_service.is_ready():
        return {"response": "AI 服务暂时不可用，请确保 Ollama 已启动", "suggestions": []}
    try:
        response = ai_service.chat(request.message, request.context, stream=False)
        return {"response": response, "suggestions": []}
    except Exception as e:
        return {"response": f"抱歉，发生了错误: {str(e)}", "suggestions": []}


@ai_router.get("/chat/stream")
def ai_chat_stream(message: str, context: Optional[str] = None):
    """AI 聊天（流式响应）"""
    if not ai_service.is_ready():
        return StreamingResponse(
            iter(["AI 服务暂时不可用，请确保 Ollama 已启动"]),
            media_type="text/event-stream",
        )
    try:
        ctx = json.loads(context) if context else None
        return StreamingResponse(
            ai_service.chat(message, ctx, stream=True),
            media_type="text/event-stream",
        )
    except Exception as e:
        return StreamingResponse(iter([f"错误: {str(e)}"]), media_type="text/event-stream")


@ai_router.post("/explain")
def ai_explain(kp_id: str = Body(..., embed=True)):
    """AI 解释知识点"""
    rows = neo4j_client.run(
        "MATCH (k:KnowledgePoint {kp_id: $kp_id}) RETURN k.name AS name, properties(k) AS data",
        {"kp_id": kp_id},
    )
    if not rows:
        return {"explanation": "知识点未找到"}
    try:
        return {"explanation": ai_service.explain_kp(rows[0]["name"], rows[0]["data"])}
    except Exception as e:
        return {"explanation": f"解释失败: {str(e)}"}


@ai_router.post("/recommend-path")
def ai_recommend_path(kp_id: str = Body(..., embed=True)):
    """AI 推荐学习路径"""
    rows = neo4j_client.run(
        "MATCH (k:KnowledgePoint {kp_id: $kp_id}) RETURN k.name AS name",
        {"kp_id": kp_id},
    )
    if not rows:
        return {"path": [], "message": "知识点未找到"}
    try:
        return {"path": [], "message": ai_service.recommend_path(rows[0]["name"])}
    except Exception as e:
        return {"path": [], "message": f"推荐失败: {str(e)}"}


@ai_router.post("/code-review")
def ai_code_review(code: str = Body(..., embed=True)):
    """AI 代码审查"""
    try:
        return {"review": ai_service.code_review(code)}
    except Exception as e:
        return {"review": f"审查失败: {str(e)}"}
