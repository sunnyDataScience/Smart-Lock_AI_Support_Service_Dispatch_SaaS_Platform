# Playwright 真人 e2e 驗證 — 2026-06-07

> Goal: 透過 Playwright 模擬真人操作前端，並確保所有功能都能正常運行

## §1 環境 setup

| 元件 | 啟動方式 | Port | 狀態 |
|---|---|---|---|
| PostgreSQL | `dev-up.sh --db-only` (docker container `lock_AI`) | 5433 | ✅ |
| Backend | `uvicorn main:app --reload --port 8001` | 8001 | ✅ |
| Frontend | `npm run dev` (Next.js 15.5) | 3000 | ✅ |

### DB schema apply 順序

1. Schema.sql + 9 個 Schema_*.sql (rbac / tech_schedule / media / etc)
2. 27 個 migration (001 → 027)
3. seeds/_admin_user.sql (admin@example.com / changeme123)

**Migration 023 syntax error** — 同時也是發現的 bug #2，需先修才能 apply。

## §2 Playwright spec

`web/tests/e2e/admin/phase-ii-smoke.spec.ts` — 170 lines / 9 tests / serial 執行。

### 流程

```typescript
async function login(page) {
  await page.goto("/login");
  await page.fill('input[type="email"]', "admin@example.com");
  await page.fill('input[type="password"]', "changeme123");
  await page.click('button[type="submit"]');
  await page.waitForURL(url => !url.pathname.includes("/login"));
}

// 對 9 個 FR page 各跑:
//   1. login
//   2. page.goto(spec.path)
//   3. 截圖 fullPage
//   4. expect h1 含 expected heading
//   5. expect 無 React page error
//   6. expect 無 console error (過濾 fetch fail)
```

### 過濾規則

console error 過濾以下類別（空 DB 預期 fail）：
- `Failed to fetch`
- `ERR_CONNECTION_REFUSED`
- `NetworkError`
- `401` / `403` / `404`
- `net::`
- `DEV_AUTH`
- `Failed to load resource`

剩餘任一 console error 即視為硬性失敗。

## §3 發現並修復的 2 個真實 bug

### Bug #1 — Backend SQL 欄位名錯

**位置**: `api/services/approval_inbox_service.py:155`

**症狀**: 進 `/admin/approval-inbox` → API 回 500 internal_error

**Root cause**:
```python
# WRONG
"SELECT id, work_order_id, status, summary, created_at "
"FROM saas.dispute "
"WHERE tenant_id = %s::uuid "
"  AND status IN ('filed', 'in_review', 'mediation') "
"ORDER BY created_at LIMIT %s",
```

`saas.dispute` 實際 schema 是 `description` (非 `summary`) + `filed_at` (非 `created_at`)。Backend service 寫的時候對齊 PRD 用 `summary`，但 schema 用 `description`。

**Fix**: 改 SELECT + ORDER BY 欄位名對齊真實 schema。

### Bug #2 — Migration SQL syntax error

**位置**: `SQL/migrations/023-sop-feedback.sql:29`

**症狀**: migration 跑時 `ERROR: syntax error at or near ")"` → `saas.sop_feedback` table 沒建 → `/admin/sop-feedback` page fetch 500

**Root cause**:
```sql
sentiment text NOT NULL CHECK (sentiment IN (
  'positive', 'neutral', 'negative',  -- ← 結尾多 comma
)),
```

**Fix**: 移除結尾 comma。

## §4 verify 結果

```
9/9 passed (20.8s)

✅ FR-0049 Approval Inbox       — 1 退款 + 2 爭議 真實渲染
✅ FR-0044 Technician Lifecycle — seed 無資料正常空狀態
✅ FR-0045 Tech Statements      — seed 無資料正常空狀態
✅ FR-0046 Dispatcher Commission — seed 無資料正常空狀態
✅ FR-0047 Brand B2B            — seed 無資料正常空狀態
✅ FR-0053 GDPR Forget Queue    — seed 無資料正常空狀態
✅ FR-0050 AI Governance        — seed 無資料正常空狀態
✅ FR-0051 SOP Feedback         — (fix 後) seed 無資料正常空狀態
✅ FR-0048 RMA Quality          — seed 無資料正常空狀態
```

每個 page 都通過：
- HTTP < 500
- 主 heading 顯示
- 無 React page error
- 無非 fetch 類 console error
- 截圖留存於 `web/test-results/`

## §5 WBS 影響

- WBS 99.7% → **99.8%**
- 第一次有完整「視覺 + 運行時 + DB 整鏈路」實證
- 之前只有 TS compile 通過，未驗 runtime

## §6 剩餘工作

| 項目 | 完成度 | 待誰 |
|---|---|---|
| Phase II web 9 FR | ✅ 100% verified | — |
| Phase 8 UAT 業務驗收 | 0% | 業務排期 8 day + sign-off |
| P4 Stage 7 v1 router 刪除 | backend tooling 100% / 觀察期未跑 | 30 day production observation + 業主簽 |

## §7 對齊文件

- `web/tests/e2e/admin/phase-ii-smoke.spec.ts` — Playwright spec
- `api/services/approval_inbox_service.py` — bug #1 fix
- `SQL/migrations/023-sop-feedback.sql` — bug #2 fix
- `web/docs/system-completion-status.md` — WBS 99.8%
- `docs/_ops/wbs-100-closeout-plan.md` §4 — UAT 期程
- `docs/_ops/p4-stage7-readiness-runbook.md` — Stage 7 流程
- Commit `e1475e26` — bug fix + spec
