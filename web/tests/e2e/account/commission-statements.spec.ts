/**
 * web/tests/e2e/account/commission-statements.spec.ts — FR-0046 Dispatcher Commission smoke
 *
 * 對應 Sprint 4 (per docs/_audit/phase-ii-web-integration-plan.md §2)。
 * Backend endpoints (FR-0046 MVP):
 *   GET /tenants/{tid}/dispatcher-commissions?dispatcher_user_id=me
 *   POST .../dispatcher-commissions/{id}:dispute
 *
 * 派工人 self-service 查月結 commission + 派工指標 + dispute window。
 * 結構鏡像 FR-0045 Tech Statement (per Sprint 4 plan)。
 *
 * 範圍（最小 smoke）：
 *   1. /account/commission-statements 路徑可達
 *   2. 頁面 header 含 "Commission|抽成|派工抽成"
 *   3. statement 列表存在
 *   4. 派工指標顯示: total_dispatched / total_completed / completion_rate
 *   5. 金額拆解: base_commission + performance_bonus - penalty = net
 *   6. dispute button 對 disputable status 顯示
 */

import { test, expect } from '@playwright/test';

test.describe.skip('Dispatcher Commission self-service Smoke (Sprint 4 BUILD pending)', () => {
  test('renders page without 5xx', async ({ page }) => {
    const response = await page.goto('/account/commission-statements');
    expect(response?.status()).toBeLessThan(500);

    await expect(
      page.locator('h1, h2').filter({ hasText: /Commission|抽成|派工/i }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('list region exists', async ({ page }) => {
    await page.goto('/account/commission-statements');

    await expect(
      page.locator(
        'table, ul[role="list"], div[role="list"], ' +
        '[data-testid="commission-list"]',
      ),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('dispatch metrics shown (dispatched/completed/rate)', async ({ page }) => {
    await page.goto('/account/commission-statements');

    const items = page.locator(
      '[data-testid="commission-item"], tr[data-statement-id]',
    );
    const count = await items.count();
    if (count === 0) {
      test.skip(true, 'no commission statements; skip metrics check');
      return;
    }

    const first = items.first();
    for (const field of ['dispatched', 'completed', 'completion-rate']) {
      await expect(
        first.locator(`[data-testid="metric-${field}"], .metric-${field}`),
      ).toBeVisible({ timeout: 3_000 });
    }
  });

  test('amount breakdown: base + bonus - penalty = net', async ({ page }) => {
    await page.goto('/account/commission-statements');

    const items = page.locator('[data-testid="commission-item"]').first();
    if ((await items.count()) === 0) {
      test.skip(true, 'no items; skip amount check');
      return;
    }
    for (const field of ['base', 'bonus', 'penalty', 'net']) {
      await expect(
        items.locator(`[data-testid="amount-${field}"], .amount-${field}`),
      ).toBeVisible({ timeout: 3_000 });
    }
  });

  test('status badges 6 種', async ({ page }) => {
    await page.goto('/account/commission-statements');

    const items = page.locator('[data-testid="commission-item"]');
    if ((await items.count()) === 0) {
      test.skip(true, 'no items');
      return;
    }
    await expect(
      items.first().locator(
        '[data-testid="status-badge"], .status-draft, .status-pending_review, ' +
        '.status-disputed, .status-approved, .status-rejected, .status-paid',
      ),
    ).toBeVisible({ timeout: 5_000 });
  });

  test('dispute button for pending_review', async ({ page }) => {
    await page.goto('/account/commission-statements');

    const disputable = page.locator(
      '[data-statement-status="pending_review"]:not([data-window-expired="true"])',
    );
    if ((await disputable.count()) === 0) {
      test.skip(true, 'no disputable statements');
      return;
    }
    await expect(
      disputable.first().locator(
        'button:has-text("Dispute"), button:has-text("申訴"), ' +
        '[data-testid="dispute-button"]',
      ),
    ).toBeVisible({ timeout: 5_000 });
  });
});

/**
 * Sprint 4 BUILD 啟用本 spec 流程：
 *
 * 1. 建立 web/src/app/account/commission-statements/page.tsx
 *    (結構鏡像 account/statements 即 FR-0045)
 * 2. 接 GET dispatcher-commissions?dispatcher_user_id=me
 * 3. UI: 派工指標 + 金額拆解 + dispute action
 * 4. 移除 test.describe.skip
 *
 * 對照 backend service:
 *   - api/services/dispatcher_commission_service.py
 *   - api/routers/dispatcher_commission_v2.py (8 endpoints)
 *   - api/tests/test_dispatcher_commission.py (17 tests passing)
 *
 * 設計 reuse:
 *   - <StatementStateBadge> component (FR-0045 已建)
 *   - <DisputeWindowCountdown> (FR-0045 已建)
 *   - <AmountBreakdown> (新建供 FR-0045/0046 共用)
 */
