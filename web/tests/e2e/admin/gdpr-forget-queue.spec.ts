/**
 * web/tests/e2e/admin/gdpr-forget-queue.spec.ts — FR-0053 admin queue smoke
 *
 * 對應 Sprint 3 (per docs/_audit/phase-ii-web-integration-plan.md §2)。
 * Backend endpoints (FR-0053 MVP):
 *   GET /tenants/{tid}/gdpr/forget-requests?status=...
 *   POST .../forget-requests/{id}:legal-hold-deny
 *   POST .../forget-requests/{id}:soft-delete
 *   POST .../forget-requests/{id}:hard-delete
 *
 * admin 視角：管理 customer GDPR forget request queue + 5 狀態流程。
 *
 * 本 spec 為 Sprint 3 BUILD 的 e2e starter；用 test.describe.skip 標記。
 *
 * 範圍（最小 smoke）：
 *   1. /admin/gdpr/forget-queue 路徑可達（無 5xx）
 *   2. 頁面 header 含 "GDPR" 或 "Forget" 字眼
 *   3. status filter 含 5 個 option (received/legal_hold_denied/
 *      soft_deleted/hard_deleted/cancelled)
 *   4. (若有 received row) 3 actions 按鈕（legal-hold-deny /
 *      soft-delete / hard-delete）
 *   5. (若有 soft_deleted row) cooldown 倒數計時
 */

import { test, expect } from '@playwright/test';

test.describe.skip('GDPR Forget Queue Smoke (Sprint 3 BUILD pending)', () => {
  test('renders queue page without 5xx', async ({ page }) => {
    const response = await page.goto('/admin/gdpr/forget-queue');
    expect(response?.status(), 'queue page should not 5xx').toBeLessThan(500);

    await expect(
      page.locator('h1, h2').filter({ hasText: /GDPR|Forget|遺忘|刪除/i }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('status filter has 5 status + all', async ({ page }) => {
    await page.goto('/admin/gdpr/forget-queue');

    const statusFilter = page.locator(
      'select[name="status"], select[aria-label*="status" i], ' +
      '[data-testid="status-filter"]',
    ).first();
    await expect(statusFilter).toBeVisible({ timeout: 10_000 });

    const options = await statusFilter.locator('option').allTextContents();
    const expectedStatus = [
      'received', 'legal_hold_denied', 'soft_deleted',
      'hard_deleted', 'cancelled',
    ];
    for (const s of expectedStatus) {
      expect(
        options.some(opt => opt.toLowerCase().includes(s)),
        `status filter missing ${s}`,
      ).toBeTruthy();
    }
  });

  test('action buttons for received requests', async ({ page }) => {
    await page.goto('/admin/gdpr/forget-queue?status=received');

    const items = page.locator('[data-status="received"]');
    const count = await items.count();
    if (count === 0) {
      test.skip(true, 'no received requests; skip action button check');
      return;
    }
    const first = items.first();
    // 3 actions per row: deny / soft-delete / hard-delete
    for (const action of ['legal-hold-deny', 'soft-delete', 'cancel']) {
      await expect(
        first.locator(
          `button[data-action="${action}"], ` +
          `button:has-text("${action}"), ` +
          `[data-testid="${action}-button"]`,
        ),
      ).toBeVisible({ timeout: 3_000 });
    }
  });

  test('cooldown countdown shown for soft_deleted', async ({ page }) => {
    await page.goto('/admin/gdpr/forget-queue?status=soft_deleted');

    const items = page.locator('[data-status="soft_deleted"]');
    const count = await items.count();
    if (count === 0) {
      test.skip(true, 'no soft_deleted; skip countdown check');
      return;
    }
    await expect(
      items.first().locator(
        '[data-testid="cooldown-countdown"], .cooldown, ' +
        '[aria-label*="cooldown" i], [aria-label*="hard-delete" i]',
      ),
    ).toBeVisible({ timeout: 5_000 });
  });

  test('hard-delete button only enabled when cooldown passed', async ({ page }) => {
    await page.goto('/admin/gdpr/forget-queue?status=soft_deleted');

    const items = page.locator('[data-status="soft_deleted"]');
    const count = await items.count();
    if (count === 0) {
      test.skip(true, 'no soft_deleted; skip cooldown gate check');
      return;
    }

    for (let i = 0; i < count; i++) {
      const item = items.nth(i);
      const eligibility = await item.getAttribute('data-cooldown-passed');
      const hardDeleteBtn = item.locator(
        'button[data-action="hard-delete"], button:has-text("hard-delete")',
      );

      if (eligibility === 'true') {
        await expect(hardDeleteBtn).toBeEnabled();
      } else {
        await expect(hardDeleteBtn).toBeDisabled();
      }
    }
  });
});

/**
 * Sprint 3 BUILD 啟用本 spec 流程：
 *
 * 1. 建立 web/src/app/admin/gdpr/forget-queue/page.tsx
 * 2. 接 backend endpoints (5 endpoints from forget_v2 router)
 * 3. 加 cooldown countdown component (BR-PII-001 30 days)
 * 4. 移除 test.describe.skip
 *
 * 對照 backend service:
 *   - api/services/gdpr_forget_service.py
 *   - api/routers/gdpr_forget_v2.py (7 endpoints)
 *   - api/tests/test_gdpr_forget.py (14 backend tests passing)
 *   - api/realtime/gdpr_hard_delete_cron.py (T+30 cron)
 *
 * 注：customer LIFF page (track/forget-request) 另寫 spec。
 */
