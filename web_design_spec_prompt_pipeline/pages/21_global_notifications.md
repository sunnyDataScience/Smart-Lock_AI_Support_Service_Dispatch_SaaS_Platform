# Page-Level Prompt: 全域 — 通知中心

> IA 編號 **G1**（Global 類）。跨角色的統一通知收件匣，整合 WebSocket 事件、LINE Push 鏡像、系統告警。

---

## [PAGE META]

- **page_name**: 通知中心 Notification Center
- **route_path**: `/notifications`（全路徑；Admin + Technician 共用）
- **page_type**: inbox
- **primary_goal**: 讓使用者集中管理所有類型通知（未讀 / 已讀 / 全部），點擊深連結回來源頁
- **secondary_goal**: 提供過濾與搜尋，避免通知淹沒
- **target_users**:
  - Admin panel 所有角色（`admin`, `operations_manager`, `accountant`, `support_agent` 等）
  - Technician（PWA 內同路由）
- **entry_point**:
  - 全站 header bell icon（含未讀紅點）
  - Push notification 點擊
  - Email 連結
  - Deep link from LINE message
- **expected_time_on_page**: 30 秒 – 5 分鐘（掃讀 → 處理關鍵 → 離開）

---

## [STRUCTURE: SECTIONS]

1. **header_bar**
   - section_type: top_bar
   - section_purpose: 頁面標題、未讀計數、批量動作按鈕

2. **tab_group**
   - section_type: segmented_tabs
   - section_purpose: 切換「全部 / 未讀 / 已讀 / 已存檔」

3. **filter_chips**
   - section_type: filter_chips
   - section_purpose: 依類型篩選（工單 / 退款 / 爭議 / RBAC / 庫存 / 系統）

4. **notification_list**
   - section_type: timeline_list
   - section_purpose: 通知卡片列表，依時間倒序

5. **empty_state**
   - section_type: empty_state
   - section_purpose: 無通知時的友善說明

6. **detail_preview**
   - section_type: side_preview（桌面） / overlay（手機）
   - section_purpose: 點卡片預覽詳細內容與原始事件 payload

7. **bulk_actions_toolbar**
   - section_type: sticky_toolbar
   - section_purpose: 複選後出現 — 標記已讀 / 存檔 / 刪除 / 批量跳轉

8. **preference_shortcut**
   - section_type: link
   - section_purpose: 連到「通知偏好設定」（A16 系統設定）

---

## [SECTION COMPONENT SPEC]

### Section: header_bar

- **layout**: 頂部固定，高度 64px
- **elements**:
  - title: Heading H2 / 「通知中心」
  - unread_count: Chip / required / 「未讀 12」（即時更新）
  - mark_all_read_btn: Button Secondary / 「全部標為已讀」（有未讀時顯示）
  - settings_btn: IconButton / Settings icon / 連到偏好設定
- **states**:
  - default: 正常顯示
  - all_read: 隱藏 mark_all_read_btn

### Section: tab_group

- **layout**: header 下方，segmented 4 Tab，水平排列
- **tabs**:
  - all: 全部（所有狀態，不含已刪除）
  - unread: 未讀（預設 Tab）
  - read: 已讀
  - archived: 已存檔
- **badge**: 每 Tab 顯示數量（`未讀 12`）
- **states**:
  - active / inactive

### Section: filter_chips

- **layout**: 可水平捲動的 Chip group
- **chips**:
  - all: 預設選中
  - work_order: 工單類
  - refund: 退款審批
  - dispute: 爭議
  - rbac: 權限變更
  - inventory: 庫存告警
  - sla: SLA 告警
  - system: 系統類（維護、升級）
  - mention: 被 @ 的通知
- **states**:
  - selected / default：多選（OR 關係）

### Section: notification_list

