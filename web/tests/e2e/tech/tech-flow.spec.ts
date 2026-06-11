/**
 * web/tests/e2e/tech/tech-flow.spec.ts — 技師手機端 user flow E2E（S2：師傅接案 → 到場 → 完工）
 *
 * 對應 S2 子流程頁：/tech-login、/pool、/my-orders、/my-orders/[id]、
 * 子流程 /signature 等。本 spec 以「真實 backend（localhost:8001）+ 真實 demo 種子」
 * happy-path 走查為主，不打不可逆寫入（接單 / 完工 / 簽章提交）以免污染 demo 資料。
 *
 * 跑法（環境已就緒，勿啟動新 server）：
 *   cd web && USE_EXISTING_SERVER=1 BASE_URL=http://localhost:3000 \
 *     npx playwright test tech-flow --project=tech --reporter=list
 *
 * 策略：
 *   1. 真實 UI 登入 happy-path：開 /tech-login（AuthGuard PUBLIC_PATHS 已含 /tech-login，
 *      未登入可達、不再被踢去 admin /login）→ 填 demo-tech 帳密 → 送出 →
 *      loginTechnician() 打 /api/v1/technicians/login → 導向技師首頁 /pool，
 *      localStorage 寫入 access_token。（兩個歷史 bug PROD-BUG-A / PROD-BUG-B 均已由主程式修復。）
 *   2. 後續頁面走查（pool / my-orders / detail / signature）以「技師專用通道取得的有效
 *      token 注入 localStorage」做 per-test session setup，讓每個頁面 test 獨立、
 *      不串接 UI 登入 test（測試隔離），主要斷言為「乾淨渲染、不 crash」。
 *   3. demo 環境目前 0 筆工單，pool / my-orders 走 empty-state；spec 只驗 empty-state
 *      乾淨呈現（不硬湊工單）。若未來有指派工單，detail/signature 斷言仍成立。
 */

import { test, expect, Page } from "@playwright/test";

const BASE_URL = process.env.BASE_URL ?? "http://localhost:3000";
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";
const TENANT_ID = "00000000-0000-0000-0000-000000000001";

const TECH_EMAIL = "demo-tech@example.com";
const TECH_PASSWORD = "techpass123";

// localStorage keys（對齊 src/lib/api.ts STORAGE_KEYS）
const STORAGE = {
  access: "smartlock.access_token",
  refresh: "smartlock.refresh_token",
  tenant: "smartlock.tenant_id",
  email: "smartlock.email",
} as const;

/**
 * 從技師專用認證通道 (/api/v1/technicians/login) 取得有效 token，供後續頁面走查的
 * per-test session setup 用（與 UI 登入打的是同一個端點；此處走 API 直取是為了
 * 讓每個頁面 test 獨立、不重跑完整 UI 登入流程）。
 * 回傳 null 表示這條通道拿不到 token（環境/種子問題），由呼叫端決定 skip。
 */
async function fetchTechTokens(
  page: Page,
): Promise<{ access: string; refresh: string } | null> {
  const res = await page.request.post(
    `${API_BASE}/api/v1/technicians/login`,
    {
      data: { email: TECH_EMAIL, password: TECH_PASSWORD },
      headers: { "Content-Type": "application/json" },
      failOnStatusCode: false,
    },
  );
  if (!res.ok()) return null;
  const body = await res.json().catch(() => null);
  const data = body?.data;
  if (!data?.access_token) return null;
  return {
    access: data.access_token,
    refresh: data.refresh_token ?? data.access_token,
  };
}

/**
 * 在 localStorage 注入技師 session，讓 /pool、/my-orders 等頁面以真實 token 打 API。
 * 必須在 page.goto 之前注入（用 addInitScript 確保每次導頁都帶上）。
 */
async function injectTechSession(
  page: Page,
  tokens: { access: string; refresh: string },
) {
  await page.addInitScript(
    ([s, t, tid, email]) => {
      window.localStorage.setItem(s.access, t.access);
      window.localStorage.setItem(s.refresh, t.refresh);
      window.localStorage.setItem(s.tenant, tid);
      window.localStorage.setItem(s.email, email);
    },
    [STORAGE, tokens, TENANT_ID, TECH_EMAIL] as const,
  );
}

/** 收集 page 上的 console error / pageerror，供 crash 斷言用。 */
function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const txt = msg.text();
      // 過濾掉預期的 API 401 / network error log（無 token / 後端錯誤非 crash）
      if (
        !/401|Unauthenticated|Failed to load resource|favicon/i.test(txt)
      ) {
        errors.push(`console.error: ${txt}`);
      }
    }
  });
  return errors;
}

