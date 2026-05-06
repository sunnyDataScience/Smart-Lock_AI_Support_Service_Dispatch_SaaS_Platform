# Doc Agent A — E9 部署運維指南同步報告

- **日期**: 2026-05-06 15:21
- **檔案**: docs/04-deliver/E9--deployment-and-operations-guide.md
- **矩陣條目**: U11（部署平台）、U12（Dockerfile 範本）、U13（CI workflow yml 範本）

## 改了什麼

- **頂部新增「遷移備註：uv workspace（2026-05）」callout**：列出新舊指令對照表（安裝依賴 / Agent CLI / API 啟動 / 部署 / 本機 DB 切換 / 開發環境啟動），並明確標示本文件中 docker-compose / nginx / alembic 段落的範圍定位（僅供 local dev 多服務一鍵起 / self-host 參考）。
- **§2.2 ci.yml 重寫**：兩個 backend job（lint-backend、test-backend）改為 `astral-sh/setup-uv@v3 (enable-cache: true)` + `uv sync --frozen` + `uv run ruff/mypy/pytest`。修正舊版殘留的 `backend/src/`、`smart_lock` package 名等錯誤路徑。Build job 改為分別 build `agent/Dockerfile` 與 `api/Dockerfile`。
- **§2.3 deploy.yml 大改**：從 SSH + docker-compose 流程改為 Cloud Run 流程。新增 `deploy-agent` / `deploy-api` 兩個獨立 job，各自呼叫 `./scripts/deploy/agent.sh` / `./scripts/deploy/api.sh`；smoke-test job 改用 `tests/smoke/api.sh`。新增 §2.3.1 完整解釋三大旗標（`--build-only` / `--deploy-only` / `--update-db-uri`）的用途與範例。
- **§4.0 新章節「Cloud Run 部署（V1.0 實際採用）」**：放在 §4.1 Blue-Green 之前作為主要部署路徑。涵蓋：（1）標準部署流程；（2）Cloud Run 原生 revision-based 回滾（`gcloud run services update-traffic`）；（3）Cloud SQL 連線方式（生產用 Unix socket、本機用 cloud-sql-proxy + `scripts/dev/proxy-up.sh`、`scripts/env/use-local.sh` / `use-gcp.sh` 切換 .env）。
- **§4.1 / §4.2 / §4.3 標題加註「self-host 參考」**：保留原 docker-compose 內容作為自架 VPS 場景參考，但明確標註生產環境已遷至 Cloud Run。§4.3 新增 Cloud Run 首次部署 callout。
- **§7.3 Dockerfile 整段重寫**：刪除舊的 `backend/Dockerfile`（用錯 `smart-lock-agent` package 名、錯誤的 `src/`、`alembic/`、`smart_lock.main:app`）。改為兩個生產實際使用的 multi-stage uv Dockerfile：`agent/Dockerfile`（`uv sync --frozen --no-dev --package agent`）+ `api/Dockerfile`（`--package api`），runtime stage 只 copy `.venv` 與對應模組目錄，EXPOSE 8080 對齊 Cloud Run。明確說明 build/push/deploy 應透過 `scripts/deploy/*.sh`，不直接用 `docker build`。
- **§9.x runbook 全面重構**：每個子節（9.1 DB migration、9.3 服務重啟、9.4 水平擴展、9.5 日誌查詢、9.6 SSL 憑證、9.7 密鑰輪替、9.8 災難復原）皆採「9.x.1 Cloud Run（生產實際採用）+ 9.x.2 Self-host（參考用）」雙層結構。新增 9.2.1 Cloud SQL 備份、9.7.1 Secret Manager 輪替（含 DB 密碼快速通道 `--update-db-uri`）。9.1 明確說明本專案目前未啟用 Alembic，schema 演進透過 `SQL/*.sql` 手動套用。
- **§1.2 / §1.3 / §1.4 拓撲標註**：新增 §1.2.1 Cloud Run mermaid 拓撲圖（兩個 Cloud Run service + Cloud SQL Unix socket + Secret Manager + Artifact Registry）作為主要拓撲；§1.2.2 docker-compose 拓撲明確降級為 self-host 參考。
- **§10.1 Development 環境**：從 `docker compose up -d` 改為 `./scripts/dev/dev-up.sh`，補上 `./scripts/env/use-local.sh` / `use-gcp.sh` / `proxy-up.sh` / `proxy-down.sh` 切換指令，以及 `cd agent && uv run uvicorn app:app` / `cd api && uv run uvicorn main:app` 直連啟動方式。
- **§10.2 / §10.3 / §10.4 環境配置**：Staging 改為 Cloud Run 獨立 service；Production 注意事項從「容器設 restart: always」改為「Cloud Run min-instances=1」等 serverless 概念；env list 重寫對齊現行 `.env.example`（`POSTGRES_URI` / `PG_VECTOR_URI` / `VERTEX_PROJECT_ID` / `OPIK_*`，移除 Alembic 相關 `DATABASE_URL`）。

