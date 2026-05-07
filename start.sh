#!/bin/bash
# C 语言知识图谱系统 - 启动脚本

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

CLEAN_MODE=false
for arg in "$@"; do
  case "$arg" in
    --clean)
      CLEAN_MODE=true
      ;;
  esac
done

echo "🚀 启动 C 语言知识图谱系统..."

# 检查依赖
command -v python3 >/dev/null 2>&1 || { echo "❌ 未找到 Python 3"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "❌ 未找到 Node.js"; exit 1; }

# 激活虚拟环境
cd "$ROOT"
if [ ! -d venv ]; then
  /opt/homebrew/opt/python@3.11/bin/python3.11 -m venv venv
  source venv/bin/activate
  pip install -q -r requirements.txt
else
  source venv/bin/activate
fi

# 端口工具
is_port_in_use() {
  lsof -ti :"$1" >/dev/null 2>&1
}

kill_port_listener() {
  local port="$1"
  local pids
  pids=$(lsof -ti :"$port" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill -9 2>/dev/null || true
  fi
}

pick_free_port() {
  local start_port="$1"
  local port="$start_port"
  while is_port_in_use "$port"; do
    port=$((port + 1))
  done
  echo "$port"
}

if [ "$CLEAN_MODE" = true ]; then
  echo "🧹 清理旧的开发端口占用..."
  for p in 3000 3001 3002 3003 8000 8001 8002 8003; do
    kill_port_listener "$p"
  done
fi

BACKEND_PORT=$(pick_free_port 8000)
FRONTEND_PORT=$(pick_free_port 3000)
BACKEND_TARGET="http://127.0.0.1:${BACKEND_PORT}"

# 启动后端
echo "📦 启动后端 (${BACKEND_TARGET})..."
venv/bin/python -m uvicorn backend.app:app --reload --host 0.0.0.0 --port "$BACKEND_PORT" &
BACKEND_PID=$!

# 等待后端启动，快速失败提示
sleep 2
if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
  echo "❌ 后端启动失败，请检查日志"
  exit 1
fi

# 启动前端
echo "📱 启动前端 (http://localhost:${FRONTEND_PORT})..."
cd "$ROOT/frontend"
[ ! -d node_modules ] && npm install
VITE_PORT="$FRONTEND_PORT" VITE_BACKEND_TARGET="$BACKEND_TARGET" npm run dev -- --port "$FRONTEND_PORT" &
FRONTEND_PID=$!

echo ""
echo "✅ 系统已启动！"
echo "   前端: http://localhost:${FRONTEND_PORT}"
echo "   后端: ${BACKEND_TARGET}"
echo "   API 文档: ${BACKEND_TARGET}/docs"
echo ""
echo "提示: 使用 ./start.sh --clean 可先清理旧端口再启动"
echo "按 Ctrl+C 停止服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait $BACKEND_PID $FRONTEND_PID
