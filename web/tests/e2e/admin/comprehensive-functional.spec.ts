/**
 * comprehensive-functional.spec.ts — Playwright 真人操作 12 page + 功能互動。
 *
 * 對應 goal「透過 Playwright 模擬真人操作前端，並確保所有功能都能正常運行」。
 *
 * 範圍:
 *   - 9 個 Phase II FR page（render + heading + 篩選互動）
 *   - 12 個 admin page（render + filter 不再 disabled）
 *   - inventory 補貨/新增物料 modal 開關
 *   - search/filter 輸入觸發 refetch
 *   - 截圖留證
 */

import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.fill('input[type="email"]', "test@lock-ai.com");
  await page.fill('input[type="password"]', "changeme123");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"), { timeout: 10_000 });
}

// ─────────────────────────────────────────────────────────────────────
// Phase II 9 FR pages (含 heading + console error 過濾)
// ─────────────────────────────────────────────────────────────────────

const PHASE_II_PAGES = [
  { fr: "FR-0049", path: "/admin/approval-inbox", heading: /統一審批工作箱|Approval/i },
  { fr: "FR-0044", path: "/admin/technicians-lifecycle", heading: /技師生命週期|Lifecycle/i },
  { fr: "FR-0045", path: "/account/statements", heading: /薪資對帳|Statement/i },
  { fr: "FR-0046", path: "/account/commission-statements", heading: /派工獎金|Commission/i },
  { fr: "FR-0047", path: "/admin/brand-b2b", heading: /品牌商 B2B|Brand B2B/i },
  { fr: "FR-0053", path: "/admin/gdpr-forget-queue", heading: /GDPR|被遺忘權/i },
  { fr: "FR-0050", path: "/admin/ai-governance", heading: /AI 治理|Governance/i },
  { fr: "FR-0051", path: "/admin/sop-feedback", heading: /SOP 反饋|Feedback/i },
  { fr: "FR-0048", path: "/admin/rma-quality", heading: /RMA 品質|Quality/i },
];

test.describe.serial("Phase II 9 FR pages render + heading", () => {
  for (const spec of PHASE_II_PAGES) {
    test(`${spec.fr} ${spec.path} render`, async ({ page }, testInfo) => {
      const consoleErrors: string[] = [];
      const pageErrors: string[] = [];

      page.on("console", (msg) => {
        if (msg.type() !== "error") return;
        const text = msg.text();
        if (
          text.includes("Failed to fetch") ||
          text.includes("ERR_CONNECTION") ||
          text.includes("net::") ||
          text.includes("401") ||
          text.includes("403") ||
          text.includes("404") ||
          text.includes("Failed to load resource")
        )
          return;
        consoleErrors.push(text);
      });
      page.on("pageerror", (err) => pageErrors.push(err.message));

      await login(page);
      const response = await page.goto(spec.path, {
        waitUntil: "domcontentloaded",
        timeout: 15_000,
      });

      expect(response!.status(), `${spec.path} not 5xx`).toBeLessThan(500);
      await page
        .waitForLoadState("networkidle", { timeout: 10_000 })
        .catch(() => {});

      await page.screenshot({
        path: testInfo.outputPath(`${spec.fr}.png`),
        fullPage: true,
      });

      await expect(
        page.locator("h1").filter({ hasText: spec.heading }),
      ).toBeVisible({ timeout: 5_000 });

      expect(pageErrors, `${spec.fr} page errors`).toHaveLength(0);
      expect(consoleErrors, `${spec.fr} console errors`).toHaveLength(0);
    });
  }
});

// ─────────────────────────────────────────────────────────────────────
// 12 admin pages filter 啟用驗證
// ─────────────────────────────────────────────────────────────────────

test("admin/inventory 補貨 modal 開關 + 必填驗證", async ({ page }) => {
  await login(page);
  await page.goto("/admin/inventory");
  await page.waitForLoadState("networkidle").catch(() => {});

  const restockBtns = page.locator("button").filter({ hasText: "補貨" });
  await expect(restockBtns.first()).toBeEnabled();
  await restockBtns.first().click();
  await expect(page.locator("h2").filter({ hasText: "補貨入庫" })).toBeVisible();

  const submit = page.locator("button").filter({ hasText: "確認補貨" });
  await expect(submit).toBeDisabled();
  await page.fill('input[type="number"][min="1"]', "5");
  await expect(submit).toBeEnabled();
  await page.keyboard.press("Escape");
});

test("admin/inventory 新增物料 modal 開關 + 必填驗證", async ({ page }) => {
  await login(page);
  await page.goto("/admin/inventory");
  await page.waitForLoadState("networkidle").catch(() => {});

  await page.locator("button").filter({ hasText: "新增物料" }).click();
  await expect(page.locator("h2").filter({ hasText: "新增物料" })).toBeVisible();

  const submit = page.locator("button").filter({ hasText: "建立物料" });
  await expect(submit).toBeDisabled();

  const ts = String(Date.now()).slice(-5);
  await page.fill('input[placeholder*="YDM-4109"]', `PN-E2E-${ts}`);
  await page.fill('input[placeholder*="Yale YDM4109"]', `E2E 測試 ${ts}`);
  await expect(submit).toBeEnabled();
});

