/**
 * web/tests/e2e/admin/gdpr-and-config.spec.ts
 *
 * 跑真實 server（不 mock、不啟新 server）：
 *   cd web && USE_EXISTING_SERVER=1 BASE_URL=http://localhost:3000 \
 *     npx playwright test gdpr-and-config.spec.ts --project=admin --reporter=list
 *
 * 涵蓋兩條 user flow：
 *   Flow A — FR-0053 GDPR 被遺忘權佇列（/admin/gdpr-forget-queue）
 *     精讀 web/src/app/admin/gdpr-forget-queue/page.tsx：
 *       - 列表 / empty state 渲染（無資料時顯示「無申請」）
 *       - 6 個狀態 tab（全部 / 已收件 / 法務扣留 / 軟刪除 / 硬刪除 / 已取消）切換
 *       - 重新整理（fetch）不 crash
 *       - 本頁無列動作按鈕（純唯讀佇列），故只驗 tab / render
 *
 *   Flow B — M18 系統設定（/settings 預設 tab = system → SystemConfigForm）
 *     精讀 web/src/components/settings/SystemConfigForm.tsx + page.tsx，端點 /api/v1/config：
 *       - config 載入 → 改一個 benign 數值欄位（最大對話輪次）→ 儲存
 *       - 驗證儲存成功指示（subtitle 變為「已儲存：HH:MM:SS」）
 *       - 測完把值改回原值再次儲存還原，避免污染 demo config
 *       - reload 驗證持久化
 *
 * 預設 locale = zh-TW（src/i18n/config.ts DEFAULT_LOCALE），故文案斷言用繁中。
 */

import { test, expect, Page } from "@playwright/test";

// --- admin 登入（真實表單流程，對齊任務說明）---------------------------------
async function loginAsAdmin(page: Page) {
  await page.goto("/login");
  await page.fill('input[type="email"]', "admin@example.com");
  await page.fill('input[type="password"]', "changeme123");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"), {
    timeout: 15_000,
  });
}

// ===========================================================================
// Flow A — GDPR 被遺忘權佇列（FR-0053）
// ===========================================================================
test.describe("Flow A — GDPR 被遺忘權佇列 (FR-0053)", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  test("佇列頁渲染 + empty state 乾淨處理 + 不 crash", async ({ page }) => {
    await page.goto("/admin/gdpr-forget-queue");

    // header 標題渲染（h1 "GDPR 被遺忘權佇列"）
    await expect(
      page.getByRole("heading", { name: "GDPR 被遺忘權佇列" }),
    ).toBeVisible({ timeout: 15_000 });

    // 表格表頭一定在（即使 0 筆資料）
    await expect(
      page.getByRole("columnheader", { name: "收件時間" }),
    ).toBeVisible();
    await expect(
      page.getByRole("columnheader", { name: "狀態" }),
    ).toBeVisible();

    // 列表區：有資料→至少一列 data row；無資料→empty state「無申請」。
    // 兩者擇一成立即可（不硬湊資料）。
    const emptyState = page.getByText("無申請", { exact: true });
    const dataRows = page.locator("tbody tr");
    const rowCount = await dataRows.count();

    if (rowCount === 1 && (await emptyState.isVisible().catch(() => false))) {
      // 乾淨的 empty state
      await expect(emptyState).toBeVisible();
    } else {
      // 有資料：至少一列存在，頁面未 crash
      expect(rowCount).toBeGreaterThanOrEqual(1);
    }
  });

  test("6 個狀態 tab 切換（含 法務扣留 legal_hold_denied）皆不 crash", async ({
    page,
  }) => {
    await page.goto("/admin/gdpr-forget-queue");
    await expect(
      page.getByRole("heading", { name: "GDPR 被遺忘權佇列" }),
    ).toBeVisible({ timeout: 15_000 });

    const tabLabels = [
      "全部",
      "已收件",
      "法務扣留", // legal_hold_denied
      "軟刪除",
      "硬刪除",
      "已取消",
    ];

    for (const label of tabLabels) {
      const tab = page.getByRole("button", { name: label, exact: true });
      await expect(tab, `tab「${label}」應存在`).toBeVisible();
      await tab.click();

      // 切換後（會觸發 useEffect → fetch）標題仍在、表頭仍在 = 未 crash
      await expect(
        page.getByRole("heading", { name: "GDPR 被遺忘權佇列" }),
      ).toBeVisible();
      await expect(
        page.getByRole("columnheader", { name: "狀態" }),
      ).toBeVisible();

      // tab 進入 active 樣式（bg-blue-600 text-white）—驗證點選有反應
      await expect(tab).toHaveClass(/bg-blue-600/);
    }
  });

  test("重新整理按鈕可點且不 crash", async ({ page }) => {
    await page.goto("/admin/gdpr-forget-queue");
    await expect(
      page.getByRole("heading", { name: "GDPR 被遺忘權佇列" }),
    ).toBeVisible({ timeout: 15_000 });

    const refreshBtn = page.getByRole("button", { name: "重新整理" });
    await expect(refreshBtn).toBeVisible();
    await refreshBtn.click();

    // refresh 後頁面結構仍完整
    await expect(
      page.getByRole("columnheader", { name: "收件時間" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "GDPR 被遺忘權佇列" }),
    ).toBeVisible();
  });
});

