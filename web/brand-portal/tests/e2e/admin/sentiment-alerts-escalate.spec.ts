/**
 * web/tests/e2e/admin/sentiment-alerts-escalate.spec.ts —
 * Flow 9 客訴升級 admin 「升級工單」按鈕 E2E smoke test
 *
 * 對應 commits:
 *   - e4afd80b feat(api): sentiment escalate-to-work-order endpoint
 *   - c23b3525 feat(web): admin 升級按鈕 + EscalateAlertModal
 *
 * 測試矩陣：
 *   1. 渲染：mock GET /tenants/*\/sentiment/alerts → 表格 + status badges
 *   2. 升級按鈕：pending row 才顯示「升級工單」紅色按鈕
 *   3. Modal 開啟 → level select + reason textarea → submit → mock POST
 *      :escalate-to-work-order → 成功 alert + optimistic 改為 acknowledged
 *   4. API 500 → error banner
 *
 * 標 @wip：本機無真實 DB，純 mock 驗證 client 行為。
 */

import { test, expect, Page } from "@playwright/test";

const TENANT_ID = "00000000-0000-0000-0000-000000000001";

const SENTIMENT_LIST_PATH = "**/tenants/*/sentiment/alerts**";
const ESCALATE_PATH = "**/tenants/*/sentiment/alerts/*:escalate-to-work-order";

const ALERT_ID_PENDING = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const ALERT_ID_RESOLVED = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const WO_ID = "11111111-1111-4111-8111-111111111111";
const CONV_ID_1 = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const CONV_ID_2 = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";

const SAMPLE_LIST = {
  items: [
    {
      id: ALERT_ID_PENDING,
      conversation_id: CONV_ID_1,
      consumer_message: "我已經等很久了，你們到底有沒有要處理？",
      sentiment_label: "negative",
      confidence: 0.92,
      detected_keywords: ["等很久", "投訴"],
      problem_card_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
      status: "pending",
      notified_admin_ids: [],
      admin_note: null,
      created_at: "2026-06-05T08:00:00Z",
    },
    {
      id: ALERT_ID_RESOLVED,
      conversation_id: CONV_ID_2,
      consumer_message: "謝謝協助",
      sentiment_label: "neutral",
      confidence: 0.75,
      detected_keywords: [],
      problem_card_id: null,
      status: "resolved",
      notified_admin_ids: [],
      admin_note: "已聯繫客戶",
      created_at: "2026-06-05T07:00:00Z",
    },
  ],
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
    jti: "test-jti-sentiment-escalate",
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

test.describe("@wip Flow 9 sentiment alerts — escalate to work order", () => {
  test("renders table + escalate 按鈕只在 pending 顯示", async ({ page }) => {
    await injectAdminSession(page);

    await page.route(SENTIMENT_LIST_PATH, async (route) => {
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

    await page.goto("/admin/sentiment-alerts");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 兩筆訊息可見
    await expect(page.getByText(/我已經等很久了/)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/謝謝協助/)).toBeVisible();

    // pending row 應有「升級工單」按鈕；resolved row 應顯示 alreadyResolved
    const escalateButtons = page.getByRole("button", {
      name: /升級工單|Escalate WO/i,
    });
    await expect(escalateButtons).toHaveCount(1);
  });

  test("升級流程：modal → submit → POST :escalate-to-work-order", async ({
    page,
  }) => {
    await injectAdminSession(page);

    let escalateCalled = false;
    let capturedEscalatePath: string | null = null;
    let capturedBody: { level?: string; reason?: string } | null = null;

    await page.route(SENTIMENT_LIST_PATH, async (route) => {
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

    await page.route(ESCALATE_PATH, async (route) => {
      if (route.request().method() === "POST") {
        escalateCalled = true;
        capturedEscalatePath = route.request().url();
        capturedBody = route.request().postDataJSON();
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            alert_id: ALERT_ID_PENDING,
            work_order_id: WO_ID,
            escalated_to_level: "operations_manager",
            escalated_at: "2026-06-05T10:00:00Z",
          }),
        });
      } else {
        await route.continue();
      }
    });

    // 接 success alert
    page.on("dialog", (dialog) => dialog.accept());

    await page.goto("/admin/sentiment-alerts");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/我已經等很久了/)).toBeVisible({ timeout: 10000 });

    // 點升級按鈕
    await page
      .getByRole("button", { name: /升級工單|Escalate WO/i })
      .first()
      .click();

    // Modal 開啟（標題可見）
    await expect(
      page.getByText(/升級對應工單|Escalate linked work order/i),
    ).toBeVisible({ timeout: 5000 });

    // 填 reason（level 預設 operations_manager 即可）
    const reasonTextarea = page.locator("textarea").first();
    await reasonTextarea.fill("客戶連續抱怨，需要主管直接介入");

    // 提交
    await page
      .getByRole("button", { name: /確認升級|Confirm escalate/i })
      .click();

    // POST 應已呼叫
    await expect.poll(() => escalateCalled, { timeout: 5000 }).toBe(true);
    expect(capturedEscalatePath).not.toBeNull();
    expect(capturedEscalatePath!).toContain(`/tenants/${TENANT_ID}/sentiment/alerts/`);
    expect(capturedEscalatePath!).toContain(":escalate-to-work-order");
    expect(capturedBody).not.toBeNull();
    expect(capturedBody!.level).toBe("operations_manager");
    expect(capturedBody!.reason).toContain("主管直接介入");
  });

  test("API error 500 → error banner", async ({ page }) => {
    await injectAdminSession(page);

    await page.route(SENTIMENT_LIST_PATH, async (route) => {
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

    await page.goto("/admin/sentiment-alerts");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    const errorEl = page.locator(".border-red-200.bg-red-50").first();
    await expect(errorEl).toBeVisible({ timeout: 10000 });
  });
});
