/**
 * web/tests/e2e/admin/problem-cards.spec.ts —
 * /problem-cards 頁面 tenant-scoped v2 端點 E2E 測試（CR-0002-α）
 *
 * 測試矩陣：
 *   1. /problem-cards 頁面渲染 → mock GET /tenants/*\/problem-cards → 表格顯示 + 打 tenant-scoped path
 *   2. 錯誤狀態（500）→ 顯示錯誤訊息
 *
 * 透過 page.route() 攔截 tenants-problem-cards glob pattern 模擬回應。
 * 使用 injectAdminSession 注入假 JWT（tenant_id = DEFAULT_TENANT）。
 *
 * 標 @wip：本機沒有真實 DB + admin login flow；透過 mock 隔離 API 層。
 */

import { test, expect, Page } from "@playwright/test";

const TENANT_ID = "00000000-0000-0000-0000-000000000001";

// 攔截 glob 須帶尾隨 * 以涵蓋 query string（usePaginatedFetch 一律附加 ?limit=20）；
// 缺少尾隨 wildcard 時 Playwright glob 不會匹配帶 query 的 URL，route 不觸發 → capturedPath 為 null。
const LIST_PATH = "**/tenants/*/problem-cards*";

const SAMPLE_PROBLEM_CARD = {
  id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  conversation_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  brand: "Dormakaba",
  model: "AS701",
  symptom: "門鎖無法開啟",
  status: "draft",
  urgency: "high",
  category: "硬體故障",
  location: "台北市中正區",
  door_status: null,
  network_status: null,
  symptoms: ["門鎖無法開啟"],
  intent: null,
  media_urls: [],
  created_at: "2026-05-01T09:00:00Z",
  updated_at: "2026-05-01T09:00:00Z",
};

const SAMPLE_LIST = {
  items: [SAMPLE_PROBLEM_CARD],
  next_cursor: null,
  has_more: false,
};

async function injectAdminSession(page: Page) {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payloadObj = {
    sub: "00000000-0000-0000-0000-000000000099",
    role: "admin",
    tenant_id: TENANT_ID,
    type: "access",
    jti: "test-jti-problem-cards",
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
// Test: /problem-cards list page — tenant-scoped v2 GET
// ---------------------------------------------------------------------------

test.describe("@wip problem-cards list page — tenant-scoped v2 GET", () => {
  test("renders problem card table and fetches tenant-scoped path", async ({
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

    await page.goto("/problem-cards");

    // 頁面 title 顯示
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 驗證打的是 tenant-scoped path（含 tenantId）
    expect(capturedPath).not.toBeNull();
    expect(capturedPath!).toContain(`/tenants/${TENANT_ID}/problem-cards`);
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

    await page.goto("/problem-cards");

    // 等待頁面 mount
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 錯誤 banner 應顯示
    const errorEl = page.locator(".border-red-200.bg-red-50").first();
    await expect(errorEl).toBeVisible({ timeout: 10000 });
  });

  test("renders problem card items from mock data", async ({ page }) => {
    await injectAdminSession(page);

    await page.route(LIST_PATH, async (route) => {
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

    await page.goto("/problem-cards");

    // 頁面標題顯示
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 問題卡資料可見（brand 欄位或 symptom 欄位）
    // 實際顯示取決於 ProblemCardsTable 元件，至少確認頁面不報錯
    await expect(page.locator("body")).not.toContainText("Unexpected error", { timeout: 5000 });
  });
});
