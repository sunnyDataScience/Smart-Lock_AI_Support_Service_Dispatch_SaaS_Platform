/**
 * web/tests/e2e/admin/vouchers.spec.ts —
 * /accounting/vouchers 頁面 tenant-scoped v2 端點 E2E 測試（CR-0002-α）
 *
 * 測試矩陣：
 *   1. /accounting/vouchers 頁面渲染 → mock GET /tenants/*\/vouchers → 表格顯示 + 打 tenant-scoped path
 *   2. 錯誤狀態（500）→ 顯示錯誤訊息
 *
 * 透過 page.route() 攔截 tenants-vouchers glob pattern 模擬回應。
 * 使用 injectAdminSession 注入假 JWT（tenant_id = DEFAULT_TENANT）。
 *
 * 標 @wip：本機沒有真實 DB + admin login flow；透過 mock 隔離 API 層。
 */

import { test, expect, Page } from "@playwright/test";

const TENANT_ID = "00000000-0000-0000-0000-000000000001";
const VOUCHER_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";

// 傳票號格式 regex（對齊現行 seed：V + YYYYMMDD + - + NNNN）。
// 測試只驗結構，不綁特定號碼，避免 seed 變動時 hardcode 失效。
const VOUCHER_NUMBER_RE = /V\d{8}-\d{4}/;

// 傳票列表 GET 走 /tenants/{id}/vouchers?posting_date_start=...&...&limit=...
// page.route 的 glob `**/tenants/*/vouchers` 無法匹配帶 query string 的 URL，
// 故改用 regex 攔截「以 /vouchers 結尾、後接可選 query」且排除 /vouchers/{id}/export。
const LIST_PATH = /\/tenants\/[^/]+\/vouchers(\?[^/]*)?$/;

const SAMPLE_VOUCHER = {
  id: VOUCHER_ID,
  voucher_number: "V20260427-0001",
  related_entity_type: "settlement",
  related_entity_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
  debit_account: "應收帳款",
  credit_account: "服務收入",
  amount: "1200.00",
  currency: "TWD",
  posting_date: "2026-05-15",
  memo: "技師派工結算",
  created_at: "2026-05-15T08:00:00+08:00",
};

const SAMPLE_LIST = {
  items: [SAMPLE_VOUCHER],
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
    jti: "test-jti-vouchers",
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
// Test: /accounting/vouchers list page
// ---------------------------------------------------------------------------

test.describe("@wip vouchers list page — tenant-scoped v2 GET", () => {
  test("renders voucher table and fetches tenant-scoped path", async ({
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

    await page.goto("/accounting/vouchers");

    // 頁面 title 顯示
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 傳票號碼以格式驗結構（不綁特定號碼），mock 回的 voucher_number 應渲染出來
    await expect(page.getByText(VOUCHER_NUMBER_RE).first()).toBeVisible({
      timeout: 10000,
    });

    // 驗證打的是 tenant-scoped path（含 tenantId）
    expect(capturedPath).not.toBeNull();
    expect(capturedPath!).toContain(`/tenants/${TENANT_ID}/vouchers`);
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

    await page.goto("/accounting/vouchers");

    // 等待頁面 mount
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 錯誤 banner 應顯示
    const errorEl = page.locator(".border-red-200.bg-red-50").first();
    await expect(errorEl).toBeVisible({ timeout: 10000 });
  });
});
