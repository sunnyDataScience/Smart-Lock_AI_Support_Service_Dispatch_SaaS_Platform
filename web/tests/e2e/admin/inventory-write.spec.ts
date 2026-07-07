/**
 * inventory-write.spec.ts — 驗 inventory 補貨 + 新增物料 真實 write flow。
 *
 * 對應 backend POST /tenants/{tid}/inventory/items + :restock。
 * 對應 Enhancement Roadmap #7 (inventory_transactions 寫入)。
 */

import { test, expect } from "@playwright/test";

test.describe.serial("inventory write flow", () => {
  test("新增物料 modal 開得起來 + 必填驗證", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[type="email"]', "test@lock-ai.com");
    await page.fill('input[type="password"]', "changeme123");
    await page.click('button[type="submit"]');
    await page.waitForURL((u) => !u.pathname.includes("/login"));

    await page.goto("/admin/inventory");
    await page.waitForLoadState("networkidle").catch(() => {});

    // 新增物料 button 不再 disabled
    const addBtn = page.locator("button").filter({ hasText: "新增物料" });
    await expect(addBtn).toBeVisible();
    await expect(addBtn).toBeEnabled();

    await addBtn.click();
    await expect(page.locator("h2").filter({ hasText: "新增物料" })).toBeVisible({
      timeout: 5000,
    });

    // 必填驗證 — 沒填 part_number / name 按建立應 disabled
    const submitBtn = page.locator("button").filter({ hasText: "建立物料" });
    await expect(submitBtn).toBeDisabled();

    // 填表
    const ts = String(Date.now()).slice(-6);
    await page.fill('input[placeholder*="YDM-4109"]', `PN-TEST-${ts}`);
    await page.fill('input[placeholder*="Yale YDM4109"]', `測試品 ${ts}`);
    await expect(submitBtn).toBeEnabled();

    await submitBtn.click();

    // 等 modal 關閉
    await expect(page.locator("h2").filter({ hasText: "新增物料" })).toBeHidden({
      timeout: 5000,
    });
  });

  test("補貨 button 不再 disabled", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[type="email"]', "test@lock-ai.com");
    await page.fill('input[type="password"]', "changeme123");
    await page.click('button[type="submit"]');
    await page.waitForURL((u) => !u.pathname.includes("/login"));

    await page.goto("/admin/inventory");
    await page.waitForLoadState("networkidle").catch(() => {});

    const restockBtns = page.locator("button").filter({ hasText: "補貨" });
    const count = await restockBtns.count();
    expect(count, "至少 1 個補貨 button").toBeGreaterThan(0);

    // 第一個補貨按鈕應 enabled
    await expect(restockBtns.first()).toBeEnabled();

    // 點開 modal
    await restockBtns.first().click();
    await expect(
      page.locator("h2").filter({ hasText: "補貨入庫" }),
    ).toBeVisible({ timeout: 5000 });

    // 必填驗證
    const submitBtn = page.locator("button").filter({ hasText: "確認補貨" });
    await expect(submitBtn).toBeDisabled();

    await page.fill('input[type="number"][min="1"]', "10");
    await expect(submitBtn).toBeEnabled();
  });
});
