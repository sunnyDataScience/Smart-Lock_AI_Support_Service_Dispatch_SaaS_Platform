---
id: P4-STAGES-2-7-PREP
title: P4 Cutover Stage 2-7 預備 BUILD Checklists
status: open
created_at: 2026-06-05
related:
  - P4-cutover-v1-caller-inventory-2026-06-05.md
  - P4-stage1-build-checklist.md
purpose: 對齊 P4 inventory §3 表格，給 Stage 2-7 各別 BUILD 啟動前可直接走的 step-by-step。
---

# P4 Stage 2-7 預備 BUILD Checklists

> Stage 1 已完 backend 部分；本 doc 為剩 6 stage 啟動前 prep。
> 每 stage 含 scope / pre-conditions / tasks / verification / risk。

## Stage 2: auth + knowledge-base + manuals 遷移（半天，🟢 低）

### 2.1 Scope

- `auth` — **user-scoped 永久保留**（per P4-cutover-inventory §2.4）
- `knowledge-base` (3 refs) — v2 已 100% (CR-0005 落)
- `manuals` (2 refs) — v2 既有

### 2.2 Pre-conditions

- [ ] Stage 1 已 merge to main / production
- [ ] v2 對應 endpoint 100% 對齊 (CR-0005)
- [ ] DeprecationMiddleware metrics reset 後 7d 觀察

### 2.3 Tasks

- [ ] grep `/api/v1/knowledge-base` 找全 web caller
- [ ] grep `/api/v1/manuals` 找全 web caller
- [ ] 逐個改 tenantPath() v2
- [ ] tsc + Playwright (admin/knowledge-base + cases pages)

### 2.4 Risk

| 風險 | 機率 | 緩解 |
|:---|:---:|:---|
| kb manuals upload flow break | M | 跑 e2e 上傳 PDF 確認 |
| case_entries v2 path 不同 | L | 對齊 CR-0005 docs |

### 2.5 Time: ~3-4 hr

---

## Stage 3: technicians + work-orders 遷移（1d，🟢 低）

### 3.1 Scope

- `technicians` (8 refs)
  - **user-scoped 永久保留**: technicians/me, technicians/me/availability
  - **可遷**: admin 端 list/get (~6 refs)
- `work-orders` (4 refs) — v2 已 100% (CR-0003)

### 3.2 Pre-conditions

- [ ] Stage 2 已 merge
- [ ] Stage 1 metrics 顯示 /api/v1/technicians admin 路徑無流量

### 3.3 Tasks

- [ ] 分類 8 個 technicians refs:
  - 標 user-scoped (me 系列) → 留
  - 標 admin → 遷 v2
- [ ] 遷 work-orders 4 refs 全 v2 (work_orders_v2 + work_orders_ops_v2)
- [ ] tsc + Playwright (admin/technicians, work-orders, my-orders pages)

### 3.4 Risk

| 風險 | 機率 | 緩解 |
|:---|:---:|:---|
| work-orders subflow caller 遺漏 | M | grep 同 path :accept/:complete/:cancel |
| technicians admin list response shape | L | Type 對齊既有 |

### 3.5 Time: ~6-8 hr

---

## Stage 4: config 遷移 case-by-case（1d，🟡 中）

### 4.1 Scope

- `config` (7 refs)
  - settings/page.tsx system config — 看是否走 M18 governance
  - admin/api-status/page.tsx 也用 /api/v1/config — debug 頁面
  - components/settings/SystemConfigForm.tsx 用 GET + PATCH

### 4.2 Pre-conditions

- [ ] M18 config governance 完整 BUILD 完成 (config_m18 router 落)
- [ ] 業主確認 system config / M18 config 兩軌策略

### 4.3 Tasks

- [ ] 對每個 `/api/v1/config` ref 確認:
  - 該欄位是否在 M18 governance 範圍 → 改用 GET configActiveVersion
  - 非 M18 範圍 → 保留 v1 system config endpoint
- [ ] 寫遷移 mapping table

### 4.4 Risk

| 風險 | 機率 | 緩解 |
|:---|:---:|:---|
| system config 與 M18 config 兩軌混淆 | H | 寫 mapping table；業主審 |
| api-status debug page 失效 | L | Stage 4 期間保留 v1 caller |

### 4.5 Time: ~6 hr + 業主審

---

## Stage 5: accounting Reconciliation dual-sign UX rework（1-2d，🟡 中-產品）

### 5.1 Scope

