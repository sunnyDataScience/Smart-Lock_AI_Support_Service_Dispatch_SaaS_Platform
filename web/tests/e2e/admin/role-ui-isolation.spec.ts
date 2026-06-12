/**
 * role-ui-isolation.spec.ts — 5 角色前端 route 權限隔離（CR-0021）。
 *
 * 取代舊 rbac.spec.ts（@wip + mock 假 JWT）：用真實登入驗 AuthGuard 的 route gate
 * —— 禁區 URL 被導回 /dashboard、許可區可進、sidebar 依角色隱藏 nav。對應 §8 Q3。
 *
 * 每個 test 各自 fresh context（Playwright 預設）登入單一角色,不跨登入。
 */

import { test, expect, type Page } from "@playwright/test";

async function loginAs(page: Page, email: string) {
  await page.goto("/login");
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', "changeme123");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"), { timeout: 15_000 });
}

async function expectRedirectedToDashboard(page: Page, url: string) {
  await page.goto(url);
  await page.waitForURL(/\/dashboard/, { timeout: 8_000 });
  expect(page.url()).toContain("/dashboard");
}

async function expectAllowed(page: Page, url: string) {
  await page.goto(url);
  await page.waitForLoadState("domcontentloaded");
  await expect(page).toHaveURL(new RegExp(url.replace(/\//g, "\\/")));
}

test("dispatcher：可進工單/技師，禁區（會計/報表/角色）被導 dashboard", async ({ page }) => {
  await loginAs(page, "dispatcher@example.com");
  await expectAllowed(page, "/work-orders");
  await expectAllowed(page, "/technicians");
  await expectRedirectedToDashboard(page, "/accounting");
  await expectRedirectedToDashboard(page, "/admin/reports/kpi");
  await expectRedirectedToDashboard(page, "/admin/roles");
  // sidebar 不顯示會計 / 管理(稽核) 頂層 nav（皆 admin/ops 專屬）
  await page.goto("/dashboard");
  await expect(page.locator('nav a[href="/accounting"]')).toHaveCount(0);
  await expect(page.locator('nav a[href="/admin/audit-events"]')).toHaveCount(0);
});

test("customer_service：可進客戶/知識庫，禁區（技師/庫存/會計）被導 dashboard", async ({
  page,
}) => {
  await loginAs(page, "cs@example.com");
  await expectAllowed(page, "/admin/customers");
  await expectAllowed(page, "/knowledge-base/cases");
  await expectRedirectedToDashboard(page, "/technicians");
  await expectRedirectedToDashboard(page, "/admin/inventory");
  await expectRedirectedToDashboard(page, "/accounting");
});

test("operations_manager：可進會計/報表，禁區（角色/稽核）被導 dashboard", async ({
  page,
}) => {
  await loginAs(page, "ops@example.com");
  await expectAllowed(page, "/accounting");
  await expectAllowed(page, "/admin/reports/kpi");
  await expectRedirectedToDashboard(page, "/admin/roles");
  await expectRedirectedToDashboard(page, "/admin/audit-events");
});

test("admin：full access，敏感頁皆可進 + sidebar 有完整 nav", async ({ page }) => {
  await loginAs(page, "admin@example.com");
  await expectAllowed(page, "/admin/roles");
  await expectAllowed(page, "/accounting");
  await expectAllowed(page, "/admin/inventory");
  // admin sidebar 應含會計 / 管理(稽核) 頂層 nav（dispatcher 看不到的）
  await page.goto("/dashboard");
  await expect(page.locator('nav a[href="/accounting"]')).toHaveCount(1);
  await expect(page.locator('nav a[href="/admin/audit-events"]')).toHaveCount(1);
});