## 修改前後對比（Top 3）

- **CI lint-backend job**：舊版混雜 `uv sync --group dev` 與 `ruff format --check backend/src/` / `mypy backend/src/`（錯誤路徑、用了不存在的 `backend/` 目錄）。新版統一為 `uv sync --frozen` + `uv run ruff check . / ruff format --check . / mypy agent api data`，與專案實際 workspace 結構對齊。
- **deploy.yml**：舊版用 `appleboy/ssh-action` + `docker compose pull && up -d --remove-orphans`，假設有 SSH 進入 VPS 的權限。新版用 `google-github-actions/auth@v2`（Workload Identity）+ `setup-gcloud@v2`，呼叫 `./scripts/deploy/agent.sh` 與 `./scripts/deploy/api.sh`，無需 SSH，無需 GHCR/長效 service account key。
- **Dockerfile (`backend/Dockerfile` → `agent/Dockerfile` + `api/Dockerfile`)**：舊版使用了不存在的 package 名 `smart-lock-agent`、嘗試 COPY 不存在的 `src/` / `alembic/` / `alembic.ini`，runtime CMD 為 `smart_lock.main:app`（與實際 `app:app` 不符）。新版兩個獨立 Dockerfile 對應兩個 Cloud Run service，runtime port 8080 對齊 Cloud Run 預設，CMD 為 `uvicorn app:app` / `uvicorn main:app`，不依賴 alembic 或 src/。

## 影響評估

- **嚴重度**: HIGH
- **影響範圍**:
  - **新加入的工程師**：跟著 E9 設置 CI/CD 不再會被舊 `pip install -r requirements.txt` 卡住。
  - **DevOps**：runbook 直接給 Cloud Run 操作（`gcloud run services logs tail` / `gcloud sql backups restore` / `--update-db-uri`），不再需要先翻譯 docker-compose 指令到 Cloud Run。
  - **新功能設計者**：架構決策參考（Cloud Run vs self-host）一目了然，不會錯誤地以為生產還在 docker-compose。

## 行動項目

- [ ] **後續審閱者重點看**：
  - §2.3 deploy.yml — Workload Identity Federation 細節是否需要進一步補設置文件（建立 WIF provider / pool 的指令未在本文件展開）
  - §4.0.3 Cloud SQL 連線 — `cloud-sql-proxy` 在 Apple Silicon 與 Linux 上的安裝方式可能需要補一段
  - §9.1 schema 變更流程 — 目前手動 SQL 套用是否足夠，未來何時引入 Alembic（D1 議題的延伸）
  - §10.4 環境變數速查表 — 與 `agent/config.toml` / `data/config.toml` 的對應是否需要交叉引用補強
- [ ] **跨文件一致性**：本次標註的 self-host 範圍若後續完全棄用，整段 §1.2.2 / §7.1 / §7.2 / §4.1-§4.3 的 self-host 內容可移至 docs/_archive/ 或獨立 self-host-deployment-legacy.md
- [ ] **CI 旗標細節**：`scripts/deploy/agent.sh --build-only` 是否真的不 push（待確認 scripts/deploy/agent.sh 實作）— 若 build-only 仍會 push，需修正 §2.3.1 表格描述
