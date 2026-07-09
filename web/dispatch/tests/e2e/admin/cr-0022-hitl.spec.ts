/**
 * web/tests/e2e/admin/cr-0022-hitl.spec.ts —
 * CR-0022 LINE→工單 HITL 前端流程 E2E（mock-based，對齊 problem-cards.spec.ts 範式）。
 *
 * 對應 CIA §6 TC-e2e-line-to-wo + ADR-0112。涵蓋：
 *   1. /problem-cards 篩 source=ai_line → AI 草擬卡顯「AI 草擬」badge + 缺漏欄位 hint。
 *   2. 問題卡詳情頁「開單」→ ConvertModal：服務地址必填（空則「確認開單」disabled），
 *      填地址送出 → convert-to-work-order 帶 customer_address body（修 422 缺口的回歸守線）。
 *
 * 透過 page.route() mock API + injectAdminSession 注入假 JWT。標 @wip（本機無真 DB + login）。
 */

import { test, expect, Page } from "@playwright/test";

const TENANT_ID = "00000000-0000-0000-0000-000000000001";
const PC_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";

// AI 草擬卡（source=ai_line、缺品牌/型號、待補欄位 hint）
const AI_DRAFT_CARD = {
  id: PC_ID,
  conversation_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
  brand: "",
  model: "",
  symptom: "門打不開請派師傅",
  status: "draft",
  urgency: "high",
  category: "其他",
  media_urls: [],
  created_at: "2026-06-14T09:00:00Z",
  updated_at: "2026-06-14T09:00:00Z",
  source: "ai_line",
  ai_missing_fields: ["brand", "model", "location"],
};

async function injectAdminSession(page: Page) {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = btoa(
    JSON.stringify({
      sub: "00000000-0000-0000-0000-000000000099",
      role: "admin",
      tenant_id: TENANT_ID,
      type: "access",
      jti: "test-jti-cr0022",
    })
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
// Test 1：佇列 AI 草擬 badge + 缺漏 hint
// ---------------------------------------------------------------------------

test.describe("@wip CR-0022 AI 草擬佇列", () => {
  test("source=ai_line 卡顯示「AI 草擬」badge + 待補欄位 hint", async ({ page }) => {
    await injectAdminSession(page);

    await page.route("**/tenants/*/problem-cards*", async (route) => {
      if (route.request().method() !== "GET") return route.continue();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [AI_DRAFT_CARD], next_cursor: null, has_more: false }),
      });
    });

    await page.goto("/problem-cards");
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 「AI 草擬」badge —— 用 span + exact 比對，避免誤抓篩選下拉的
    // <option>「AI 草擬（待轉工單）」（隱藏元素）。
    await expect(
      page.locator("span").getByText("AI 草擬", { exact: true }).first(),
    ).toBeVisible({ timeout: 10000 });
    // 缺漏欄位 hint（只出現在列，不在下拉）
    await expect(page.getByText("待補：", { exact: false }).first()).toBeVisible({ timeout: 10000 });
  });
});

// ---------------------------------------------------------------------------
// Test 2：開單 address modal — 地址必填 + convert 帶 customer_address
// ---------------------------------------------------------------------------

test.describe("@wip CR-0022 開單 address modal", () => {
  test("AI 草擬卡開單必填地址，convert 帶 customer_address", async ({ page }) => {
    await injectAdminSession(page);

    // 詳情頁卡片 = 已確認的 ai_line 卡（confirmed → 顯示「開單」）
    const confirmedCard = { ...AI_DRAFT_CARD, status: "confirmed" };
    let convertBody: Record<string, unknown> | null = null;

    await page.route("**/tenants/*/problem-cards/**", async (route) => {
      const req = route.request();
      const url = req.url();
      if (req.method() === "POST" && url.includes("/convert-to-work-order")) {
        convertBody = JSON.parse(req.postData() || "{}");
        return route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({ data: { id: "eeeeeeee-0000-4000-8000-000000000001", status: "inquiring" } }),
        });
      }
      if (req.method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ data: confirmedCard }),
        });
      }
      return route.continue();
    });

    await page.goto(`/problem-cards/${PC_ID}`);
    await expect(page.locator("h1").first()).toBeVisible({ timeout: 15000 });

    // 點「開單」→ ConvertModal 開啟
    await page.locator('button:has-text("開單")').first().click();
    await expect(page.locator('text=轉為工單').first()).toBeVisible({ timeout: 5000 });

    // 地址空 → 「確認開單」disabled
    const submit = page.locator('button:has-text("確認開單")');
    await expect(submit).toBeDisabled();

    // 填服務地址 → 啟用 → 送出
    await page.locator('input[placeholder*="林口"]').fill("新北市林口區文化二路一段 99 號");
    await expect(submit).toBeEnabled();
    await submit.click();

    // convert 必須帶 customer_address（修 422 缺口的回歸守線）
    await expect.poll(() => convertBody, { timeout: 8000 }).not.toBeNull();
    const body = convertBody!;
    expect(body).toHaveProperty("customer_address");
    expect(String(body.customer_address)).toContain("林口");
  });
});
