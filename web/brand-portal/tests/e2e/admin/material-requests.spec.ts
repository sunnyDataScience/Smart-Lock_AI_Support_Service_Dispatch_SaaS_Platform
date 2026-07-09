/**
 * web/tests/e2e/admin/material-requests.spec.ts —
 * Flow 4 admin 補料管理彙整視圖 E2E smoke test
 *
 * 對應 commits:
 *   - bd95838a feat(api): list endpoint listPendingMaterialRequestsV2
 *   - 7fa67f3b feat(web): admin 補料管理彙整頁
 *   - e163c21e feat(api+web): supply_arrived 收尾 (mark supplied 按鈕)
 *
 * 測試矩陣：
 *   1. 渲染：mock GET /tenants/*\/material-requests → 表格顯示 urgency badge + items + WO 鏈結
 *   2. urgency filter chips 切換 → 過濾後行數變化
 *   3. supplied 按鈕：mock POST /tenants/*\/work-orders/*\/material-request/*:supplied
 *      → row 從列表移除 (optimistic)
 *   4. 錯誤 (500) → 顯示錯誤 banner
 *
 * 透過 page.route() 攔截 glob pattern；injectAdminSession 注入假 JWT。
 * 標 @wip：本機無真實 DB，純 mock 路徑驗證。
 */

import { test, expect, Page } from "@playwright/test";

const TENANT_ID = "00000000-0000-0000-0000-000000000001";

const MATERIAL_REQUESTS_LIST_PATH = "**/tenants/*/material-requests**";
const MARK_SUPPLIED_PATH = "**/tenants/*/work-orders/*/material-request/*:supplied";

const WO_ID_1 = "11111111-1111-4111-8111-111111111111";
const WO_ID_2 = "22222222-2222-4222-8222-222222222222";
const EVENT_ID_1 = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const EVENT_ID_2 = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

const SAMPLE_LIST = {
  items: [
    {
      event_id: EVENT_ID_1,
      created_at: "2026-06-05T08:30:00Z",
      payload: {
        items: [{ brand: "Dormakaba", model: "ML-500", quantity: 1 }],
        urgency: "now",
        note: "客戶要求今日完工",
      },
      actor_user_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      work_order_id: WO_ID_1,
      wo_status: "in_progress",
      scheduled_at: "2026-06-05T14:00:00Z",
      technician_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    },
    {
      event_id: EVENT_ID_2,
      created_at: "2026-06-05T09:00:00Z",
      payload: {
        items: [
          { brand: "Yale", model: "YDM-7220", quantity: 2 },
          { brand: "Yale", model: "YDM-3168", quantity: 1 },
        ],
        urgency: "tomorrow",
        note: null,
      },
      actor_user_id: null,
      work_order_id: WO_ID_2,
      wo_status: "assigned",
      scheduled_at: "2026-06-06T10:00:00Z",
      technician_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    },
  ],
  count: 2,
};

