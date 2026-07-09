/**
 * web-tech/playwright.config.ts — Playwright E2E configuration
 *
 * 對應 docs/_flows-bdd-test/v-model-right/E7x--test-plan-and-readiness.md §5.2 e2e layer (5%)
 * 與 §13 Verification 第 2 步 (8 條 Happy Path E2E)。
 *
 * 設計（多 project 對齊 E7x §10 #10）：
 *   - admin：admin / 客服 / 管理員視角（從 /login 進）
 *   - tech：技師視角（從 /login 進，手機 viewport）
 *
 * 預設 webServer：next dev on :3000（不另起 Prism mock，避免 next routing
 * 與 mock 解耦的 confidence loss）。要對 Prism 跑時，設 USE_PRISM=1。
 *
 * 不在範圍：
 *   - happy-path specs（綁 PM Q1-Q10，不知該 mock 哪個角色登入）
 *   - visual regression（E7x §9 不做，team < 3 designer）
 */

import { defineConfig, devices } from '@playwright/test';

const PORT = Number(process.env.PORT ?? 3001);
const BASE_URL = process.env.BASE_URL ?? `http://localhost:${PORT}`;
const USE_EXISTING_SERVER = process.env.USE_EXISTING_SERVER === '1';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  // 本地也給 1 retry：多支 admin spec 共用同一帳號從 /login 登入,fullyParallel
  // 多 worker 下偶發 login 往返 timing 競爭（單跑必綠）。retry 只重跑失敗案例,
  // 無法掩蓋穩定失敗,專治此類 transient flake。
  retries: 1,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: 'playwright-report' }],
  ],
  outputDir: 'test-results',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'tech',
      testDir: './tests/e2e/tech',
      use: { ...devices['Pixel 7'] },
    },
    {
      name: 'account',
      testDir: './tests/e2e/account',
      use: { ...devices['Pixel 7'] },
    },
  ],
  webServer: USE_EXISTING_SERVER
    ? undefined
    : {
        command: 'npm run dev',  // 師傅站 dev :3001
        port: PORT,
        timeout: 120_000,
        reuseExistingServer: !process.env.CI,
        env: {
          NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8001',
        },
      },
});
