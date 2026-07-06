/**
 * ui-sweep.spec.ts — 全 admin-shell 靜態路由互動健檢 sweep。
 *
 * 對應 goal「Playwright 測試畫面上所有按鈕/篩選/滑動是否正常」。
 *
 * 每條路由跑三項：
 *   1. render：status < 500、無 pageerror、無 Next error overlay。
 *   2. 捲軸健康：<main> 不可撐破 viewport 又無法內部捲動（min-h-0 bug 的偵測）。
 *      —— bug 症狀：main 底邊超出視窗底部，但 main 自身 overflow 不捲（滾輪失效）。
 *   3. 互動清點：button / enabled / disabled / select / input 數量，第一個 select 變更不 crash。
 *
 * 設計：單一 test 內 login 一次後 loop 全路由，避免每路由重登。
 * viewport 固定 1280x720（桌機）以穩定捲軸量測。
 */

import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.fill('input[type="email"]', "test@lock-ai.com");
  await page.fill('input[type="password"]', "changeme123");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"), { timeout: 15_000 });
}

// 所有走 admin shell（Sidebar + Header + <main>）的靜態路由
const ROUTES = [
  "/dashboard",
  "/conversations",
  "/problem-cards",
  "/work-orders",
  "/work-orders/kanban",
  "/work-orders/map",
  "/technicians",
  "/notifications",
  "/settings",
  // knowledge-base
  "/knowledge-base",
  "/knowledge-base/cases",
  "/knowledge-base/cases/new",
  "/knowledge-base/family-reviews",
  "/knowledge-base/manuals",
  "/knowledge-base/sop-drafts",
  // accounting
  "/accounting",
  "/accounting/invoices",
  "/accounting/revenue",
  "/accounting/vouchers",
  // admin
  "/admin/dispatch-queue",
  "/admin/dispatch-manual",
  "/admin/customers",
  "/admin/customers/new",
  "/admin/inventory",
  "/admin/material-requests",
  "/admin/warranty-claims",
  "/admin/disputes",
  "/admin/refunds",
  "/admin/roles",
  "/admin/audit-events",
  "/admin/approval-inbox",
  "/admin/technicians-lifecycle",
  "/admin/brand-b2b",
  "/admin/gdpr-forget-queue",
  "/admin/ai-governance",
  "/admin/sop-feedback",
  "/admin/rma-quality",
  "/admin/api-status",
  "/admin/sentiment-alerts",
  "/admin/schedule-requests",
  "/admin/warranty-claims",
  "/admin/knowledge-base/sop-performance",
  "/admin/reports/kpi",
  "/admin/reports/revenue",
  "/admin/reports/technician-ranking",
];

type RouteReport = {
  path: string;
  status: number;
  buttons: number;
  enabled: number;
  disabled: number;
  selects: number;
  inputs: number;
  scrollBug: boolean;
  mainBottom: number;
  scrollOk: string;
  pageErrors: string[];
  consoleErrors: string[];
};

// 偵測 min-h-0 捲軸 bug（通用版，不限 <main>）：
// 任一宣告 overflow-y:auto/scroll 的容器,底邊超出視窗,但自身無法內部捲動
// （scrollHeight≈clientHeight,因缺 min-h-0 被撐成內容高度）,且視窗本身也無法
// 捲動把它帶進視野 → 內容被困、滾輪失效。
const SCROLL_PROBE = `(() => {
  const vh = window.innerHeight;
  const docScrollable = document.documentElement.scrollHeight > window.innerHeight + 8;
  const all = Array.from(document.querySelectorAll('main, div, section'));
  const trapped = [];
  for (const el of all) {
    const s = getComputedStyle(el);
    const canScroll = s.overflowY === 'auto' || s.overflowY === 'scroll';
    if (!canScroll) continue;
    const rect = el.getBoundingClientRect();
    if (rect.height < 200) continue;                       // 忽略小元件
    const overflowsViewport = rect.bottom > vh + 24;        // 底邊明顯超出視窗
    const notScrollable = el.scrollHeight <= el.clientHeight + 8; // 自身不可捲
    if (overflowsViewport && notScrollable && !docScrollable) {
      trapped.push({
        tag: el.tagName.toLowerCase(),
        cls: String(el.className).slice(0, 50),
        bottom: Math.round(rect.bottom),
      });
    }
  }
  const scrollBug = trapped.length > 0;
  const main = document.querySelector('main');
  return {
    scrollBug,
    mainBottom: main ? Math.round(main.getBoundingClientRect().bottom) : 0,
    trapped: trapped.slice(0, 2),
    note: scrollBug
      ? ('內容被困:' + trapped.map(t => t.tag + '.' + t.cls.split(' ')[0]).join(','))
      : (docScrollable ? '視窗可捲 OK' : '內容在視窗內/容器可捲'),
  };
})()`;

