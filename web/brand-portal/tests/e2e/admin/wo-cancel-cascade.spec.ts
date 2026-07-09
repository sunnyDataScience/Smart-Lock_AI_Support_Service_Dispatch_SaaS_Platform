/**
 * web/tests/e2e/admin/wo-cancel-cascade.spec.ts —
 * 工單 6-stage 取消費分層 cascade user flow E2E（FR-0010 + FR-0052，後端 ADR-0102）
 *
 * 對應規格：
 *   - User Flow：docs/ux/user-flow-smart-lock-saas.md Flow S2（6-stage 取消費分層）
 *   - 後端端點：POST /tenants/{tenantId}/work-orders/{woId}/cancel（api/routers/cancellation.py）
 *   - 前端動作：web/src/app/work-orders/[id]/page.tsx → CancelModal + handleCancel
 *
 * 偵察結論（撰寫時實際確認）：
 *   - 前端「取消工單」UI 完整存在：CANCEL_FROM 11 種狀態顯示取消按鈕 →
 *     CancelModal 含「取消原因分類」下拉（11 個 reason code，涵蓋 S1~S5 + 師傅主動 +
 *     系統取消 + 平台取消）、「發起方」、「覆核主管 ID（SoD）」、「善意豁免」、「備註」。
 *   - 送出走 tenant-scoped v2 端點 + SoD headers（X-Initiator / X-Approver），
 *     回 CancellationResult（cancellation_stage / customer_fee / travel_fee），
 *     前端以 toast 顯示「已取消（階段 {stage}）；客戶費用 NT${customerFee}、車馬費 NT${travelFee}」。
 *   - 後端健康、DB 83 工單、26 筆處於可取消狀態。
 *
 * 測試策略（避免不可逆汙染 83 筆真實工單）：
 *   - Test 1：真實 admin 登入 → 進可取消工單詳情 → 開取消 modal →
 *     驗證 6-stage 費分層 UI 完整（reason code 涵蓋 S1~S5 各 tier）。
 *     **不送出** → 不改 DB。
 *   - Test 2：真實登入 + 進詳情 → **攔截 cancel POST**（不打到後端、DB 不變）→
 *     填表送出 → 驗證 client 端 cascade 行為：正確 tenant-scoped 端點 +
 *     SoD headers + payload，以及收到後端回的分層費用後 toast 正確渲染。
 *
 * 為何攔截而非真打：取消是不可逆狀態轉移（→ cancelled），真打會永久消耗一筆 demo 工單；
 * cascade 的「分層費用 → 前端渲染」邏輯在 client，攔截即可完整覆蓋而不汙染資料。
 */

import { test, expect, Page } from "@playwright/test";

const TENANT_ID = "00000000-0000-0000-0000-000000000001";

// 真實 admin 登入（依任務指定流程，走 UI /login）
async function adminLogin(page: Page) {
  await page.goto("/login");
  await page.fill('input[type="email"]', "test@lock-ai.com");
  await page.fill('input[type="password"]', "changeme123");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"), {
    timeout: 15_000,
  });
}

// 從工單列表頁挑一筆「可取消」狀態的工單，回傳其 id。
// 用真實 API 查（透過已登入的 localStorage token），避免硬編 id 隨 seed 變動而脆裂。
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

async function pickCancellableWorkOrderId(page: Page): Promise<string> {
  const result = await page.evaluate(async ({ tenantId, apiBase }) => {
    const token = window.localStorage.getItem("smartlock.access_token");
    const res = await fetch(`${apiBase}/api/v1/work-orders?limit=100`, {
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Tenant-ID": tenantId,
      },
    });
    const json = await res.json();
    // 列表端點回 {items, next_cursor, has_more, total_count}（非 {data} 信封）
    const items: Array<{ id: string; status: string }> =
      json.items ?? json.data ?? [];
    const cancelFrom = new Set([
      "inquiring",
      "qualified",
      "quoted",
      "negotiating",
      "accepted",
      "scheduled",
      "dispatching",
      "assigned",
      "en_route",
      "arrived",
      "in_progress",
    ]);
    // 偏好 assigned（對應 S2「已派工、未出發」tier，cascade 中段最具代表性）
    const assigned = items.find((w) => w.status === "assigned");
    const any = items.find((w) => cancelFrom.has(w.status));
    return (assigned ?? any)?.id ?? null;
  }, { tenantId: TENANT_ID, apiBase: API_BASE_URL });

  if (!result) {
    throw new Error(
      "找不到任何可取消狀態的工單（DB 可能無 CANCEL_FROM 狀態資料）",
    );
  }
  return result;
}

