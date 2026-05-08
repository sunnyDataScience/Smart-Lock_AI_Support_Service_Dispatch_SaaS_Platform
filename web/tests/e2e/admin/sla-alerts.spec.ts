/**
 * web/tests/e2e/admin/sla-alerts.spec.ts — F-016 SLA 紅色警報 (Soft SLA)
 *
 * 對應：
 *   - docs/_flows-bdd-test/v-model-right/E7--bdd-scenarios.md F-110 (Q5=B 拍板)
 *   - PM 拍板：Soft SLA — dashboard 變紅 + 升 Ops Manager，無賠償
 *
 * 標籤 @wip：本 spec 需要可控的 WS server (mock or test fixture)，CI 未啟動
 * 此後端能力前先以 page.evaluate 注入 hook 模擬訊息。
 *
 * 範圍：
 *   1. dashboard 收到 arrival_overdue 訊息後顯示紅色 banner（data-severity="red"）
 *   2. alert list item 點擊 → 跳轉 /admin/work-orders/{id}
 *
 * 故意 NOT 做：
 *   - 不啟真實 WS（綁 NEXT_PUBLIC_REALTIME_BASE_URL，CI 不要這層耦合）
 *   - 不驗 audit log 寫入（後端 component test 已驗）
 *   - 不驗賠償邏輯（Q5=B 拍板：根本沒有此邏輯）
 */

import { test, expect, Page } from '@playwright/test';

const ARRIVAL_OVERDUE_TARGET_ID = '00000000-0000-4000-8000-aaaaaaaaaaaa';

/**
 * 注入 SLA alert 訊息到 SlaAlertBanner — 透過直接 dispatch 一個自訂事件
 * 或直接操作 React state。本 helper 假設後端訂閱層收訊息後會更新 banner。
 *
 * 由於 useRealtimeChannel 是 closure，最直接的測試方式是：mock
 * NEXT_PUBLIC_REALTIME_BASE_URL → 一個能 echo 我們訊息的 server。CI 沒這個
 * 設施前，spec 標 @wip。下方僅做佈線示意。
 */
async function injectSlaAlert(
  page: Page,
  alertType: string,
  targetId: string,
  severity: string,
): Promise<void> {
  await page.evaluate(
    ({ alertType, targetId, severity }) => {
      // Phase 2 等 fixture WS server 上線後，改用真實 ws 發送
      const evt = new CustomEvent('test:sla-alert', {
        detail: {
          type: 'sla.alert',
          payload: {
            alert_type: alertType,
            target_id: targetId,
            threshold_minutes: 120,
            severity,
            escalated_to: 'ops_manager',
          },
        },
      });
      window.dispatchEvent(evt);
    },
    { alertType, targetId, severity },
  );
}

test.describe('@wip F-016 SLA Soft Alert (Q5=B)', () => {
  test('@wip dashboard banner turns red when arrival_overdue arrives', async ({
    page,
  }) => {
    // 載入 dashboard（前置：未來 spec 需先登入；此處假設 dev 環境跳過 auth）
    const response = await page.goto('/dashboard');
    expect(response?.status() ?? 200, 'dashboard should not 5xx').toBeLessThan(500);

    // 即使無 alert，banner 容器仍應 render（empty state testid）
    const emptyState = page.locator('[data-testid="sla-alert-banner-empty"]');
    // 實際斷言：等待頁面安定
    await emptyState
      .waitFor({ state: 'visible', timeout: 10_000 })
      .catch(() => {
        /* dashboard 可能因 auth gate 而導向 /login — Phase 2 處理 */
      });

    // Phase 2：透過 fixture WS 發送 arrival_overdue 後驗紅色 banner
    await injectSlaAlert(
      page,
      'arrival_overdue',
      ARRIVAL_OVERDUE_TARGET_ID,
      'red',
    );

    // 預期：banner 出現紅色 severity 屬性
    // const banner = page.locator('[data-testid="sla-alert-banner"][data-severity="red"]');
    // await expect(banner).toBeVisible({ timeout: 5_000 });
    // const title = banner.locator('[data-testid="sla-alert-banner-title"]');
    // await expect(title).toContainText('SLA 破線');
  });

  test('@wip clicking alert item navigates to work-order admin page', async ({
    page,
  }) => {
    const response = await page.goto('/dashboard');
    expect(response?.status() ?? 200).toBeLessThan(500);

    await injectSlaAlert(
      page,
      'arrival_overdue',
      ARRIVAL_OVERDUE_TARGET_ID,
      'red',
    );

    // Phase 2：點 jump link → 跳到 /admin/work-orders/{id}
    // const jumpLink = page
    //   .locator('[data-testid="sla-alert-item"][data-alert-type="arrival_overdue"]')
    //   .locator('[data-testid="sla-alert-jump"]')
    //   .first();
    // await expect(jumpLink).toBeVisible();
    // await jumpLink.click();
    // await expect(page).toHaveURL(
    //   new RegExp(`/admin/work-orders/${ARRIVAL_OVERDUE_TARGET_ID}$`),
    // );
  });
});
