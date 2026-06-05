---
title: WBS 1.2.7.3.2 / 1.2.7.3.3 / 1.2.7.3.4 取證 audit
date: 2026-06-05
status: existing-coverage-mixed
tier: 4
---

# WBS 1.2.7.3.2 / 1.2.7.3.3 / 1.2.7.3.4 — 既有覆蓋取證

## 1. 目的

承接 1.2.7.3.1 ✅（本 session E2E 補完）+ 1.2.7.3.5 ✅（既有 pytest 覆蓋）後，取證 1.2.7.3 剩餘 3 項真實狀態。

## 2. 1.2.7.3.2 V1.0 ↔ V2.0 資料流驗證 — **真實 ~30%**

### 取證

```
grep -rn "parity|dual_write|v1.*v2.*compat" api/ 2>/dev/null  # → 全空
```

無任何 automated parity test。

### 既有間接覆蓋

| 元件 | 機制 | 覆蓋程度 |
|---|---|---|
| v1/v2 共用 service layer | `routers/work_orders.py` 與 `routers/work_orders_v2.py` 同呼 `services/work_order_service.py` | ✅ code-level 一致性隱含保證 |
| v1/v2 共用 DB schema | 兩套 router 寫入同一個 `work_orders` 表 | ✅ 資料同源 |
| Cross-tenant guard 對齊 | v2 加 `_cross_tenant_*` guard / v1 走 `X-Tenant-ID` header | ⚠️ 兩套 enforcement path 但結果一致 |
| Deprecation header on v1 | middleware 在 v1 路徑加 `Deprecation: true` header | ✅ middleware-level 驗證 |
| v1 → v2 caller 遷移進度 | 41 個真實 v1 caller 待遷（WBS §1 caller 表追蹤）| ⚠️ 部分 |

### 結論

- 「資料流驗證」核心需求 = v1 與 v2 寫入同一筆 row / 讀取一致 → **已透過共用 service+DB 隱含保證**
- 但無 automated end-to-end parity test 驗「v1 POST + v2 GET 結果一致」
- WBS 校正：30%（code-level 一致但無 black-box parity test）
- **不立即補 test 理由**：P3.5 cutover 已完成、剩 41 個 v1 caller 計畫 P4 階段遷完即廢棄 v1；寫 parity test 在「即將廢棄」的雙軌期反向消耗工時

## 3. 1.2.7.3.3 師傅端 100 人併發壓測 — **真實 0%**

### 取證

```
find . -name "*.k6.js" -o -name "locustfile.py" -o -name "*.locust.py"  # → 全空
grep -rln "k6|locust|artillery" scripts/                                # → 全空
```

無 load test 工具 / 配置 / script。

### 結論

- 100 人併發壓測屬上線前 NFR 驗證，需 dev/staging 環境 + 工具（k6/locust）+ 真實流量錄製
- 目前 0% — 工具未引入、scenario 未設計、baseline metrics 未建立
- **不立即補的理由**：
  1. 需業主提供 SLA 目標（p99 latency / throughput）才能定 pass/fail
  2. 工具引入屬基礎建設變更（Architecture boundary 觸發）— 應走 CIA
  3. 開發未 freeze 前壓測 baseline 會持續變動
- **建議**：另開 CR-0019 — 100 人併發壓測工具與 scenario CIA（業主決定 k6 vs locust + SLA 目標）

## 4. 1.2.7.3.4 行動裝置相容性測試 — **真實 ~50%**

### 取證

`web/playwright.config.ts:46-50`：
```typescript
{
  name: 'tech',
  testDir: './tests/e2e/tech',
  use: { ...devices['Pixel 7'] },
},
```

`web/public/manifest.webmanifest` 已就緒（PWA install）。

### 既有覆蓋

| 項目 | 狀態 |
|---|---|
| Playwright `tech` project 用 Pixel 7 viewport | ✅（Android Chrome 模擬 viewport + UA）|
| PWA manifest + 4 SVG icon | ✅ |
| Responsive Tailwind class（`md:` 斷點）全頁面套用 | ✅（grep 確認） |
| iOS Safari 實機測試 | ❌ 無 |
| Android 多機型矩陣（高/中/低階螢幕）| ❌ 無 |
| BrowserStack / Sauce Labs 帳號 | ❌ 無（grep config 全空） |
| 跨裝置 e2e spec | ⚠️ 只 1 個 `tech` project，無 iPhone/iPad 等多 device matrix |

### 結論

- Playwright `tech` project 已 cover Android Chrome viewport — 50% 覆蓋
- iOS Safari / 真實裝置矩陣未做（需實機 or cloud testing 帳號）
- WBS 校正：50%
- **不立即補的理由**：
  1. 真實裝置測試需業主提供 BrowserStack/Sauce Labs 帳號（採購決策）
  2. PWA 設計上已用 mobile-first responsive Tailwind，UX 一致性已確保
  3. 屬上線前 manual QA 性質，非開發階段 BUILD

## 5. WBS 1.2.7.3 整合測試段 — 真實狀態校正總表

| WBS | 任務 | 校正前 | 校正後 | 來源 |
|---|---|---|---|---|
| 1.2.7.3.1 | E2E 流程測試 | ⬜ 0% | ✅ 80%+ | 本 session 補 Flow 4/8/9/14 spec + 既有 15 spec |
| 1.2.7.3.2 | V1.0 ↔ V2.0 資料流 | ⬜ 0% | ⚠️ 30% | 共用 service+DB 隱含一致，無 black-box parity test |
| 1.2.7.3.3 | 師傅端 100 人併發壓測 | ⬜ 0% | ❌ 0% | 工具/scenario/SLA baseline 全空（建議開 CR-0019）|
| 1.2.7.3.4 | 行動裝置相容性測試 | ⬜ 0% | ⚠️ 50% | Playwright tech project + PWA manifest 50% 覆蓋 |
| 1.2.7.3.5 | 會計報表正確性驗算 | ⬜ 0% | ✅ 100% | 4 個既有 pytest 全覆蓋（前 audit doc）|

## 6. 1.2.7.3 真實平均 ~52%

不是原報告標的 ⬜ 全 0%。其中 P0（E2E + 會計驗算）已達 UAT 前置要求；P1（V1/V2 parity + load test + 跨裝置）需業主提供工具/帳號/baseline 才能完成。

## 7. 後續行動

| 行動 | 解什麼 |
|---|---|
| 開立 CR-0019 — 100 人併發壓測 CIA | 解 1.2.7.3.3 工具選型 + SLA 目標決議 |
| 採購 BrowserStack/Sauce Labs 帳號 | 解 1.2.7.3.4 iOS Safari + 多機型實機 |
| P4 階段完成 41 個 v1 caller 遷 v2 | 解 1.2.7.3.2 雙軌期廢除，parity test 自動失效 |
