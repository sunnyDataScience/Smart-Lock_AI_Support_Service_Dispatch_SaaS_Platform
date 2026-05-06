#!/usr/bin/env bash
# up.sh — 一鍵啟動全部組件（DB → API → Web → Agent）
#
# 使用方式：
#   ./scripts/setup/up.sh              # 啟動全部（DB + API + Web + Agent）
#   ./scripts/setup/up.sh --no-agent   # 不啟 agent（小白只看 admin dashboard）
#   ./scripts/setup/up.sh --no-web     # 不啟 web
#   ./scripts/setup/up.sh --db-only    # 只起 DB
#   ./scripts/setup/up.sh --api-only   # DB + API
#
# 設計原則：
#   - 完全 idempotent，重複跑不會壞東西
#   - 每階段獨立可重跑（可單跑 start-db.sh / start-api.sh / 等）
#   - 失敗時清楚告訴小白怎麼修
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_lib.sh"
cd "$REPO_ROOT"

DO_DB=1; DO_API=1; DO_WEB=1; DO_AGENT=1

for arg in "$@"; do
  case "$arg" in
    --no-agent) DO_AGENT=0 ;;
    --no-web)   DO_WEB=0 ;;
    --db-only)  DO_API=0; DO_WEB=0; DO_AGENT=0 ;;
    --api-only) DO_WEB=0; DO_AGENT=0 ;;
    -h|--help)
      grep -E "^# " "$0" | sed 's/^# //'
      exit 0
      ;;
    *)
      log_warn "未知選項：$arg"
      ;;
  esac
done

START_TIME=$(date +%s)

log_title "Smart Lock 一鍵啟動"
echo "Repo: $REPO_ROOT"
echo "計畫：DB=$DO_DB  API=$DO_API  Web=$DO_WEB  Agent=$DO_AGENT"

# 0. Prereq
bash "$SCRIPT_DIR/check-prereqs.sh"

# 1. DB
if (( DO_DB == 1 )); then
  bash "$SCRIPT_DIR/start-db.sh"
fi

# 2. API
if (( DO_API == 1 )); then
  bash "$SCRIPT_DIR/start-api.sh"
fi

# 3. Web
if (( DO_WEB == 1 )); then
  bash "$SCRIPT_DIR/start-web.sh"
fi

# 4. Agent
if (( DO_AGENT == 1 )); then
  bash "$SCRIPT_DIR/start-agent.sh" || {
    log_warn "Agent 啟動失敗（多半是 .env 缺 VERTEX_PROJECT_ID 或 gcloud auth）"
    log_info "Web/API 不受影響，小白可先用 admin dashboard：http://localhost:${WEB_PORT}"
  }
fi

ELAPSED=$(( $(date +%s) - START_TIME ))

# === 收尾 summary ===
log_title "啟動完成（耗時 ${ELAPSED}s）"
echo ""
printf "${C_BOLD}服務一覽${C_RESET}\n"
(( DO_DB == 1 ))    && echo "  ├─ DB:    postgresql://lock:0000@localhost:${DB_HOST_PORT}/lock_AI_data"
(( DO_API == 1 ))   && echo "  ├─ API:   http://localhost:${API_HOST_PORT}        ${C_GREEN}(/docs 可看 OpenAPI)${C_RESET}"
(( DO_WEB == 1 ))   && echo "  ├─ Web:   http://localhost:${WEB_PORT}        ${C_GREEN}(admin@example.com / changeme123)${C_RESET}"
(( DO_AGENT == 1 )) && echo "  └─ Agent: http://localhost:${AGENT_PORT}        ${C_GREEN}(curl /chat?q=...)${C_RESET}"
echo ""
printf "${C_BOLD}常用指令${C_RESET}\n"
echo "  狀態：./scripts/setup/status.sh"
echo "  停止：./scripts/setup/down.sh"
echo "  Web logs：  tail -f $WEB_LOG_FILE"
echo "  Agent logs：tail -f $AGENT_LOG_FILE"
echo "  API logs：  docker logs -f $API_CONTAINER"
echo "  DB shell：  docker exec -it $DB_CONTAINER psql -U lock -d lock_AI_data"
echo ""
log_ok "Done"
