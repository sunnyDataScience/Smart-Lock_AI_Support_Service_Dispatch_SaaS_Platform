---
id: CR-0023
title: agent per-user 記憶後端 SQLite → Postgres
tier: 4-exploration
status: implemented
date: 2026-06-15
author: Claude (pair w/ 業主)
related:
  - ADR-0113-agent-memory-postgres-backend.md
  - SQL/migrations/033-agent-memory-schema.sql
  - agent/lockcore/agent/user_memory/postgres_store.py
triggers: [DB schema, Architecture boundary, External integration]
---

# CR-0023 — agent per-user 記憶後端 SQLite → Postgres

## 1. 背景與動機（WHY）

LockCore CS agent 的 per-user 記憶與轉真人稽核紀錄目前寫在 **agent 端本地 SQLite**
（`agent/memory.db`，FTS5 trigram 中文檢索）。這讓記憶成為**資料孤島**：

- 與營運後台的 Postgres（`saas.*` / `public.*`）完全分離，後台讀不到客人記憶。
- 多實例 / Cloud Run 部署時，本地檔案不共享、重啟即失（除非掛 volume）。
- 先前方案 A（CR-0022）只把**對話 / escalation** 旁路進 Postgres 讓工單可見，
  **記憶本身仍在 SQLite**。

目標：把記憶後端遷到與 API 共用的 lock-ai Cloud SQL，統一持久化與可運維性，
同時**不違反 Architecture Lock**（利用既有可插拔 `MemoryProvider` 抽象）。

## 2. 觸發面向（CIA Gate）

| 面向 | 命中 | 說明 |
|---|---|---|
| DB schema | ✅ | 新增 schema `agent` + 2 表 + pg_trgm extension |
| Architecture boundary | ✅ | agent 引入直連 Postgres 的記憶後端（但走既有 provider 抽象，非新核心）|
| External integration | ✅ | agent 進程新增對 Cloud SQL 的連線依賴 |
| API contract | ❌ | 不改任何 HTTP endpoint |
| Domain model | ❌ | MemoryEntry / EscalationRecord dataclass 不變 |

## 3. 現況盤點

- `agent/lockcore/agent/user_memory/`：`MemoryStore`（SQLite+FTS5）、`EscalationStore`、
  可插拔 `MemoryProvider`（`provider.py` 註解明寫「日後換後端只需新增一個 Provider」）。
- API：`psycopg`(psycopg3) async + `POSTGRES_URI`；schema `saas.*`(UUID tenant) / `public.*`。
- agent tenant = 字串 `"locksmart"`，**不對齊** saas 的 UUID `tenant_id`。

## 4. 變更內容（WHAT）

1. **新後端**（不動 SQLite 路徑）：
   - `postgres_store.py`：`PostgresMemoryStore` / `PostgresEscalationStore`（sync psycopg，
     同 dataclass 同方法簽名；lazy connect + autocommit + 斷線重連）。
   - `provider.py`：抽出共用 `_StoreBackedProvider`，`SqliteMemoryProvider` /
     `PostgresMemoryProvider` 各自只建 store（DRY，store-agnostic）。
2. **config 切換**：`config.toml [memory] backend = "sqlite"|"postgres"` + `postgres_uri_env`；
   `app_config.build_memory_manager` / `build_escalation_store` 依 backend 分流。
3. **DB**：`SQL/migrations/033`：schema `agent` + pg_trgm + `agent.memory_entry` /
   `agent.escalation` + 4 indexes（含 trigram GIN）。
4. **依賴**：`pyproject.toml` 新增 optional `[postgres] = psycopg[binary]`（SQLite-only 安裝免裝）。
5. **測試**：`tests/test_memory_postgres.py`（SQLite 基準 + Postgres `POSTGRES_URI` 在則跑）。

## 5. Architecture Lock 合規

- ✅ 不另寫 agent 核心：記憶後端走既有 `MemoryProvider` 抽象（設計原意即「換後端加 provider」）。
- ✅ 不動 `CS_TOOL_ALLOWLIST`：記憶非 agent tool，是 turn 狀態機 BUILD/SAVE 的內部設施。
- ✅ skill / LiteLLMProvider 不受影響。

## 6. 測試計畫（TC）

- TC-mem-pg-1：中文子字串檢索（pg_trgm）命中 ✅
- TC-mem-pg-2：tenant+user_id scope 隔離（看不到他人）+ forget ✅
- TC-mem-pg-3：default-deny（缺 user_id 拒絕）✅
- TC-mem-pg-4：escalation log/list + JSONB roundtrip ✅
- TC-mem-pg-5：app_config backend 切換（postgres ↔ sqlite 回歸守線）✅
- 實測：本機 Docker `lock_AI_data`(pg17) 跑 migration 033 + 7 tests passed。

## 7. 影響範圍（IMPACT）

- 預設仍 `backend="sqlite"`（零行為變更，反相容）；正式環境改 `postgres` 即切。
- 部署：Cloud Run agent 需 `POSTGRES_URI` env + 先跑 migration 033（forward-only、可重跑）。
- 評測 harness 仍可用 `backend="sqlite"` + `:memory:` 維持 run 隔離（不受影響）。

## 8. Human Decisions Required（已裁決 2026-06-15）

| # | 決策 | 業主裁決 |
|---|---|---|
| 1 | 記憶放哪個 Postgres / tenant 模型 | **沿用 lock-ai Cloud SQL + 新 `agent` schema，tenant 仍存字串**（不對齊 saas UUID）|
| 2 | 全文檢索策略 | **pg_trgm + GIN**（trigram 對中文無空格子字串，與 FTS5 行為最近）|
| 3 | SQLite 去留 | **config 切換，保留 SQLite**（測試 / `:memory:` 隔離續用）|
| 4 | 既有 memory.db 資料 | **不遷，丟棄 PoC 資料**（正式環境從空白起）|

## 9. 實作順序（已完成）

1. ✅ 開分支 `feat/agent-memory-postgres`
2. ✅ `postgres_store.py`（PostgresMemoryStore / PostgresEscalationStore）
3. ✅ `provider.py` 抽 `_StoreBackedProvider` + PostgresMemoryProvider
4. ✅ `app_config.py` + `config.toml` backend 切換
5. ✅ `pyproject.toml` `[postgres]` optional dep
6. ✅ `SQL/migrations/033` + registry 登記
7. ✅ 本機 Postgres 套用 migration + 7 tests passed
8. ✅ ADR-0113 / CHANGELOG / 完成度文件
