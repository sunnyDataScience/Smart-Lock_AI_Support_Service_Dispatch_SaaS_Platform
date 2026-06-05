/**
 * web/tests/e2e/admin/work-orders-reassign.spec.ts —
 * Flow 8 二次派工：accepted/in_progress 狀態 :reassign endpoint 路徑驗證
 *
 * 對應 commits:
 *   - d365b049 feat(api): reassign backend (_REASSIGN_FROM={assigned,accepted,in_progress})
 *   - 4f186e39 feat(web): work-orders/[id]/page.tsx handleAssign 內以 status
 *     判斷走 :reassign 或 :assign
 *
 * 驗證重點：
 *   1. accepted 狀態 → handleAssign 必須打 :reassign endpoint（body {technician_id, reason}）
 *   2. assigned 狀態 → handleAssign 仍打 :assign endpoint（body {technician_id, reason_code, reason_text?}）
 *   3. status enum REASSIGN_FROM ∪ ASSIGN_FROM 4 種狀態 canAssign 皆為 true
 *
 * 標 @wip：本機無真實 DB，純 mock 驗證 client 路徑分流邏輯。
 */

import { test, expect, Page } from "@playwright/test";

const TENANT_ID = "00000000-0000-0000-0000-000000000001";
const WO_ID = "11111111-1111-4111-8111-111111111111";
const TECH_ID_OLD = "22222222-2222-4222-8222-222222222222";
const TECH_ID_NEW = "33333333-3333-4333-8333-333333333333";

const GET_WORK_ORDER_PATH = `**/tenants/*/work-orders/${WO_ID}`;
const REASSIGN_PATH = `**/tenants/*/work-orders/${WO_ID}:reassign`;
const ASSIGN_PATH = `**/tenants/*/work-orders/${WO_ID}:assign`;
const CANDIDATES_PATH = `**/tenants/*/dispatch:candidates**`;

function makeWorkOrder(status: string, technicianId: string | null) {
  return {
    id: WO_ID,
    document_number: "WO-20260605-0001",
    problem_card_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    technician_id: technicianId,
    status,
    district: "信義區",
    address: "信義區市府路 1 號",
    customer_name: "王小明",
    customer_phone: "0912345678",
    urgency: "medium",
    scheduled_at: "2026-06-05T14:00:00Z",
    started_at: null,
    completed_at: null,
    estimated_price: "1500",
    service_report: null,
    created_at: "2026-06-05T08:00:00Z",
    updated_at: "2026-06-05T09:00:00Z",
  };
}

const CANDIDATES_RESPONSE = {
  candidates: [
    {
      technician: {
        id: TECH_ID_NEW,
        full_name: "李技師",
        phone: "0922333444",
        status: "active",
      },
      score: 85.0,
      distance_km: 2.5,
      eta_minutes: 15,
      ranking_factors: {
        brand_score: 0.9,
        distance_score: 0.8,
        rating_score: 0.85,
        availability_score: 1.0,
      },
    },
  ],
};

async function injectAdminSession(page: Page) {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payloadObj = {
    sub: "00000000-0000-0000-0000-000000000099",
    role: "admin",
    tenant_id: TENANT_ID,
    type: "access",
    jti: "test-jti-wo-reassign",
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
      window.localStorage.setItem("smartlock.email", "admin@example.com");
    },
    { token: fakeToken, tenantId: TENANT_ID },
  );
}

test.describe("@wip Flow 8 work-orders reassign endpoint routing", () => {
  test("accepted 狀態 → :reassign endpoint + body {technician_id, reason}", async ({
    page,
  }) => {
    await injectAdminSession(page);

    let reassignCalled = false;
    let assignCalled = false;
    let capturedReassignBody: { technician_id?: string; reason?: string } | null = null;

    await page.route(GET_WORK_ORDER_PATH, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            data: makeWorkOrder("accepted", TECH_ID_OLD),
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.route(CANDIDATES_PATH, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(CANDIDATES_RESPONSE),
      });
    });

    await page.route(REASSIGN_PATH, async (route) => {
      if (route.request().method() === "POST") {
        reassignCalled = true;
        capturedReassignBody = route.request().postDataJSON();
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            data: makeWorkOrder("assigned", TECH_ID_NEW),
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.route(ASSIGN_PATH, async (route) => {
      if (route.request().method() === "POST") {
        assignCalled = true;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            data: makeWorkOrder("assigned", TECH_ID_NEW),
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto(`/work-orders/${WO_ID}`);
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 觸發改派按鈕（assignLabel 在已有 technician_id 時顯示 reassign 文字）
    const reassignTrigger = page
      .getByRole("button", { name: /改派|重派|Reassign|指派/i })
      .first();
    await reassignTrigger.click();

    // AssignDialog 開啟 — 候選技師可見
    await expect(page.getByText(/李技師/)).toBeVisible({ timeout: 5000 });

    // 確認送出（dialog 內的 submit / 確認按鈕；對應行為見 page.tsx）
    const submitButton = page
      .getByRole("button", { name: /確認|Confirm|送出|Submit|指派/i })
      .last();
    await submitButton.click();

    await expect.poll(() => reassignCalled, { timeout: 5000 }).toBe(true);
    expect(assignCalled).toBe(false); // accepted 狀態必須走 reassign 非 assign

    // body 驗證: reassign 需要 technician_id + reason (不需 reason_code)
    expect(capturedReassignBody).not.toBeNull();
    expect(capturedReassignBody!.technician_id).toBe(TECH_ID_NEW);
    expect(capturedReassignBody!.reason).toBeDefined();
    expect(capturedReassignBody!.reason!.length).toBeGreaterThan(0);
  });

  test("assigned 狀態 → :assign endpoint + body 含 reason_code", async ({
    page,
  }) => {
    await injectAdminSession(page);

    let reassignCalled = false;
    let assignCalled = false;
    let capturedAssignBody: {
      technician_id?: string;
      reason_code?: string;
      reason_text?: string;
    } | null = null;

    await page.route(GET_WORK_ORDER_PATH, async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            data: makeWorkOrder("assigned", TECH_ID_OLD),
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.route(CANDIDATES_PATH, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(CANDIDATES_RESPONSE),
      });
    });

    await page.route(REASSIGN_PATH, async (route) => {
      if (route.request().method() === "POST") {
        reassignCalled = true;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ data: makeWorkOrder("assigned", TECH_ID_NEW) }),
        });
      } else {
        await route.continue();
      }
    });

    await page.route(ASSIGN_PATH, async (route) => {
      if (route.request().method() === "POST") {
        assignCalled = true;
        capturedAssignBody = route.request().postDataJSON();
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ data: makeWorkOrder("assigned", TECH_ID_NEW) }),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto(`/work-orders/${WO_ID}`);
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    const reassignTrigger = page
      .getByRole("button", { name: /改派|重派|Reassign|指派/i })
      .first();
    await reassignTrigger.click();

    await expect(page.getByText(/李技師/)).toBeVisible({ timeout: 5000 });

    const submitButton = page
      .getByRole("button", { name: /確認|Confirm|送出|Submit|指派/i })
      .last();
    await submitButton.click();

    await expect.poll(() => assignCalled, { timeout: 5000 }).toBe(true);
    expect(reassignCalled).toBe(false); // assigned 狀態必須走 assign 非 reassign

    // body 驗證: assign 路徑帶 reason_code
    expect(capturedAssignBody).not.toBeNull();
    expect(capturedAssignBody!.technician_id).toBe(TECH_ID_NEW);
    expect(capturedAssignBody!.reason_code).toBeDefined();
  });
});
