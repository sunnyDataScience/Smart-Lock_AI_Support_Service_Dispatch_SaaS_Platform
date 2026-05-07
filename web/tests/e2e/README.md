# Web E2E 測試（Playwright）

對應 [`docs/_flows-bdd-test/E7x--test-plan-and-readiness.md`](../../../docs/_flows-bdd-test/E7x--test-plan-and-readiness.md) §5.2 e2e layer (5%)。

## 結構

```
web/tests/e2e/
├── admin/   # admin / 客服 / 管理員視角（Desktop Chrome）
└── tech/    # 技師視角（mobile viewport, Pixel 7）
```

## 跑法

```bash
# 首次安裝（下載 chromium ~150MB）
cd web && npm install && npm run test:e2e:install

# 跑全部
npm run test:e2e

# 互動 UI 模式（debug）
npm run test:e2e:ui

# 跑單個 project
npx playwright test --project=admin
npx playwright test --project=tech

# 跑單個 spec
npx playwright test admin/login.spec.ts
```

## 預設行為

- `webServer` 自動啟 `npm run dev` on :3000，CI 不重用既有 server
- 失敗時自動 retain trace / video / screenshot 在 `test-results/`
- HTML report 在 `playwright-report/`

## 環境變數

| 變數 | 預設 | 說明 |
|------|------|------|
| `PORT` | 3000 | next dev port |
| `BASE_URL` | http://localhost:$PORT | 覆寫 base URL（用真 staging 跑時用） |
| `USE_EXISTING_SERVER` | unset | 設 1 表示不啟 webServer，用既有 process |
| `NEXT_PUBLIC_API_BASE_URL` | http://localhost:8001 | next dev 連的 api |

## 不在範圍

- happy-path specs（綁 PM Q1-Q10，不知該 mock 哪個角色登入）
- 視覺回歸（E7x §9 explicit non-goal）
- IE / 舊 Safari 相容性（E7x §9 explicit non-goal）
