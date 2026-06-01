# Commands 全集

> 主檔 `CLAUDE.md` 只放最高頻的幾條。完整指令、部署 flag、debug 工具、環境切換都在這裡。
> 由 `CLAUDE.md` 透過 `@.claude/docs/commands.md` 路標帶入；只在需要時展開。

## Setup

```bash
# uv workspace (Python 3.11)。uv 安裝任一方式：
#   pip install --user uv   |   pipx install uv
uv sync                     # 一行裝齊三個 module 的 deps + dev tools；pyproject.toml 改了就重跑

cd web && npm install       # Web dashboard（Node 環境，與 uv 無關）
```

## Run（本地）

```bash
cd agent && uv run python main.py                          # Agent CLI（驗證 LLM 連線，免 LINE Bot）
cd agent && uv run uvicorn app:app --reload --port 8000    # Agent FastAPI（LINE webhook 模式）
cd api   && uv run uvicorn main:app --reload --port 8001   # REST API backend
cd web   && npm run dev                                    # Web dashboard（http://localhost:3000）

./scripts/dev/dev-up.sh                                    # 一鍵起本地環境（DB + ngrok + uvicorn）
./scripts/dev/dev-down.sh                                  # 拆除（DB container 保留）
```

## 測試端點 / 健康檢查

```bash
curl "http://localhost:8000/chat?q=門打不開"                       # 繞過 LINE webhook + debounce，直呼 run_agent()
curl "http://localhost:8000/chat?q=門打不開&user_id=test-user-1"   # 自訂 thread
curl http://localhost:8000/health                                  # 健康檢查（facts_db + audit_db）
```

> `GET /chat` 不會經過 Quick Reply / multimodal 流程，僅供快速測試。

## Quality testing（LLM-as-Judge eval）

```bash
cd agent && uv run python -m quality.quality_check                 # Full：agent + keyword + LLM judge
cd agent && uv run python -m quality.quality_check --no-judge      # agent 回答 + keyword match
cd agent && uv run python -m quality.quality_check --judge-only    # 重新評分既有 quality_report.json
cd agent && uv run python -m quality.quality_check --retry-failed  # 只重測非 pass 案例
# --turn-cycle 旗標可做 Belief-Augmented A/B
```

> 無自動化 unit test 套件。測試靠 `quality_check`、CLI（`python main.py`）、或 `/chat` 端點。

## Web build / lint

```bash
cd web && npm run build      # Production build
cd web && npm run lint       # ESLint
```

## Debug 工具（從專案根目錄跑，工具會自動把 agent/ 加進 sys.path）

```bash
# 推薦用 uv run 確保 venv 解析正確（不需手動 source .venv/bin/activate）
uv run tests/tools/view_context.py <user_id>    # 檢視 checkpoint state
uv run tests/tools/view_facts.py <user_id>      # 檢視 user facts
uv run tests/tools/view_logs.py                 # 查 audit logs
uv run tests/tools/view_corrections.py          # 檢視 #資料修正 記錄
uv run tests/tools/clean_data.py                # DB cleanup
uv run tests/tools/simulate_e2e.py              # E2E 模擬
# 已 activate venv 時也可：./tests/tools/view_facts.py（shebang）；Windows: python tests\tools\view_facts.py
```

## Skill approval（data pipeline → agent，legacy）

```bash
uv run python data/pipeline/silver_to_skill/approve_drafts.py --dry-run
uv run python data/pipeline/silver_to_skill/approve_drafts.py --confirm
```

## 環境 / DB target 切換（.env 管理）

```bash
./scripts/env/use-local.sh        # → .env.local（本機 docker）
./scripts/env/use-gcp.sh          # → .env.gcp（GCP Cloud SQL via proxy）
./scripts/env/use-gcp.sh --fetch  # 從 Secret Manager 刷新 .env.gcp
./scripts/dev/proxy-up.sh         # 起 cloud-sql-proxy（GCP 模式）
./scripts/dev/proxy-down.sh       # 停 cloud-sql-proxy
```

## API 契約工具 / smoke test

```bash
ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=changeme123 ./tests/smoke/api.sh   # API smoke（uvicorn 起好後）
./scripts/ci/generate-api-types.sh    # 從 OpenAPI 生 TypeScript 型別
./scripts/ci/mock-server.sh           # 起 Prism mock server（port 4010）
npx @stoplight/spectral-cli lint docs/architecture/api/openapi.yaml   # Lint spec
```

## Deployment（Cloud Run）

```bash
# LINE Bot agent
./scripts/deploy/agent.sh                 # Full：pre-flight → build → push → deploy → health check
./scripts/deploy/agent.sh --build-only    # 只 build Docker image
./scripts/deploy/agent.sh --deploy-only   # deploy 既有 image
./scripts/deploy/agent.sh --update-db-uri # 從 DB_PASSWORD 重建 POSTGRES_URI（自動 URL encode）

# FastAPI backend
./scripts/deploy/api.sh                   # Full deploy
./scripts/deploy/api.sh --build-only
./scripts/deploy/api.sh --deploy-only
```

## Environment Configuration

- `.env.example` → `.env`（專案根目錄）。必要變數：
  - `VERTEX_PROJECT_ID`, `VERTEX_LOCATION` — Vertex AI / Gemini
  - `POSTGRES_URI` — PostgreSQL（checkpointer, facts, audit）。格式 `postgresql://user:pass@host:port/db`
  - `LINE_CHANNEL_SECRET`, `LINE_CHANNEL_ACCESS_TOKEN` — LINE Bot（CLI / `/chat` 不需要）
  - `OPIK_API_KEY`, `OPIK_WORKSPACE` — LLM 觀測（optional）
- `credentials.json`（GCP service account）放專案根目錄 — data pipeline 與 Vertex AI 在非 `gcloud auth` 時需要
- Agent 讀 `agent/config.toml`；data pipeline 讀 `data/config.toml`
- Config pattern：TOML 存環境變數**名稱**（如 `postgres_uri_env = "POSTGRES_URI"`），實際值來自 `.env`
