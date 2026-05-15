# Page-Level Prompt: 全域 — 離線狀態頁

> IA 編號 **G2**（Global 類）。當 PWA / Web App 完全離線（無快取可用）或 Service Worker 偵測不到任何可用 endpoint 時顯示。亦作為技師端外勤訊號弱時的降級頁。

---

## [PAGE META]

- **page_name**: 離線狀態頁 Offline Fallback
- **route_path**: `/offline`（Service Worker 靜態快取）
- **page_type**: full-screen status page
- **ia_pages**: G2
- **openapi_ops**: none
- **asyncapi_ops**: none
- **primary_goal**: 當使用者完全無網路時提供清晰狀態 + 可離線執行的動作清單
- **secondary_goal**: 展示離線佇列內容，讓使用者安心「未送出的操作不會丟」
- **target_users**:
  - 技師（外勤連線不穩）
  - 管理員（IT 維護期間）
- **entry_point**:
  - Service Worker 無法 fetch 任何路由時自動渲染
  - 全站 header 「離線」banner 點擊進入
  - PWA 啟動時若 offline 自動重導
- **expected_time_on_page**: 5-60 秒（通常是等連線回復的間隙）

---

## [STRUCTURE: SECTIONS]

1. **status_banner**
   - section_type: prominent_banner
   - section_purpose: 居中大字顯示「目前離線」+ 動畫 icon

2. **connection_retry**
   - section_type: action_card
   - section_purpose: 「重新嘗試連線」按鈕 + 自動重試倒數

3. **offline_queue_summary**
   - section_type: list_card
   - section_purpose: 顯示離線佇列待送請求數與摘要

4. **cached_pages_list**
   - section_type: link_list
   - section_purpose: 可離線瀏覽的頁面清單（已預快取）

5. **recent_work_orders**（技師端）
   - section_type: card_list
   - section_purpose: 今日工單快取列表，可離線點入繼續處理

6. **system_info**
   - section_type: info_panel
   - section_purpose: 顯示上次同步時間、SW 版本、網路狀態 API 資訊

---

## [SECTION COMPONENT SPEC]

### Section: status_banner

- **layout**: 置中，佔 viewport 上 1/3
- **elements**:
  - offline_icon: SVG 動畫（雲朵帶斜線或訊號弱 icon）
  - title: Heading H1 / 「目前離線」
  - subtitle: Body / 「您的裝置未連線到網路或伺服器。我們會在連線回復時自動同步所有動作。」
- **states**:
  - detecting: 嘗試連線中（spinner）
  - confirmed_offline: 確認離線（紅/橙底）
  - reconnecting: 正重新連線
  - back_online: 2 秒內顯示綠色「已連線」後自動關閉此頁

### Section: connection_retry

- **layout**: status_banner 下方 card
- **elements**:
  - retry_btn: Button Primary / 「重新嘗試」
  - auto_retry_countdown: 「將於 N 秒後自動重試」（指數退避：5s → 10s → 30s → 60s → 300s）
  - online_status_indicator: 瀏覽器 `navigator.onLine` 即時顯示
- **states**:
  - waiting: 倒數中
  - attempting: spinner + 「檢查中...」
  - failed: 紅字「仍無法連線」
  - succeeded: 綠字 + 自動導向原路由

### Section: offline_queue_summary

- **layout**: 右上角或底部可折疊 card
- **elements**:
  - queue_count: 大數字 / 「3 個動作待同步」
  - queue_breakdown: 分類小計（完工回報 x 1、簽章 x 1、T5 範圍變更 x 1）
  - queue_detail_list: 可展開的每筆列表（時間、動作、目標工單）
  - manual_retry_btn: 「立即嘗試送出」（單筆或全部）
  - cancel_btn: 「取消未送請求」（帶二次確認）
- **states**:
  - empty: 「目前無待同步動作」
  - with_items: 顯示清單
  - syncing: 正在送出 N/M 筆
  - partial_failed: 部分失敗（顯示失敗原因）

### Section: cached_pages_list

- **layout**: 卡片網格 或 連結清單
- **elements**:
  - page_link: 每則含 icon + 頁名 + 「上次快取：X 前」
- **cached pages**（SW 預快取清單）：
  - `/pool` 案件池（技師）
  - `/my-orders` 我的工單（技師）
  - `/my-orders/[id]` 近期 10 張詳情
  - `/account` 帳戶中心
  - `/dashboard`（管理員，資料可能過期）
- **states**:
  - normal: 正常可點
  - stale: > 1 小時顯示橙色警告「資料可能已過時」

### Section: recent_work_orders（僅技師端）

- **layout**: 卡片列表，每卡 96px
- **elements**:
  - wo_number + status
  - customer_name（去識別化）
  - address
  - action_btn: 「繼續作業」→ 進 T3，支援完整離線操作
- **states**:
  - normal: 可點
  - fully_offline_supported: 綠色標「離線可用」

### Section: system_info

- **layout**: 底部小字資訊
- **elements**:
  - last_sync_at: 「上次同步：2026-04-23 14:35」
  - sw_version: Service Worker 版本
  - cache_version: 快取版本
  - nav_online: `navigator.onLine` 當前值
  - rtt_estimate: 若 `Network Information API` 可用，顯示估計 RTT
  - device_id: 匿名化的設備識別（協助除錯）
