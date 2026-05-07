#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PORT=8011
FRONTEND_PORT=5173
FRONTEND_URL="http://127.0.0.1:$FRONTEND_PORT"
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
if [ -n "$LAN_IP" ]; then
  SHARED_URL="http://$LAN_IP:$FRONTEND_PORT"
else
  SHARED_URL=""
fi

log() {
  printf '\n[%s] %s\n' "$1" "$2"
}

warn_if_port_in_use() {
  local port="$1"
  local name="$2"
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    log "WARN" "$name 端口 $port 已被占用，可能会导致启动失败。"
  fi
}

escape_for_applescript() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

require_cmd() {
  local cmd="$1"
  local hint="$2"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    log "ERROR" "未找到命令: $cmd。$hint"
    exit 1
  fi
}

if [ ! -d "$BACKEND_DIR" ] || [ ! -d "$FRONTEND_DIR" ]; then
  log "ERROR" "目录结构不完整，请确认脚本位于项目根目录。"
  exit 1
fi

require_cmd "python3" "请先安装 Python 3.9+。"
require_cmd "npm" "请先安装 Node.js 与 npm。"
require_cmd "osascript" "此脚本依赖 macOS Terminal 自动开窗。"
require_cmd "ipconfig" "无法获取本机局域网地址。"

warn_if_port_in_use "$BACKEND_PORT" "后端"
warn_if_port_in_use "$FRONTEND_PORT" "前端"

BACKEND_CMD=$(cat <<EOF
cd "$BACKEND_DIR"
echo "[backend] 当前目录: \$(pwd)"
if [ ! -d ".venv" ]; then
  echo "[backend] 未检测到虚拟环境，正在创建 .venv ..."
  python3 -m venv .venv
fi
source .venv/bin/activate
if [ ! -f ".venv/.deps_ready" ]; then
  echo "[backend] 首次安装依赖，请稍候 ..."
  python -m pip install --upgrade pip
  pip install -r requirements.txt
  touch .venv/.deps_ready
fi
echo "[backend] 启动中: http://127.0.0.1:$BACKEND_PORT"
echo "[backend] 文档地址: http://127.0.0.1:$BACKEND_PORT/docs"
uvicorn app.main:app --host 127.0.0.1 --port $BACKEND_PORT --reload
EOF
)

FRONTEND_CMD=$(cat <<EOF
cd "$FRONTEND_DIR"
echo "[frontend] 当前目录: \$(pwd)"
if [ ! -d "node_modules" ]; then
  echo "[frontend] 首次安装依赖，请稍候 ..."
  npm install
fi
echo "[frontend] 启动中 (局域网可访问) ..."
npm run dev -- --host 0.0.0.0 --port $FRONTEND_PORT --strictPort
EOF
)

BACKEND_CMD_ESCAPED="$(escape_for_applescript "$BACKEND_CMD")"
FRONTEND_CMD_ESCAPED="$(escape_for_applescript "$FRONTEND_CMD")"

log "INFO" "即将打开两个 Terminal 标签页，分别启动后端与前端。"
if [ -n "$SHARED_URL" ]; then
  log "INFO" "同局域网分享地址: $SHARED_URL"
else
  log "WARN" "未识别到局域网 IP，请手动执行: ipconfig getifaddr en0"
fi

osascript <<EOF
tell application "Terminal"
  activate
  do script "$BACKEND_CMD_ESCAPED"
  delay 1.2
  do script "$FRONTEND_CMD_ESCAPED"
end tell
EOF

log "INFO" "等待前端服务启动后自动打开浏览器 ..."
sleep 3
open "$FRONTEND_URL" || log "WARN" "自动打开浏览器失败，请手动访问: $FRONTEND_URL"

log "DONE" "启动指令已发送到 Terminal。关闭对应终端窗口即可停止服务。"