- **layout**: 垂直列表，每項 80-120px 高度（依內容）
- **card_elements**:
  - unread_indicator: Dot / required if 未讀 / 左側藍點
  - type_icon: Icon / required / 依類型（工單 📋 / 退款 💰 / 爭議 ⚖ / RBAC 🔑 / 庫存 📦 / SLA ⏰ / 系統 ⚙）
  - title: Heading H4 / required / 通知標題（最多 2 行 overflow ellipsis）
  - preview: Body SM / required / 內容預覽（1 行 ellipsis）
  - meta_row:
    - timestamp: Caption / 相對時間（「5 分鐘前」），hover 顯示絕對時間
    - severity_badge: Badge / required if 非 info / 顏色：warning=橙、critical=紅
    - source_chip: Chip / 來源（WebSocket / LINE / System）
  - action_buttons: 快速動作 chips（依類型）：
    - 工單類：「查看工單」「指派」
    - 退款類：「審批」
    - 爭議類：「進入仲裁」
- **states**:
  - default: 白底
  - unread: 淺藍背景（#F0F9FF）
  - selected: 外框 2px primary
  - hovered: shadow elevation
  - actioned: 灰字 + strikethrough（已完成相關動作）
- **interactions**:
  - 點卡片：右側 preview 展開（桌面） / 切換到 detail（手機）
  - checkbox：複選（長按或 hover 出現）
  - 右滑（手機）：快速標記已讀 / 存檔

### Section: empty_state

- **layout**: 置中顯示
- **elements**:
  - illustration: 友善插畫
  - title: 「沒有通知」 / 「已看完所有未讀」
  - cta: 「查看設定」連到偏好

### Section: detail_preview

- **layout**: 桌面右側 400px / 手機全屏
- **elements**:
  - close_btn: IconButton X
  - full_title: Heading
  - full_body: 完整內容（可含圖片、mermaid 圖、表格）
  - related_entity_link: 「查看工單 #WO-042」Button Primary
  - raw_payload_toggle: 「查看事件 JSON」（開發者模式）
  - action_buttons: 原卡片的 action（放大版）
  - mark_read_btn: 標為已讀 / 未讀
  - archive_btn: 存檔

### Section: bulk_actions_toolbar

- **layout**: 底部 sticky（有選取時）
- **elements**:
  - selected_count: 「已選 N 則」
  - mark_read_btn / mark_unread_btn
  - archive_btn
  - delete_btn（帶二次確認 modal）
  - cancel_btn: 清除選取

### Section: preference_shortcut

- **layout**: 列表底部或 header 右側 icon
- **elements**:
  - link: 「管理通知偏好」→ /admin/settings?tab=notifications

---

## [INTERACTION & STATE FLOW]

### 進入流程

| 來源 | 行為 |
|:---|:---|
| Bell icon 點擊 | 開啟並自動切到「未讀」Tab |
| Push notification click | 開啟對應那則的 detail_preview 預設展開 |
| URL `/notifications?tab=all&type=refund` | 依參數載入 |
| 深連結 `/notifications?id=xxx` | 直接 scroll 到該則並 highlight |

### 核心互動

1. 載入：預設顯示「未讀」+ 最近 50 則
2. 滾動至底：loading spinner + cursor 分頁取下 50 則
3. 點卡片：右側 preview 展開；同時自動標為已讀（2 秒延遲避免誤點）
4. 複選：bulk_actions_toolbar 顯示 → 批量動作
5. 即時更新：WS 推播新通知 → 列表頂部插入新項 + 紅點 + 可選音效

### Dirty State / Error

- 無表單輸入，無 dirty state
- 網路錯誤：Banner + 重試；本地預快取最近 100 則

### 即時更新

訂閱 `/realtime/notifications/{user_id}`：
- 新通知 → 列表頂部插入 + unread_count + 1
- 該通知被他 tab 標已讀 → 同步更新（BroadcastChannel）
- 全部標為已讀 → unread_count = 0

---

## [DATA & API]

### 列表

