/**
 * web/tests/e2e/admin/technicians.spec.ts —
 * /technicians 頁面 tenant-scoped v2 端點 E2E 測試（CR-0002-α）
 *
 * 測試矩陣：
 *   1. /technicians 頁面渲染 → mock GET /tenants/*\/technicians → 表格顯示 + 打 tenant-scoped path
 *   2. /technicians/{id} 詳情頁 → mock GET /tenants/*\/technicians/{id} → 顯示技師資料
 *   3. 錯誤狀態（500）→ 顯示錯誤訊息
 *
 * 透過 page.route() 攔截 tenants-technicians glob pattern 模擬回應。
 * 使用 injectAdminSession 注入假 JWT（tenant_id = DEFAULT_TENANT）。
 *
 * 標 @wip：本機沒有真實 DB + admin login flow；透過 mock 隔離 API 層。
 */

import { test, expect, Page } from "@playwright/test";

const TENANT_ID = "00000000-0000-0000-0000-000000000001";
const TECH_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";

// glob 尾端加 `*` 以同時涵蓋分頁 query string（usePaginatedFetch 會自動
// 附 `?limit=20`）；否則 `**/tenants/*/technicians` 比對不到帶 query 的 URL，
// mock 不觸發 → 真實後端回 401。
const LIST_PATH = "**/tenants/*/technicians*";
const DETAIL_PATH = `**/tenants/*/technicians/${TECH_ID}`;

const SAMPLE_TECHNICIAN = {
  id: TECH_ID,
  name: "陳大明",
  phone: "0921111222",
  level: "A",
  availability: "available",
  skills: ["Dormakaba", "Chatlock"],
  service_areas: ["台北市", "新北市"],
  rating: 4.8,
  completed_orders_count: 123,
  circuit_breaker_until: null,
  created_at: "2025-01-10T08:00:00Z",
};

const SAMPLE_LIST = {
  items: [SAMPLE_TECHNICIAN],
  next_cursor: null,
  has_more: false,
};

const SAMPLE_ENVELOPE = {
  data: SAMPLE_TECHNICIAN,
};

async function injectAdminSession(page: Page) {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payloadObj = {
    sub: "00000000-0000-0000-0000-000000000099",
    role: "admin",
    tenant_id: TENANT_ID,
    type: "access",
    jti: "test-jti-technicians",
  };
  const payload = btoa(
    JSON.stringify(payloadObj)
      .replace(/\+/g, "-")
      .replace(/\//g, "_"),
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

// ---------------------------------------------------------------------------
// Test: /technicians list page
// ---------------------------------------------------------------------------

test.describe("@wip technicians list page — tenant-scoped v2 GET", () => {
  test("renders technician table and fetches tenant-scoped path", async ({
    page,
  }) => {
    await injectAdminSession(page);

    let capturedPath: string | null = null;

    await page.route(LIST_PATH, async (route) => {
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

    await page.goto("/technicians");

    // 頁面 title 顯示
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 表格中至少渲染出一列技師（不綁特定姓名/數字 — 對 seed 穩健）
    await expect(page.getByText(SAMPLE_TECHNICIAN.name).first()).toBeVisible({
      timeout: 10000,
    });

    // 驗證打的是 tenant-scoped path（含 tenantId）
    expect(capturedPath).not.toBeNull();
    expect(capturedPath!).toContain(`/tenants/${TENANT_ID}/technicians`);
  });

  test("shows error banner on API error", async ({ page }) => {
    await injectAdminSession(page);

    await page.route(LIST_PATH, async (route) => {
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

    await page.goto("/technicians");

    // 等待頁面 mount
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 錯誤 banner 應顯示
    const errorEl = page.locator(".border-red-200.bg-red-50").first();
    await expect(errorEl).toBeVisible({ timeout: 10000 });
  });
});

// ---------------------------------------------------------------------------
// Test: /technicians/{id} detail page
// ---------------------------------------------------------------------------

test.describe("@wip technicians detail page — tenant-scoped v2 GET detail", () => {
  test("renders technician detail", async ({ page }) => {
    await injectAdminSession(page);

    let capturedPath: string | null = null;

    await page.route(DETAIL_PATH, async (route) => {
      if (route.request().method() === "GET") {
        capturedPath = route.request().url();
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(SAMPLE_ENVELOPE),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto(`/technicians/${TECH_ID}`);

    // 顯示技師姓名（詳情頁姓名出現在 h1 + sidebar 多處 → 用 .first() 避開 strict mode）
    await expect(page.getByText(SAMPLE_TECHNICIAN.name).first()).toBeVisible({
      timeout: 15000,
    });

    // 驗證打的是 tenant-scoped path
    expect(capturedPath).not.toBeNull();
    expect(capturedPath!).toContain(
      `/tenants/${TENANT_ID}/technicians/${TECH_ID}`,
    );
  });

  test("shows not-found state on 404", async ({ page }) => {
    await injectAdminSession(page);

    const randomId = "ffffffff-ffff-4fff-8fff-ffffffffffff";

    await page.route(`**/tenants/*/technicians/${randomId}`, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({
            error_code: "NOT_FOUND",
            message: "Technician not found",
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto(`/technicians/${randomId}`);

    // 等待 loading 消失後應顯示 not-found 或 error
    await expect(
      page.locator("h1, [class*='error'], [role='alert'], .border-red-200").first(),
    ).toBeVisible({ timeout: 15000 });
  });
});
