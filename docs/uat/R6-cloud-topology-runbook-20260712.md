# R6 雲端拓撲對齊 Runbook（CR-0166 R6 / WBS 3.4.1）

- **日期**：2026-07-12
- **狀態**：**腳本/checklist 備妥；GCP 執行需業主授權協同（D1 裁決＝列協同待辦，一起跑）。**
- **範圍**：tech／platform 面雲端部署＋技師庫上雲（品牌 api/web/agent 面雲端部署已有 `scripts/deploy/{api,web,agent}.sh`）。

> ⚠️ 本 runbook 是**執行手冊**，不含實際 GCP 操作——建 GCP 專案／Cloud SQL／Secret Manager／
> Cloud Run 需業主帳號授權與費用權限。備妥後與業主一起逐步執行。

## §1 現況（本機 as-is）

| 面 | 本機 | 雲端目標 |
|---|---|---|
| 品牌（dispatch） | :8001 api／:3000 web／:8000 agent／:5433 db | 每品牌一 GCP 專案（ADR-002，`scripts/deploy/*.sh` 已就緒） |
| 師傅（tech） | :8002 tech-api／:3001 web／:5434 lock_tech | **本輪目標：tech 面 Cloud Run＋技師庫上雲** |
| 平台（platform） | :8003 platform-api／:3003 web／:5435 lock_platform | **本輪目標：platform 面 Cloud Run＋平台庫上雲** |
| 事件骨幹（R4） | Redpanda（profile events，opt-in） | 集中共用 Redpanda/Kafka（ADR-006，設 KAFKA_BOOTSTRAP） |

## §2 tech 面上雲 checklist

- ☐ 技師庫 Cloud SQL 實例 `lock-sql-tech`（db=lock_tech，user=lock-ai）
- ☐ 套 tech schema：`SQL/Schema.sql` 子集 + `SQL/tech_authority/*.sql`（含 R4 投影 schema）
      ——用 `scripts/db/split-tech-db.sh` 邏輯對雲端庫初建（或 pg_dump 品牌雲端庫技師域）
- ☐ Secret Manager：`TECH_POSTGRES_URI`（Cloud SQL 連線，`./scripts/deploy/agent.sh --update-db-uri` 樣式自動 URL-encode）
- ☐ tech-api Cloud Run：`SERVICE_NAME=lock-tech-api API_SURFACE=tech ./scripts/deploy/api.sh`
      （tech surface：一般 worker 停用、R4 event consumer 啟用——設 `KAFKA_BOOTSTRAP`）
- ☐ tech-web Cloud Run：`SERVICE_NAME=lock-tech-web ./scripts/deploy/web.sh`
- ☐ 雙庫模式：品牌 api 設 `TECH_POSTGRES_URI`（否則師傅身分寫入漂移）

## §3 platform 面上雲 checklist

- ☐ 平台庫 Cloud SQL 實例 `lock-sql-platform`（db=lock_platform）
- ☐ 套 platform schema：`SQL/platform/Schema_platform.sql` + `SQL/platform/migrations/001-*.sql`（R3 License 欄）
- ☐ Secret Manager：`PLATFORM_POSTGRES_URI`＋`API_JWT_SECRET_KEY`（platform surface 拒啟守衛需 ≥16 字元獨立密鑰，CR-0114）
- ☐ platform-api Cloud Run：`SERVICE_NAME=lock-platform-api API_SURFACE=platform ./scripts/deploy/api.sh`
- ☐ platform-web Cloud Run：`SERVICE_NAME=lock-platform-web ./scripts/deploy/web.sh`

## §4 事件骨幹上雲（R4，可選）

- ☐ 集中共用 Redpanda（Cloud Run／GKE／Redpanda Cloud）——非 per-brand（ADR-006）
- ☐ 各面 api 設 `KAFKA_BOOTSTRAP=<broker>:9092` → producer/consumer 生效（未設仍 outbox 保底）
- ☐ 對帳閘門（`commissionReconcileGateV2`）驗投影一致後，考慮 outbox 退役（另輪）

## §5 部署後驗證（smoke）

- ☐ 三面 `/health` 200
- ☐ 品牌→tech 雙庫：`split-tech-db.sh --verify` 無漂移（或雲端等效查詢）
- ☐ platform GET `/platform/tenants/{id}/license` 回正確 entitlements（R3）
- ☐ 開站 dry-run：`provision_brand.py --slug <新品牌> --dry-run`（R5）
- ☐ deprecation-metrics collector 部署（R7 v1 移除前置）——OTel／SigNoz 記 v1 端點命中

## §6 GCP 多專案統一 view（0707 會議 AI #10）

- ☐ GCP console 多專案合成單一畫面（資源用量／雲端 metrics）——GCP 內建 view，介面設定
- ☐ 應用層 metrics（API 延遲／agent 呼叫）走 SigNoz 自建儀表板（CR-0156 OTel 埋點已備）

> **執行方式**：業主提供 GCP 專案授權後，助手可代跑 `scripts/deploy/*.sh`（需 `gcloud auth login`
> 由業主於本 session 以 `! gcloud auth login` 執行），或業主自跑、助手在旁協助排錯。
