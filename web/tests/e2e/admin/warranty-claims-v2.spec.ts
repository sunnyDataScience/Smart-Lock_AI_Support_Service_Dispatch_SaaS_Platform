/**
 * web/tests/e2e/admin/warranty-claims-v2.spec.ts —
 * F-015 createWarrantyClaim 前端 E2E（CR-0003 P2 — tenant-scoped v2 POST）
 *
 * 測試矩陣:
 *   1. POST 建立保固申訴 → mock 201 → toast 出現 + POST 打 /tenants/{tenantId}/warranty-claims
 *   2. GET list 打 /api/v1/warranty-claims（legacy 不動）
 *   3. POST body 含正確欄位（customer_id, claim_type, requested_by_role）
 *
 * 透過 page.route() 攔截所有 warranty-claims 路徑，分 method 回應。
 * 使用 injectAdminSession（對齊 customers.spec.ts 模式）。
 *
 * 標 @wip：透過 mock 隔離 API 層，無需真實 DB。
 */

import { test, expect, Page } from "@playwright/test";

const TENANT_ID = "00000000-0000-0000-0000-000000000001";

// v2 tenant-scoped POST path（測試核心目標）
const V2_POST_PATH = `**/tenants/${TENANT_ID}/warranty-claims`;
// legacy GET list path（不動）
const LEGACY_LIST_PATH = "**/api/v1/warranty-claims**";

const SAMPLE_CLAIM = {
  id: "11111111-1111-1111-1111-111111111111",
  document_number: "WC-20260602-0001",
  work_order_id: null,
  customer_id: "33333333-3333-3333-3333-333333333333",
  device_brand: "Yale",
  device_model: "YDR-1",
  purchase_date: null,
  warranty_start_date: "2026-01-01",
  warranty_end_date: "2028-01-01",
  claim_date: "2026-06-02",
  is_within_warranty: true,
  status: "filed",
  dispute_reason: null,
  verification_source: null,
  resolution: null,
  discount_offered: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

const SAMPLE_LIST = {
  items: [SAMPLE_CLAIM],
  next_cursor: null,
  has_more: false,
};

const CREATED_CLAIM = {
  ...SAMPLE_CLAIM,
  id: "44444444-4444-4444-4444-444444444444",
  document_number: "WC-20260602-0042",
  device_brand: "Dormakaba",
  device_model: "AS701",
  customer_id: "33333333-3333-3333-3333-333333333333",
};

async function injectAdminSession(page: Page) {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payloadObj = {
    sub: "00000000-0000-0000-0000-000000000099",
    role: "admin",
    tenant_id: TENANT_ID,
    type: "access",
    jti: "test-jti-warranty-v2",
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
      window.localStorage.setItem("smartlock.email", "admin@example.com");
    },
    { token: fakeToken, tenantId: TENANT_ID },
  );
}

// ---------------------------------------------------------------------------
// Test: POST 建立保固申訴 → 打 v2 tenant-scoped path
// ---------------------------------------------------------------------------

test.describe("@wip warranty-claims v2 POST — tenant-scoped path（CR-0003 P2）", () => {
  test("opens Modal, submits form, POSTs to /tenants/{tenantId}/warranty-claims, sees toast", async ({
    page,
  }) => {
    await injectAdminSession(page);

    let capturedPostPath: string | null = null;
    let capturedPostBody: Record<string, unknown> | null = null;

    // mock GET /api/v1/warranty-claims → list
    await page.route(LEGACY_LIST_PATH, async (route) => {
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

    // mock POST /tenants/{tenantId}/warranty-claims → 201
    await page.route(V2_POST_PATH, async (route) => {
      if (route.request().method() === "POST") {
        capturedPostPath = route.request().url();
        capturedPostBody = route.request().postDataJSON() as Record<string, unknown>;
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({ data: CREATED_CLAIM }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/admin/warranty-claims");

    // 等頁面 mount
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 點「建立保固申訴」
    const createBtn = page.getByRole("button", { name: /建立保固申訴/ });
    await expect(createBtn).toBeVisible({ timeout: 8000 });
    await createBtn.click();

    // Modal 顯示（UUID placeholder 定位 customer input）
    const customerInput = page.locator('input[placeholder*="00000000"]').first();
    await expect(customerInput).toBeVisible({ timeout: 5000 });

    // 填 customer_id
    await customerInput.fill("33333333-3333-3333-3333-333333333333");

    // 填品牌型號
    await page.getByText("品牌", { exact: true }).locator("..").locator("input").fill("Dormakaba");
    await page.getByText("型號", { exact: true }).locator("..").locator("input").fill("AS701");

    // 提交（Modal 內唯一「建立」按鈕）
    await page.getByRole("button", { name: "建立", exact: true }).click();

    // toast 顯示
    await expect(page.getByText("保固申訴已建立")).toBeVisible({
      timeout: 10000,
    });

    // 驗證 POST 打的是 v2 tenant-scoped path
    expect(capturedPostPath).not.toBeNull();
    expect(capturedPostPath!).toContain(
      `/tenants/${TENANT_ID}/warranty-claims`,
    );

    // 驗證 POST body 欄位正確
    const body = capturedPostBody as unknown as Record<string, unknown>;
    expect(body["customer_id"]).toBe(
      "33333333-3333-3333-3333-333333333333",
    );
    expect(body["device_brand"]).toBe("Dormakaba");
    expect(body["device_model"]).toBe("AS701");
    expect(body["claim_type"]).toBe("defective");
    expect(body["requested_by_role"]).toBe("customer_service");
    // 沒填 work_order_id → body 不應帶此欄位
    expect(body["work_order_id"]).toBeUndefined();
  });

  test("legacy GET /api/v1/warranty-claims still fetches list correctly", async ({
    page,
  }) => {
    await injectAdminSession(page);

    let capturedGetPath: string | null = null;

    await page.route(LEGACY_LIST_PATH, async (route) => {
      if (route.request().method() === "GET") {
        capturedGetPath = route.request().url();
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(SAMPLE_LIST),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/admin/warranty-claims");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 確認 GET 打了 legacy list path（legacy 不動）
    expect(capturedGetPath).not.toBeNull();
    expect(capturedGetPath!).toContain("/api/v1/warranty-claims");
  });
});
