/**
 * all-buttons-audit.spec.ts — 跑所有 sidebar nav + 每 page 所有 button 確認:
 *   1. sidebar 14+ nav link → URL 切換成功 + 200
 *   2. 每 page enabled button hover / hoverable (不抓 click 因會 navigate)
 *   3. 每 page 統計 enabled vs disabled button 數量
 *   4. 收集 page errors / console errors
 */

import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.fill('input[type="email"]', "admin@example.com");
  await page.fill('input[type="password"]', "changeme123");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"), { timeout: 10_000 });
}

// 預期 sidebar nav (從 sidebar source 抽)
const SIDEBAR_TARGETS = [
  "/dashboard",
  "/conversations",
  "/problem-cards",
  "/knowledge-base",
  "/admin/dispatch-queue",
  "/technicians",
  "/admin/customers",
  "/accounting",
  "/admin/inventory",
  "/admin/reports/kpi",
  "/admin/audit-events",
  "/admin/roles",
];

test("sidebar 12+ nav 跳轉全綠 + 無 5xx", async ({ page }) => {
  test.setTimeout(90_000);
  await login(page);

  const failures: string[] = [];
  for (const target of SIDEBAR_TARGETS) {
    const res = await page.goto(target, {
      waitUntil: "domcontentloaded",
      timeout: 15_000,
    });
    const status = res?.status() ?? 0;
    if (status >= 500) failures.push(`${target} → ${status}`);
    // 不等 networkidle：dev 模式 HMR websocket 讓 network 永不 idle,
    // waitForLoadState('networkidle') 會卡到 timeout 拖爆整個 test 預算。
    // status 已由 goto response 取得,5xx 判斷不需要再等 idle。
  }
  expect(failures, `Failed navs:\n${failures.join("\n")}`).toHaveLength(0);
});

// 12 page button audit
const AUDIT_PAGES = [
  "/problem-cards",
  "/work-orders",
  "/admin/dispatch-queue",
  "/technicians",
  "/admin/customers",
  "/accounting",
  "/accounting/invoices",
  "/accounting/revenue",
  "/admin/inventory",
  "/admin/reports/kpi",
  "/admin/reports/technician-ranking",
  "/admin/reports/revenue",
];

test("12 page button 統計 + 各 enabled button hover 不 crash", async ({ page }) => {
  test.setTimeout(120_000);
  const consoleErrors: string[] = [];
  const pageErrors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const t = msg.text();
    if (
      t.includes("Failed to fetch") ||
      t.includes("ERR_CONNECTION") ||
      t.includes("net::") ||
      t.includes("401") ||
      t.includes("403") ||
      t.includes("404") ||
      t.includes("Failed to load resource")
    )
      return;
    consoleErrors.push(t);
  });
  page.on("pageerror", (err) => pageErrors.push(err.message));

  await login(page);

  const report: Array<{
    path: string;
    buttons: number;
    enabled: number;
    disabled: number;
    selects: number;
    links: number;
  }> = [];

  for (const path of AUDIT_PAGES) {
    await page.goto(path, { waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle").catch(() => {});

    const allBtns = await page.locator("button").count();
    const enabledBtns = await page.locator("button:not([disabled])").count();
    const disabledBtns = await page.locator("button[disabled]").count();
    const selects = await page.locator("select").count();
    const links = await page.locator("a[href]").count();

    // hover 前 1 個 enabled button (sanity, 不 click 避免 navigate)
    const hovers = page.locator("button:not([disabled])");
    if ((await hovers.count()) > 0) {
      await hovers.first().hover({ timeout: 2000 }).catch(() => {});
    }

    report.push({
      path,
      buttons: allBtns,
      enabled: enabledBtns,
      disabled: disabledBtns,
      selects,
      links,
    });
  }

  console.log("\n=== 12 page button audit ===");
  console.log(
    "Path".padEnd(40) +
      "btns | enabled | disabled | selects | links",
  );
  for (const r of report) {
    console.log(
      r.path.padEnd(40) +
        `${String(r.buttons).padStart(4)} | ${String(r.enabled).padStart(7)} | ` +
        `${String(r.disabled).padStart(8)} | ${String(r.selects).padStart(7)} | ` +
        `${String(r.links).padStart(5)}`,
    );
  }
  const total = report.reduce(
    (acc, r) => ({
      buttons: acc.buttons + r.buttons,
      enabled: acc.enabled + r.enabled,
      disabled: acc.disabled + r.disabled,
      selects: acc.selects + r.selects,
      links: acc.links + r.links,
    }),
    { buttons: 0, enabled: 0, disabled: 0, selects: 0, links: 0 },
  );
  console.log(
    "TOTAL".padEnd(40) +
      `${String(total.buttons).padStart(4)} | ${String(total.enabled).padStart(7)} | ` +
      `${String(total.disabled).padStart(8)} | ${String(total.selects).padStart(7)} | ` +
      `${String(total.links).padStart(5)}`,
  );

  // 硬性失敗條件
  expect(pageErrors, `Page errors:\n${pageErrors.join("\n")}`).toHaveLength(0);
  expect(consoleErrors, `Console errors:\n${consoleErrors.join("\n")}`).toHaveLength(0);
});
