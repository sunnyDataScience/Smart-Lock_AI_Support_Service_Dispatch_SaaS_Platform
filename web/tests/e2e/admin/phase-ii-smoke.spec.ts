/**
 * web/tests/e2e/admin/phase-ii-smoke.spec.ts — Phase II 9 FR + A37 drawer 真實 smoke。
 *
 * 跑 9 page 確認:
 *   - login 走通
 *   - HTTP 200 不 5xx
 *   - 主標題顯示對 (FR-XXXX label)
 *   - 無 React page error / console error (過濾 fetch fail)
 *   - 截圖留存 (test-results/)
 */

import { test, expect, type ConsoleMessage, type Page } from "@playwright/test";

interface PageSpec {
  fr: string;
  name: string;
  path: string;
  expectedHeading: RegExp;
}

const PAGES: PageSpec[] = [
  {
    fr: "FR-0049",
    name: "Approval Inbox",
    path: "/admin/approval-inbox",
    expectedHeading: /統一審批工作箱|Approval Inbox/i,
  },
  {
    fr: "FR-0044",
    name: "Technician Lifecycle",
    path: "/admin/technicians-lifecycle",
    expectedHeading: /技師生命週期|Lifecycle/i,
  },
  {
    fr: "FR-0045",
    name: "Tech Statements",
    path: "/account/statements",
    expectedHeading: /薪資對帳|Statement/i,
  },
  {
    fr: "FR-0046",
    name: "Dispatcher Commission",
    path: "/account/commission-statements",
    expectedHeading: /派工獎金|Commission/i,
  },
  {
    fr: "FR-0047",
    name: "Brand B2B",
    path: "/admin/brand-b2b",
    expectedHeading: /品牌商 B2B|Brand B2B/i,
  },
  {
    fr: "FR-0053",
    name: "GDPR Forget Queue",
    path: "/admin/gdpr-forget-queue",
    expectedHeading: /GDPR|被遺忘權/i,
  },
  {
    fr: "FR-0050",
    name: "AI Governance",
    path: "/admin/ai-governance",
    expectedHeading: /AI 治理|Governance/i,
  },
  {
    fr: "FR-0051",
    name: "SOP Feedback",
    path: "/admin/sop-feedback",
    expectedHeading: /SOP 反饋|Feedback/i,
  },
  {
    fr: "FR-0048",
    name: "RMA Quality",
    path: "/admin/rma-quality",
    expectedHeading: /RMA 品質|Quality/i,
  },
];

async function login(page: Page) {
  await page.goto("/login");
  await page.fill('input[type="email"]', "test@lock-ai.com");
  await page.fill('input[type="password"]', "changeme123");
  await page.click('button[type="submit"]');
  // 等待 redirect 出 /login
  await page.waitForURL((url) => !url.pathname.includes("/login"), {
    timeout: 10_000,
  });
}

test.describe.serial("Phase II 9 FR smoke (with login)", () => {
  let loggedInOnce = false;

  for (const spec of PAGES) {
    test(`${spec.fr} ${spec.name} — page renders without crash`, async ({
      page,
      context,
    }, testInfo) => {
      const consoleErrors: string[] = [];
      const pageErrors: string[] = [];

      page.on("console", (msg: ConsoleMessage) => {
        if (msg.type() === "error") {
          const text = msg.text();
          // 過濾 fetch fail (空 DB 預期會 fail)
          if (
            text.includes("Failed to fetch") ||
            text.includes("ERR_CONNECTION_REFUSED") ||
            text.includes("NetworkError") ||
            text.includes("401") ||
            text.includes("403") ||
            text.includes("404") ||
            text.includes("net::") ||
            text.includes("DEV_AUTH") ||
            text.includes("Failed to load resource")
          ) {
            return;
          }
          consoleErrors.push(text);
        }
      });

      page.on("pageerror", (err) => {
        pageErrors.push(err.message);
      });

      // 先 login
      await login(page);
      loggedInOnce = true;

      const response = await page.goto(spec.path, {
        waitUntil: "domcontentloaded",
        timeout: 15_000,
      });

      expect(response, `${spec.path} response`).not.toBeNull();
      expect(response!.status(), `${spec.path} status not 5xx`).toBeLessThan(500);

      // 等 React render
      await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

      // 截圖
      await page.screenshot({
        path: testInfo.outputPath(
          `${spec.fr}-${spec.name.replace(/ /g, "-")}.png`,
        ),
        fullPage: true,
      });

      // page error 為硬性失敗
      expect(
        pageErrors,
        `${spec.fr} page errors:\n${pageErrors.join("\n")}`,
      ).toHaveLength(0);

      // 驗 heading 存在
      const heading = page.locator("h1").filter({ hasText: spec.expectedHeading });
      await expect(heading, `${spec.fr} heading should match`).toBeVisible({
        timeout: 5_000,
      });

      // console error 為硬性失敗 (已過濾 fetch 類)
      expect(
        consoleErrors,
        `${spec.fr} console errors:\n${consoleErrors.join("\n")}`,
      ).toHaveLength(0);
    });
  }
});
