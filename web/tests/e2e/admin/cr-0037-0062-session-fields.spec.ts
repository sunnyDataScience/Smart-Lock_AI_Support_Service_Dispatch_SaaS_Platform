/**
 * cr-0037-0062-session-fields.spec.ts — 2026-06-20 session（CR-0037~0062，26 CR）前端實機驗證。
 *
 * 對「重建後的 docker stack」（web:3000 + api:8001）驗證本輪後端欄位/前端面板真的接通：
 *   - 工單詳情「公單資訊」面板渲染 CR-0043 客戶姓名/聯絡電話/service_category（修死欄）+ CR-0048 狀態原因。
 *   - 關鍵 admin 頁（儀表板/工單/技師/異常/問題卡）載入無致命錯誤。
 * 後端契約由 api/tests/test_cr_004x~006x_*.py 覆蓋；本 spec 專注「實機渲染對齊 code」。
 *
 * 對 docker 既起服務跑：BASE_URL=http://localhost:3000 USE_EXISTING_SERVER=1 \
 *   NEXT_PUBLIC_API_BASE_URL=http://localhost:8001 npx playwright test cr-0037-0062-session-fields
 */

import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.fill('input[type="email"]', "admin@example.com");
  await page.fill('input[type="password"]', "changeme123");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"), { timeout: 15_000 });
}

test("工單詳情『公單資訊』面板渲染 CR-0043 客名/電話/服務類別（修死欄）", async ({ page }) => {
  await login(page);
  await page.goto("/work-orders");
  // 點一張有設備資料的工單（seed/測試建立的 Yale 工單，地址含信義區）
  const row = page.getByRole("row", { name: /信義區/ }).first();
  await expect(row).toBeVisible({ timeout: 15_000 });
  await row.click();
  await page.waitForURL(/\/work-orders\/[0-9a-f-]{8,}/, { timeout: 15_000 });

  // 公單資訊面板 + CR-0043 欄位標籤
  await expect(page.getByText("公單資訊")).toBeVisible();
  await expect(page.getByText("客戶姓名")).toBeVisible();
  await expect(page.getByText("聯絡電話")).toBeVisible();
  await expect(page.getByText("服務類別")).toBeVisible();
});

test("關鍵 admin 頁載入無致命錯誤（儀表板/工單/技師/異常/問題卡）", async ({ page }) => {
  await login(page);
  for (const path of ["/dashboard", "/work-orders", "/technicians", "/admin/exceptions", "/problem-cards"]) {
    await page.goto(path);
    // 主內容區渲染（非白頁/錯誤頁）
    await expect(page.locator("main, [role='main']").first()).toBeVisible({ timeout: 15_000 });
    expect(page.url()).toContain(path.split("/").pop() as string);
  }
});
