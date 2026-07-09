/**
 * work-orders-filter.spec.ts — /work-orders status/brand/period 3 filter 啟用驗證
 */
import { test, expect } from "@playwright/test";

test("/work-orders 3 filter select 不再 disabled", async ({ page }) => {
  await page.goto("/login");
  await page.fill('input[type="email"]', "test@lock-ai.com");
  await page.fill('input[type="password"]', "changeme123");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"));

  await page.goto("/work-orders");
  await page.waitForLoadState("networkidle").catch(() => {});

  // 至少 3 個 enabled <select>
  const selects = page.locator("select");
  const count = await selects.count();
  expect(count, "expect 3 selects").toBeGreaterThanOrEqual(3);

  for (let i = 0; i < Math.min(3, count); i++) {
    await expect(selects.nth(i)).toBeEnabled();
  }

  // 改 status filter 觸發 refetch
  await selects.first().selectOption("completed");
  await page.waitForLoadState("networkidle").catch(() => {});

  // page 仍渲染 (heading 在)
  await expect(page.locator("h1").filter({ hasText: /工單|Work/ })).toBeVisible();
});
