/**
 * doc-conformance-audit.spec.ts — 以 web/docs/page-status.md 為 source of truth,
 * Playwright 跑真人操作驗證每項文件宣稱.
 *
 * 三種結果:
 *   ✅ MATCH    — 文件 ✅ + UI 啟用
 *   ⚠️ AHEAD    — 文件 ⏳ + UI 已啟用 (文件落後 code)
 *   ❌ MISSING  — 文件 ✅ + UI 不啟用或無功能
 */

import { test, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.fill('input[type="email"]', "test@lock-ai.com");
  await page.fill('input[type="password"]', "changeme123");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"));
}

type DocClaim = {
  doc: "✅" | "⏳" | "🟡";
  page: string;
  feature: string;
  selector: string; // Playwright locator (用 hasText)
  check: "enabled" | "disabled" | "visible";
};

// 從 page-status.md 提取的關鍵 claim
const CLAIMS: DocClaim[] = [
  // /admin/dispatch-queue
  { doc: "✅", page: "/admin/dispatch-queue", feature: "上方四張統計卡 (待派工/重試中/卡住/平均派工時長)", selector: "text=/待派工|重試|卡住|平均/", check: "visible" },
  { doc: "✅", page: "/admin/dispatch-queue", feature: "下方派工歷程表 (DispatchQueueTable)", selector: "text=工單編號", check: "visible" },

  // /admin/customers
  { doc: "✅", page: "/admin/customers", feature: "客戶清單 (listCustomers)", selector: "h1", check: "visible" },
  { doc: "✅", page: "/admin/customers", feature: "風險等級 filter (06-07 同步: migration 030)", selector: "select:has(option:text-is('低風險'))", check: "enabled" },
  { doc: "✅", page: "/admin/customers", feature: "偏好技師 filter (06-07 同步)", selector: "input[placeholder*='技師 UUID']", check: "enabled" },
  { doc: "✅", page: "/admin/customers", feature: "保固狀態 filter (06-07 同步)", selector: "select:has(option:text-is('保固中'))", check: "enabled" },

  // /accounting
  { doc: "✅", page: "/accounting", feature: "對帳列表 (listReconciliations)", selector: "h1, h2", check: "visible" },
  { doc: "✅", page: "/accounting", feature: "期間選擇器 (06-07 同步: client-side period)", selector: "select:has(option:text-is('最近 3 個月'))", check: "enabled" },
  { doc: "✅", page: "/accounting", feature: "批次確認 / 標記已付 (06-07 同步: batchSettlementsV2)", selector: "button:has-text('批次確認')", check: "visible" },

  // /admin/refunds
  { doc: "✅", page: "/admin/refunds", feature: "退款申請列表 (listRefundRequests)", selector: "h1", check: "visible" },

  // /admin/warranty-claims
  { doc: "✅", page: "/admin/warranty-claims", feature: "保固索賠列表 (listWarrantyClaims)", selector: "h1", check: "visible" },

  // /admin/inventory
  { doc: "✅", page: "/admin/inventory", feature: "庫存清單 (listInventory)", selector: "h1", check: "visible" },
  { doc: "✅", page: "/admin/inventory", feature: "補貨 (06-07 同步: restockInventoryV2)", selector: "button:has-text('補貨')", check: "enabled" },
  { doc: "✅", page: "/admin/inventory", feature: "編輯 (06-07 同步: updateInventoryItemV2)", selector: "button:text-is('編輯')", check: "enabled" },
  { doc: "✅", page: "/admin/inventory", feature: "異動紀錄 (06-07 同步: listInventoryTransactionsV2)", selector: "button:text-is('紀錄')", check: "enabled" },

  // /admin/reports/kpi
  { doc: "✅", page: "/admin/reports/kpi", feature: "轉換漏斗 / 異常率 / 平均處理時長", selector: "h1", check: "visible" },

  // /admin/reports/technician-ranking
  { doc: "✅", page: "/admin/reports/technician-ranking", feature: "本週/本月/本季/本年 segment (06-07 同步)", selector: "button:has-text('本週'), button:has-text('本季')", check: "visible" },
  { doc: "✅", page: "/admin/reports/technician-ranking", feature: "排序/區域/分頁 (06-07 同步: client-side useMemo)", selector: "select", check: "enabled" },

  // /admin/reports/revenue
  { doc: "✅", page: "/admin/reports/revenue", feature: "日/週/月/季 切片 (06-07 同步: _VALID_GRANULARITY)", selector: "button:text-is('日'), button:text-is('週'), button:text-is('季')", check: "visible" },
  { doc: "✅", page: "/admin/reports/revenue", feature: "排程發送 (06-07 同步: migration 029 scheduled_report)", selector: "button:has-text('排程發送')", check: "enabled" },
];

