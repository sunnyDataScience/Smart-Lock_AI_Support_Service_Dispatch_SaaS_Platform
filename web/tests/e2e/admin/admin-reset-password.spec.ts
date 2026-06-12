/**
 * admin-reset-password.spec.ts — 管理員代為重設使用者密碼 UI（A4，會議 2026-06-10 Action #7）。
 *
 * 後端契約由 api/tests/test_admin_reset_password.py 覆蓋；本 spec 專注前端 UI 行為：
 * modal 開啟、email 驗證、送出後顯示臨時密碼。攔截 POST 不真改 DB。
 */

import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.fill('input[type="email"]', "admin@example.com");
  await page.fill('input[type="password"]', "changeme123");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"), { timeout: 15_000 });
}

const RESET_PATH = "**/api/v1/auth/admin-reset-password";

test("admin 可開重設密碼 modal、email 驗證、送出顯示臨時密碼", async ({ page }) => {
  let captured: { email?: string } | null = null;
  await page.route(RESET_PATH, async (route) => {
    if (route.request().method() === "POST") {
      captured = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: { email: captured?.email, temp_password: "Tmp_9aZ4kQ2x" },
        }),
      });
    } else {
      await route.fallback();
    }
  });

  await login(page);
  await page.goto("/admin/roles");
  await page.waitForLoadState("domcontentloaded");

  // 開啟 modal
  const trigger = page.getByRole("button", { name: "重設使用者密碼" });
  await expect(trigger).toBeVisible({ timeout: 10_000 });
  await trigger.click();

  const heading = page.getByRole("heading", { name: "重設使用者密碼" });
  await expect(heading).toBeVisible();

  // email 空 → 送出 disabled
  const submit = page.getByRole("button", { name: "重設密碼" });
  await expect(submit).toBeDisabled();

  // 無效 email → 仍 disabled
  await page.fill('input[type="email"]', "not-an-email");
  await expect(submit).toBeDisabled();

  // 有效 email → enabled，送出
  await page.fill('input[type="email"]', "dispatcher@example.com");
  await expect(submit).toBeEnabled();
  await submit.click();

  // 顯示臨時密碼
  await expect(page.getByText("Tmp_9aZ4kQ2x")).toBeVisible({ timeout: 10_000 });
  expect(captured?.email).toBe("dispatcher@example.com");
});