test.describe("技師手機端 — S2 接案→到場→完工 flow", () => {
  // ---------------------------------------------------------------------------
  // 1) tech-login 頁可達性（手機 viewport）
  //
  // ✅ PROD-BUG-A 已修復：AuthGuard PUBLIC_PATHS 現含 "/tech-login"，未登入訪客
  //    可正常開 /tech-login，不再被 router.replace("/login") 踢去 admin 登入頁。
  // ---------------------------------------------------------------------------
  test("未登入可正常開 /tech-login，登入表單乾淨渲染、不被踢去 /login", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    const response = await page.goto("/tech-login");
    expect(response?.status(), "回應不應 5xx").toBeLessThan(500);

    // 等 AuthGuard 的 useEffect 跑完（確認不會被導走）
    await page.waitForTimeout(2000);

    // 修復後：停在 /tech-login，未被導向 admin /login
    await expect(page).toHaveURL(/\/tech-login(\?|$)/);

    // 登入表單應渲染：identifier 輸入框、password 輸入框、送出按鈕
    await expect(page.locator('input[type="text"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();

    expect(errors, errors.join("\n")).toEqual([]);
  });

  // ---------------------------------------------------------------------------
  // 2) 真實 UI 登入 happy-path（PROD-BUG-A + PROD-BUG-B 均已修復）
  //
  // ✅ PROD-BUG-B 已修復：loginTechnician() 改打 /api/v1/technicians/login（技師庫），
  //    demo-tech 帳密通過、回 technician role token，導向技師首頁 /pool。
  // ---------------------------------------------------------------------------
  test("UI 登入 happy-path：填 demo-tech 帳密 → 導向 /pool、localStorage 有 access_token", async ({
    page,
  }) => {
    const errors = collectErrors(page);
    await page.goto("/tech-login");
    await page.waitForTimeout(1000);
    await expect(page).toHaveURL(/\/tech-login(\?|$)/);

    // 填表單（identifier=email、password）
    await page.locator('input[type="text"]').fill(TECH_EMAIL);
    await page.locator('input[type="password"]').fill(TECH_PASSWORD);

    // 送出登入（submit button 文字為「登入」，disabled 條件已隨 fill 解除）
    await page.locator('button[type="submit"]').click();

    // 登入成功 → 導向技師首頁 /pool（page.tsx: router.replace("/pool")）
    await expect(page).toHaveURL(/\/pool(\?|$)/, { timeout: 15_000 });

    // 案件池標題渲染，證明確實進到技師端（帶有效 token）
    await expect(page.getByRole("heading", { name: "案件池" })).toBeVisible({
      timeout: 10_000,
    });

    // localStorage 應已寫入 access_token（loginTechnician → auth.setTokens）
    const accessToken = await page.evaluate(
      (k) => window.localStorage.getItem(k),
      STORAGE.access,
    );
    expect(accessToken, "登入後 localStorage 應有 access_token").toBeTruthy();

    expect(errors, errors.join("\n")).toEqual([]);
  });

  // ---------------------------------------------------------------------------
  // 以下測試用「技師專用通道」取得的有效 token 注入 session，繞過上述登入 bug，
  // 續走 pool / my-orders / detail / signature 各頁，驗證 happy-path 渲染。
  // ---------------------------------------------------------------------------
  test.describe("已登入技師 — 頁面走查（注入有效 session）", () => {
    let tokens: { access: string; refresh: string } | null = null;

    test.beforeEach(async ({ page }) => {
      tokens = await fetchTechTokens(page);
      test.skip(
        !tokens,
        "技師專用認證通道 (/api/v1/technicians/login) 也無法取得 token — 環境/種子問題，跳過已登入走查",
      );
      await injectTechSession(page, tokens!);
    });

    test("/pool 案件池：列表或 empty-state 乾淨渲染、可捲動、不 crash", async ({
      page,
    }) => {
      const errors = collectErrors(page);
      const res = await page.goto("/pool");
      expect(res?.status(), "/pool 不應 5xx").toBeLessThan(500);

      // 標題（sticky header）應渲染
      await expect(page.getByRole("heading", { name: "案件池" })).toBeVisible({
        timeout: 10_000,
      });

      // 等列表載入完成（loading 文字消失或 empty-state / 卡片出現）
      await page.waitForTimeout(1500);

      const cards = page.locator("article");
      const cardCount = await cards.count();
      if (cardCount > 0) {
        // 有可接工單：第一張卡應含「接受工單」按鈕（不點擊，避免接單寫入）
        await expect(
          page.getByRole("button", { name: /接受工單/ }).first(),
        ).toBeVisible();
      } else {
        // empty-state：應顯示「目前沒有可接工單」
        await expect(page.getByText("目前沒有可接工單")).toBeVisible();
      }

      // 手機 viewport 下版面不破：body 可捲動（scrollHeight ≥ clientHeight）
      const scrollable = await page.evaluate(
        () =>
          document.documentElement.scrollHeight >=
          document.documentElement.clientHeight,
      );
      expect(scrollable).toBeTruthy();

      // 底部導覽列（TechBottomNav）應存在 — 手機端核心導覽
      await expect(page.locator("nav").first()).toBeVisible();

      expect(errors, errors.join("\n")).toEqual([]);
    });

    test("/my-orders 我的工單：tab 切換 + empty-state 乾淨渲染、不 crash", async ({
      page,
    }) => {
      const errors = collectErrors(page);
      const res = await page.goto("/my-orders");
      expect(res?.status(), "/my-orders 不應 5xx").toBeLessThan(500);

      await expect(
        page.getByRole("heading", { name: "我的工單" }),
      ).toBeVisible({ timeout: 10_000 });

      // 三個 tab 應渲染
      await expect(page.getByRole("button", { name: /進行中/ })).toBeVisible();
      await expect(page.getByRole("button", { name: /待確認/ })).toBeVisible();
      await expect(page.getByRole("button", { name: /歷史/ })).toBeVisible();

      await page.waitForTimeout(1500);

      // 預設 active tab：有工單則顯示卡片連結，否則 empty-state
      const orderLinks = page.locator('a[href^="/my-orders/"]');
      const linkCount = await orderLinks.count();
      if (linkCount > 0) {
        await expect(orderLinks.first()).toBeVisible();
      } else {
        await expect(page.getByText("目前沒有進行中的工單")).toBeVisible();
        // active tab empty-state 應提供「前往案件池接單」捷徑
        await expect(
          page.getByRole("link", { name: /前往案件池接單/ }),
        ).toBeVisible();
      }

      // 切到「歷史」tab 不 crash
      await page.getByRole("button", { name: /歷史/ }).click();
      await page.waitForTimeout(500);
      // 歷史 tab 為空時顯示「沒有歷史工單」（或有卡片，二擇一不 crash）
      const historyEmpty = page.getByText("沒有歷史工單");
      const historyLinks = page.locator('a[href^="/my-orders/"]');
      const ok =
        (await historyEmpty.isVisible().catch(() => false)) ||
        (await historyLinks.count()) > 0;
      expect(ok, "歷史 tab 應顯示卡片或 empty-state").toBeTruthy();

      expect(errors, errors.join("\n")).toEqual([]);
    });

    test("有指派工單則開詳情驗動作按鈕；無則確認 empty-state（不污染寫入）", async ({
      page,
    }) => {
      await page.goto("/my-orders");
      await expect(
        page.getByRole("heading", { name: "我的工單" }),
      ).toBeVisible({ timeout: 10_000 });
      await page.waitForTimeout(1500);

      const orderLinks = page.locator('a[href^="/my-orders/"]');
      const linkCount = await orderLinks.count();

      if (linkCount === 0) {
        // demo 無指派工單 — 驗 empty-state 即可，不硬湊
        await expect(page.getByText("目前沒有進行中的工單")).toBeVisible();
        test.info().annotations.push({
          type: "note",
          description:
            "demo-tech 目前無指派工單（DB 0 筆 work order）；詳情頁動作按鈕走查略過。",
        });
        return;
      }

      // 有工單：開第一筆詳情，驗關鍵唯讀 / 安全動作可達
      const errors = collectErrors(page);
      await orderLinks.first().click();
      await expect(page).toHaveURL(/\/my-orders\/[^/]+$/, { timeout: 10_000 });

      // 詳情頁標題 + 服務地址區塊
      await expect(
        page.getByText("工單詳情").or(page.getByText("找不到工單")),
      ).toBeVisible({ timeout: 10_000 });

      // 唯讀動作：導航按鈕（外連 google maps，不寫入）應存在
      const navigate = page.getByRole("link", { name: /導航前往/ });
      const completeCta = page.getByRole("button", { name: /完工回報/ });
      // 至少其中一個關鍵動作可見（依工單狀態）
      const hasAction =
        (await navigate.isVisible().catch(() => false)) ||
        (await completeCta.isVisible().catch(() => false));
      expect(hasAction, "詳情頁應有導航 / 完工回報等關鍵動作").toBeTruthy();

      expect(errors, errors.join("\n")).toEqual([]);
    });

    test("子流程頁 /signature 可開啟、簽章 pad 渲染、不 crash", async ({
      page,
    }) => {
      const errors = collectErrors(page);
      // 用一個合法格式的假 id 直開簽章頁（純前端 canvas pad，不送出 → 不寫入）
      const fakeId = "11111111-1111-4111-8111-111111111111";
      const res = await page.goto(`/my-orders/${fakeId}/signature`);
      expect(res?.status(), "/signature 不應 5xx").toBeLessThan(500);

      // 簽章頁標題
      await expect(page.getByText("雙方電子簽章")).toBeVisible({
        timeout: 10_000,
      });

      // 技師 / 客戶兩個簽章 pad（canvas）應渲染
      await expect(page.locator("canvas")).toHaveCount(2);
      await expect(page.getByText("技師簽名")).toBeVisible();
      await expect(page.getByText("客戶簽名")).toBeVisible();

      // 提交按鈕存在但因尚未簽章而 disabled（安全：不會誤觸寫入）
      const submit = page.getByRole("button", { name: /確認簽章/ });
      await expect(submit).toBeVisible();
      await expect(submit).toBeDisabled();

      expect(errors, errors.join("\n")).toEqual([]);
    });
  });
});
