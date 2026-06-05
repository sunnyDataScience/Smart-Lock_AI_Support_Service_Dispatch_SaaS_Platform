/**
 * web/tests/e2e/admin/sop-feedback.spec.ts — FR-0051 SOP Feedback Spiral smoke
 *
 * 對應 Sprint 3 第 4 page。
 * Backend: 3 endpoints (sop_feedback_v2 router; FR-0051 MVP)。
 */

import { test, expect } from '@playwright/test';

test.describe.skip('SOP Feedback Smoke (Sprint 3 BUILD pending)', () => {
  test('renders page without 5xx', async ({ page }) => {
    const response = await page.goto('/admin/knowledge-base/sop-feedback');
    expect(response?.status()).toBeLessThan(500);

    await expect(
      page.locator('h1, h2').filter({ hasText: /SOP|Feedback|回饋/i }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('source filter has 5 options', async ({ page }) => {
    await page.goto('/admin/knowledge-base/sop-feedback');

    const filter = page.locator(
      'select[name="source"], [data-testid="source-filter"]',
    ).first();
    await expect(filter).toBeVisible({ timeout: 10_000 });

    const options = await filter.locator('option').allTextContents();
    const expected = [
      'customer_thumbs', 'technician_onsite', 'rma_finding',
      'ai_eval', 'csm_manual',
    ];
    for (const s of expected) {
      expect(
        options.some(opt => opt.toLowerCase().includes(s)),
        `source missing ${s}`,
      ).toBeTruthy();
    }
  });

  test('sentiment_score gauge prominently displayed', async ({ page }) => {
    await page.goto('/admin/knowledge-base/sop-feedback');

    // sentiment_score = (positive - negative) / total × 100 (-100..+100)
    await expect(
      page.locator(
        '[data-testid="sentiment-score-gauge"], .sentiment-score, ' +
        '[data-metric="sentiment_score"]',
      ),
    ).toBeVisible({ timeout: 5_000 });
  });

  test('summary: by_source + by_sentiment charts', async ({ page }) => {
    await page.goto('/admin/knowledge-base/sop-feedback');

    for (const chart of ['source-chart', 'sentiment-chart']) {
      await expect(
        page.locator(`[data-testid="${chart}"], .chart-${chart}`),
      ).toBeVisible({ timeout: 5_000 });
    }
  });
});

/**
 * Backend ref: api/services/sop_feedback_service.py + 12 tests
 *   - 含 cascade from FR-0048 RMA Quality (source='rma_finding')
 *   - sentiment_score 為 NPS-style -100..+100
 */
