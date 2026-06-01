/**
 * web/tests/e2e/public/consumer-track.spec.ts — 消費者匿名追蹤頁面 E2E（v2 路徑）
 *
 * 對應 spec M16 Consumer Tracking FR-0022（CR-0002-α P2-α）：
 *   消費者點 LINE 短連結 → /track/[token] →
 *   後端 v2: GET /consumer/work-orders/{trackingToken}
 *          (operationId: getConsumerWorkOrderV2, ConsumerWOView schema)
 *
 * 與 track.spec.ts 的差異：
 *   - 本檔 mock 的 API path 為 /consumer/work-orders/** （v2 路徑）
 *   - 回應 schema 對齊 ConsumerWOView（work_order_state, technician_display_name,
 *     last_update_at）而非 legacy PublicWorkOrderStatus schema
 *
 * 使用 page.route() 攔截 API 回 mock，驗證前端渲染邏輯（不需真實後端）。
 *
 * 啟用方式：`npx playwright test public/consumer-track.spec.ts`
 * （本 spec 不加 @wip — v2 前端已切換到 /consumer/work-orders/ 路徑）
 */

import { test, expect } from '@playwright/test';

const SAMPLE_TOKEN = 'mock-signed-token-for-e2e-consumer-test-v2';
/** 對齊 /consumer/work-orders/{trackingToken}（spec M16） */
const API_PATH_RE = /\/consumer\/work-orders\/[^/]+$/;

test.describe('Consumer Track Page v2 (M16 FR-0022)', () => {
  test('有效 token → 顯示 on_the_way 狀態（ConsumerWOView schema）', async ({ page }) => {
    await page.route(API_PATH_RE, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          work_order_state: 'on_the_way',
          eta_minutes: 15,
          technician_display_name: '陳師傅',
          last_update_at: '2026-06-01T10:30:00Z',
        }),
      }),
    );

    const response = await page.goto(`/track/${SAMPLE_TOKEN}`);
    expect(response?.status(), 'page should not 5xx').toBeLessThan(500);

    // 等待 heading 出現
    await expect(
      page.getByRole('heading', { name: '工單即時追蹤' }),
    ).toBeVisible({ timeout: 10_000 });

    // status panel 出現
    await expect(page.getByTestId('track-status')).toBeVisible({ timeout: 5_000 });

    // status-badge 顯示 on_the_way 對應文字
    const badge = page.getByTestId('status-badge');
    await expect(badge).toBeVisible({ timeout: 5_000 });

    // 技師顯示名（v2: technician_display_name）
    await expect(page.getByText('陳師傅')).toBeVisible();
  });

  test('completed 狀態 → 顯示已完成 badge（ConsumerWOView schema）', async ({ page }) => {
    await page.route(API_PATH_RE, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          work_order_state: 'completed',
          eta_minutes: null,
          technician_display_name: '李師傅',
          last_update_at: '2026-06-01T14:00:00Z',
        }),
      }),
    );

    await page.goto(`/track/${SAMPLE_TOKEN}`);
    await expect(page.getByTestId('track-status')).toBeVisible({ timeout: 5_000 });
    // badge 應顯示 completed 對應的翻譯文字
    await expect(page.getByTestId('status-badge')).toBeVisible();
  });

  test('404 invalid token → 顯示連結無效錯誤頁', async ({ page }) => {
    await page.route(API_PATH_RE, (route) =>
      route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({
          error_code: 'NOT_FOUND',
          message: 'token invalid or expired',
        }),
      }),
    );

    await page.goto(`/track/${SAMPLE_TOKEN}`);

    const errorBox = page.getByTestId('track-error');
    await expect(errorBox).toBeVisible({ timeout: 5_000 });
    await expect(errorBox).toHaveAttribute('data-error-code', 'not_found');
  });

  test('410 expired token → 顯示連結已失效錯誤頁', async ({ page }) => {
    await page.route(API_PATH_RE, (route) =>
      route.fulfill({
        status: 410,
        contentType: 'application/json',
        body: JSON.stringify({
          error_code: 'GONE',
          message: '工單完工超過 90 天，連結已封存',
        }),
      }),
    );

    await page.goto(`/track/${SAMPLE_TOKEN}`);

    const errorBox = page.getByTestId('track-error');
    await expect(errorBox).toBeVisible({ timeout: 5_000 });
    await expect(errorBox).toHaveAttribute('data-error-code', 'expired');
    await expect(errorBox).toContainText('連結已失效');
  });

  test('不帶 Authorization / X-Tenant-ID header → API 仍可回 200', async ({ page }) => {
    /**
     * 驗證前端呼叫時確實沒有帶 auth headers（consumer endpoint 是 public token，
     * 不應帶 JWT）。用 page.route handler 攔截並檢查 request headers。
     */
    let capturedAuthHeader: string | null = null;
    let capturedTenantHeader: string | null = null;

    await page.route(API_PATH_RE, (route) => {
      capturedAuthHeader = route.request().headers()['authorization'] ?? null;
      capturedTenantHeader = route.request().headers()['x-tenant-id'] ?? null;
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          work_order_state: 'pending',
          eta_minutes: null,
          technician_display_name: null,
          last_update_at: null,
        }),
      });
    });

    await page.goto(`/track/${SAMPLE_TOKEN}`);
    await expect(page.getByTestId('track-status')).toBeVisible({ timeout: 5_000 });

    expect(
      capturedAuthHeader,
      'consumer endpoint should NOT send Authorization header',
    ).toBeNull();
    expect(
      capturedTenantHeader,
      'consumer endpoint should NOT send X-Tenant-ID header',
    ).toBeNull();
  });
});
