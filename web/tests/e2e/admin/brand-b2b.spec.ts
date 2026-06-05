/**
 * web/tests/e2e/admin/brand-b2b.spec.ts — FR-0047 Brand B2B Settlement admin smoke
 *
 * 對應 Sprint 5 (per docs/_audit/phase-ii-web-integration-plan.md §2)。
 * Backend endpoints (FR-0047 MVP):
 *   GET /tenants/{tid}/brand-b2b-statements?direction=AR|AP|NET
 *
 * admin 視角：管理品牌 B2B 月結 — AR (品牌付服務費) / AP (平台付 commission) /
 * NET (相沖)。
 *
 * 範圍（最小 smoke）：
 *   1. /admin/accounting/brand-b2b 路徑可達
 *   2. 頁面 header 含 "Brand B2B|品牌"
 *   3. direction filter 含 AR / AP / NET 3 option
 *   4. net_payable_to dual-state UI (brand 應收 vs platform 應收)
 *   5. NET direction 顯示 ar - ap + warranty + sla = net 計算
 *   6. 服務量指標: total_service_orders / warranty_claims / sla_breach
 */

import { test, expect } from '@playwright/test';

test.describe.skip('Brand B2B Settlement Admin Smoke (Sprint 5 BUILD pending)', () => {
  test('renders page without 5xx', async ({ page }) => {
    const response = await page.goto('/admin/accounting/brand-b2b');
    expect(response?.status()).toBeLessThan(500);

    await expect(
      page.locator('h1, h2').filter({ hasText: /Brand|B2B|品牌|月結/i }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('direction filter has AR / AP / NET 3 options', async ({ page }) => {
    await page.goto('/admin/accounting/brand-b2b');

    const directionFilter = page.locator(
      'select[name="direction"], select[aria-label*="direction" i], ' +
      '[data-testid="direction-filter"]',
    ).first();
    await expect(directionFilter).toBeVisible({ timeout: 10_000 });

    const options = await directionFilter.locator('option').allTextContents();
    for (const d of ['AR', 'AP', 'NET']) {
      expect(
        options.some(opt => opt.includes(d)),
        `direction filter missing ${d}`,
      ).toBeTruthy();
    }
  });

  test('net_payable_to dual-state UI', async ({ page }) => {
    await page.goto('/admin/accounting/brand-b2b?direction=NET');

    const items = page.locator('[data-direction="NET"]');
    const count = await items.count();
    if (count === 0) {
      test.skip(true, 'no NET direction statements');
      return;
    }

    // 對每 NET item 確認 net_payable_to 標 "brand" or "platform"
    for (let i = 0; i < Math.min(count, 5); i++) {
      const item = items.nth(i);
      const payable = await item.getAttribute('data-payable-to');
      expect(['brand', 'platform']).toContain(payable);

      // UI text 應對應顯示 "platform 應付 brand" 或 "brand 應付 platform"
      const payableText = item.locator('[data-testid="payable-to-label"]');
      await expect(payableText).toBeVisible({ timeout: 3_000 });
    }
  });

  test('amount breakdown for NET direction', async ({ page }) => {
    await page.goto('/admin/accounting/brand-b2b?direction=NET');

    const items = page.locator('[data-direction="NET"]').first();
    if ((await items.count()) === 0) {
      test.skip(true, 'no NET items');
      return;
    }
    // 4 金額欄位：ar_service_fee / ap_commission / warranty_deduction / sla_penalty / net
    for (const field of ['ar-service-fee', 'ap-commission', 'warranty-deduction', 'sla-penalty', 'net-amount']) {
      await expect(
        items.locator(`[data-testid="amount-${field}"], .amount-${field}`),
      ).toBeVisible({ timeout: 3_000 });
    }
  });

  test('service metrics shown', async ({ page }) => {
    await page.goto('/admin/accounting/brand-b2b');

    const items = page.locator('[data-testid="brand-statement-item"]').first();
    if ((await items.count()) === 0) {
      test.skip(true, 'no items');
      return;
    }
    // 服務量指標
    for (const field of ['service-orders', 'warranty-claims', 'sla-breach']) {
      await expect(
        items.locator(`[data-testid="metric-${field}"], .metric-${field}`),
      ).toBeVisible({ timeout: 3_000 });
    }
  });

  test('AR direction net = ar_service_fee', async ({ page }) => {
    await page.goto('/admin/accounting/brand-b2b?direction=AR');

    const items = page.locator('[data-direction="AR"]').first();
    if ((await items.count()) === 0) {
      test.skip(true, 'no AR items');
      return;
    }
    // AR direction net = ar_service_fee (純收)
    const arFee = await items.locator(
      '[data-testid="amount-ar-service-fee"], .amount-ar-service-fee',
    ).textContent();
    const net = await items.locator(
      '[data-testid="amount-net-amount"], .amount-net-amount',
    ).textContent();

    // 純數字比對 (移除幣別 / 千分位)
    const normalize = (s: string | null) => s?.replace(/[^\d.-]/g, '') ?? '';
    expect(normalize(arFee)).toBe(normalize(net));
  });
});

/**
 * Sprint 5 BUILD 啟用本 spec 流程：
 *
 * 1. 建立 web/src/app/admin/accounting/brand-b2b/page.tsx
 * 2. 接 GET brand-b2b-statements?direction=AR|AP|NET endpoint
 * 3. 加 direction tab + 3 direction filter
 * 4. UI: net_payable_to dual-state display
 * 5. 移除 test.describe.skip
 *
 * 對照 backend service:
 *   - api/services/brand_b2b_statement_service.py
 *   - api/routers/brand_b2b_statement_v2.py (8 endpoints)
 *   - api/tests/test_brand_b2b_statement.py (20 tests passing)
 *
 * 注：Brand partner portal 為 Phase III scope，本 sprint skip。
 * 注：Phase II 9 FR e2e starter 完整 — 對應 Sprint 1-5 全覆蓋。
 */
