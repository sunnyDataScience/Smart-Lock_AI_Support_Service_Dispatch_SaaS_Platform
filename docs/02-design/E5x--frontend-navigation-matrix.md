# E5x — 前端導航與狀態規範 (Frontend Navigation & State Matrix)

> **文件版本**：v0.1（draft，待人工校對）
> **建立日期**：2026-04-23
> **狀態**：Claude 起草
> **適用範圍**：全站（Admin Panel + Technician App + Super Portal）
> **觸發原因**：plan §S 驗證閘軸三（頁面狀態變化 + 上下游關係），B 類僅 46/100
>
> **參考文件**：
> - `E5x--frontend-architecture.md §2.2 路由設計`
> - `E5x--frontend-information-arch.md §5 網站地圖 §9 URL 結構`
> - `web_design_spec_prompt_pipeline/pages/MAPPING.md`
> - 19 份 `web_design_spec_prompt_pipeline/pages/*.md`
>
> **本檔用途**：補足 pipeline page spec 中**統一缺失的 4 個規範層**：
> 1. 頁面之間的 upstream / downstream 矩陣
> 2. Dirty State 恢復策略
> 3. 錯誤狀態（401/403/404/409 / 離線）統一行為
> 4. Query String 保留字、深連結、多頁簽規則

---

## 目錄

