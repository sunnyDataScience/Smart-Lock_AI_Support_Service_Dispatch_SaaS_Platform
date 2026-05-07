/**
 * web/tests/e2e/public/track.spec.ts — 消費者匿名追蹤頁面 smoke test
 *
 * 對應 PM Q3=C / Q9=B 共用機制：消費者點 LINE 短連結 → /track/[token] →
 *   後端 GET /api/v1/public/work-orders/{token}/status (operationId: getWorkOrderPublicStatus)
 *
 * 目前狀態：@wip — 後端只回 placeholder，前端僅渲染 skeleton。
 * Skeleton 階段不做：
 *   - 不真實打 API（需 token 簽章 + DB seed）
 *   - 不驗 PII 遮罩（要等 mask_phone / mask_technician_name 真實實作）
 *   - 不驗 polling 行為（on_the_way 30s polling 尚未實作）
 *
 * ## Q3=C/Q9=B Implementation TODO
 *
 *  1. 移除 @wip tag，啟用 CI 跑這支
 *  2. 在 fixtures/ 加 mock token（與 mock-server.sh / Prism 一致）
 *  3. 補測：404 / 410 / 429 三種錯誤頁面文案
 *  4. 補測：on_the_way 狀態下 ETA 區塊顯示 + 30s 後重抓
 *  5. 補測：technician_phone_masked 點擊 → tel: link
 */

import { test, expect } from '@playwright/test';

const SAMPLE_TOKEN = 'placeholder-token-for-skeleton-only-not-signed-yet';

test.describe('Public Track Page Smoke @wip', () => {
  test.skip(
    !process.env.RUN_WIP_TESTS,
    'WIP — Q3=C/Q9=B skeleton only; set RUN_WIP_TESTS=1 to opt in'
  );

  test('renders skeleton placeholder without 5xx', async ({ page }) => {
    const response = await page.goto(`/track/${SAMPLE_TOKEN}`);
    expect(response?.status(), 'page should not 5xx').toBeLessThan(500);

    // skeleton 標題
    await expect(page.getByRole('heading', { name: '工單即時追蹤' })).toBeVisible({
      timeout: 10_000,
    });

    // TODO: 後端串接後改驗 status badge / technician name / phone masked
    await expect(page.getByText(/SKELETON/i)).toBeVisible();
  });
});
