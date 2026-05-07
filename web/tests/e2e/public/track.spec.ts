/**
 * web/tests/e2e/public/track.spec.ts — 消費者匿名追蹤頁面 E2E
 *
 * 對應 PM Q3=C / Q9=B 共用機制：消費者點 LINE 短連結 → /track/[token] →
 *   後端 GET /api/v1/public/work-orders/{token}/status (operationId: getWorkOrderPublicStatus)
 *
 * 目前狀態：@wip — 後端為 stub，端到端跑會 fail。
 * 本檔以 page.route() 攔截 API 並回 mock，驗證前端渲染邏輯。
 *
 * 啟用方式：`RUN_WIP_TESTS=1 npx playwright test public/track.spec.ts`
 *
 * ## Q3=C/Q9=B Implementation TODO
 *
 *  1. 後端 endpoint 真實實作後，移除 @wip tag（CI 跑 happy path）
 *  2. 補測：on_the_way 狀態下 ETA 區塊顯示 + 30s 後重抓 polling
 *  3. 補測：technician_phone_masked 點擊 → tel: link
 *  4. 補 429 rate-limit 場景測試
 */

import { test, expect } from '@playwright/test';

const SAMPLE_TOKEN = 'mock-signed-token-for-e2e-test';
const API_PATH_RE = /\/api\/v1\/public\/work-orders\/[^/]+\/status$/;

test.describe('Public Track Page @wip', () => {
  test.skip(
    !process.env.RUN_WIP_TESTS,
    'WIP — BE stub only; set RUN_WIP_TESTS=1 to opt in (用 page.route mock 驗 FE 邏輯)',
  );

  test('valid token → 顯示工單狀態與技師資訊', async ({ page }) => {
    await page.route(API_PATH_RE, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          work_order_id: '550e8400-e29b-41d4-a716-446655440000',
          status: 'on_the_way',
          scheduled_at: '2026-05-08T09:00:00Z',
          completed_at: null,
          technician_name: '陳師傅',
          technician_phone_masked: '****1234',
          eta_minutes: 12,
        }),
      }),
    );

    const response = await page.goto(`/track/${SAMPLE_TOKEN}`);
    expect(response?.status(), 'page should not 5xx').toBeLessThan(500);

    await expect(
      page.getByRole('heading', { name: '工單即時追蹤' }),
    ).toBeVisible({ timeout: 10_000 });

    // 等待 fetch 完成 → status panel 出現
    await expect(page.getByTestId('track-status')).toBeVisible({ timeout: 5_000 });
    await expect(page.getByTestId('status-badge')).toContainText('技師前往中');
    await expect(page.getByText('陳師傅')).toBeVisible();
    await expect(page.getByText('****1234')).toBeVisible();
    // ETA 區塊（on_the_way + eta_minutes 才顯示）
    await expect(page.getByText(/技師預計.*12.*分鐘/)).toBeVisible();
  });

  test('410 expired token → 顯示連結失效錯誤頁', async ({ page }) => {
    await page.route(API_PATH_RE, (route) =>
      route.fulfill({
        status: 410,
        contentType: 'application/json',
        body: JSON.stringify({
          error_code: 'LINK_EXPIRED',
          message: 'work order archived',
        }),
      }),
    );

    await page.goto(`/track/${SAMPLE_TOKEN}`);

    const errorBox = page.getByTestId('track-error');
    await expect(errorBox).toBeVisible({ timeout: 5_000 });
    await expect(errorBox).toHaveAttribute('data-error-code', 'expired');
    await expect(errorBox).toContainText('連結已失效');
  });
});
