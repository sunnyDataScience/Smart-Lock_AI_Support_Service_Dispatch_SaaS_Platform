/**
 * web/tests/e2e/admin/ai-governance.spec.ts — FR-0050 AI Governance Trace smoke
 *
 * 對應 Sprint 3 第 3 page。
 * Backend: 3 endpoints (ai_governance_trace_v2 router; FR-0050 MVP)。
 */

import { test, expect } from '@playwright/test';

test.describe.skip('AI Governance Smoke (Sprint 3 BUILD pending)', () => {
  test('renders page without 5xx', async ({ page }) => {
    const response = await page.goto('/admin/observability/ai-governance');
    expect(response?.status()).toBeLessThan(500);

    await expect(
      page.locator('h1, h2').filter({ hasText: /AI|Governance|治理/i }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('decision_type filter has 5 + all', async ({ page }) => {
    await page.goto('/admin/observability/ai-governance');

    const filter = page.locator(
      'select[name="decision_type"], [data-testid="decision-type-filter"]',
    ).first();
    await expect(filter).toBeVisible({ timeout: 10_000 });

    const options = await filter.locator('option').allTextContents();
    for (const t of ['reasoning', 'tool_call', 'output', 'guardrail_block', 'human_handoff']) {
      expect(
        options.some(opt => opt.toLowerCase().includes(t)),
        `decision_type missing ${t}`,
      ).toBeTruthy();
    }
  });

  test('summary widget: by_decision_type + by_guardrail_action', async ({ page }) => {
    await page.goto('/admin/observability/ai-governance');

    for (const widget of ['decision-type-chart', 'guardrail-action-chart', 'agent-version-chart']) {
      await expect(
        page.locator(`[data-testid="${widget}"], .chart-${widget}`),
      ).toBeVisible({ timeout: 5_000 });
    }
  });

  test('block_rate_pct prominently displayed', async ({ page }) => {
    await page.goto('/admin/observability/ai-governance');

    await expect(
      page.locator(
        '[data-testid="block-rate-pct"], .block-rate, [data-metric="block_rate_pct"]',
      ),
    ).toBeVisible({ timeout: 5_000 });
  });
});

/**
 * Backend ref: api/services/ai_governance_trace_service.py + 11 tests
 *   block_rate_pct 為 governance dashboard 關鍵 KPI
 */
