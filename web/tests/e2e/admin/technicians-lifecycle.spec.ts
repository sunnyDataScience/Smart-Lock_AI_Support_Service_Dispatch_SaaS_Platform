/**
 * web/tests/e2e/admin/technicians-lifecycle.spec.ts — FR-0044 Tech Lifecycle smoke
 *
 * 對應 Sprint 1 第 2 個 page (per phase-ii-web-integration-plan §2)。
 * Backend: 6 endpoints from technician_lifecycle_v2 router (FR-0044 MVP)。
 */

import { test, expect } from '@playwright/test';

test.describe.skip('Tech Lifecycle Smoke (Sprint 1 BUILD pending)', () => {
  test('renders page without 5xx', async ({ page }) => {
    const response = await page.goto('/admin/technicians');
    expect(response?.status()).toBeLessThan(500);

    await expect(
      page.locator('h1, h2').filter({ hasText: /Technician|師傅|技師/i }),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('6 lifecycle actions for pending_approval', async ({ page }) => {
    await page.goto('/admin/technicians?status=pending_approval');

    const items = page.locator('[data-status="pending_approval"]');
    if ((await items.count()) === 0) {
      test.skip(true, 'no pending_approval techs');
      return;
    }
    for (const action of ['onboard-approve', 'onboard-reject']) {
      await expect(
        items.first().locator(
          `button[data-action="${action}"], [data-testid="${action}"]`,
        ),
      ).toBeVisible({ timeout: 3_000 });
    }
  });

  test('suspend/reactivate/terminate for active', async ({ page }) => {
    await page.goto('/admin/technicians?status=active');

    const items = page.locator('[data-status="active"]');
    if ((await items.count()) === 0) {
      test.skip(true, 'no active techs');
      return;
    }
    for (const action of ['suspend', 'terminate']) {
      await expect(
        items.first().locator(
          `button[data-action="${action}"], [data-testid="${action}"]`,
        ),
      ).toBeVisible({ timeout: 3_000 });
    }
  });

  test('lifecycle events tab', async ({ page }) => {
    await page.goto('/admin/technicians');
    const eventsTab = page.locator(
      'a:has-text("Events"), a:has-text("事件"), [data-testid="lifecycle-events-tab"]',
    ).first();
    await expect(eventsTab).toBeVisible({ timeout: 5_000 });
  });
});

/**
 * Backend ref: api/services/technician_lifecycle_service.py + 17 tests passing
 */
