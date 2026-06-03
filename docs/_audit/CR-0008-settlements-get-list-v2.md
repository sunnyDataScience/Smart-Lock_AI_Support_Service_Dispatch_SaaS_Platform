---
id: CR-0008
title: "Settlements GET list v2（解 accounting/page 1 caller，最小 CIA）"
status: awaiting-owner-decision
tier: 4-exploration
owner: HYBRID
created: 2026-06-04
target-release: P3 track-A 收尾 wave-5
product-version: null
supersedes: null
superseded-by: null
related:
  - docs/_audit/CR-0003-full-cutover-wbs.md
  - api/routers/settlements_v2.py
---

# CR-0008 — Settlements GET list v2

> **Tier**: 4-exploration → CIA  
> **Mandated by**: `.claude/rules/change-governance.md`  
> **Scope**: 最小 CIA，只補 1 個 GET endpoint。

---

## 1. Change Statement

**As-is**：
- `settlements_v2.py` 只有 `POST /tenants/{tid}/settlements/monthly`（觸發月結）
- web `accounting/page.tsx:124` 還在打 `GET /api/v1/accounting/settlements?limit=50` 列 settlement 清單
- 無 v2 GET list endpoint 可遷

**To-be**：
- 補 `GET /tenants/{tid}/settlements` v2 list endpoint
- web caller drop-in 切到 v2

**Driver**：
- 最小可行 P3 收尾單位（1 caller × 1 endpoint）
- 與 CR-0005/0006/0007 並列等業主裁決，但本 CIA HD 最少

---

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| `BF-AC-001`（會計 settlement 列表）| Modified | web 從 legacy 改 v2 tenant-scoped |

---

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| `FR-AC-001`（settlement 月結列表）| Modified | API surface 改 tenant-scoped |
| `NFR-AC-001`（list p95 < 300ms）| Unchanged | — |

---

## 4. Affected API

| API ID | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| `API-SETT-V2-LIST` | `GET /tenants/{tid}/settlements` | **New** | — | cursor 分頁 + status filter（pending/paid）+ period_start / period_end 範圍 query |

---

## 5. Affected Data

無 schema 變動（既有 `settlements` 表沿用）。

---

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| `TC-SETT-001`（v2 list cursor）| **New** | cursor + 過濾條件 |
| `TC-SETT-XT-001`（cross-tenant guard）| **New** | 跨 tenant 403 |

---

## 7. Affected Architecture

無 ADR；純 endpoint 補齊。

---

## 8. Human Decisions Required

🛑 **CIA blocks code changes until every row here has a recorded decision.**

| # | Question | Options | Owner | Status | Decision |
|---|---|---|---|---|---|
| **HD-01** | settlement list 預設過濾範圍 | (a) 最近 3 個月<br>(b) 最近 12 個月<br>(c) 全部（cursor 分頁）| Product | open | — |
| **HD-02** | 排序欄位 | (a) period_end desc<br>(b) created_at desc<br>(c) 兩者 secondary sort | Product | open | — |

---

## 9. Suggested Implementation Order

§8 裁決後：

1. `settlements_v2.py` 補 GET list endpoint（~30 lines）
2. `settlement_service` 補 `list_settlements` 函式（~50 lines）
3. TC-SETT-001 + TC-SETT-XT-001
4. `web/src/app/accounting/page.tsx:124` 改 `tenantPath("/settlements")` + query
5. CR-0003 §5 wave-5 ✅

---

## 10. Risks & Rollback

無重大風險；純 additive，可逆。

---

## 11. Out of Scope

- settlement detail / approve（已有 reconciliations 流程處理）
- AP 月結（FR-0045 Phase II）

---

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product | | | |
| Engineering Lead | | | |

---

## §A 取證附錄

```bash
$ grep -n "api/v1/accounting/settlements" web/src/app/accounting/page.tsx
# → 124: "/api/v1/accounting/settlements?limit=50"

$ grep "@router\." api/routers/settlements_v2.py
# → 1 個（POST monthly），缺 GET list
```

---

> 🛑 **§8 裁決前不動 code。** 預計裁決後工時 < 0.5 天（最小 CR）。
