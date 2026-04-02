#!/bin/bash
# C 语言知识图谱系统 - 启动脚本

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "🚀 启动 C 语言知识图谱系统..."

# 检查依赖
command -v python3 >/dev/null 2>&1 || { echo "❌ 未找到 Python 3"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ 未找到 Node.js"; exit 1; }

# 激活虚拟环境
cd "$ROOT"
[ ! -d venv ] && /opt/homebrew/opt/python@3.11/bin/python3.11 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt 2>/dev/null || true

# 启动后端
echo "📦 启动后端 (http://localhost:8000)..."
venv/bin/python -m uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# 启动前端
echo "📱 启动前端 (http://localhost:3000)..."
cd "$ROOT/frontend"
[ ! -d node_modules ] && npm install
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ 系统已启动！"
echo "   前端: http://localhost:3000"
echo "   后端: http://localhost:8000"
echo "   API 文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait $BACKEND_PID $FRONTEND_PID
