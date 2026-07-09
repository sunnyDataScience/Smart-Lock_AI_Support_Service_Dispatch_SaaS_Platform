/**
 * web/tests/e2e/account/statements.spec.ts — FR-0045 Tech AP Statement self-service smoke
 *
 * 對應 Sprint 2 (per docs/_audit/phase-ii-web-integration-plan.md §2)。
 * Backend endpoints (FR-0045 MVP):
 *   GET /tenants/{tid}/tech-statements?technician_id=me
 *   POST /tenants/{tid}/tech-statements/{id}:dispute
 *
 * 技師 self-service 查月結 statement + dispute window 倒數 + dispute action。
 *
 * 本 spec 為 Sprint 2 BUILD 的 e2e starter；用 test.describe.skip 標記
 * 直到 web page 落地後可移除 skip 直接用。
 *
 * 範圍（最小 smoke）：
 *   1. /account/statements 路徑可達（無 5xx）
 *   2. 頁面顯示 "月結" 或 "Statement" header
 *   3. statement 列表/卡片區域存在
 *   4. (若有 pending_review row) dispute window countdown 顯示
 *   5. (若有 disputable row) dispute 按鈕存在
 *
 * 故意 NOT 做：
 *   - 不打真 dispute API （需 backend test seed pending row）
 *   - 不驗具體金額計算（單元測試已驗 17 backend tests）
 *   - 不驗 reason form submit 流程（留 Sprint 2 末 BUILD）
 */

import { test, expect } from '@playwright/test';

test.describe.skip('Tech Statement self-service Smoke (Sprint 2 BUILD pending)', () => {
  test('renders statements page without 5xx', async ({ page }) => {
    const response = await page.goto('/account/statements');
    expect(response?.status(), 'statements page should not 5xx').toBeLessThan(500);

    await expect(
      page.locator('h1, h2').filter({ hasText: /Statement|月結|統計/i }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('list/card region exists', async ({ page }) => {
    await page.goto('/account/statements');

    await expect(
      page.locator(
        'table, ul[role="list"], div[role="list"], [data-testid="statement-list"]',
      ),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('status badges rendered for each statement', async ({ page }) => {
    await page.goto('/account/statements');

    const items = page.locator(
      '[data-testid="statement-item"], tr[data-statement-id], div[data-statement-id]',
    );
    const count = await items.count();
    if (count === 0) {
      test.skip(true, 'no statements; skip badge check');
      return;
    }
    // status badge 6 種：draft/pending_review/disputed/approved/rejected/paid
    await expect(
      items.first().locator(
        '[data-testid="status-badge"], .status-draft, .status-pending_review, ' +
        '.status-disputed, .status-approved, .status-rejected, .status-paid',
      ),
    ).toBeVisible({ timeout: 5_000 });
  });

  test('dispute window countdown shown for pending_review', async ({ page }) => {
    await page.goto('/account/statements');

    const pendingItems = page.locator(
      '[data-statement-status="pending_review"], ' +
      '[data-testid="statement-item"][data-status="pending_review"]',
    );
    const count = await pendingItems.count();
    if (count === 0) {
      test.skip(true, 'no pending_review statements; skip countdown check');
      return;
    }
    await expect(
      pendingItems.first().locator(
        '[data-testid="dispute-window-countdown"], .countdown, [aria-label*="dispute" i]',
      ),
    ).toBeVisible({ timeout: 5_000 });
  });

  test('dispute button exists for disputable status', async ({ page }) => {
    await page.goto('/account/statements');

    const disputable = page.locator(
      '[data-statement-status="pending_review"]:not([data-window-expired="true"])',
    );
    const count = await disputable.count();
    if (count === 0) {
      test.skip(true, 'no disputable statements; skip button check');
      return;
    }
    await expect(
      disputable.first().locator(
        'button:has-text("Dispute"), button:has-text("申訴"), ' +
        '[data-testid="dispute-button"]',
      ),
    ).toBeVisible({ timeout: 5_000 });
  });

  test('amount breakdown visible', async ({ page }) => {
    await page.goto('/account/statements');

    const items = page.locator('[data-testid="statement-item"]').first();
    if ((await items.count()) === 0) {
      test.skip(true, 'no items; skip amount check');
      return;
    }
    // amount fields: gross / deductions / net
    for (const field of ['gross', 'deduction', 'net']) {
      await expect(
        items.locator(`[data-testid="amount-${field}"], .amount-${field}`),
      ).toBeVisible({ timeout: 3_000 });
    }
  });
});

/**
 * Sprint 2 BUILD 啟用本 spec 流程：
 *
 * 1. 建立 web/src/app/account/statements/page.tsx
 * 2. 接 GET /tenants/${tid}/tech-statements?technician_id=me endpoint
 * 3. 加 dispute action form
 * 4. 移除本 spec test.describe.skip
 * 5. 跑 npx playwright test account/statements.spec.ts
 *
 * 對照 backend service:
 *   - api/services/technician_statement_service.py
 *   - api/routers/technician_statement_v2.py (8 endpoints)
 *   - api/tests/test_technician_statement.py (17 backend tests passing)
 *
 * 注：admin 側 statements page (admin/accounting/tech-statements) 另寫 spec。
 */
