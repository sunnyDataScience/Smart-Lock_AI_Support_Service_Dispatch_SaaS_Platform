#!/usr/bin/env bash
# start-web.sh — npm install + dev server（背景啟動，PID 寫入 .runtime/web.pid）
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"
cd "$REPO_ROOT"

log_title "Stage 3/4 — 前端 Web"

cd web

# 1. .env.local
if [[ ! -f .env.local ]]; then
  if [[ -f .env.local.example ]]; then
    cp .env.local.example .env.local
    log_ok "建立 .env.local（從 .env.local.example 複製）"
  else
    cat > .env.local <<EOF
NEXT_PUBLIC_API_BASE_URL=http://localhost:${API_HOST_PORT}
EOF
    log_ok "建立預設 .env.local（指向 localhost:${API_HOST_PORT}）"
  fi
else
  log_ok ".env.local 已存在（不覆寫）"
fi

# 2. npm install（只在 node_modules 不存在或 package-lock 較新時跑）
if [[ ! -d node_modules ]]; then
  log_step "安裝依賴（首次約 1-2 分鐘）"
  npm install --silent
  log_ok "npm install 完成"
elif [[ package-lock.json -nt node_modules ]]; then
  log_step "package-lock 更新，重新安裝依賴"
  npm install --silent
  log_ok "npm install 完成"
else
  log_ok "node_modules 已存在（package-lock.json 無變更）"
fi

# 3. 如果已有 web 在跑，先停掉
if [[ -f "$WEB_PID_FILE" ]]; then
  old_pid=$(cat "$WEB_PID_FILE" 2>/dev/null || echo "")
  if is_pid_alive "$old_pid"; then
    log_step "停止既有的 web dev server (pid=$old_pid)"
    kill "$old_pid" 2>/dev/null || true
    sleep 2
  fi
  rm -f "$WEB_PID_FILE"
fi

# 4. 背景啟動 dev server
log_step "啟動 dev server（背景）"
nohup npm run dev >"$WEB_LOG_FILE" 2>&1 &
WEB_PID=$!
echo "$WEB_PID" >"$WEB_PID_FILE"
log_info "PID=$WEB_PID，logs=$WEB_LOG_FILE"

# 5. 等 Next.js ready（看 log 出現 "Ready"）
log_step "等待 Next.js 編譯（最多 60s）"
i=0
while (( i < 60 )); do
  if grep -q "Ready in" "$WEB_LOG_FILE" 2>/dev/null; then
    break
  fi
  if ! is_pid_alive "$WEB_PID"; then
    log_err "Web dev server 已退出，看 log：$WEB_LOG_FILE"
    tail -20 "$WEB_LOG_FILE"
    exit 1
  fi
  sleep 1
  ((i++))
done

# 6. HTTP 健康檢查
if wait_http "http://localhost:${WEB_PORT}" 15 "Web"; then
  echo ""
  log_ok "Web 就緒：http://localhost:${WEB_PORT}"
  log_info "登入：admin@example.com / changeme123"
  log_info "Logs：tail -f $WEB_LOG_FILE"
  log_info "停止：./scripts/setup/down.sh 或 kill $WEB_PID"
else
  log_warn "HTTP 檢查未通過，但 dev server 可能還在編譯。看 logs：tail -f $WEB_LOG_FILE"
fi