1. [全局導航矩陣](#1-全局導航矩陣)
2. [Dirty State 策略](#2-dirty-state-策略)
3. [錯誤狀態頁面行為](#3-錯誤狀態頁面行為)
4. [Query String 保留字規範](#4-query-string-保留字規範)
5. [深連結與 PWA 頁面棧](#5-深連結與-pwa-頁面棧)
6. [多頁簽同步](#6-多頁簽同步)
7. [跨子頁面返回](#7-跨子頁面返回)

---

## 1. 全局導航矩陣

### 1.1 設計原則

- **每頁至少有一個明確的 upstream** — 除了根（dashboard、登入）
- **每頁宣告 downstream targets** — 列表頁通常導向詳情；詳情頁通常導向編輯
- **反向索引 = 導航矩陣** — 前端可據此生成 breadcrumb、back button 行為
- **State Persistence 對齊頁面邏輯** — 列表頁的 filter 要回跳時保留、表單頁的 input 要重進時恢復

### 1.2 標準 `page_metadata` 區塊（每份 pipeline spec 頂部必備）

每份 `web_design_spec_prompt_pipeline/pages/*.md` 需於頂部加入此結構化區塊：

```yaml
---
ia_id: A12  # 對應 MAPPING.md
route: /work-orders/[id]
role_required: [admin, operations_manager]
upstream:
  - page: A11 /work-orders          # 從列表進
    trigger: click row
    pass: work_order_id
  - page: A28 /admin/dispatch-queue # 從派工監控進
    trigger: click work order card
    pass: work_order_id, highlight
downstream:
  - page: T5 /my-orders/[id]/scope-change
    trigger: 範圍變更按鈕
    pass: work_order_id
  - page: T9 /my-orders/[id]/signature
    trigger: 完工回報完成後
    pass: work_order_id
  - page: A17 /admin/refunds/[id]
    trigger: 建立退款後
    pass: work_order_id, refund_id
state_persistence:
  query_string: [tab, highlight]    # 需保留在 URL
  session_storage: []
  indexed_db: []
  discard_on_leave: true           # 離開不保留未送草稿
  dirty_state: prompt              # 離開前 prompt
error_navigation:
  "404": redirect:/work-orders + toast
  "403": downgrade:readonly
  "409": refetch + toast
  offline: banner:/offline-indicator
deep_link: supported              # PWA 開啟可直達
multi_tab: sync_via_ws           # 同資源多頁簽同步
---
```

### 1.3 矩陣表（節錄）— 核心頁面

完整矩陣見 `MAPPING.md §11`（T1.6 後建立）。此處列核心樣本：

| IA | 頁面 | Upstream | Downstream |
|:---|:---|:---|:---|
| A0 | `/login` | — | A1 dashboard |
| A1 | `/dashboard` | A0 登入後 | A11 工單、A28 派工、A17 退款、A29 KPI |
| A2 | `/conversations` | A1 側邊選單 | A3 對話詳情 |
| A3 | `/conversations/[id]` | A2 列表、LINE Push 深連結 | A4 問題卡、A11 開新工單 |
| A11 | `/work-orders` | A1 側邊選單、搜尋 | A12 工單詳情、A37 手動派工 |
| A12 | `/work-orders/[id]` | A11、A28、搜尋、深連結、LINE Push | A17 退款、A22 爭議、T5-T9 子流程、客訴升級 |
| A17 | `/admin/refunds` | A1、A12、深連結 | A17/[id] 詳情 |
| A22 | `/admin/disputes` | A1、A12、A17 | A22/[id] 仲裁 |
| A28 | `/admin/dispatch-queue` | A1、側邊選單 | A12、A37 |
| A37 | `/admin/dispatch-manual` | A28、A2 Flow 2 告警 | A12 |
| T0 | `/tech-login` | — | T1 |
| T1 | `/pool` | T0、下拉刷新 | T2 接單後、T3 詳情 |
| T2 | `/my-orders` | T1 接單、bottom nav | T3 |
| T3 | `/my-orders/[id]` | T2、LINE Push、PWA 深連結 | T5-T9 子流程、T11 改期 |
| T5-T9 | 子流程 | T3 | T3（完成後返回）|
| T10 | `/account/schedule` | T4 帳戶 | — |
| T11 | `/my-orders/[id]/reschedule` | T3 延遲按鈕、客戶不在場 Flow | T3 |
| G1 | `/notifications` | 任何頁面 bell icon | 依通知跳回來源頁 |
| A34 | `/admin/settings/tenant` | A1、side nav | A35 品牌、B2B Tab、Offboarding Tab |

### 1.4 Breadcrumb 生成規則

前端依 upstream metadata 自動生成：

```
A1 > A11 > A12 > A17
(dashboard > 工單 > #WO-042 > 退款)
```

規則：
- 若當前頁多個 upstream，依「最近一次進入路徑」決定（存 sessionStorage）
- 若無 referrer（深連結）→ 以 metadata 第一個 upstream 為預設
- 最多顯示 4 層，中間用 `…` 折疊
- 點擊 breadcrumb 回跳時清掉 downstream 的 state

---

## 2. Dirty State 策略

### 2.1 分類

| 類別 | 典型頁面 | 策略 |
|:---|:---|:---|
| **一次性表單**（提交後不需回改） | 退款申請、爭議提出 | `sessionStorage` + 離開 prompt |
| **長期編輯**（草稿可多次回來） | 完工回報、SOP 草稿、品牌設定 | `IndexedDB` + 明確「儲存草稿」按鈕 |
| **列表篩選** | 工單列表、技師列表 | URL query string |
| **離線佇列** | 技師 T5-T9 子流程 | `IndexedDB` + Service Worker Background Sync |
| **即時編輯** | 對話輸入框 | 記憶體（組件 state），不需持久化 |

### 2.2 各類別實作規範

#### 2.2.1 一次性表單（`sessionStorage` + prompt）

```typescript
// 儲存 key: "draft:{route}:{user_id}"
// 例：draft:/admin/refunds/new:user-42

onFormChange: throttle(() => {
  sessionStorage.setItem(key, JSON.stringify(formData))
}, 500)

onRouteLeave: (nextUrl) => {
  if (isDirty) {
    if (!confirm('有未儲存變更，確定離開？')) return false
  }
  sessionStorage.removeItem(key)
}

onPageLoad: () => {
  const draft = sessionStorage.getItem(key)
  if (draft) restoreForm(JSON.parse(draft))
}
```

- **過期**：sessionStorage 隨 tab 關閉清除
- **跨 tab**：不跨 tab（每個 tab 獨立）
- **衝突**：重開同頁 → 提示「還原上次輸入？」

#### 2.2.2 長期編輯（`IndexedDB` + 明確儲存）

- 使用 `idb` 或 `Dexie.js`
- DB 名：`sunny-drafts`，store 名對應資源類型（`work_order_completion`、`sop_drafts`）
- 主鍵：`{resource_id}:{user_id}`
- 可顯示「上次編輯時間」給使用者
- **明確「儲存草稿」按鈕**，與「提交」不同 — 草稿只存 IndexedDB，提交才呼叫 API

#### 2.2.3 列表篩選（URL query）

所有列表頁的 filter、sort、page、tab 必須透過 URL 傳遞（不用 state），目的：
- 可分享連結
- 前進 / 後退行為正確
- 重新整理不丟狀態

#### 2.2.4 離線佇列（IndexedDB + SW）

對齊 `frontend-architecture.md §8.7`：
- Service Worker 攔截 POST/PUT/PATCH 請求
- 失敗（離線 / 網路錯誤）→ 排入 IndexedDB queue
- 重連後 Background Sync 重送
- UI 顯示「已離線，X 個動作待同步」
- 技師 T5-T9 子流程必須支援離線

### 2.3 Dirty State Prompt 統一文案

| 情境 | 文案 |
|:---|:---|
| 未儲存變更離開 | 「有未儲存變更，確定離開？」 |
| 提交前最後確認（關鍵操作） | 「確認送出？送出後不可修改」 |
| 草稿自動儲存成功 | Toast「草稿已儲存」（右下 3 秒） |
| 草稿衝突（IndexedDB 已有更新）| 「偵測到另一個 tab 的變更，要使用哪一份？」 |

---

## 3. 錯誤狀態頁面行為

### 3.1 統一行為表

| HTTP | error_code 範例 | 頁面行為 | UX 要素 |
|:---|:---|:---|:---|
| **401** UNAUTHORIZED | `UNAUTHORIZED`, `TOKEN_EXPIRED` | Refresh 失敗 → 跳登入；retainParams | 登入後自動回到原頁 |
| **403** FORBIDDEN | `FORBIDDEN`, `TENANT_MISMATCH`, `ROLE_REVOKED` | 頁面降級為只讀；顯示 Banner | 「您沒有權限修改此資料」 |
| **404** NOT_FOUND | `NOT_FOUND`, `WORK_ORDER_NOT_FOUND` | 導向列表或 404 頁 | 「此項目已刪除或不存在」 |
| **409** CONFLICT | `WORK_ORDER_CONFLICT`, `OPTIMISTIC_LOCK_FAILED` | 自動 refetch + 顯示 Diff 對話框 | 「資料已被修改，請選擇」|
| **410** GONE | `QUOTE_EXPIRED`, `DISPUTE_SLA_OVERDUE` | 顯示「已過期」狀態，提供新流程 CTA | 報價過期 → 重新報價按鈕 |
| **422** VALIDATION | `VALIDATION_ERROR` | 表單行內錯誤；聚焦第一個錯誤欄位 | 紅框 + 錯誤文案 |
| **423** LOCKED | `LOGIN_ACCOUNT_LOCKED`, `TENANT_SUSPENDED` | 完整頁面訊息（非 toast） | 顯示鎖定時間與聯繫方式 |
| **429** RATE_LIMITED | `RATE_LIMITED` | Toast + 遵循 Retry-After 倒數 | 「請求過於頻繁，X 秒後重試」 |
| **500-504** | `INTERNAL_ERROR`, `SERVICE_UNAVAILABLE`, `GATEWAY_TIMEOUT` | 錯誤頁 + 顯示 X-Request-ID | 「系統異常，請聯繫客服並提供：`req_xxx`」 |
| **離線** | — | 全站 Banner + OfflineQueueIndicator | 「已離線，N 個動作待同步」 |

### 3.2 401 登入後返回原頁

- 登入頁必須接受 `?redirect=/original/path`
- 登入成功後：`router.push(searchParams.get('redirect') || '/dashboard')`
- 若原頁需要特定權限且登入後仍不足 → 降級為 403

### 3.3 403 只讀降級 vs 完整拒絕

| 情境 | 處理 |
|:---|:---|
| 頁面主資料可讀但無寫權限 | 隱藏/禁用所有寫按鈕 + Banner 說明 |
| 頁面主資料完全不可讀（跨租戶） | 404（避免暴露資源存在性） |
| 權限剛被撤銷（透過 WS） | Toast「您的權限已變更，頁面即將刷新」+ 3 秒後 reload |

### 3.4 409 衝突處理

以工單詳情為例：

```
後端：UPDATE work_orders WHERE id=? AND version=?
      → 影響行數 0 → 拋 OPTIMISTIC_LOCK_FAILED

前端：
  1. catch error → 不丟表單資料
  2. GET /work-orders/{id}（取得最新）
  3. 顯示 DiffDialog：「您的編輯」vs「最新版本」
  4. 使用者選擇：保留我的 / 使用最新 / 手動合併
  5. 若選保留我的 → 帶新 version 重送
```

### 3.5 離線 UX 規範

- 全站固定 banner（`OfflineQueueIndicator`）在頂部或底部
- 顯示內容：`已離線` / `連線中...` / `已同步`
- 點擊可展開查看 pending queue
- 每個 queue 項可手動重試、取消
- 技師端特別強化（外勤訊號不穩常見）

---

## 4. Query String 保留字規範

### 4.1 保留字（禁止覆用作業務參數）

| 保留字 | 用途 | 範例 |
|:---|:---|:---|
| `cursor` | Cursor 分頁 | `?cursor=eyJpZCI6NDJ9` |
| `limit` | 分頁大小 | `?limit=50` |
| `sort_by` | 排序欄位 | `?sort_by=created_at` |
| `sort_order` | 排序方向 | `?sort_order=desc` |
| `tab` | 多 Tab 頁面當前 Tab | `?tab=pricing` |
| `q` | 搜尋關鍵字 | `?q=LINE+Pay+失敗` |
| `filter` | 複合篩選（JSON or custom syntax） | `?filter=status:active,brand:LOCKLY` |
| `highlight` | 跳入後標亮某項 | `?highlight=dispute-42` |
| `redirect` | 登入後返回目標 | `?redirect=/work-orders/42` |
| `from` | 來源頁標記（breadcrumb） | `?from=dispatch-queue` |
| `modal` | 開啟指定 modal | `?modal=edit-pricing` |
| `date_from` / `date_to` | 日期範圍 | `?date_from=2026-04-01` |

### 4.2 業務參數命名

- 使用 `snake_case`（對齊後端 API）
- 布林：`true` / `false`（字串，不用 `1`/`0`）
- 日期：ISO 8601（`2026-04-23` 或 `2026-04-23T10:00:00Z`）
- 多值：重複 key（`?category=a&category=b`）或逗號（`?category=a,b`）— **全專案擇一**

**決策：** 採重複 key 方式（對齊 OpenAPI `explode: true` style=form 慣例）。

### 4.3 長 URL 處理

- 任何單一 URL 總長 > 2048 字元 → 改用 POST body + opaque `?query_id=xxx`
- 前端列表頁的複雜 filter 若超長，後端提供 `POST /queries` 儲存後回 id

---

## 5. 深連結與 PWA 頁面棧

### 5.1 深連結支援清單

以下頁面必須支援深連結（從 LINE Push、Email、PWA 捷徑直接開啟）：

| IA | 路由 | 深連結情境 |
|:---|:---|:---|
| A3 `/conversations/[id]` | LINE Push 對話提醒 |
| A12 `/work-orders/[id]` | LINE Push 工單變更 |
| A17 `/admin/refunds/[id]` | Email 審批請求 |
| A22 `/admin/disputes/[id]` | Email 爭議升級 |
| T3 `/my-orders/[id]` | LINE Push 派工 / PWA |
| T1 `/pool` | PWA 捷徑 |
| T11 `/my-orders/[id]/reschedule` | LINE Push 客戶改期請求 |

### 5.2 深連結初始化規則

深連結開啟時：
1. **驗證登入狀態** — 未登入 → 存 `?redirect=<current-url>` → `/login`
2. **驗證權限** — 無權限 → 403 頁
3. **驗證資源存在** — 不存在 → 404 頁
4. **初始化 breadcrumb** — 從 metadata upstream 取第一個
5. **清除無關 state** — 不帶 sessionStorage 的 pending state

### 5.3 PWA 特殊行為

- 開啟 PWA 時檢查 service worker 更新 → 有新版本 → 提示「更新可用」
- 離線時 PWA 仍可開 T1-T3（預快取）
- 技師 PWA 預設首頁 `/pool`；管理員 PWA 預設 `/dashboard`
- PWA 內的外連結（LINE、Email、電話）→ 開啟系統預設 app

### 5.4 頁面棧

- 瀏覽器 history stack 正常維護（勿用 `replace` 除非必要）
- `replace` 使用場景：登入後重導、404 自動導向、modal 關閉
- `push` 使用場景：正常導航

---

## 6. 多頁簽同步

### 6.1 問題情境

- 管理員同時開兩個 tab 看同一張工單 A12，其中一個 tab 按了「接受退款」，另一個 tab 畫面仍是舊狀態

### 6.2 同步機制

採雙層策略：

| 層級 | 實作 | 覆蓋情境 |
|:---|:---|:---|
| **層 1：WebSocket 廣播** | 訂閱 `/realtime/work-orders/{id}` 等頻道，收到事件 → refetch | 跨 tab + 跨使用者 |
| **層 2：BroadcastChannel**（同 origin 跨 tab） | 頁面內寫操作後 → `channel.postMessage({type:'work_order.updated',id})` | 同裝置同 origin 即時同步 |

### 6.3 實作規範

```typescript
// lib/realtime/broadcast.ts
const channel = new BroadcastChannel('sunny-realtime')

// 寫操作後廣播
export function broadcastUpdate(resource: string, id: string) {
  channel.postMessage({ type: `${resource}.updated`, id, timestamp: Date.now() })
}

// 訂閱端
channel.addEventListener('message', (e) => {
  if (matches(e.data, currentResource)) {
    queryClient.invalidateQueries([resource, id])
  }
})
```

### 6.4 衝突處理

當本 tab 正在編輯，另一 tab 有變更：
- 本 tab **不自動覆蓋使用者輸入**
- 顯示 Toast：「另一個 tab 剛變更了此工單，儲存前請重新檢視」
- 使用者可按「看最新版本」或繼續編輯（儲存時以 409 optimistic lock 防護）

### 6.5 通知頻道汰舊

單使用者開 10+ tabs 可能導致 WS 連線數爆量，採：
- 每頁獨立訂閱（簡單）
- 或使用 Shared Worker 集中訂閱（進階，V3.1 優化）

**決策：** V3.0 採每頁獨立訂閱；若 WS 連線數超負荷再改 Shared Worker。

---

## 7. 跨子頁面返回

### 7.1 情境

- A12 工單詳情 → 點爭議 → A22/[id] 爭議頁 → 結案後回 A12
- A11 工單列表（帶 filter）→ A12 詳情 → 返回需要保留 filter

### 7.2 返回策略

| 來源 → 目標 | 返回方式 | 保留內容 |
|:---|:---|:---|
| 列表 → 詳情 → 返回 | `router.back()` | 列表的 filter、sort、page、scroll position |
| 詳情 → 子頁 → 返回 | `router.back()` | 詳情頁的 tab、scroll |
| 深連結 → 詳情 → 返回 | 走 metadata upstream 預設 | — |
| 多步驟流程（Wizard）| Stepper 上一步按鈕 | 每步填寫內容 |
| 錯誤頁 → 返回 | `router.back()`，若無 history → 回儀表板 | — |

### 7.3 `highlight` 參數使用

從子頁回主頁時，若需要標亮剛才的項目：

```
/work-orders/42?highlight=dispute-17&from=dispute-resolve
```

主頁 A12 的實作：
- 讀 `?highlight` → 捲到該元素並套 5 秒閃爍動畫
- 讀 `?from` → 決定 toast 文案（「爭議已結案」）
- 處理完成後清掉 query（`router.replace` 移除 highlight/from）

### 7.4 Scroll Position Restoration

- Next.js 14 App Router 預設支援 `scrollRestoration`
- 但對帶 filter 的列表需手動：
  - 離開前存 `sessionStorage.setItem('scroll:'+path, window.scrollY)`
  - 返回後 `window.scrollTo(0, parseInt(sessionStorage.getItem(...)))`
- 無限捲動列表需特別處理：記錄 cursor + scrollY，返回時重放

---

## 8. 校對檢核表（給使用者）

- [ ] §1.2 `page_metadata` 區塊結構是否合理？是否需改為 JSON Schema 以利工具驗證？
- [ ] §1.3 矩陣列的核心頁面取樣是否具代表性？
- [ ] §2.1 表單分類 5 類是否覆蓋全站所有表單？
- [ ] §2.2.2 `sunny-drafts` IndexedDB DB 命名是否與其他模組衝突？
- [ ] §3.1 錯誤狀態表是否對齊 `error-codes.md`？
- [ ] §3.3 403 降級 vs 404（跨租戶）的隱私考量是否充分？
- [ ] §4.1 12 個保留字是否齊全？`per_page` / `page_size` 等同義詞統一為 `limit` 是否夠明確？
- [ ] §4.2 多值採重複 key vs 逗號 — 決策是否需與後端確認？
- [ ] §5.1 深連結頁面清單 7 頁是否完整？客戶端（LINE Webview）是否需要獨立清單？
- [ ] §6.2 BroadcastChannel 瀏覽器相容性（Safari 從 15.4 才支援）→ 降級策略？
- [ ] §6.5 Shared Worker 延後到 V3.1 是否合理？
- [ ] §7.3 `?highlight` + `?from` 是否會與 §4.1 的 `filter` / `tab` 等衝突？

---

## 9. 實施計畫（與 T1.5 銜接）

本檔建立後，T1.5「19 份 spec 補 4 個標準段」改以本檔為藍本：

**每份 pipeline page spec 頂部加入：**
```
## 頁面元資料 (Page Metadata)

見 `docs/02-design/E5x--frontend-navigation-matrix.md §1.2` 結構。
```

**每份 spec 結尾加入「導航與狀態」段：**
```
## 導航與狀態 (Navigation & State)

### Upstream Sources
[依矩陣填]

### Downstream Targets
[依矩陣填]

### State Persistence
[查表決定採哪類策略]

### Error Navigation
[參見 §3.1 統一行為表]
```

---

## 10. 變更記錄

| 日期 | 版本 | 變更摘要 |
|:---|:---|:---|
| 2026-04-23 | v0.1 | 初稿（Claude 起草）：7 節（導航矩陣/Dirty State/錯誤/QS/深連結/多頁簽/返回）+ 校對清單 |
| 2026-04-23 | v0.2 | T1.5 完整附錄：21 份 pipeline spec 的 Upstream/Downstream/State/Error 矩陣 |

---

## 附錄 A：21 份 Pipeline Spec 導航與狀態矩陣（T1.5）

> 每份 pipeline page spec 的標準「Upstream Sources / Downstream Targets / State Persistence / Error Navigation / Deep Link / Multi-tab」彙總於本附錄。
> 各 spec 透過「見 navigation-matrix §附錄 A」一行引用，避免 19 份檔案重複維護。

### 02_admin_dashboard.md — A1 /dashboard
- **Upstream**: A0 登入後、任一頁 app header home icon
- **Downstream**: A11 工單、A28 派工、A17 退款、A29 KPI、G1 通知
- **State Persistence**: widget 折疊狀態 via localStorage；即時指標不持久化
- **Error Navigation**: 401 → 登入；500 → 顯示 degraded banner
- **Deep Link**: supported（PWA 首頁）
- **Multi-tab**: WS `/realtime/sla-alerts` + `/realtime/notifications`

### 03_admin_conversations.md — A2 列表 / A3 詳情
- **Upstream A2**: A1 side nav、搜尋；**A3**: A2 列表、LINE Push 深連結
- **Downstream A2**: A3；**A3**: A4/A5 問題卡、A11 新建工單、A37 人工派工
- **State Persistence**: A2 filter via URL query；A3 對話捲軸位置 via sessionStorage
- **Error Navigation**: 404 → A2 + toast「對話不存在」；409 併入 diff
- **Deep Link**: supported（A3 `/conversations/[id]?message=msg_xxx` highlight 單則訊息）
- **Multi-tab**: WS `/realtime/work-orders/*` 若對話已開工單

### 04_admin_problem_cards.md — A4 列表 / A5 詳情
- **Upstream**: A3 對話衍生、A2 搜尋、A12 工單詳情反查
- **Downstream**: A5、A11 / A12、A3 對話
- **State Persistence**: filter via URL query；草稿 via sessionStorage
- **Error Navigation**: 404 → A4；409 `PROBLEM_CARD_LOCKED` → 只讀模式
- **Deep Link**: supported
- **Multi-tab**: WS 對應對話頻道

### 05_admin_knowledge_base.md — A6/A7/A8/A9/A10
- **Upstream**: A1 side nav、A3 對話案例衍生、A10 SOP 審核佇列
- **Downstream**: 案例詳情、手冊預覽、SOP diff、A33 績效
- **State Persistence**: tab 選擇 via URL（?tab=cases|manuals|sop-drafts）；SOP 草稿編輯 via IndexedDB（長期編輯類）
- **Error Navigation**: 404 → tab 列表；423 審核中鎖定 → 顯示編輯中提示
- **Deep Link**: supported（`?case_id=xxx` 深連結案例）
- **Multi-tab**: WS 無專用頻道；BroadcastChannel 本地同步

### 06_admin_work_orders.md — A11
- **Upstream**: A1 side nav、全域搜尋、A2/A3 轉工單、外部連結
- **Downstream**: A12、A37 手動派工、A28 派工佇列
- **State Persistence**: 列表 filter/sort/page via URL query（含 Kanban vs List 切換）；scroll 位置 via sessionStorage
- **Error Navigation**: 401 重導、403 禁用按鈕、5xx 錯誤 banner
- **Deep Link**: supported（filter 可書籤）
- **Multi-tab**: WS `/realtime/dispatch-queue` + BroadcastChannel

### 07_admin_work_order_detail.md — A12（已於 T1.4 延伸）
- **Upstream**: A11、A28、搜尋、深連結、LINE Push、A37 指派後
- **Downstream**: A17 退款、A22 爭議、T5-T9 子流程、A37、客訴升級
- **State Persistence**: 編輯表單 via IndexedDB（長期編輯）；tab 選擇 via URL
- **Error Navigation**: 404 → A11；409 `OPTIMISTIC_LOCK_FAILED` → diff 對話框；423 → 只讀
- **Deep Link**: supported
- **Multi-tab**: WS `/realtime/work-orders/{id}` + BroadcastChannel

### 08_admin_technicians.md — A13 列表 / A14 詳情
- **Upstream**: A1 side nav、A12 指派連結、搜尋
- **Downstream**: A14、A25 排班、A26 技能、A27 結算
- **State Persistence**: filter/sort via URL
- **Error Navigation**: 404 → A13；423 熔斷中 → 警告 banner
- **Deep Link**: supported
- **Multi-tab**: WS `/realtime/rbac` 權限變更即時生效

### 09_admin_accounting.md — A15
- **Upstream**: A1 side nav、A17 退款後、A12 工單計費衍生
- **Downstream**: 發票 PDF 預覽、A20 稽核、A22 爭議
- **State Persistence**: 期間選擇 via URL；對帳篩選 via URL
- **Error Navigation**: 5xx 降級為快取；402 `PAYMENT_FAILED` → 行內重試
- **Deep Link**: supported（期間參數）
- **Multi-tab**: WS `/realtime/refunds`

### 10_admin_advanced.md — A17/A18/A19/A20/A21/A22
- **Upstream**: A1 side nav、儀表板告警、G1 通知跳轉
- **Downstream**: A12（爭議/退款關聯）、A14（稽核行為主體）
- **State Persistence**: 子頁 tab via URL；列表 filter via URL；草稿 via sessionStorage
- **Error Navigation**: 409 雙簽 pending、423 已鎖定、403 權限不足（依 RBAC 子權限）
- **Deep Link**: supported（每子頁獨立 route）
- **Multi-tab**: WS 依子頁 `/realtime/refunds` `/realtime/disputes` `/realtime/rbac` `/realtime/inventory/low-stock`

### 11_tech_pool.md — T1
- **Upstream**: T0 登入後、bottom nav、Push notification
- **Downstream**: T3 工單詳情（接單後）
- **State Persistence**: 地圖 center/zoom via sessionStorage
- **Error Navigation**: 離線 → 本地快取顯示；5xx → degraded banner
- **Deep Link**: supported（PWA 首頁）
- **Multi-tab**: WS `/realtime/pool/{tech_id}`

### 12_tech_my_orders.md — T2 列表 / T3 詳情
- **Upstream T2**: T1 接單後、bottom nav、Push；**T3**: T2、LINE Push、PWA 捷徑
- **Downstream T3**: T5-T9 子流程、T11 改期
- **State Persistence**: tab via URL；T3 完工報告 via IndexedDB（長期 + offline queue）
- **Error Navigation**: 離線 queue via SW；409 → refetch；404 → T2
- **Deep Link**: supported
- **Multi-tab**: WS `/realtime/work-orders/{id}` + BroadcastChannel

### 13_tech_account.md — T4
- **Upstream**: bottom nav
- **Downstream**: T10 排班（`/account/schedule`）、登出
- **State Persistence**: 個資編輯 via sessionStorage（一次性）
- **Error Navigation**: 401 → T0
- **Deep Link**: supported
- **Multi-tab**: WS `/realtime/rbac`

### 14_auth_and_settings.md — A0 / T0 / A16
- **Upstream A0/T0**: 直接；**A16**: A1 header settings
- **Downstream**: A1 / T1（登入後）；A16 登出、租戶切換
- **State Persistence**: MFA secret via sessionStorage（短暫）；A16 設定 via IndexedDB（長期編輯類，有 dirty warning）
- **Error Navigation**: 401 `LOGIN_INVALID_CREDENTIALS` 行內紅字；423 `LOGIN_ACCOUNT_LOCKED` 頁面鎖定
- **Deep Link**: A16 sub tab via URL `?tab=notifications|pricing|rules|integrations`
- **Multi-tab**: WS `/realtime/rbac`（權限變更即時重繪）

### 15_admin_customers_and_diagnostics.md — A23/A24/A32/A33
- **Upstream**: A1、A3 對話延伸、A12 工單延伸
- **Downstream**: A12 相關工單、A22 爭議歷史、SOP 詳情
- **State Persistence**: 客戶 PII 檢視歷程 via sessionStorage；A32 診斷 reasoning 串流 via React state（不持久）
- **Error Navigation**: 403 PII 遮蔽降級；410 串流過期
- **Deep Link**: A24 tabs via URL、A32 `/admin/diagnostics/[conv_id]`
- **Multi-tab**: WS `/realtime/diagnostics/{conv_id}` SSE（A32）

### 16_admin_technician_detail.md — A25/A26/A27
- **Upstream**: A14 技師詳情
- **Downstream**: A12 關聯工單、A15 結算匯出
- **State Persistence**: 排班編輯 via IndexedDB；技能認證上傳 via SW offline queue
- **Error Navigation**: 409 排班衝突（對齊 Flow 14）→ 顯示衝突詳情；422 技能過期阻擋
- **Deep Link**: supported
- **Multi-tab**: WS `/realtime/dispatch-queue`

### 17_admin_dispatch_queue_and_reports.md — A28/A29/A30/A31
- **Upstream**: A1 side nav、儀表板告警、A37 返回
- **Downstream**: A12 工單詳情、A37 手動派工、PDF 匯出
- **State Persistence**: 過濾器 via URL；報表期間 via URL
- **Error Navigation**: 413 匯出過大 → 改非同步；410 快取過期 → 重查
- **Deep Link**: supported（PDF direct link）
- **Multi-tab**: WS `/realtime/dispatch-queue` + `/realtime/sla-alerts`

### 18_admin_multi_tenant.md — A34/A35/A36
- **Upstream**: A1 side nav（super_admin）、A16 租戶切換
- **Downstream**: A35 品牌詳情、A36 子頁、B2B Key 詳情、租戶 Wizard
- **State Persistence**: 品牌草稿 via IndexedDB；送審後 via server state
- **Error Navigation**: 403 非 super_admin 重導；422 `BRAND_CONFIG_INVALID` 行內
- **Deep Link**: supported（子頁 tab via URL）
- **Multi-tab**: WS `/realtime/rbac`（租戶狀態變更即時生效）

### 19_tech_workorder_subflows.md — T5/T6/T7/T8/T9/T10（含客戶 RSVP）
- **Upstream**: T3 工單詳情各 action button
- **Downstream**: T3（完成後返回）；T9 簽章 → 客戶 LINE Flex；T11 改期
- **State Persistence**: 各子流程草稿 via IndexedDB；離線 queue via SW Background Sync
- **Error Navigation**: 離線佇列；409 狀態機阻擋；422 表單
- **Deep Link**: supported
- **Multi-tab**: WS `/realtime/work-orders/{id}` + BroadcastChannel

### 20_admin_dispatch_manual.md — A37（已於 T1.3 含）
（已在檔案內「導航與狀態」段定義）

### 21_global_notifications.md — G1（已於 T1.3 含）
（已在檔案內「導航與狀態」段定義）

### 22_reschedule_calendar.md — T11（已於 T1.3 含）
（已在檔案內「導航與狀態」段定義）

---

## 附錄 B：T1.5 套用規範

每份 `pages/*.md`（除 20/21/22 已完整外）於檔末追加：

```markdown
---

## 導航與狀態 (Navigation & State)

完整 Upstream / Downstream / State / Error 規範見
`docs/02-design/E5x--frontend-navigation-matrix.md §附錄 A`。

本檔覆蓋的頁面：<IA 編號>
```

採集中維護模式避免 19 份檔案各自手動同步時漂移。未來若個別頁面有特殊規則，可在此引用下方補一行 `本檔特例：...`。
