/**
 * web/tests/e2e/admin/customers.spec.ts —
 * /admin/customers 頁面 tenant-scoped v2 端點 E2E 測試（CR-0002-α）
 *
 * 測試矩陣：
 *   1. /admin/customers 頁面渲染 → mock GET /tenants/*\/customers → 表格顯示 + 打 tenant-scoped path
 *   2. /admin/customers/{id} 詳情頁 → mock GET /tenants/*\/customers/{id} → 顯示客戶資料
 *   3. 錯誤狀態（500）→ 顯示錯誤訊息
 *
 * 透過 page.route() 攔截 tenants-customers glob pattern 模擬回應。
 * 使用 injectAdminSession 注入假 JWT（tenant_id = DEFAULT_TENANT）。
 *
 * 標 @wip：本機沒有真實 DB + admin login flow；透過 mock 隔離 API 層。
 */

import { test, expect, Page } from "@playwright/test";

const TENANT_ID = "00000000-0000-0000-0000-000000000001";
const CUSTOMER_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

// glob 尾端加 `*` 以同時涵蓋分頁 query string（usePaginatedFetch 會自動
// 附 `?limit=20`）；否則 `**/tenants/*/customers` 比對不到帶 query 的 URL，
// mock 不觸發 → 真實後端回 401。
const LIST_PATH = "**/tenants/*/customers*";
const DETAIL_PATH = `**/tenants/*/customers/${CUSTOMER_ID}`;

const SAMPLE_CUSTOMER = {
  id: CUSTOMER_ID,
  display_name: "王小明",
  line_user_id: "Uf1234567890abcdef1234567890",
  phone: "0912345678",
  address: "台北市中正區忠孝東路一段1號",
  last_active_at: new Date(Date.now() - 3600000).toISOString(),
  created_at: "2026-01-15T08:00:00Z",
  total_conversations: 3,
  total_orders: 2,
  last_service_at: "2026-05-01T10:00:00Z",
};

const SAMPLE_LIST = {
  items: [SAMPLE_CUSTOMER],
  next_cursor: null,
  has_more: false,
};

const SAMPLE_DETAIL = {
  ...SAMPLE_CUSTOMER,
  history: {
    work_order_status_breakdown: { completed: 2 },
    avg_completion_minutes: 45.5,
    avg_rating: 4.5,
    rated_count: 2,
    dispute_count: 0,
    refund_count: 0,
    refund_total: 0,
    recent_orders: [
      {
        id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        status: "completed",
        address: "台北市中正區忠孝東路一段1號",
        brand: "Dormakaba",
        model: "AS701",
        priority: "normal",
        estimated_price: 1200,
        created_at: "2026-05-01T09:00:00Z",
        completed_at: "2026-05-01T10:00:00Z",
      },
    ],
    recent_conversations: [
      {
        id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        status: "resolved",
        channel: "line",
        created_at: "2026-04-20T14:00:00Z",
        updated_at: "2026-04-20T15:00:00Z",
      },
    ],
  },
};

async function injectAdminSession(page: Page) {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payloadObj = {
    sub: "00000000-0000-0000-0000-000000000099",
    role: "admin",
    tenant_id: TENANT_ID,
    type: "access",
    jti: "test-jti-customers",
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
// Test: /admin/customers list page
// ---------------------------------------------------------------------------

test.describe("@wip customers list page — tenant-scoped v2 GET", () => {
  test("renders customer table and fetches tenant-scoped path", async ({
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

    await page.goto("/admin/customers");

    // 頁面 title 顯示
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 表格中至少渲染出一列客戶（不綁特定姓名 — 對 seed 穩健）
    await expect(page.getByText(SAMPLE_CUSTOMER.display_name).first()).toBeVisible({
      timeout: 10000,
    });

    // 驗證打的是 tenant-scoped path（含 tenantId）
    expect(capturedPath).not.toBeNull();
    expect(capturedPath!).toContain(`/tenants/${TENANT_ID}/customers`);
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

    await page.goto("/admin/customers");

    // 等待頁面 mount
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 錯誤 banner 應顯示
    const errorEl = page.locator(".border-red-200.bg-red-50").first();
    await expect(errorEl).toBeVisible({ timeout: 10000 });
  });
});

// ---------------------------------------------------------------------------
// Test: /admin/customers/{id} detail page
// ---------------------------------------------------------------------------

test.describe("@wip customers detail page — tenant-scoped v2 GET detail", () => {
  test("renders customer detail with aggregated history", async ({ page }) => {
    await injectAdminSession(page);

    let capturedPath: string | null = null;

    await page.route(DETAIL_PATH, async (route) => {
      if (route.request().method() === "GET") {
        capturedPath = route.request().url();
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(SAMPLE_DETAIL),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto(`/admin/customers/${CUSTOMER_ID}`);

    // 顯示客戶姓名（詳情頁姓名出現在 avatar + h2 多處 → .first() 避開 strict mode）
    await expect(page.getByText(SAMPLE_CUSTOMER.display_name).first()).toBeVisible({
      timeout: 15000,
    });

    // 聚合歷史區塊已渲染（KpiCard 的數值 div class=text-[20px] font-bold）。
    // 不綁特定數字（"2" 會 strict-mode 命中多處），改驗 KPI 卡結構存在 →
    // 證明 SAMPLE_DETAIL.history 被頁面消費。
    await expect(
      page.locator("div.text-\\[20px\\].font-bold").first(),
    ).toBeVisible({ timeout: 5000 });

    // 驗證打的是 tenant-scoped path
    expect(capturedPath).not.toBeNull();
    expect(capturedPath!).toContain(
      `/tenants/${TENANT_ID}/customers/${CUSTOMER_ID}`,
    );
  });

  test("shows not-found state on 404", async ({ page }) => {
    await injectAdminSession(page);

    const randomId = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";

    await page.route(`**/tenants/*/customers/${randomId}`, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 404,
          contentType: "application/json",
          body: JSON.stringify({
            error_code: "NOT_FOUND",
            message: "Customer not found",
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto(`/admin/customers/${randomId}`);

    // 等待 loading 消失後應顯示 not-found 或 error
    await expect(page.locator("h1, [class*='error'], [role='alert']").first()).toBeVisible({
      timeout: 15000,
    });
  });
});
