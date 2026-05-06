# scripts/ — 腳本統一管理

依用途分為四類：開發 / 環境切換 / CI / 部署。所有腳本都從**專案根目錄**執行。

```
scripts/
├── dev/      啟動 / 收尾本機開發環境
├── env/      .env 模式切換（本機 docker ↔ GCP Cloud SQL）
├── ci/       API 契約相關 CI 工具（OpenAPI / mock / 一致性檢查）
└── deploy/   GCP Cloud Run 部署
```

> 額外位置：`tests/smoke/`（happy-path smoke test）、`tests/tools/`（除錯工具
> 如 view_facts / view_logs / clean_data 等）、`api/scripts/generate_models.sh`
> （API 內部 codegen，與 api/models 強耦合，未集中）。

---

## 三種開發情境

| 情境 | 說明 | DB | 用什麼 secrets |
| :--- | :--- | :--- | :--- |
| **A. 開發 + 本地** | 日常 coding，跑假資料 seed | 本機 docker container `lock_AI` (port 5433) | `.env.local` |
| **B. 開發 + 遠端** | 用真資料測試 / debug prod | GCP Cloud SQL via cloud-sql-proxy | `.env.gcp`（從 Secret Manager） |
| **C. 產品 + 遠端** | Cloud Run 部署 | Cloud SQL（直連 Unix socket） | Secret Manager |

> 「產品 + 本地」情境不存在。

---

## 情境 A — 本地開發（日常用）

```bash
# 首次設定
cp .env.local.example .env.local
# 編輯 .env.local 填入個人 GEMINI_API_KEY / LINE / OPIK 等金鑰

# 切換 .env 到本地模式（會自動備份原 .env）
./scripts/env/use-local.sh

# 啟動 DB + ngrok + uvicorn
./scripts/dev/dev-up.sh                # 預設全開
./scripts/dev/dev-up.sh --no-ngrok     # 不要 ngrok
./scripts/dev/dev-up.sh --db-only      # 只起 DB

# 收尾
./scripts/dev/dev-down.sh              # 預設保留 DB container
./scripts/dev/dev-down.sh --stop-db    # 連 DB 一起停
./scripts/dev/dev-down.sh --remove-db  # 連 DB 一起停並刪除 container（清空資料）
```

### 本地驗證

```bash
# uvicorn 起來後快速測 LLM 連線
curl "http://localhost:8000/chat?q=門打不開"

# API smoke test（18 endpoints happy-path）
ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD=changeme123 ./tests/smoke/api.sh
```

---

## 情境 B — 連 GCP Cloud SQL（用真資料 debug）

```bash
# 1. 前置條件（一次性）
gcloud auth login                           # 互動式登入 GCP
gcloud auth application-default login       # ADC（cloud-sql-proxy 要）
gcloud config set project cedar-scope-489604-g3

# 2. 從 Secret Manager 取最新 POSTGRES_URI（首次或密碼輪替後）
./scripts/env/use-gcp.sh --fetch

# 3. 切換 .env 到 GCP 模式（會自動備份）
./scripts/env/use-gcp.sh

# 4. 啟動 cloud-sql-proxy（背景跑，PID 寫在 .dev-logs/）
./scripts/dev/proxy-up.sh                # 背景
./scripts/dev/proxy-up.sh --foreground   # 前景看 log

# 5. 啟動 agent（不需要 dev-up.sh，因為 DB 是遠端）
cd agent && uvicorn app:app --reload --port 8000

# 結束：先停 agent (Ctrl+C)，再停 proxy
./scripts/dev/proxy-down.sh
```

### ⚠️ 安全注意

- `.env.gcp` 含真實 prod 密碼，每次 `use-gcp.sh` 自動 `chmod 600`
- 切換時自動備份原 `.env` 為 `.env.bak.<時間>`
- GCP 模式打的是真資料，**請勿在此模式跑 `quality_check`、`clean_data.py`、
  或測試 LINE webhook**。要驗證流程請切回情境 A

---

## 情境 C — Cloud Run 部署

```bash
# Agent (LINE Bot)
./scripts/deploy/agent.sh                # 完整：pre-flight → build → push → deploy → health check
./scripts/deploy/agent.sh --build-only   # 只 build image
./scripts/deploy/agent.sh --deploy-only  # 用既有 image 部署
./scripts/deploy/agent.sh --update-db-uri # 從 DB_PASSWORD 重建 POSTGRES_URI secret

# API (FastAPI 後端)
./scripts/deploy/api.sh
./scripts/deploy/api.sh --build-only
./scripts/deploy/api.sh --deploy-only
```

部署細節（image tag、Secret Manager、Cloud SQL Unix socket、health check
重試）請看各腳本檔頭註解。

---

## CI 工具（API 契約相關）

```bash
# 從 openapi.yaml 生成 TypeScript 型別
./scripts/ci/generate-api-types.sh
./scripts/ci/generate-api-types.sh --check   # CI 模式（只檢查不寫檔）

# 從 page spec [PAGE META] 生成 MAPPING.md AUTO-GEN 區塊
./scripts/ci/generate-mapping-api-index.sh
./scripts/ci/generate-mapping-api-index.sh --check

# 啟動 Prism mock server（OpenAPI）
./scripts/ci/mock-server.sh           # port 4010
./scripts/ci/mock-server.sh 4011      # 自訂 port
./scripts/ci/mock-server.sh 4010 --errors  # 產生錯誤回應範例

# 檢查 OpenAPI / AsyncAPI operationId 與文件之間的一致性
./scripts/ci/check-operationid-orphans.sh
```

---

## 除錯與資料工具（tests/tools/）

```bash
# 從專案根目錄執行（腳本內已自行把 agent/ 加入 sys.path）
python tests/tools/view_context.py <user_id>      # 看 checkpoint 對話狀態
python tests/tools/view_facts.py [--user <id>]    # 看 user_facts (SCD2)
python tests/tools/view_logs.py [N]               # 看 audit logs
python tests/tools/view_corrections.py [--all|--export|--clear]
python tests/tools/clean_data.py [--pg|--sqlite|--profile]
python tests/tools/simulate_e2e.py                # debounce / Quick Reply / 多模態 模擬
```

---

## 設計原則

1. **單一入口**：每種任務只有一個對的腳本，不要在多個地方備份
2. **路徑無關**：腳本內以 `BASH_SOURCE` 計算 `PROJECT_ROOT`，不依賴 cwd
3. **冪等**：`dev-up.sh`、`proxy-up.sh` 重跑不會出錯（已有檢查 PID / port）
4. **明確失敗**：找不到指令、port 被佔、ADC 未設定 → 立刻明確 `exit 1` 加修復提示
5. **Secret 不入庫**：`.env`、`.env.local`、`.env.gcp` 全部 gitignored，
   只有 `*.example` 範本可入庫
