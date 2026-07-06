/**
 * wo-document-number.spec.ts — 工單列表顯示公單號 {2碼地區}-{6碼流水}（CR-0020）。
 *
 * 驗證列表第一欄顯示地區公單號（如 TP-000001），而非內部 UUID slice。
 */

import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.fill('input[type="email"]', "test@lock-ai.com");
  await page.fill('input[type="password"]', "changeme123");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"), { timeout: 15_000 });
}

test("工單列表顯示地區公單號（XX-NNNNNN），不顯示內部 UUID", async ({ page }) => {
  await login(page);
  await page.goto("/work-orders");
  await page.waitForLoadState("networkidle").catch(() => {});

  // 列表至少出現一個 {2碼大寫}-{6碼} 公單號
  await expect(page.getByText(/^[A-Z]{2}-\d{6}$/).first()).toBeVisible({
    timeout: 15_000,
  });

  // 列表第一欄不應有 title 掛內部 UUID（A6 同類洩漏，已移除）
  await expect(
    page.locator('[role="cell"] span[title]').filter({ hasText: /^[0-9a-f]{8}$/ }),
  ).toHaveCount(0);
});
