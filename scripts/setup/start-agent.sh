#!/usr/bin/env bash
# start-agent.sh — 建 Python venv + 安裝依賴 + 背景啟動 FastAPI agent
#
# 模式：
#   - 預設：背景啟 uvicorn（webhook 模式），無 LINE 金鑰也能跑 /chat 與 /health
#   - --cli：前景跑 main.py（product_info 自檢，不啟服務）
#   - --check：只檢查 .env 是否齊備，不啟動
#
# Agent 必須：VERTEX_PROJECT_ID + gcloud 已 auth（Application Default Credentials）
# Agent 選用：LINE_CHANNEL_SECRET / LINE_CHANNEL_ACCESS_TOKEN（webhook 才用）
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"
cd "$REPO_ROOT"

MODE="serve"
for arg in "$@"; do
  case "$arg" in
    --cli) MODE="cli" ;;
    --check) MODE="check" ;;
    -h|--help)
      grep -E "^# " "$0" | sed 's/^# //'
      exit 0
      ;;
  esac
done

log_title "Stage 4/4 — Agent (LINE Bot / FastAPI)"

# 1. 確認 .env 存在 & 必填
if [[ ! -f .env ]]; then
  log_step "建立 .env（從 .env.example 複製）"
  cp .env.example .env
  log_warn "已複製模板，請填入 VERTEX_PROJECT_ID 後重跑"
  log_info "  vi .env  # 至少填 VERTEX_PROJECT_ID"
  exit 1
fi

# 解析 .env（簡單 grep，不用 source 避免汙染）
get_env() {
  grep -E "^${1}=" .env 2>/dev/null | head -1 | sed -E "s/^${1}=//; s/^[\"']//; s/[\"']$//"
}

VERTEX_PROJECT_ID_VAL=$(get_env VERTEX_PROJECT_ID)
LINE_SECRET=$(get_env LINE_CHANNEL_SECRET)
POSTGRES_URI_VAL=$(get_env POSTGRES_URI)

# 自動補 POSTGRES_URI（指向本機 DB）— 若使用者填了「your_」開頭預設值或留空
if [[ -z "$POSTGRES_URI_VAL" ]] || [[ "$POSTGRES_URI_VAL" == *"user:password"* ]]; then
  log_warn ".env 的 POSTGRES_URI 未配置，自動指向本機 DB"
  # 直接覆寫 .env 的這一行（macOS sed 與 Linux sed 兼容寫法）
  if grep -q "^POSTGRES_URI=" .env; then
    sed -i.bak -E 's|^POSTGRES_URI=.*|POSTGRES_URI="postgresql://lock:0000@localhost:5433/lock_AI_data"|' .env
  else
    echo 'POSTGRES_URI="postgresql://lock:0000@localhost:5433/lock_AI_data"' >> .env
  fi
  rm -f .env.bak
  log_ok "已寫入 POSTGRES_URI=postgresql://lock:0000@localhost:5433/lock_AI_data"
fi

# 必填檢查
MISSING=()
if [[ -z "$VERTEX_PROJECT_ID_VAL" || "$VERTEX_PROJECT_ID_VAL" == "your_gcp_project_id" ]]; then
  MISSING+=("VERTEX_PROJECT_ID（GCP 專案 ID，必填）")
fi
if (( ${#MISSING[@]} > 0 )); then
  log_err ".env 缺必填項："
  for m in "${MISSING[@]}"; do echo "    - $m"; done
  log_info "編輯 .env 後重跑：vi .env"
  exit 1
fi
log_ok ".env 必填欄位齊備"

# LINE 金鑰（選用）
if [[ -z "$LINE_SECRET" || "$LINE_SECRET" == "your_line_channel_secret" ]]; then
  log_warn "LINE_CHANNEL_SECRET 未填 — webhook 模式不能用，但 /chat 與 /health 可用"
fi

# gcloud auth 檢查
if have gcloud; then
  if gcloud auth application-default print-access-token >/dev/null 2>&1; then
    log_ok "gcloud Application Default Credentials 已配置"
  else
    log_warn "尚未 gcloud auth — 需執行：gcloud auth application-default login"
  fi
else
  log_warn "找不到 gcloud CLI — 若要呼叫 Vertex AI 需安裝（brew install google-cloud-sdk）"
fi

if [[ "$MODE" == "check" ]]; then
  log_ok ".env 檢查完成（--check 模式不啟動）"
  exit 0
fi

# 2. Python venv
VENV_DIR="agent/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
  log_step "建立 Python venv（agent/.venv）"
  python3 -m venv "$VENV_DIR"
  log_ok "venv 已建立"
fi

# 啟用 venv（在子 shell 內，不污染外層）
PY="$REPO_ROOT/$VENV_DIR/bin/python"
PIP="$REPO_ROOT/$VENV_DIR/bin/pip"

# 3. 安裝依賴（用 hash 偵測 requirements 是否變更）
REQ_HASH_FILE="$VENV_DIR/.req.hash"
CURR_HASH=$(shasum agent/requirements.txt | awk '{print $1}')
PREV_HASH=$(cat "$REQ_HASH_FILE" 2>/dev/null || echo "")

if [[ "$CURR_HASH" != "$PREV_HASH" ]]; then
  log_step "安裝/更新 agent 依賴（首次約 2-5 分鐘）"
  "$PIP" install --upgrade pip --quiet
  "$PIP" install -r agent/requirements.txt --quiet
  echo "$CURR_HASH" >"$REQ_HASH_FILE"
  log_ok "依賴安裝完成"
else
  log_ok "依賴已 up-to-date（requirements.txt 無變更）"
fi

# 4. CLI 模式：前景跑 main.py
if [[ "$MODE" == "cli" ]]; then
  log_step "CLI 模式：執行 agent/main.py（product_info 自檢）"
  cd agent && "$PY" main.py
  exit $?
fi

# 5. Serve 模式：背景啟 uvicorn
# 停掉舊的
if [[ -f "$AGENT_PID_FILE" ]]; then
  old_pid=$(cat "$AGENT_PID_FILE" 2>/dev/null || echo "")
  if is_pid_alive "$old_pid"; then
    log_step "停止既有 agent (pid=$old_pid)"
    kill "$old_pid" 2>/dev/null || true
    sleep 2
  fi
  rm -f "$AGENT_PID_FILE"
fi

log_step "背景啟動 agent (uvicorn :${AGENT_PORT})"
cd agent
nohup "$PY" -m uvicorn app:app --host 0.0.0.0 --port "${AGENT_PORT}" \
  >"$AGENT_LOG_FILE" 2>&1 &
AGENT_PID=$!
echo "$AGENT_PID" >"$AGENT_PID_FILE"
cd "$REPO_ROOT"
log_info "PID=$AGENT_PID，logs=$AGENT_LOG_FILE"

# 6. 健康檢查
if wait_http "http://localhost:${AGENT_PORT}/health" 30 "Agent"; then
  echo ""
  log_ok "Agent 就緒：http://localhost:${AGENT_PORT}"
  log_info "測試 /chat：curl 'http://localhost:${AGENT_PORT}/chat?q=門打不開'"
  log_info "Logs：tail -f $AGENT_LOG_FILE"
  log_info "停止：./scripts/setup/down.sh 或 kill $AGENT_PID"
else
  log_warn "Agent 健康檢查未通過，看 logs：tail -50 $AGENT_LOG_FILE"
  tail -20 "$AGENT_LOG_FILE" 2>/dev/null || true
  exit 1
fi