- **states**:
  - 可折疊（預設收起）

---

## [INTERACTION & STATE FLOW]

### 進入條件

| 觸發 | 行為 |
|:---|:---|
| Service Worker fetch error (status 0, network error) | SW 回傳此頁 HTML |
| 所有預快取皆過期 | SW 降級到此頁 |
| 使用者主動點 header「離線」banner | `router.push('/offline')` |
| PWA 啟動 + `navigator.onLine === false` | 啟動閃屏後導至此頁 |

### 離線時仍可執行的操作

1. 瀏覽 cached pages（有效期內）
2. 編輯技師端子流程表單（存 IndexedDB）
3. 查看離線佇列內容 + 手動取消未送請求
4. 讀通知中心的本地快取副本
5. 登出（清 local storage + 清 cache，下次上線重新登入）

### 離線時**禁止**的操作

- 新增 / 修改 / 刪除操作（自動進佇列而非 reject）
- 查看 PII（已快取的簡略資訊可看，不會查新）
- 金流相關動作（強制阻擋，顯示 Toast）

### 連線回復流程

```
navigator 發出 online event
  → SW 開始 Background Sync
  → 依佇列順序重送（帶原 Idempotency-Key）
  → 逐筆完成 → WS 推播更新到其他頁
  → offline_queue_summary 即時更新進度
  → 全部成功 → status_banner 變 "已連線" 綠色 2 秒後自動返回原路由
  → 部分失敗 → 停在本頁，列失敗詳情讓使用者決定重試或放棄
```

---

## [DATA & API]

### Service Worker 快取策略

- **Cache First**（靜態資產）：`/offline`, CSS/JS/Font, design tokens, Logo
- **Network First, Cache Fallback**（API 讀取）：最近 100 則通知、今日工單
- **Background Sync**（API 寫入）：`workbox-background-sync` 處理 POST/PUT/PATCH 佇列

### 本地 IndexedDB stores

- `offline_request_queue`: 待送請求
- `work_order_drafts`: T5-T9 子流程草稿
- `notifications_cache`: 最近通知
- `cached_work_orders`: 最近 10 張工單

### 離線佇列資料結構

```
{
  id: uuid,
  endpoint: "/api/v1/work-orders/{id}/complete",
  method: "POST",
  headers: { "Idempotency-Key": "...", ... },
  body: { ... },
  queued_at: ISO8601,
  attempts: 0,
  last_error: null,
  priority: "high" | "normal"
}
```

### 連線回復後 Background Sync

```javascript
self.addEventListener('sync', (event) => {
  if (event.tag === 'offline-queue-sync') {
    event.waitUntil(replayOfflineQueue())
  }
})
```

---

## [EXCEPTION TO GLOBAL RULES]

- 本頁**不發 API 請求**（避免 fetch loop）
- 網路狀態由 `navigator.onLine` + 定期 fetch `/api/health` 雙重確認
- 「取消未送請求」需二次確認，因可能影響業務連續性
- 本頁渲染不依賴 React Query（預設 SSR 或 SW 直出 HTML）
- 若佇列 > 100 筆，警告使用者並建議先上線再繼續操作

---

## [ACCEPTANCE CRITERIA]

- [ ] 完全離線時 `/offline` 可正常渲染（SW 快取）
- [ ] `navigator.onLine` 變化即時反映
- [ ] 離線佇列即時顯示 + 手動重試可用
- [ ] Cached pages 連結可點且成功渲染
- [ ] 連線回復後 Background Sync 全部送出 < 5 秒（10 筆以內）
- [ ] 失敗請求保留在佇列 + 顯示原因
- [ ] 技師端：T5-T9 子流程離線操作流暢
- [ ] 登出按鈕離線可用（清 cache + storage）
- [ ] 無障礙：離線狀態 screen reader 清楚播報

---

## 導航與狀態 (Navigation & State)

- **Upstream**: SW fetch error 自動導向、header 離線 banner 點擊、PWA 啟動偵測離線
- **Downstream**: 重新連線後導回 `document.referrer` 或預設（/dashboard / /pool）
- **State Persistence**: 所有離線資料在 IndexedDB；頁面本身 stateless
- **Error Navigation**: 本頁即為錯誤 fallback，不再降級
- **Deep Link**: 不適用（使用者主動到達表示主動檢查）
- **Multi-tab**: 透過 BroadcastChannel 同步佇列變化

完整規範見 `docs/02-design/E5x--frontend-navigation-matrix.md §3.1 離線 UX`。

---

## 校對檢核表

- [ ] 預快取清單 5 頁（pool/my-orders 等）是否足夠？管理員端是否需要類似快取？
- [ ] 自動重試指數退避（5s → 300s）是否合理？
- [ ] 「取消未送請求」的 UX 是否會誤操作導致業務資料遺失？
- [ ] PWA 與純 Web 的離線體驗是否該有差異？
- [ ] 金流操作強制阻擋的 UX 是否足夠清楚？
- [ ] IndexedDB 佇列 > 100 筆的警告門檻是否合理？
- [ ] 是否需要 offline mode 的視覺識別（例如整站色調變灰）？
