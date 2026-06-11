/**
 * web/tests/e2e/admin/dispute-cosign.spec.ts —
 * FR-0013「爭議 dual-sign 仲裁結案」user flow E2E
 *
 * 對應頁面：
 *   - web/src/app/admin/disputes/page.tsx（清單 + 狀態 tab + 類型 filter + 結案表單）
 *   - web/src/components/admin/DisputesTable.tsx（列表渲染）
 *
 * 後端端點：POST /tenants/{tenant}/disputes/{id}:co-sign（dual-sign 第二步）
 *
 * dual-sign 模型（讀 page.tsx 確認）：
 *   - filed     → step-1 CSM review（POST :review）
 *   - in_review / mediation → step-2 Ops Manager co-sign（POST :co-sign）→ resolved
 *   只有 status 屬於 canCoSign（in_review / mediation）的爭議才能 co-sign 結案。
 *   co-sign 需填「最終決議 ≥ 5 字」。
 *
 * 測試矩陣：
 *   1. /admin/disputes 渲染、狀態 tab 切換（全部/待處理/調解中/已結案/已駁回）
 *      + 類型 filter（價格…）切換不 crash。
 *   2. 找一筆可 co-sign 的爭議（切到「調解中」tab，status=in_review/mediation）
 *      → 填最終決議 → 點「Co-Sign 結案」→ 驗證成功 toast「已 co-sign 結案」
 *        且該爭議狀態變 resolved。
 *
 * 韌性設計：
 *   - co-sign 會真的改 DB，整個 spec 只 co-sign 一筆。
 *   - 若 DB 內查無 in_review/mediation 爭議（前置條件未滿足），
 *     step-2 用 test.skip 跳過並回報，不做無意義斷言、不啟 server、不改產品碼。
 *   - selector 全以 page.tsx / DisputesTable.tsx 實際 DOM 為準。
 */

import { test, expect, Page } from "@playwright/test";

const DISPUTES_URL = "/admin/disputes";

// i18n 可見文字（src/i18n/messages/zh-TW.json）
const TAB_LABELS = ["全部", "待處理", "調解中", "已結案", "已駁回"] as const;
const TYPE_LABEL_PRICING = "價格";

/** admin 登入 — 依任務提供之 pattern */
async function loginAsAdmin(page: Page): Promise<void> {
  await page.goto("/login");
  await page.fill('input[type="email"]', "admin@example.com");
  await page.fill('input[type="password"]', "changeme123");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"), {
    timeout: 15_000,
  });
}

/** 等清單載入完成（loading spinner 結束 → 連線狀態徽章顯示） */
async function waitDisputesLoaded(page: Page): Promise<void> {
  // 標題確保進到正確頁面
  await expect(
    page.getByRole("heading", { name: "爭議案件處理" }),
  ).toBeVisible({ timeout: 15_000 });
  // 表格 header「爭議編號」永遠 render（不論有無資料）
  await expect(page.getByText("爭議編號").first()).toBeVisible({
    timeout: 15_000,
  });
}

test.describe("FR-0013 爭議 dual-sign 仲裁結案", () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto(DISPUTES_URL);
    await waitDisputesLoaded(page);
  });

  test("清單渲染 + 狀態 tab 切換 + 類型 filter 不 crash", async ({ page }) => {
    // 斷言 1：頁面標題與表格 header 渲染（waitDisputesLoaded 已驗）
    await expect(
      page.getByRole("heading", { name: "爭議案件處理" }),
    ).toBeVisible();

    // 斷言 2：五個狀態 tab 都在
    for (const label of TAB_LABELS) {
      await expect(
        page.getByRole("button", { name: label, exact: true }),
      ).toBeVisible();
    }

    // 斷言 3：逐一點每個狀態 tab → 不 crash、tab 變 active、表格 header 仍在
    for (const label of TAB_LABELS) {
      await page.getByRole("button", { name: label, exact: true }).click();
      // 切換後等清單重新 fetch 安定：error banner 不應出現
      await expect(page.getByText("爭議編號").first()).toBeVisible();
      await expect(
        page.locator("text=/error|Error|undefined/i"),
      ).toHaveCount(0);
    }

    // 斷言 4：類型 filter（價格）toggle on / off 不 crash
    const pricingFilter = page.getByRole("button", {
      name: TYPE_LABEL_PRICING,
      exact: true,
    });
    await pricingFilter.click(); // 套用
    await expect(page.getByText("爭議編號").first()).toBeVisible();
    // 套用後出現「清除類型」按鈕
    await expect(
      page.getByRole("button", { name: "清除類型" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "清除類型" }).click(); // 清除
    await expect(page.getByText("爭議編號").first()).toBeVisible();
  });

  test("co-sign 結案：in_review/mediation → resolved + 成功 toast", async ({
    page,
  }) => {
    // 切到「調解中」tab（status=in_review）→ 這些才能 co-sign 結案
    await page.getByRole("button", { name: "調解中", exact: true }).click();
    await expect(page.getByText("爭議編號").first()).toBeVisible();

    // 等列表 fetch 安定後判斷有無可 co-sign 的爭議
    await page.waitForTimeout(800);

    // 列表每筆是一個 <button>（DisputesTable）；表頭非 button row。
    // 找出第一筆爭議列（id 為 8 碼 mono span）。
    const firstRow = page
      .locator("button")
      .filter({ has: page.locator("span.font-mono") })
      .first();

    const hasCoSignable = await firstRow.count();
    test.skip(
      hasCoSignable === 0,
      "DB 無 in_review/mediation 爭議，無法測 co-sign（前置：需 CSM 先 review 進 in_review）",
    );

    // 選取第一筆 → 下方出現結案表單
    await firstRow.click();

    // 結案表單標頭出現 step-2 徽章才是 canCoSign 狀態
    const coSignBadge = page.getByText("step-2 Ops Manager co-sign");
    await expect(coSignBadge).toBeVisible({ timeout: 10_000 });

    // 填最終決議（page.tsx 要求 ≥ 5 字）
    const noteField = page.getByPlaceholder("說明最終處理方案...");
    await expect(noteField).toBeEnabled();
    await noteField.fill("E2E 仲裁測試：雙方協議結案，平台補償客戶");

    // 點「Co-Sign 結案」
    const coSignBtn = page.getByRole("button", { name: "Co-Sign 結案" });
    await expect(coSignBtn).toBeEnabled();
    await coSignBtn.click();

    // 斷言：成功 toast「已 co-sign 結案」（Radix ToastPrimitive.Title 渲染標題文字）
    await expect(
      page.getByText("已 co-sign 結案"),
    ).toBeVisible({ timeout: 15_000 });

    // 斷言：co-sign 後 page 會 refetch 同 tab（調解中）→ 該筆離開此清單
    // 切到「已結案」tab 應能看到至少一筆 resolved（剛結案的或既有的）
    await page.getByRole("button", { name: "已結案", exact: true }).click();
    await expect(page.getByText("爭議編號").first()).toBeVisible();
    // resolved 狀態徽章文字為「已結案」（components.admin.disputes.status.resolved）
    // 列表中至少出現一個 resolved 徽章
    const resolvedBadge = page
      .locator("button")
      .filter({ has: page.locator("span.font-mono") })
      .locator("span", { hasText: "已結案" })
      .first();
    await expect(resolvedBadge).toBeVisible({ timeout: 10_000 });
  });
});