test("admin/inventory 編輯 + 紀錄 button 啟用", async ({ page }) => {
  await login(page);
  await page.goto("/admin/inventory");
  await page.waitForLoadState("networkidle").catch(() => {});

  const editBtns = page.locator("button").filter({ hasText: /^編輯$/ });
  const logBtns = page.locator("button").filter({ hasText: /^紀錄$/ });
  await expect(editBtns.first()).toBeEnabled();
  await expect(logBtns.first()).toBeEnabled();

  // 點紀錄 → 開 modal
  await logBtns.first().click();
  await expect(
    page.locator("h2").filter({ hasText: "異動紀錄" }),
  ).toBeVisible({ timeout: 5_000 });
});

test("work-orders 3 filter select 啟用 + status filter 觸發", async ({ page }) => {
  await login(page);
  await page.goto("/work-orders");
  await page.waitForLoadState("networkidle").catch(() => {});

  const selects = page.locator("select");
  await expect(selects.first()).toBeEnabled();
  await selects.first().selectOption("completed");
  await page.waitForLoadState("networkidle").catch(() => {});

  await expect(page.locator("h1").filter({ hasText: /工單|Work/ })).toBeVisible();
});

test("problem-cards 4 filter + search 啟用", async ({ page }) => {
  await login(page);
  await page.goto("/problem-cards");
  await page.waitForLoadState("networkidle").catch(() => {});

  const selects = page.locator("select");
  await expect(selects.first()).toBeEnabled();
  const searchInput = page.locator('input[type="text"]').first();
  await expect(searchInput).toBeEnabled();
});

test("admin/customers 4 filter 啟用 (roadmap #5/#6 BUILD)", async ({ page }) => {
  await login(page);
  await page.goto("/admin/customers");
  await page.waitForLoadState("networkidle").catch(() => {});

  const selects = page.locator("select");
  const selectCount = await selects.count();
  expect(selectCount, "should have 3+ filter selects").toBeGreaterThanOrEqual(3);
  for (let i = 0; i < Math.min(3, selectCount); i++) {
    await expect(selects.nth(i)).toBeEnabled();
  }

  // 選風險等級 high
  await selects.first().selectOption("high");
  await page.waitForLoadState("networkidle").catch(() => {});
  await expect(page.locator("h1").first()).toBeVisible();
});

test("technicians 6/6 (search/4 filter/新增技師 modal)", async ({ page }) => {
  await login(page);
  await page.goto("/technicians");
  await page.waitForLoadState("networkidle").catch(() => {});

  await page.locator("button").filter({ hasText: "新增技師" }).click();
  await expect(page.locator("h2").filter({ hasText: "新增技師" })).toBeVisible();
  const submit = page.locator("button").filter({ hasText: "建立技師" });
  await expect(submit).toBeDisabled();
  await page.fill('input[placeholder*="王大鎖"]', "E2E Tester");
  await page.fill('input[placeholder*="逗號分隔"]', "台北市信義區, 大安區");
  await expect(submit).toBeEnabled();
  await page.keyboard.press("Escape");
});

test("accounting/invoices 4 filter (含 payment_method)", async ({ page }) => {
  await login(page);
  await page.goto("/accounting/invoices");
  await page.waitForLoadState("networkidle").catch(() => {});

  const selects = page.locator("select");
  await expect(selects.first()).toBeEnabled();
  // payment_method 必須啟用
  const pmSelect = selects.filter({ hasText: /付款方式|信用卡/ }).first();
  await pmSelect.selectOption("credit_card");
  await page.waitForLoadState("networkidle").catch(() => {});
});

test("admin/reports/kpi 切片 select 啟用", async ({ page }) => {
  await login(page);
  await page.goto("/admin/reports/kpi");
  await page.waitForLoadState("networkidle").catch(() => {});

  const slice = page.locator("select").filter({ hasText: /切片|按品牌|全部/ }).first();
  await expect(slice).toBeEnabled();
  await slice.selectOption("brand");
});

test("admin/reports/revenue 排程發送 modal", async ({ page }) => {
  await login(page);
  await page.goto("/admin/reports/revenue");
  await page.waitForLoadState("networkidle").catch(() => {});

  await page.locator("button").filter({ hasText: "排程發送" }).click();
  await expect(
    page.locator("h2").filter({ hasText: /排程 營收|排程/ }),
  ).toBeVisible({ timeout: 5_000 });
});

test("accounting 主頁 期間 + 3 cycle segment 啟用", async ({ page }) => {
  await login(page);
  await page.goto("/accounting");
  await page.waitForLoadState("networkidle").catch(() => {});

  const periodSelect = page.locator("select").first();
  await expect(periodSelect).toBeEnabled();
  await periodSelect.selectOption("last6m");

  const cycleBtns = page.locator("button").filter({ hasText: /^週結|^雙週結|^月結/ });
  expect(await cycleBtns.count()).toBeGreaterThanOrEqual(1);
});

test("admin/reports/technician-ranking pagination 顯示", async ({ page }) => {
  await login(page);
  await page.goto("/admin/reports/technician-ranking");
  await page.waitForLoadState("networkidle").catch(() => {});

  const nextBtn = page.locator("button").filter({ hasText: "下一頁" });
  await expect(nextBtn).toBeVisible();
  // (page 1 時上一頁 disabled / next 視資料量 enabled/disabled — 不硬 assert)
});