test.describe("工單 6-stage 取消費分層 cascade（FR-0010 + FR-0052 / ADR-0102）", () => {
  test("取消 modal 呈現完整 6-stage 費分層 UI（S1~S5 tier 皆可選；不送出、不改 DB）", async ({
    page,
  }) => {
    await adminLogin(page);
    const woId = await pickCancellableWorkOrderId(page);

    await page.goto(`/work-orders/${woId}`);
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15_000 });

    // 觸發「取消工單」按鈕（CANCEL_FROM 狀態才顯示）
    const cancelTrigger = page.getByRole("button", { name: "取消工單" });
    await expect(cancelTrigger).toBeVisible({ timeout: 10_000 });
    await cancelTrigger.click();

    // CancelModal 開啟 — 標題確認
    await expect(page.getByText("取消工單", { exact: true }).last()).toBeVisible();

    // 取消原因分類下拉 = 費分層 tier 的入口
    const reasonSelect = page.locator("select").first();
    await expect(reasonSelect).toBeVisible();

    // 驗證 6-stage cascade 各 tier 對應的 reason code option 皆存在：
    //   S1 未確認報價（免費）/ S1.5 已確認未派工（免費）/ S2 已派工未出發 /
    //   S3 已出發未到場（車馬費）/ S3 到場客戶不在 / S4 到場無法施工（車馬+檢測）/
    //   S4 到場拒絕 / S5 部分施工按比例 / 師傅主動 / 系統取消 / 平台取消
    const expectedTierOptions = [
      "報價未確認前取消（S1，免費）",
      "已確認報價、未派工取消（S1.5，免費）",
      "已派工、未出發取消（S2）",
      "已出發、未到場取消（S3）",
      "師傅到場、客戶不在（S3，需存證）",
      "已到場、無法施工（S4）",
      "已到場、客戶拒絕施工（S4）",
      "已部分施工後取消（S5）",
      "師傅主動取消（客戶免費）",
      "未付款／未回覆逾時（系統取消）",
      "平台主動取消",
    ];
    for (const label of expectedTierOptions) {
      await expect(
        reasonSelect.locator("option", { hasText: label }),
      ).toHaveCount(1);
    }

    // SoD / cascade 旁路控制項也須存在：發起方、覆核主管 ID、善意豁免
    await expect(page.getByText("發起方")).toBeVisible();
    await expect(page.getByText(/覆核主管 ID/)).toBeVisible();
    await expect(page.getByText(/善意豁免/)).toBeVisible();

    // 送出鈕在未填 SoD 覆核主管前應 disabled（前端先擋 X-Approver 空白）
    const submitBtn = page.getByRole("button", { name: "確認取消" });
    await expect(submitBtn).toBeDisabled();

    // 不送出 → 關閉 modal，DB 不變
    await page.getByRole("button", { name: "返回" }).click();
  });

  test("送出取消 → client 走 tenant-scoped 端點 + SoD headers + 分層費用 toast（攔截 POST，不改 DB）", async ({
    page,
  }) => {
    await adminLogin(page);
    const woId = await pickCancellableWorkOrderId(page);

    let cancelPostCalled = false;
    let capturedBody: Record<string, unknown> | null = null;
    let capturedHeaders: Record<string, string> | null = null;

    // 攔截 6-stage cancel 端點：模擬後端回 S2（已派工未出發）分層費用，
    // 不打到後端 → DB 完全不變。
    await page.route(
      `**/tenants/*/work-orders/${woId}/cancel`,
      async (route) => {
        if (route.request().method() === "POST") {
          cancelPostCalled = true;
          capturedBody = route.request().postDataJSON();
          capturedHeaders = route.request().headers();
          await route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
              data: {
                work_order_id: woId,
                cancellation_stage: "S2",
                customer_fee: 0,
                travel_fee: 300,
                technician_penalty: null,
                reason_code: "dispatched_not_departed",
                audit_event_id: "evt-test-cancel-cascade",
              },
            }),
          });
        } else {
          await route.continue();
        }
      },
    );

    await page.goto(`/work-orders/${woId}`);
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15_000 });

    await page.getByRole("button", { name: "取消工單" }).click();
    await expect(page.locator("select").first()).toBeVisible();

    // 選 S2 tier reason code（已派工、未出發）
    await page
      .locator("select")
      .first()
      .selectOption({ label: "已派工、未出發取消（S2）" });

    // 填 SoD 覆核主管 ID（X-Approver 必填）
    await page
      .getByPlaceholder("輸入覆核主管帳號 ID")
      .fill("supervisor-e2e");

    // 送出
    const submitBtn = page.getByRole("button", { name: "確認取消" });
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // 驗證 client 確實打了 tenant-scoped cancel 端點
    await expect.poll(() => cancelPostCalled, { timeout: 8_000 }).toBe(true);

    // payload 對齊後端 CancellationRequest（reason_code + initiator_role 必填）
    expect(capturedBody).not.toBeNull();
    expect(capturedBody!.reason_code).toBe("dispatched_not_departed");
    expect(capturedBody!.initiator_role).toBeDefined();
    expect(capturedBody!.goodwill_waiver).toBe(false);

    // SoD headers（ADR-0102 require_sod_actors）
    expect(capturedHeaders).not.toBeNull();
    expect(capturedHeaders!["x-approver"]).toBe("supervisor-e2e");
    expect(capturedHeaders!["x-initiator"]).toBeDefined();

    // cascade 結果：前端拿到分層費用 → toast 顯示對應 tier 費用
    // i18n feeResult: 「已取消（階段 {stage}）；客戶費用 NT${customerFee}、車馬費 NT${travelFee}」
    await expect(
      page.getByText(/已取消（階段 S2）/),
    ).toBeVisible({ timeout: 8_000 });
    await expect(page.getByText(/車馬費 NT\$300/)).toBeVisible();
  });
});
