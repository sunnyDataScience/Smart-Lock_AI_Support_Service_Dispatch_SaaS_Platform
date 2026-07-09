/**
 * sop-internal-id-leak.spec.ts — SOP 草稿詳情頁不可洩漏內部 UUID（A6，會議 2026-06-10 Action #6）。
 *
 * 修復前：詳情頁標題旁的 font-mono badge 在無 document_number 時 fallback 顯示
 * draft.id.slice(0,8),且 title={draft.id} hover 露出完整內部 UUID。
 * 修復後：只在有 document_number 時顯示該公開編號;絕不露出內部 id。
 */

import { test, expect, type Page } from "@playwright/test";

async function login(page: Page) {
  await page.goto("/login");
  await page.fill('input[type="email"]', "test@lock-ai.com");
  await page.fill('input[type="password"]', "changeme123");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.includes("/login"), { timeout: 15_000 });
}

// 種子 SOP 草稿（document_number 為空 → 修復前會 fallback 露 id.slice）
const DRAFT_ID = "bbbb1111-cccc-4ddd-8eee-ffffffff0001";
const ID_PREFIX8 = "bbbb1111"; // draft.id.slice(0,8)

test("SOP 草稿詳情頁不顯示內部 UUID（id 全碼 / 前 8 碼 / title 皆不洩漏）", async ({
  page,
}) => {
  await login(page);
  await page.goto(`/knowledge-base/sop-drafts/${DRAFT_ID}`);
  await page.waitForLoadState("networkidle").catch(() => {});

  // 頁面確實渲染了詳情 header（返回連結恆在）→ 確保不是空白頁造成的假通過
  await expect(page.locator("h1").first()).toBeVisible({ timeout: 10_000 });

  // 1. 完整內部 UUID 不可出現在畫面文字
  await expect(page.getByText(DRAFT_ID)).toHaveCount(0);
  // 2. 內部 UUID 前 8 碼（舊 fallback id.slice(0,8)）不可出現
  await expect(page.getByText(ID_PREFIX8, { exact: false })).toHaveCount(0);
  // 3. 不可有任何元素以 title 掛出內部 UUID（舊 title={draft.id} hover 洩漏）
  await expect(page.locator(`[title="${DRAFT_ID}"]`)).toHaveCount(0);
  await expect(page.locator(`[title*="${ID_PREFIX8}"]`)).toHaveCount(0);
});
