/**
 * web/tests/e2e/admin/login.spec.ts — login page smoke test
 *
 * 對應 docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md §13 #2
 * 8 條 Happy Path E2E 的「最小 smoke」起點。本 spec 只驗：
 *   1. /login 路徑可達（無 5xx / 404）
 *   2. email / password 欄位存在
 *   3. 提交按鈕存在
 *
 * 故意 NOT 做：
 *   - 不打 submit（會打 api，需 admin seed + 真 DB；CI 暫不要這層耦合）
 *   - 不驗 UI 樣式（綁 visual regression，E7x §9 不做）
 *   - 不假設角色（綁 PM Q1-Q10）
 */

import { test, expect } from '@playwright/test';

test.describe('Login Page Smoke', () => {
  test('renders email + password fields without 5xx', async ({ page }) => {
    const response = await page.goto('/login');
    expect(response?.status(), 'login page should not 5xx').toBeLessThan(500);

    // 寬鬆比對：email / 信箱 / Email 任一字眼
    await expect(
      page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i]')
    ).toBeVisible({ timeout: 10_000 });

    await expect(
      page.locator('input[type="password"], input[name="password"]')
    ).toBeVisible();
  });

  test('submit button is present; disabled on empty form, enabled once filled', async ({ page }) => {
    await page.goto('/login');

    // 精確鎖 type=submit（2026-07-10 修）：登入/註冊 tab 切換鈕（type=button）
    // 也含「登入」字樣，逗號選擇器 .first() 會抓到 tab 鈕（恆 enabled）而非 submit。
    const submitButton = page.locator('button[type="submit"]').first();

    // submit 存在
    await expect(submitButton).toBeVisible({ timeout: 10_000 });

    // 刻意設計（login/page.tsx:106 `disabled={loading || !email || !password}`）：
    // 空表單時 submit 應 disabled，避免空送出（正確 UX，非 bug）。
    await expect(submitButton).toBeDisabled();

    // 填入 email + password 後，submit 應變 enabled。
    await page.locator('input[type="email"], input[name="email"]').first().fill('test@lock-ai.com');
    await page.locator('input[type="password"], input[name="password"]').first().fill('changeme123');
    await expect(submitButton).toBeEnabled();
  });
});
