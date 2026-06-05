/**
 * web/tests/e2e/admin/rma-quality.spec.ts — FR-0048 RMA Quality Feedback smoke
 *
 * 對應 Sprint 4 第 1 page。
 * Backend: 4 endpoints (rma_quality_v2 router; FR-0048 MVP)。
 */

import { test, expect } from '@playwright/test';

test.describe.skip('RMA Quality Findings Smoke (Sprint 4 BUILD pending)', () => {
  test('renders page without 5xx', async ({ page }) => {
    const response = await page.goto('/admin/quality/rma-findings');
    expect(response?.status()).toBeLessThan(500);

    await expect(
      page.locator('h1, h2').filter({ hasText: /RMA|品質|Quality/i }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('brand summary cascade tab', async ({ page }) => {
    await page.goto('/admin/quality/rma-findings');

    const brandTab = page.locator(
      'a:has-text("Brand"), a:has-text("品牌"), [data-testid="brand-summary-tab"]',
    ).first();
    await expect(brandTab).toBeVisible({ timeout: 5_000 });
  });

  test('technician summary cascade tab', async ({ page }) => {
    await page.goto('/admin/quality/rma-findings');

    const techTab = page.locator(
      'a:has-text("Technician"), a:has-text("師傅"), a:has-text("技師"), ' +
      '[data-testid="technician-summary-tab"]',
    ).first();
    await expect(techTab).toBeVisible({ timeout: 5_000 });
  });

  test('log finding form button', async ({ page }) => {
    await page.goto('/admin/quality/rma-findings');

    await expect(
      page.locator(
        'button:has-text("Log"), button:has-text("新增"), ' +
        '[data-testid="log-finding-button"]',
      ).first(),
    ).toBeVisible({ timeout: 5_000 });
  });

  test('failure_mode column displayed in list', async ({ page }) => {
    await page.goto('/admin/quality/rma-findings');

    const items = page.locator('[data-testid="finding-item"]');
    if ((await items.count()) === 0) {
      test.skip(true, 'no findings');
      return;
    }
    await expect(
      items.first().locator(
        '[data-testid="failure-mode"], .failure-mode',
      ),
    ).toBeVisible({ timeout: 3_000 });
  });
});

/**
 * Backend ref: api/services/rma_quality_service.py + 14 tests
 *   - 含 cascade 到 FR-0051 sop_feedback 自動觸發 (ai_diagnosis_accuracy
 *     wrong/partial → sop_feedback source='rma_finding')
 */
