/**
 * web/tests/e2e/admin/p0-create-warranty.spec.ts —
 * F-015 dual-trigger CS path（建立保固申訴）frontend E2E
 *
 * 對應 ADR-009 §8 D1：CS 在 admin web 主動代開保固申訴。
 *
 * 測試矩陣:
 *   1. 點「建立保固申訴」按鈕 → Modal 顯示
 *   2. 填表（含可選 work_order_id）+ 提交 → mock 201 → toast「保固申訴已建立」
 *   3. POST body 正確（含 requested_by_role=customer_service）
 *
 * 標 @wip：透過 page.route() 攔 GET + POST /api/v1/warranty-claims 模擬。
 */

import { test, expect, Page } from "@playwright/test";

const WARRANTY_PATH = "**/api/v1/warranty-claims**";

const SAMPLE_LIST = {
  items: [
    {
      id: "11111111-1111-1111-1111-111111111111",
      document_number: "WC-20260509-0001",
      work_order_id: null,
      customer_id: "33333333-3333-3333-3333-333333333333",
      device_brand: "Yale",
      device_model: "YDR-1",
      purchase_date: null,
      warranty_start_date: "2026-01-01",
      warranty_end_date: "2026-04-01",
      claim_date: "2026-05-09",
      is_within_warranty: false,
      status: "filed",
      dispute_reason: "test seed",
      verification_source: null,
      resolution: null,
      discount_offered: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ],
  next_cursor: null,
  has_more: false,
};

async function injectAdminSession(page: Page) {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = btoa(
    JSON.stringify({
      sub: "00000000-0000-0000-0000-000000000099",
      role: "admin",
      tenant_id: "00000000-0000-0000-0000-000000000001",
      type: "access",
      jti: "test-jti-warranty",
    })
      .replace(/\+/g, "-")
      .replace(/\//g, "_"),
  );
  const fakeToken = `${header}.${payload}.signature`;
  await page.addInitScript((token: string) => {
    window.localStorage.setItem("smartlock.access_token", token);
    window.localStorage.setItem("smartlock.refresh_token", "fake-refresh");
    window.localStorage.setItem(
      "smartlock.tenant_id",
      "00000000-0000-0000-0000-000000000001",
    );
    window.localStorage.setItem("smartlock.email", "admin@example.com");
  }, fakeToken);
}

test.describe("@wip F-015 createWarrantyClaim dual-trigger CS path", () => {
  test("opens Modal, submits form (no WO), sees toast on 201", async ({
    page,
  }) => {
    await injectAdminSession(page);

    let postCaptured: Record<string, unknown> | null = null;
    await page.route(WARRANTY_PATH, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(SAMPLE_LIST),
        });
      } else if (route.request().method() === "POST") {
        postCaptured = route.request().postDataJSON() as Record<string, unknown>;
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            data: {
              ...SAMPLE_LIST.items[0],
              id: "44444444-4444-4444-4444-444444444444",
              document_number: "WC-20260509-0042",
            },
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/admin/warranty-claims");
    await expect(page.getByText("保固申請管理")).toBeVisible({ timeout: 15000 });

    // 點「建立保固申訴」button
    const createBtn = page.getByRole("button", { name: /建立保固申訴/ });
    await expect(createBtn).toBeVisible();
    await createBtn.click();

    // Modal 顯示（form field 偵測）
    const customerInput = page.locator('input[placeholder*="00000000"]').first();
    await expect(customerInput).toBeVisible({ timeout: 5000 });

    // 填客戶 ID
    await customerInput.fill("33333333-3333-3333-3333-333333333333");

    // 工單 ID 留空（測無 WO 路徑）

    // 品牌型號（getByLabel 用 label 文字定位）
    await page.getByText("品牌", { exact: true }).locator("..").locator("input").fill("Yale");
    await page.getByText("型號", { exact: true }).locator("..").locator("input").fill("YDR-99");

    // 提交（Modal 內唯一）
    await page.getByRole("button", { name: "建立", exact: true }).click();

    // toast
    await expect(page.getByText("保固申訴已建立")).toBeVisible({
      timeout: 10000,
    });

    // POST body 正確
    const body = postCaptured as unknown as Record<string, unknown>;
    expect(body["customer_id"]).toBe(
      "33333333-3333-3333-3333-333333333333",
    );
    expect(body["device_brand"]).toBe("Yale");
    expect(body["device_model"]).toBe("YDR-99");
    expect(body["claim_type"]).toBe("defective");
    expect(body["requested_by_role"]).toBe("customer_service");
    // 無 WO → 後端 expect undefined
    expect(body["work_order_id"]).toBeUndefined();
  });
});
