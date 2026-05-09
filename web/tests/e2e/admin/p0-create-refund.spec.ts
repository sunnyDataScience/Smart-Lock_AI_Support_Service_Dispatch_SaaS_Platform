/**
 * web/tests/e2e/admin/p0-create-refund.spec.ts —
 * F-014 dual-trigger CS path（建立退款申請）frontend E2E
 *
 * 對應 ADR-009 §8 D1：CS 在 admin web 主動代開退款申請。
 *
 * 測試矩陣:
 *   1. 點「建立退款申請」按鈕 → Modal 顯示
 *   2. 填表 + 提交 → mock 201 → toast「退款申請已建立」
 *   3. 4xx 錯誤 → 顯示錯誤訊息 + Modal 不關
 *
 * 標 @wip：本機沒有真 admin login flow + 真 DB seed；
 * 透過 page.route() 攔 GET + POST /api/v1/refunds 模擬。
 */

import { test, expect, Page } from "@playwright/test";

const REFUNDS_PATH = "**/api/v1/refunds**";

const SAMPLE_LIST = {
  items: [
    {
      id: "11111111-1111-1111-1111-111111111111",
      document_number: "RM-20260509-0001",
      work_order_id: "22222222-2222-2222-2222-222222222222",
      requested_by: "33333333-3333-3333-3333-333333333333",
      amount: "500.00",
      reason: "test seed",
      status: "pending",
      requires_dual_sign: false,
      approval_chain: [],
      executed_at: null,
      invoice_id: null,
      complaint_id: null,
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
      jti: "test-jti-refund",
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

test.describe("@wip F-014 createRefundRequest dual-trigger CS path", () => {
  test("opens Modal, submits form, sees toast on 201", async ({ page }) => {
    await injectAdminSession(page);

    let postCaptured: Record<string, unknown> | null = null;
    await page.route(REFUNDS_PATH, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(SAMPLE_LIST),
        });
      } else if (route.request().method() === "POST") {
        postCaptured = route.request().postDataJSON();
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            data: {
              ...SAMPLE_LIST.items[0],
              id: "44444444-4444-4444-4444-444444444444",
              document_number: "RM-20260509-0042",
            },
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/admin/refunds");
    await expect(page.getByText("退款審核佇列")).toBeVisible({ timeout: 15000 });

    // 點「建立退款申請」button
    const createBtn = page.getByRole("button", { name: /建立退款申請/ });
    await expect(createBtn).toBeVisible();
    await createBtn.click();

    // Modal 顯示（用 form field 偵測，避免文字重複）
    const woInput = page.locator('input[placeholder*="00000000"]');
    await expect(woInput).toBeVisible({ timeout: 5000 });

    // 填表
    await woInput.fill("22222222-2222-2222-2222-222222222222");
    await page.locator('input[placeholder*="1500"]').fill("888.50");
    await page
      .locator("textarea")
      .fill("E2E test：客戶投訴瑕疵商品要求退款");

    // 提交（Modal 內的「建立」button — 唯一）
    await page.getByRole("button", { name: "建立", exact: true }).click();

    // toast 顯示
    await expect(page.getByText("退款申請已建立")).toBeVisible({
      timeout: 10000,
    });

    // 確認 POST body 正確
    expect(postCaptured?.work_order_id).toBe(
      "22222222-2222-2222-2222-222222222222",
    );
    expect(postCaptured?.amount).toBe("888.50");
    expect(postCaptured?.reason_code).toBe("defective_product");
    expect(postCaptured?.requested_by_role).toBe("customer_service");
  });

  test("shows error on 422 validation failure (Modal stays open)", async ({
    page,
  }) => {
    await injectAdminSession(page);

    await page.route(REFUNDS_PATH, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(SAMPLE_LIST),
        });
      } else if (route.request().method() === "POST") {
        await route.fulfill({
          status: 422,
          contentType: "application/json",
          body: JSON.stringify({
            error_code: "VALIDATION_ERROR",
            message: "amount must be > 0",
          }),
        });
      }
    });

    await page.goto("/admin/refunds");
    await expect(page.getByText("退款審核佇列")).toBeVisible({ timeout: 15000 });

    await page.getByRole("button", { name: /建立退款申請/ }).click();
    const woInput = page.locator('input[placeholder*="00000000"]');
    await expect(woInput).toBeVisible({ timeout: 5000 });

    await woInput.fill("22222222-2222-2222-2222-222222222222");
    await page.locator('input[placeholder*="1500"]').fill("100");
    await page.locator("textarea").fill("test");

    // 等 button 可點（avoid race）+ 點擊
    const submitBtn = page.getByRole("button", { name: "建立", exact: true });
    await expect(submitBtn).toBeEnabled({ timeout: 5000 });
    await submitBtn.click();

    // Modal 仍開著（textarea 仍可見）— 422 不關閉 Modal
    await expect(page.locator("textarea")).toBeVisible({ timeout: 5000 });

    // 取消 button 仍可見
    await expect(page.getByRole("button", { name: "取消" })).toBeVisible();

    // 錯誤訊息顯示（紅色 error box border 樣式 + 內容含 error_code）
    const errorBox = page.locator(".border-red-200.bg-red-50").first();
    await expect(errorBox).toBeVisible({ timeout: 5000 });
    await expect(errorBox).toContainText(/VALIDATION_ERROR|422/);
  });
});