```
GET /api/v1/notifications?status=unread&type=work_order,refund&cursor=...
Response 200: {
  items: [
    {
      id: uuid,
      type: "work_order" | "refund" | "dispute" | "rbac" | "inventory" | "sla" | "system" | "mention",
      severity: "info" | "warning" | "critical",
      title: string,
      body: string,
      source: "websocket" | "line_push" | "system" | "email_fallback",
      created_at: ISO8601,
      read_at: ISO8601 | null,
      archived_at: ISO8601 | null,
      related_entity: { type, id, url },  // 深連結回來源頁
      actions: [{ label, endpoint, method }],  // 快速動作
      raw_event_id: uuid  // 對應 domain event（除錯用）
    }
  ],
  next_cursor: string,
  unread_count: 12
}
```

### 標記已讀

```
PATCH /api/v1/notifications/{id}
Body: { read_at: ISO8601 }
```

### 批量動作

```
POST /api/v1/notifications/bulk
Body: {
  ids: [uuid, ...],
  action: "mark_read" | "mark_unread" | "archive" | "delete"
}
```

### 全部標已讀

```
POST /api/v1/notifications/mark-all-read
Body: { filter: { type?, status? } }  // 可選，不帶則全部
```

### WebSocket 訂閱

- `/realtime/notifications/{user_id}` — 新通知即時推送

### 事件 payload 範例

```json
{
  "id": "ntf_abc123",
  "type": "work_order",
  "severity": "warning",
  "title": "工單 #WO-042 SLA 即將違反",
  "body": "預計 15 分鐘後違反回應 SLA，請盡快指派技師",
  "related_entity": {
    "type": "work_order",
    "id": "wo_042",
    "url": "/admin/dispatch-manual?work_order_id=wo_042"
  },
  "actions": [
    { "label": "進入派工", "endpoint": "/admin/dispatch-manual?work_order_id=wo_042", "method": "GET" }
  ]
}
```

---

## [EXCEPTION TO GLOBAL RULES]

- 「自動標已讀」的 2 秒延遲可被全域偏好設定覆寫（`autoMarkReadOnView: boolean`）
- Critical 通知**不可**被「全部標已讀」一次清除 → 必須點進去處理（避免誤忽略）
- 通知 TTL：180 天後自動存檔、1 年後硬刪除（對齊 `audit-log-spec.md` 認證類保留期）
- 被刪除的通知若對應 entity 仍 active，系統重新建立（避免 user 誤刪關鍵 action）

---

## [ACCEPTANCE CRITERIA]

- [ ] 進入後 < 1 秒載入最近 50 則
- [ ] WS 新通知抵達 < 2 秒顯示
- [ ] unread_count 與 header bell 紅點同步
- [ ] 跨 tab 同步（BroadcastChannel）
- [ ] 點通知可正確跳到深連結頁面
- [ ] 批量動作 1000 則內 < 3 秒完成
- [ ] 離線時可讀最近 100 則快取
- [ ] 無障礙：鍵盤可完全操作（Tab / Enter / Space）
- [ ] Screen reader 正確讀出 unread_count 變化

---

## 導航與狀態 (Navigation & State)

對齊 `docs/02-design/E5x--frontend-navigation-matrix.md §1.3`：

- **Upstream**: 全站 bell icon（任何頁面）、push notification、email、LINE message
- **Downstream**: 依通知類型跳到 A12 / A17 / A22 / A18 / A19 / A37 等
- **State Persistence**: tab + filter via URL query
- **Error Navigation**: 401 重導登入回此頁、500 顯示錯誤 banner 保留快取
- **Deep Link**: supported（`?id=xxx` 直達某則）
- **Multi-tab Sync**: WS + BroadcastChannel（讀取狀態跨 tab 同步）

---

## 校對檢核表

- [ ] Critical 通知不可全部已讀的強制規則是否合理？
- [ ] 已刪除但 entity 仍 active 時「系統重建」是否會造成重複？
- [ ] Push / Email / LINE 的鏡像策略 — 哪些通知要推全管道，哪些只推 App？
- [ ] 技師 PWA 離線時的 100 則快取是否足夠？
- [ ] 通知偏好設定（勿擾時段、類型開關）是否需獨立頁面？
- [ ] 存檔 vs 刪除的差異使用者是否能理解？