- `accounting/page.tsx` (1 ref) — `/api/v1/accounting/reconciliations/.../approve`
- 改 v2 `:review` (CSM) + `:co-sign` (ops_manager) 兩步 UI

### 5.2 Pre-conditions

- [ ] 業主裁決 UX 設計（兩步驟流程 UI mockup）
- [ ] reconciliation_v2 router endpoint 已 100% (Track B S2 已落)
- [ ] 前端 product owner approved

### 5.3 Tasks

- [ ] UX 設計 wireframe (前端 + product)
- [ ] 改 accounting/page.tsx 加 review step state + co-sign step state
- [ ] 加 X-Initiator header 處理
- [ ] tsc + Playwright + 業務人員 UAT

### 5.4 Risk

| 風險 | 機率 | 緩解 |
|:---|:---:|:---|
| 改錯 dual-sign UX 流失資料 | M | 完整 e2e 驗證；staging 試 7d |
| SoD violation 處理 UX | M | 提示 toast / inline error |

### 5.5 Time: 1-2d（含 UX 設計）

---

## Stage 6: public token endpoints 整合（1d，🟡 中）

### 6.1 Scope

- `public` (4 refs)
  - `scope-change/[token]` page — `/api/v1/public/scope-changes/{token}`
  - `track/[token]` page — `/api/v1/public/work-orders/{token}`
  - consumer_v2 涵蓋部分但不全

### 6.2 Pre-conditions

- [ ] consumer_v2 router 全 endpoint 對齊 v1 path (含 token URL pattern)
- [ ] LINE Flex push 鏈路全 consumer_v2 path (CR-0017 確認)

### 6.3 Tasks

- [ ] grep 全 `/api/v1/public/` web caller
- [ ] 改 `/consumer/...` v2 path
- [ ] 確認 LINE Flex URI button 也用 v2

### 6.4 Risk

| 風險 | 機率 | 緩解 |
|:---|:---:|:---|
| 消費者 LINE 內舊 URL 失效 | H | 保留 v1 redirect 30d |
| token 驗證 path 不同 | L | 對齊 consumer_v2 token middleware |

### 6.5 Time: ~6 hr + LINE redirect 設定

---

## Stage 7: 刪 v1 router + DeprecationMiddleware 移除（1d，🔴 高）

### 7.1 Scope

- 刪所有「無 user-scoped 路徑 + no-traffic」的 v1 router
- 保留: auth.py, technicians.py (me/availability only), config v1 (case-by-case)
- 移除 DeprecationMiddleware (改保留 hit metrics middleware)
- auth 扁平化 (移除 v1/v2 dual mounting)
- OpenAPI / generated types 重生

### 7.2 Pre-conditions

- [ ] Stage 1-6 全 merge to production
- [ ] DeprecationMiddleware metrics 在 production 跑 30+ 天
- [ ] `GET /api/v1/admin/v1-inventory/no-traffic` 顯示 ≥ 80% endpoints 無流量
- [ ] 客戶端 (mobile / 第三方) 確認 0 v1 流量 (Cloud Run access log 驗證)
- [ ] 業主批准 destructive 時機

### 7.3 Tasks

- [ ] 取 `/admin/v1-inventory/no-traffic` 候選清單
- [ ] 對每候選 v1 router 確認:
  - 既有 user-scoped path? → 部分保留
  - 無 user-scoped 也無流量? → 刪
- [ ] 刪除 router import + include_router 行
- [ ] 移除對應 router file
- [ ] 移除 DeprecationMiddleware (保留 hit metrics middleware)
- [ ] auth 扁平化 (移除 dual route)
- [ ] OpenAPI regenerate (`scripts/openapi/regen.sh`)
- [ ] frontend type 重生
- [ ] 全 tests pass (regression)

### 7.4 Risk

| 風險 | 機率 | 緩解 |
|:---|:---:|:---|
| 客戶端仍用刪掉的 v1 → 404 | H | 30d access log 觀察 + ops 通知 |
| import graph 互相依賴 → 連鎖 break | M | Stage 7 前期跑 dep graph 分析 |
| OpenAPI breaking change | M | contract test + auto regen |

### 7.5 Time: 1d + staging 完整驗證 + 流量觀察

---

## §X 全 P4 完成後

- WBS 完成度 +1-1.5% (98.5% → ~100% backend)
- 配合 Phase 8 UAT 達 production-ready 完整 V2.0
- DeprecationMiddleware 移除 — codebase 清乾淨
- maintenance: 只 maintain 一套 v2 endpoint
