/**
 * web/tests/e2e/admin/p0-create-refund.spec.ts —
 * 退款建立流程（遷移至 tenant-scoped 三維 SoD + 5-tier）frontend E2E
 *
 * 對應 ADR-0040v2 / FR-0014：建立退款改打 POST /tenants/{tenantId}/refunds，
 * 帶 X-Initiator / X-Approver headers；tier 由伺服器從 amount 推算。
 * list 查詢仍走舊 GET /api/v1/refunds（未遷移，雙掛過渡）。
 *
 * 測試矩陣:
 *   1. 點「建立退款申請」按鈕 → Modal 顯示
 *   2. 填表（含 refund_class + approver）+ 提交 → mock 200 →
 *      斷言 SoD headers + body（不含舊 reason_code/requested_by_role）+ toast 含 tier
 *   3. 403 SOD_VIOLATION / 422 REFUND_CLASS_INVALID → error box + Modal 不關
 *
 * 標 @wip：本機沒有真 admin login flow + 真 DB seed；
 * 透過 page.route() 攔 GET /api/v1/refunds（list）+ POST /tenants/*\/refunds（建立）模擬。
 */

import { test, expect, Page } from "@playwright/test";

const LIST_PATH = "**/api/v1/refunds**";
const CREATE_PATH = "**/tenants/*/refunds**";

const APPROVER_UUID = "a0000000-0000-4000-8000-000000000002";

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

/** GET list 仍走舊端點 — 統一在每個 test 開頭掛上。 */
async function mockList(page: Page) {
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
}

async function openCreateModal(page: Page) {
  await page.goto("/admin/refunds");
  await expect(page.getByText("退款審核佇列")).toBeVisible({ timeout: 15000 });
  const createBtn = page.getByRole("button", { name: /建立退款申請/ });
  await expect(createBtn).toBeVisible();
  await createBtn.click();
  const woInput = page.locator('input[placeholder*="00000000"]');
  await expect(woInput).toBeVisible({ timeout: 5000 });
  return woInput;
}

test.describe("@wip createRefund tenant-scoped SoD + 5-tier path", () => {
  test("submits to tenant-scoped endpoint with SoD headers, toast shows tier", async ({
    page,
  }) => {
    await injectAdminSession(page);
    await mockList(page);

    let postHeaders: Record<string, string> | null = null;
    let postBody: Record<string, unknown> | null = null;
    await page.route(CREATE_PATH, async (route) => {
      // 只攔建立 POST；tenant-scoped path 沒有 GET list 行為
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      postHeaders = route.request().headers();
      postBody = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          data: {
            refund_id: "44444444-4444-4444-4444-444444444444",
            work_order_id: "22222222-2222-2222-2222-222222222222",
            amount: 8000,
            tier: "L3",
            refund_class: "product",
            state: "pending",
            initiator_user_id: "00000000-0000-0000-0000-000000000099",
            approver_user_ids: [APPROVER_UUID],
            executor_user_id: null,
            audit_event_id: "evt-00000000-0000-0000-0000-000000000001",
          },
        }),
      });
    });

    const woInput = await openCreateModal(page);

    // 填表
    await woInput.fill("22222222-2222-2222-2222-222222222222");
    await page.locator('input[placeholder*="1500"]').fill("8000");
    await page.locator("select").selectOption("product");
    await page.locator("textarea").fill("E2E test：客戶投訴瑕疵商品要求退款");
    await page.locator('input[placeholder*="SoD"]').fill(APPROVER_UUID);

    // 提交（Modal 內的「建立」button — 唯一）
    await page.getByRole("button", { name: "建立", exact: true }).click();

    // toast 顯示 tier
    await expect(page.getByText(/tier|L3/)).toBeVisible({ timeout: 10000 });

    // 斷言 SoD headers：X-Initiator / X-Approver 都在且不同
    expect(postHeaders).not.toBeNull();
    const headers = postHeaders as unknown as Record<string, string>;
    const initiator = headers["x-initiator"];
    const approver = headers["x-approver"];
    expect(initiator).toBeTruthy();
    expect(approver).toBe(APPROVER_UUID);
    expect(initiator).not.toBe(approver);

    // 斷言 body：新合約欄位，且不含舊 reason_code / requested_by_role
    expect(postBody).not.toBeNull();
    const body = postBody as unknown as Record<string, unknown>;
    expect(body.refund_class).toBe("product");
    expect(body.amount).toBe(8000);
    expect(body.work_order_id).toBe("22222222-2222-2222-2222-222222222222");
    expect(body.reason_code).toBeUndefined();
    expect(body.requested_by_role).toBeUndefined();
  });

  test("shows error_code on 403 SOD_VIOLATION (Modal stays open)", async ({
    page,
  }) => {
    await injectAdminSession(page);
    await mockList(page);

    await page.route(CREATE_PATH, async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({
          error_code: "SOD_VIOLATION",
          message: "initiator must differ from approver",
        }),
      });
    });

    const woInput = await openCreateModal(page);

    await woInput.fill("22222222-2222-2222-2222-222222222222");
    await page.locator('input[placeholder*="1500"]').fill("8000");
    await page.locator("select").selectOption("product");
    await page.locator("textarea").fill("test");
    await page.locator('input[placeholder*="SoD"]').fill(APPROVER_UUID);

    const submitBtn = page.getByRole("button", { name: "建立", exact: true });
    await expect(submitBtn).toBeEnabled({ timeout: 5000 });
    await submitBtn.click();

    // Modal 仍開著（textarea + 取消 button 仍可見）
    await expect(page.locator("textarea")).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole("button", { name: "取消" })).toBeVisible();

    // 錯誤訊息顯示（紅色 error box + 內容含 error_code）
    const errorBox = page.locator(".border-red-200.bg-red-50").first();
    await expect(errorBox).toBeVisible({ timeout: 5000 });
    await expect(errorBox).toContainText(/SOD_VIOLATION|403/);
  });

  test("shows error_code on 422 REFUND_CLASS_INVALID (Modal stays open)", async ({
    page,
  }) => {
    await injectAdminSession(page);
    await mockList(page);

    await page.route(CREATE_PATH, async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      await route.fulfill({
        status: 422,
        contentType: "application/json",
        body: JSON.stringify({
          error_code: "REFUND_CLASS_INVALID",
          message: "refund_class is invalid",
        }),
      });
    });

    const woInput = await openCreateModal(page);

    await woInput.fill("22222222-2222-2222-2222-222222222222");
    await page.locator('input[placeholder*="1500"]').fill("8000");
    await page.locator("select").selectOption("labor");
    await page.locator("textarea").fill("test");
    await page.locator('input[placeholder*="SoD"]').fill(APPROVER_UUID);

    const submitBtn = page.getByRole("button", { name: "建立", exact: true });
    await expect(submitBtn).toBeEnabled({ timeout: 5000 });
    await submitBtn.click();

    await expect(page.locator("textarea")).toBeVisible({ timeout: 5000 });

    const errorBox = page.locator(".border-red-200.bg-red-50").first();
    await expect(errorBox).toBeVisible({ timeout: 5000 });
    await expect(errorBox).toContainText(/REFUND_CLASS_INVALID|422/);
  });
});