async function injectAdminSession(page: Page) {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payloadObj = {
    sub: "00000000-0000-0000-0000-000000000099",
    role: "admin",
    tenant_id: TENANT_ID,
    type: "access",
    jti: "test-jti-material-requests",
  };
  const payload = btoa(
    JSON.stringify(payloadObj).replace(/\+/g, "-").replace(/\//g, "_"),
  );
  const fakeToken = `${header}.${payload}.signature`;
  await page.addInitScript(
    ({ token, tenantId }: { token: string; tenantId: string }) => {
      window.localStorage.setItem("smartlock.access_token", token);
      window.localStorage.setItem("smartlock.refresh_token", "fake-refresh");
      window.localStorage.setItem("smartlock.tenant_id", tenantId);
      window.localStorage.setItem("smartlock.email", "test@lock-ai.com");
    },
    { token: fakeToken, tenantId: TENANT_ID },
  );
}

test.describe("@wip Flow 4 admin material-requests page", () => {
  test("renders table + urgency badges + tenant-scoped GET", async ({
    page,
  }) => {
    await injectAdminSession(page);

    let capturedPath: string | null = null;

    await page.route(MATERIAL_REQUESTS_LIST_PATH, async (route) => {
      if (route.request().method() === "GET") {
        capturedPath = route.request().url();
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(SAMPLE_LIST),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/admin/material-requests");

    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 兩筆 items 摘要可見
    await expect(page.getByText(/Dormakaba.*ML-500/).first()).toBeVisible({
      timeout: 10000,
    });
    await expect(page.getByText(/Yale.*YDM-7220/).first()).toBeVisible({
      timeout: 10000,
    });

    // tenant-scoped path 驗證
    expect(capturedPath).not.toBeNull();
    expect(capturedPath!).toContain(`/tenants/${TENANT_ID}/material-requests`);
  });

  test("urgency filter chips 切換", async ({ page }) => {
    await injectAdminSession(page);

    await page.route(MATERIAL_REQUESTS_LIST_PATH, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(SAMPLE_LIST),
      });
    });

    await page.goto("/admin/material-requests");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 預設 all 顯示 2 筆 — 兩個 row 包含 Dormakaba/Yale
    await expect(page.getByText(/Dormakaba/).first()).toBeVisible();
    await expect(page.getByText(/Yale/).first()).toBeVisible();

    // 切到 now（只有 1 筆 urgency=now：Dormakaba）
    const nowChip = page.getByRole("button", { name: /立即|Now/i }).first();
    await nowChip.click();

    // 切換後 Yale row 應消失
    await expect(page.getByText(/Yale/)).toHaveCount(0, { timeout: 5000 });
    await expect(page.getByText(/Dormakaba/).first()).toBeVisible();
  });

  test("mark supplied → optimistic 從列表移除", async ({ page }) => {
    await injectAdminSession(page);

    let suppliedCalled = false;
    let capturedSuppliedPath: string | null = null;

    await page.route(MATERIAL_REQUESTS_LIST_PATH, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(SAMPLE_LIST),
        });
      } else {
        await route.continue();
      }
    });

    await page.route(MARK_SUPPLIED_PATH, async (route) => {
      if (route.request().method() === "POST") {
        suppliedCalled = true;
        capturedSuppliedPath = route.request().url();
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: WO_ID_1,
            status: "in_progress",
          }),
        });
      } else {
        await route.continue();
      }
    });

    // 跳過 window.confirm
    page.on("dialog", (dialog) => dialog.accept());

    await page.goto("/admin/material-requests");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Dormakaba/).first()).toBeVisible({
      timeout: 10000,
    });

    // 點第一筆 「標記補料完成」 按鈕
    const supplyButton = page
      .getByRole("button", { name: /標記補料完成|Mark supplied/i })
      .first();
    await supplyButton.click();

    // POST 應已呼叫，路徑含 :supplied
    await expect.poll(() => suppliedCalled, { timeout: 5000 }).toBe(true);
    expect(capturedSuppliedPath).not.toBeNull();
    expect(capturedSuppliedPath!).toMatch(/material-request\/[a-f0-9-]+:supplied/);

    // optimistic：第一筆從 UI 移除（Dormakaba 應消失，Yale 仍在）
    await expect(page.getByText(/Dormakaba/)).toHaveCount(0, { timeout: 5000 });
    await expect(page.getByText(/Yale/).first()).toBeVisible();
  });

  test("API error 500 → error banner", async ({ page }) => {
    await injectAdminSession(page);

    await page.route(MATERIAL_REQUESTS_LIST_PATH, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({
            error_code: "INTERNAL_ERROR",
            message: "Database unavailable",
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/admin/material-requests");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    const errorEl = page.locator(".border-red-200.bg-red-50").first();
    await expect(errorEl).toBeVisible({ timeout: 10000 });
  });
});
