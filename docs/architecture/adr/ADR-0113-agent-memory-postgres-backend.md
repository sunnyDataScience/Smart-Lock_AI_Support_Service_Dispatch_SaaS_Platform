---
id: ADR-0113
title: agent per-user 記憶後端 — SQLite → Postgres（agent schema / pg_trgm）
status: accepted
date: 2026-06-15
deciders: [業主]
accepted_date: 2026-06-15
related:
  - ../../4-exploration/CR-0023-agent-memory-postgres.md
  - ./ADR-0107-lockcore-supersede-product-info-trio.md
  - SQL/migrations/033-agent-memory-schema.sql
---

# ADR-0113 — agent per-user 記憶後端：SQLite → Postgres

## Status
accepted（2026-06-15，CR-0023 §8 業主裁決）

## Context

LockCore CS agent 的 per-user 記憶（`MemoryStore`）與轉真人稽核（`EscalationStore`）
原寫本地 SQLite（FTS5 trigram）。本地檔案造成：記憶資料孤島（後台 Postgres 讀不到）、
多實例 / Cloud Run 不共享、重啟即失。`provider.py` 自始即留可插拔 `MemoryProvider`
抽象（「日後換後端只需新增一個 Provider」），本 ADR 兌現該設計。

## Decision

agent 記憶後端**可由 config 切換 SQLite / Postgres**，Postgres 走與 API 共用的
lock-ai Cloud SQL，置於**獨立 schema `agent`**：

- `agent.memory_entry` / `agent.escalation`；tenant 仍存**字串**（如 `locksmart`），
  **不對齊** saas 的 UUID `tenant_id`（agent 多租戶模型與營運 SaaS 分離）。
- 中文子字串檢索改 **pg_trgm + GIN**（取代 FTS5 trigram），ILIKE 命中 + `similarity()` 排序。
- 預設仍 `backend="sqlite"`（反相容、零行為變更）；正式環境設 `backend="postgres"` +
  `POSTGRES_URI`，先跑 migration 033。

## Alternatives Considered

- **放 saas schema + 映射 UUID tenant**：後台可直接 join，但耦合營運 schema、需字串→UUID
  映射層。否決（§8 #1 選 agent schema 乾淨隔離）。
- **tsvector 全文檢索**：中文需 zhparser/pg_jieba 斷詞 extension，Cloud SQL 預設無、難裝。
  否決（§8 #2 選 pg_trgm，stock extension）。
- **硬替換 SQLite**：測試 / 評測 harness 失去 `:memory:` 快速隔離。否決（§8 #3 保留切換）。

## Consequences

**Positive**：記憶持久化統一、多實例可共享、與 API 同一 Cloud SQL 易運維；
保留 SQLite 後端讓 unit / eval 維持零依賴與 run 隔離。

**Negative**：agent 進程新增 Postgres 連線依賴（optional dep `psycopg`）；
tenant 字串不對齊 saas UUID，後台若要 join 需後續映射（暫不需要）。

**Architecture Lock**：合規 —— 走既有 `MemoryProvider` 抽象，非另寫 agent 核心；
不動 `CS_TOOL_ALLOWLIST`（記憶非 agent tool）。

## Verification

本機 Docker `lock_AI_data`(pg17) 套用 migration 033 + `tests/test_memory_postgres.py`
7 passed（中文檢索 / scope 隔離 / forget / default-deny / escalation / backend 切換）。