interface AuditRow {
  doc: string;
  page: string;
  feature: string;
  actual: "enabled" | "disabled" | "visible" | "missing" | "error";
  verdict: "MATCH" | "AHEAD" | "MISSING" | "INFO";
}

test("Doc vs UI conformance audit (web/docs/page-status.md)", async ({ page }) => {
  test.setTimeout(180_000);

  await login(page);

  const results: AuditRow[] = [];

  // 用 unique pages set 減少 navigation
  const seenPages = new Set<string>();
  let currentPath = "";

  for (const claim of CLAIMS) {
    if (currentPath !== claim.page) {
      try {
        await page.goto(claim.page, { waitUntil: "domcontentloaded", timeout: 15_000 });
        await page.waitForLoadState("networkidle", { timeout: 8_000 }).catch(() => {});
        currentPath = claim.page;
      } catch {
        results.push({
          doc: claim.doc,
          page: claim.page,
          feature: claim.feature,
          actual: "error",
          verdict: "MISSING",
        });
        continue;
      }
      seenPages.add(claim.page);
    }

    try {
      const locator = page.locator(claim.selector).first();
      const count = await locator.count();
      if (count === 0) {
        results.push({
          doc: claim.doc,
          page: claim.page,
          feature: claim.feature,
          actual: "missing",
          verdict: claim.doc === "✅" ? "MISSING" : "INFO",
        });
        continue;
      }

      if (claim.check === "visible") {
        const visible = await locator.isVisible().catch(() => false);
        results.push({
          doc: claim.doc,
          page: claim.page,
          feature: claim.feature,
          actual: visible ? "visible" : "missing",
          verdict: visible
            ? claim.doc === "✅" ? "MATCH" : "AHEAD"
            : claim.doc === "✅" ? "MISSING" : "INFO",
        });
      } else if (claim.check === "enabled") {
        const enabled = await locator.isEnabled().catch(() => false);
        const actual = enabled ? "enabled" : "disabled";
        let verdict: AuditRow["verdict"];
        if (claim.doc === "✅" && enabled) verdict = "MATCH";
        else if (claim.doc === "⏳" && enabled) verdict = "AHEAD";
        else if (claim.doc === "✅" && !enabled) verdict = "MISSING";
        else verdict = "INFO";
        results.push({
          doc: claim.doc,
          page: claim.page,
          feature: claim.feature,
          actual,
          verdict,
        });
      } else {
        results.push({
          doc: claim.doc,
          page: claim.page,
          feature: claim.feature,
          actual: "disabled",
          verdict: "INFO",
        });
      }
    } catch (e: any) {
      results.push({
        doc: claim.doc,
        page: claim.page,
        feature: claim.feature,
        actual: "error",
        verdict: "MISSING",
      });
    }
  }

  console.log("\n=== Doc vs UI Conformance Audit ===\n");
  console.log("Verdict | Doc | Page                                | Feature");
  console.log("---");
  for (const r of results) {
    const v =
      r.verdict === "MATCH"
        ? "✅ MATCH "
        : r.verdict === "AHEAD"
          ? "⚠️ AHEAD "
          : r.verdict === "MISSING"
            ? "❌ MISS  "
            : "ℹ️  INFO  ";
    console.log(
      `${v} | ${r.doc} | ${r.page.padEnd(38)} | ${r.feature} → ${r.actual}`,
    );
  }

  const match = results.filter((r) => r.verdict === "MATCH").length;
  const ahead = results.filter((r) => r.verdict === "AHEAD").length;
  const miss = results.filter((r) => r.verdict === "MISSING").length;
  console.log(`\nSummary: ${match} MATCH / ${ahead} AHEAD / ${miss} MISSING / ${results.length} total`);
});
