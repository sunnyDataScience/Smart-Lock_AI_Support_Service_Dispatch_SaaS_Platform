/**
 * web/tests/e2e/admin/approval-inbox.spec.ts — FR-0049 Approval Inbox smoke
 *
 * 對應 Sprint 1 (per docs/_audit/phase-ii-web-integration-plan.md §2)。
 * Backend endpoint: GET /tenants/{tid}/approval-inbox (FR-0049 MVP)
 *
 * 本 spec 為 future Sprint 1 BUILD 的 e2e starter；目前 web page 尚未實作，
 * 本 spec 預期 fail 直到 admin/approval-inbox/page.tsx 落地。
 *
 * 範圍（最小 smoke）：
 *   1. /admin/approval-inbox 路徑可達（無 5xx）
 *   2. page 有 header 顯示 "Approval Inbox" 字眼
 *   3. type filter dropdown 存在含 5 個 option
 *   4. table or list 區域存在
 *
 * 故意 NOT 做：
 *   - 不打真 API （需 backend seed pending row）
 *   - 不驗具體 item 內容
 *   - 不驗 click → navigate 流程（留 Sprint 1 末 BUILD）
 */

import { test, expect } from '@playwright/test';

test.describe.skip('Approval Inbox Smoke (Sprint 1 BUILD pending)', () => {
  test('renders inbox page without 5xx', async ({ page }) => {
    const response = await page.goto('/admin/approval-inbox');
    expect(response?.status(), 'inbox page should not 5xx').toBeLessThan(500);

    await expect(
      page.locator('h1, h2').filter({ hasText: /Approval.*Inbox|核准收件匣/i }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('type filter dropdown has 5 + all options', async ({ page }) => {
    await page.goto('/admin/approval-inbox');

    const typeFilter = page.locator(
      'select[name="type"], select[aria-label*="type" i], [data-testid="type-filter"]',
    ).first();
    await expect(typeFilter).toBeVisible({ timeout: 10_000 });

    const optionTexts = await typeFilter.locator('option').allTextContents();
    // 預期 6 options: all + 5 types
    expect(optionTexts.length).toBeGreaterThanOrEqual(6);

    const expectedTypes = [
      'scope_change', 'refund', 'dispute', 'reschedule', 'recon_exception',
    ];
    for (const t of expectedTypes) {
      expect(
        optionTexts.some(opt => opt.toLowerCase().includes(t)),
        `type filter missing option for ${t}`,
      ).toBeTruthy();
    }
  });

  test('list/table region exists', async ({ page }) => {
    await page.goto('/admin/approval-inbox');

    // 容忍多種 layout: table / ul / div role="list"
    await expect(
      page.locator(
        'table, ul[role="list"], div[role="list"], [data-testid="inbox-list"]',
      ),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('severity badges rendered (when items exist)', async ({ page }) => {
    await page.goto('/admin/approval-inbox');

    // 若有 item 則該見 severity badge (high/medium/low)
    const items = page.locator('[data-testid="inbox-item"], tr[data-severity]');
    const count = await items.count();
    if (count === 0) {
      test.skip(true, 'no inbox items; skip severity badge check');
      return;
    }
    await expect(
      items.first().locator(
        '[data-testid="severity-badge"], .severity-high, .severity-medium, .severity-low',
      ),
    ).toBeVisible({ timeout: 5_000 });
  });
});

/**
 * Sprint 1 BUILD 啟用本 spec 流程：
 *
 * 1. 建立 web/src/app/admin/approval-inbox/page.tsx
 * 2. 接 GET /tenants/${tid}/approval-inbox endpoint (FR-0049)
 * 3. 移除本 spec 的 .skip
 * 4. 跑 npx playwright test admin/approval-inbox.spec.ts
 * 5. 確認 4 個 test 全綠
 *
 * 失敗時對照 backend service:
 *   - api/services/approval_inbox_service.py
 *   - api/routers/approval_inbox_v2.py
 *   - api/tests/test_approval_inbox.py (10 backend tests，passing)
 */