test("全 admin-shell 路由 render + 捲軸 + 按鈕/篩選 互動健檢", async ({ page }) => {
  test.setTimeout(300_000);
  await page.setViewportSize({ width: 1280, height: 720 });
  await login(page);

  const reports: RouteReport[] = [];

  for (const path of ROUTES) {
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];
    const onConsole = (msg: import("@playwright/test").ConsoleMessage) => {
      if (msg.type() !== "error") return;
      const t = msg.text();
      if (
        t.includes("Failed to fetch") ||
        t.includes("ERR_CONNECTION") ||
        t.includes("net::") ||
        t.includes("status of 401") ||
        t.includes("status of 403") ||
        t.includes("status of 404") ||
        t.includes("Failed to load resource")
      )
        return;
      consoleErrors.push(t);
    };
    const onPageError = (err: Error) => pageErrors.push(err.message);
    page.on("console", onConsole);
    page.on("pageerror", onPageError);

    let status = 0;
    try {
      const res = await page.goto(path, { waitUntil: "domcontentloaded", timeout: 20_000 });
      status = res?.status() ?? 0;
      await page.waitForLoadState("networkidle", { timeout: 8_000 }).catch(() => {});
    } catch {
      status = -1;
    }

    // Next.js error overlay / error boundary 偵測
    const overlayCount = await page
      .locator('text=/Unhandled Runtime Error|Application error|這個頁面發生錯誤/i')
      .count()
      .catch(() => 0);
    if (overlayCount > 0) pageErrors.push("Next error overlay/boundary 出現");

    const probe = (await page.evaluate(SCROLL_PROBE).catch(() => null)) as
      | { scrollBug: boolean; mainBottom: number; note: string }
      | null;

    const buttons = await page.locator("button").count().catch(() => 0);
    const enabled = await page.locator("button:not([disabled])").count().catch(() => 0);
    const disabled = await page.locator("button[disabled]").count().catch(() => 0);
    const selects = await page.locator("select").count().catch(() => 0);
    const inputs = await page.locator("input").count().catch(() => 0);

    // 第一個 select 變更不 crash（篩選器 smoke）
    if (selects > 0) {
      const sel = page.locator("select").first();
      const opts = await sel.locator("option").count().catch(() => 0);
      if (opts > 1) {
        await sel.selectOption({ index: 1 }).catch(() => {});
        await page.waitForLoadState("networkidle", { timeout: 5_000 }).catch(() => {});
      }
    }

    reports.push({
      path,
      status,
      buttons,
      enabled,
      disabled,
      selects,
      inputs,
      scrollBug: probe?.scrollBug ?? false,
      mainBottom: probe?.mainBottom ?? 0,
      scrollOk: probe?.note ?? "n/a",
      pageErrors: [...pageErrors],
      consoleErrors: [...consoleErrors],
    });

    page.off("console", onConsole);
    page.off("pageerror", onPageError);
  }

  // ── 報表輸出 ──────────────────────────────────────────────
  console.log("\n=== UI SWEEP REPORT (" + reports.length + " routes) ===");
  console.log(
    "Path".padEnd(44) + "stat | btn | en | dis | sel | inp | scroll",
  );
  for (const r of reports) {
    const flag = r.scrollBug ? "❌捲軸" : r.pageErrors.length || r.consoleErrors.length ? "⚠️err" : "✓";
    console.log(
      r.path.padEnd(44) +
        `${String(r.status).padStart(4)} | ${String(r.buttons).padStart(3)} | ${String(r.enabled).padStart(2)} | ${String(r.disabled).padStart(3)} | ${String(r.selects).padStart(3)} | ${String(r.inputs).padStart(3)} | ${flag} ${r.scrollOk}`,
    );
  }

  const scrollBugs = reports.filter((r) => r.scrollBug);
  const errPages = reports.filter((r) => r.pageErrors.length || r.consoleErrors.length);
  const status5xx = reports.filter((r) => r.status >= 500 || r.status === -1);

  console.log("\n--- 捲軸 bug 頁 ---");
  scrollBugs.forEach((r) => console.log(`  ${r.path} (main bottom=${r.mainBottom})`));
  console.log("--- error 頁 ---");
  errPages.forEach((r) =>
    console.log(`  ${r.path}: ${[...r.pageErrors, ...r.consoleErrors].join(" | ")}`),
  );
  console.log("--- 5xx/載入失敗 ---");
  status5xx.forEach((r) => console.log(`  ${r.path} → ${r.status}`));

  expect(status5xx.map((r) => `${r.path}→${r.status}`), "5xx/載入失敗路由").toHaveLength(0);
  expect(scrollBugs.map((r) => r.path), "捲軸 bug 路由").toHaveLength(0);
  expect(
    errPages.map((r) => `${r.path}: ${[...r.pageErrors, ...r.consoleErrors].join(",")}`),
    "page/console error 路由",
  ).toHaveLength(0);
});
