---
id: BF-0000
title: Dispatch Overview (Business Flow)
tier: 2
status: accepted
last-synced-with: 4e9658e90324cbceb26f5e5445f481fc5678df1f
synced-at: 2026-05-15
trace_to_fr:
  - "FR-0003-auto-dispatch"
  - "FR-0004-manual-dispatch-audit"
  - "FR-0010-reschedule-delay"
related:
  - "../sub/SF-DSP-01-scheduling.md"
  - "../sub/SF-DSP-02-matching-algorithm.md"
  - "../sub/SF-DSP-04-rejection-reassign.md"
  - "../sub/SF-WO-02-rejection-reassign.md"
  - "../../modules/dispatch-engine.md"
  - "../../modules/dispatch-engine-weights.md"
legacy_id: E5x--workflow-dispatch
---

# BF-0000 — Dispatch Overview

> Dispatch 端到端 BF。詳細 sub-flow 見 SF-DSP-01~04 與 SF-WO-02。
> 本檔保留 §schema 與 §integration overview。

# E5x — Dispatch Operations

> **文件狀態：設計文件（V2.0 派工營運基礎設施規格）**
> 工單派工系統 7 項營運模組：技師排班、媒合演算法、薪酬分潤、拒單重派、客戶設備主檔、技能體系、報表 API。
> 建立日期：2026-04-22
> 前置文件：[[E5x--workflow-work-order]]

---

## 目錄

| # | 缺失項目 | 嚴重度 | 章節 |
|---|---------|--------|------|
| 1 | 技師排班/班表系統 | HIGH | §1 |
| 2 | 媒合演算法實作規格 | HIGH | §2 |
| 3 | 技師薪酬/分潤計算 | HIGH | §3 |
| 4 | 拒單重派流程 | MEDIUM | §4 |
| 5 | 客戶/設備主檔 | MEDIUM | §5 |
| 6 | 技師技能分類體系 | MEDIUM | §6 |
| 7 | 報表 SQL + API | MEDIUM | §7 |

---


## §8 新增表彙總 — cross-cutting（schema 支撐 F-003 / F-004 / F-005 / F-010 / F-021）

本文件新增的所有資料表：

| 表名 | 章節 | 用途 |
|------|------|------|
| `technician_schedules` | §1 | 週期性排班 |
| `technician_day_overrides` | §1 | 例外日（請假/加班） |
| `dispatch_attempts` | §4 | 派工推送記錄 |
| `customers` | §5 | 客戶主檔 |
| `customer_devices` | §5 | 客戶設備檔 |
| `skill_definitions` | §6 | 技能代碼主檔 |
| `technician_skills` | §6 | 技師-技能關聯 |
| `technician_adjustments` | §3 | 獎懲記錄 |
| `technician_settlements` | §3 | 結算記錄 |
| `customer_ratings` | §7 | 客戶評分 |

所有表均含 `tenant_id UUID NOT NULL REFERENCES tenants(id)` + RLS policy，確保多租戶就緒。

---

## §9 與現有系統的整合點 — cross-cutting（agent / api / web 三模組依賴）

| 現有元件 | 整合方式 | 改動量 |
|----------|---------|--------|
| `skills/tools.py` transfer_to_human | 建立工單時查 `customers` + `customer_devices` 自動帶入 | ~10 行 |
| `skills/tools.py` update_user_info | 同步寫入 `customers` 表 | ~5 行 |
| `harness/debounce.py` run_agent | 注入 `[進行中工單]` + 設備保固狀態 | ~15 行 |
| `profiles/manager.py` | 雙寫：update_fact 同時更新 customers | ~10 行 |
| `storage/postgres_impl.py` | 新增 dispatch_decision, settlement 事件類型 | ~5 行 |
| `config.toml` | 新增 `[dispatch]` section（媒合權重、SLA、分潤比例） | 新增 section |