// ===========================================================================
// Flow B — M18 系統設定（FR-0043，端點 /api/v1/config）
// ===========================================================================
test.describe("Flow B — M18 系統設定 (FR-0043)", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
  });

  test("/settings 預設 system tab → 載入 config → 改 benign 欄位 → 儲存成功 → 還原", async ({
    page,
  }) => {
    await page.goto("/settings");

    // 預設 tab = system → SystemConfigForm 標題「系統設定」
    await expect(
      page.getByText("系統設定", { exact: true }).first(),
    ).toBeVisible({ timeout: 15_000 });

    // benign 欄位：line_bot「最大對話輪次」(NumberField, type=number)
    const maxTurnsInput = page
      .locator("label", { hasText: "最大對話輪次" })
      .locator('input[type="number"]');
    await expect(maxTurnsInput).toBeVisible({ timeout: 15_000 });

    // 等 config 從 /api/v1/config 載入（input 拿到具體值，非空）
    await expect
      .poll(async () => (await maxTurnsInput.inputValue()).trim(), {
        timeout: 15_000,
        message: "config 應從 /api/v1/config 載入並填入 input",
      })
      .not.toBe("");

    const originalValue = (await maxTurnsInput.inputValue()).trim();
    const originalNum = Number(originalValue);
    expect(Number.isFinite(originalNum)).toBeTruthy();

    // benign 變更：在合法範圍 (min=1 max=200) 內 +1，避免邊界踩雷
    const newNum = originalNum >= 200 ? originalNum - 1 : originalNum + 1;

    // --- 改值 → 儲存 -------------------------------------------------------
    await maxTurnsInput.fill(String(newNum));

    const saveBtn = page.getByRole("button", { name: "儲存設定" });
    // dirty 後儲存鈕應 enabled
    await expect(saveBtn).toBeEnabled();
    await saveBtn.click();

    // 儲存成功指示：subtitle 變成「已儲存：HH:MM:SS」（savedAt 設值後渲染）
    await expect(page.getByText(/已儲存：/)).toBeVisible({ timeout: 15_000 });

    // 儲存後回傳 merged config → input 應為新值，dirty 消除 → 儲存鈕 disabled
    await expect(maxTurnsInput).toHaveValue(String(newNum));
    await expect(saveBtn).toBeDisabled();

    // --- 還原：改回原值再次儲存（避免污染 demo config）---------------------
    await maxTurnsInput.fill(String(originalNum));
    await expect(saveBtn).toBeEnabled();
    await saveBtn.click();
    await expect(page.getByText(/已儲存：/)).toBeVisible({ timeout: 15_000 });
    await expect(maxTurnsInput).toHaveValue(String(originalNum));
    await expect(saveBtn).toBeDisabled();

    // --- 持久化驗證（選做）：reload 後仍是還原後的原值 ----------------------
    await page.reload();
    const reloadedInput = page
      .locator("label", { hasText: "最大對話輪次" })
      .locator('input[type="number"]');
    await expect(reloadedInput).toBeVisible({ timeout: 15_000 });
    await expect
      .poll(async () => (await reloadedInput.inputValue()).trim(), {
        timeout: 15_000,
      })
      .toBe(originalValue);
  });
});
