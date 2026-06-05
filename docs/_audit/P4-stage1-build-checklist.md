---
id: P4-STAGE1-BUILD-CHECKLIST
title: P4 Cutover Stage 1 BUILD Checklist — 細部 step-by-step
status: open
created_at: 2026-06-05
related: P4-cutover-v1-caller-inventory-2026-06-05.md
purpose: Stage 1 (0.5d) 可立即 BUILD 的具體 task list — 為 ops/dev 提供 step-by-step。
---

# P4 Stage 1 BUILD Checklist

> 對應 `P4-cutover-v1-caller-inventory-2026-06-05.md` §3 Stage 1（半天，🟢 低風險）。
> session 末段補：扣除 user-scoped 後實際待清項目不到 5 項。

## §1 Scope

Stage 1 範圍：清掉「v1 caller 為 stale comment 或 reports/roles/refunds 已 v2 但未刷出 import」的微薄殘留。

**不在 Stage 1 範圍**（留 Stage 2-7）：
- foo mock — 純 docstring 範例，無實 caller (`web/src/lib/api.ts` line 14 註解 — 教學範例，不刪)
- auth-related — user-scoped 永久 v1
- technicians/me — user-scoped 永久 v1
- accounting/page.tsx — Stage 5（UX rework）

## §2 Tasks（按優先順序）

### Task 1: 清掉 stale comment「list 仍走舊」（已做）

- ✅ Status: done in `e049de22` (2026-06-05 session 末段)
- File: `web/src/app/admin/refunds/page.tsx` line 128
- 改：stale claim 「仍走舊 GET /api/v1/refunds」→ 真實「走 v2 tenantPath」

### Task 2: 確認 admin/refunds 已 100% v2

- [ ] grep `web/src/app/admin/refunds/page.tsx` 確認無 `/api/v1/refunds` 真實 caller
- [ ] 預期：全 `tenantPath("/refunds")` v2
- [ ] 已驗證（commit `e049de22`）

### Task 3: 檢查 admin/reports/revenue page

- [ ] 看 `web/src/app/admin/reports/revenue/page.tsx` line 88 TODO[E7x §4.3]
- [ ] 確認 `/api/v1/reports/revenue` 是否已有 v2 替代
- [ ] 若有 v2 → 改 caller；若無 → 保留 TODO

### Task 4: 檢查 admin/reports/technician-ranking page

- [ ] 看 `web/src/app/admin/reports/technician-ranking/page.tsx` 全 caller
- [ ] 確認 v2 對應 endpoint 已存在
- [ ] 改 caller

### Task 5: roles page 確認

- [ ] 看 `web/src/app/admin/roles/page.tsx` line 112 註解
- [ ] 註解標「v2 已遷 + legacy 雙掛」— 確認 line 112-130 caller 確實全 v2
- [ ] 若 caller 已 v2 → 清掉 line 112 註解中「legacy /api/v1/roles」refer
- [ ] 若未遷 → 改

### Task 6: refresh DeprecationMiddleware metrics

- [ ] 部署 Stage 1 後跑 `POST /api/v1/admin/deprecation/v1-metrics:reset`
- [ ] 流量觀察 7 天
- [ ] 跑 `GET /api/v1/admin/v1-inventory/no-traffic` 看新候選清單

## §3 驗證

- [ ] AST 驗證 web TypeScript (npx tsc --noEmit)
- [ ] 跑 web e2e Playwright (admin/refunds + admin/reports + admin/roles 三 page)
- [ ] confirm no 4xx/5xx on the migrated endpoints
- [ ] commit + push

## §4 Stage 1 完成後

- WBS 完成度 +0.5% (98% → 98.5%)
- 解鎖 Stage 2 (auth/knowledge-base/manuals 遷移，半天)
- P4 整體完成度 1/7

## §5 Out of Scope (留 Stage 2-7)

- Stage 2: auth/knowledge-base/manuals (auth user-scoped 永久 v1；其他 v2 已備)
- Stage 3: technicians/work-orders (大批 caller 遷)
- Stage 4: config (case-by-case 檢查)
- Stage 5: accounting Reconciliation dual-sign UX rework (產品)
- Stage 6: public token endpoints (消費者前端)
- Stage 7: 刪 v1 router (含 user-scoped 永久保留 — 須細選)

## §6 風險

| 風險 | 機率 | 緩解 |
|:---|:---:|:---|
| 刪 stale comment 導致 review confusion | L | commit msg 明示「stale comment」非 code 變動 |
| reports page caller 改錯 break revenue 顯示 | M | Stage 完成後 Playwright e2e 驗 |
| TS type 不對 | L | tsc --noEmit 必跑 |

## §7 預估工時

- Task 1-2: 0 (done)
- Task 3: 30 min (檢查 + 改 caller)
- Task 4: 30 min
- Task 5: 30 min (含註解更新)
- Task 6: 5 min (reset metrics) + 7d 觀察 → 5 min (查 no-traffic)
- 驗證 §3: 1-2 hr (含 Playwright)
- **總計**: ~3.5-4 hr (對齊 §3 半天估)

## §8 啟動

```bash
# 1. 開分支
git checkout -b feat/p4-stage1-web-caller-migration

# 2. 對 Task 3/4/5 逐個改 caller

# 3. tsc + Playwright

# 4. commit per-task or 一次 commit (Stage 1 範圍小)

# 5. merge to dev_new_arch
```
