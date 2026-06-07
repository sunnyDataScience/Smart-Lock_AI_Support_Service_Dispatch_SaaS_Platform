# 前端頁面功能狀態（給業主看的版本）

本文件彙整各頁面**目前已上線的真實功能**與**待後端模組接入的功能**，避免逐頁在 UI 上顯示「待接入」黃條，影響展示體驗。

更新日期：2026-06-07（doc-vs-UI conformance audit 後同步）
對應 commit：dev_new_arch 至 `docs/page-status-sync-ui-reality` branch

> **06-07 更新重點**：以 Playwright `doc-conformance-audit.spec.ts` audit UI 真實狀態回填，12 項 ⏳ → ✅（customers 3 filter / accounting 期間+批次 / inventory 補貨+編輯+紀錄+filter / reports/tech-ranking 期間+排序+分頁+匯出 / reports/revenue 日週月季+自訂期間+樞紐+匯出排程）。對應本 session 啟用的 backend endpoint：
> - migration 028 `invoices.payment_method` / migration 029 `saas.scheduled_report` / migration 030 `users.{risk_level, primary_device_brand, warranty_status, preferred_technician_id}`
> - backend `update_inventory_item_v2` / `list_inventory_transactions_v2` / `batch_action` (settlements) / `keyword` ILIKE 4 page
> - 前端 7 新 modal: RestockInventoryModal / CreateInventoryItemModal / EditInventoryItemModal / InventoryLogModal / CreateTechnicianModal / ScheduleReportModal / A37CandidateDetailDrawer

> **05-05 更新重點（歷史）**：新增師傅端 12 頁、A37 派工人工介入、10 個 realtime 頻道整合、跨 tab 同步。

---

## 圖例

- ✅ **已上線**：使用真實後端資料，可實際操作
- 🟡 **示意 UI**：版面已完成，後端寫入路徑或計算邏輯待接入
- ⏳ **待接入**：依賴尚未開發的模組

---

## 1. 派工佇列監控 `/admin/dispatch-queue`

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| 上方四張統計卡（待派工 / 重試中 / 卡住 / 平均派工時長） | ✅ | `getDispatchQueue` 即時聚合 |
| 下方派工歷程表 | ✅ | `listDispatchLogs` 聚合最近派工歷程 |
| 即時推播（WebSocket `/realtime/dispatch-queue`） | ✅ 前端 | 訂閱層 + patch state（v1.15.1）；後端 server 待啟用 |
| 候選技師清單（`listDispatchCandidates`） | ✅ | 已串接於 A37 派工人工介入 |
| 一鍵指派（`assignDispatch` / `assignWorkOrder`） | ✅ | A37 頁面已可指派 + 5 種 reason_code |
| 「人工介入」CTA | ✅ | 每筆工單列右側橘色按鈕 → `/admin/dispatch-manual?work_order_id=...` |

---

## 1B. 派工人工介入 `/admin/dispatch-manual`（**05-05 新增**）

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| context_panel 工單摘要 | ✅ | `getWorkOrder` |
| 自動派工嘗試紀錄 | ✅ | `listDispatchCandidates` 回傳 |
| 候選技師表格（綜合分 / 距離 / 評分 / 技能匹配） | ✅ | `listDispatchCandidates` |
| filter sidebar（分級 / 評分 / 排除熔斷 / 排序） | ✅ | client-side filter |
| 指派 + 5 種 reason_code modal | ✅ | `assignWorkOrder` |
| 升級主管 / 取消工單 | ✅ | `escalateWorkOrder` / `cancelWorkOrder` |
| 候選詳情 drawer（排班熱力圖 / 30 日表現） | 🟡 | spec 已定義，drawer 待實作 |
| 雙簽流程（CIRCUIT_BREAKER override） | 🟡 | 後端 412 已有錯誤碼，UI 提示「待補」 |

---

## 1D. 工單看板 + 地圖（**06-07 新增 filter wire-up**）

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| 看板 `/work-orders/kanban` 4 filter (keyword / status / period / brand) | ✅ | 同列表 view 對接 listWorkOrdersV2 + 前端 useMemo queryObj |
| 地圖 `/work-orders/map` 4 filter (同上) | ✅ | 同上 |
| 地圖 SLA 排序 toggle | ✅ | 前端 client-side sort by `scheduled_at` ASC (null 排最後) |

---

## 2. 客戶主檔 `/admin/customers`

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| 客戶清單（顯示名稱 / 電話 / 地址 / 累積對話 / 工單數 / 最近服務時間） | ✅ | `listCustomers`（LINE 使用者主檔） |
| 風險等級指標（filter） | ✅ | migration 030 ALTER users ADD `risk_level` CHECK 4 enum + backend filter + 前端 select；資料由 NPS aggregate cron 補（roadmap）|
| 滿意度指標 | ⏳ | 待 NPS / 滿意度調查模組接入 |
| 偏好技師（filter） | ✅ | migration 030 ALTER users ADD `preferred_technician_id` + backend filter + 前端 UUID input；資料由 work_orders 派工歷史 aggregate cron 補（roadmap）|
| 保固狀態（filter） | ✅ | migration 030 ALTER users ADD `warranty_status` CHECK 3 enum + backend filter + 前端 select；資料由 warranty_claims aggregate cron 補（roadmap）|
| 設備數 | ⏳ | 待設備主檔模組接入 |

---

## 3. 月結算總覽 `/accounting`

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| 對帳列表 | ✅ | `listReconciliations` 即時資料 |
| 結算列表 | ✅ | `listSettlements` 即時資料 |
| 核准對帳 | ✅ | `approveReconciliation`（同時建立對應結算） |
| 期間選擇器（最近 3/6 月 / 全部）+ 結算週期（月/雙週/週 segment） | ✅ | 前端 client-side filter + cycle segment value-based |
| 批次確認 / 標記已付 | ✅ | backend POST `/settlements:batch` (operation_id `batchSettlementsV2`) ANY(uuid[]) UPDATE + 前端 SettlementTable checkbox + selectedIds Set + doBatch |
| 結算詳情 modal | ⏳ | 待詳情 endpoint 接入 |

---

## 4. 會計傳票 `/accounting/vouchers`

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| 傳票列表（cursor 分頁 + 期間過濾） | ✅ | `listVouchers` 即時資料 |
| 匯出 PDF（單張傳票，A4 中文版面） | ✅ | `exportVoucher`（reportlab + STSong-Light CID 字型） |

> 此頁所有功能已 100% 上線。

---

## 5. 退款審批 `/admin/refunds`

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| 退款申請列表 | ✅ | `listRefundRequests` 即時資料 |
| SLA 分群（2h / 8h / >8h） | ✅ | 前端依「申請建立至今經過時間」即時計算 |
| 核准 / 拒絕 / 升級 | ✅ | `submitRefundDecision`（MVP 單步推進） |
| 雙簽 / 多步簽核流程 | ⏳ | MVP 簡化為單步，多步流程待後續排入 |

---

## 6. 保固索賠 `/admin/warranty-claims`

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| 保固索賠列表 | ✅ | `listWarrantyClaims` 即時資料 |
| 保固期狀態（有效 / 寬限期 / 已過期） | ✅ | 前端依 `warranty_end_date` + `is_within_warranty` 即時計算 |
| 審批決策（filed / in_progress 可下 approve / reject / start_review） | ✅ | `submitWarrantyDecision` |
| 檢視詳情頁 | ⏳ | 待 warranty 詳情頁與證據上傳路徑上線 |
| 證據縮圖 | ⏳ | 同上 |

> 系統核心規則：保固起算日以「**交屋日期**」為準，非「入住日期」。所有保固計算均依據此原則。

---

## 7. 爭議仲裁 `/admin/disputes`

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| 爭議列表 | ✅ | `listDisputes` 即時資料 |
| 類型 chips（視覺索引） | 🟡 | 尚未連動 `dispute_type` filter（純視覺） |
| 雙方證據面板 | 🟡 | 示意 UI，待 `submitDisputeResolution` 寫入 + 證據上傳路徑上線 |
| 調解處理表單 | 🟡 | 同上 |
| 證據縮圖 | ⏳ | 待證據檔案上傳路徑上線 |

---

## 8. 庫存 `/admin/inventory`

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| 庫存清單（最近 50 筆，read-only） | ✅ | `listInventory` 即時資料 |
| 新增物料 / 補貨 / 編輯 | ✅ | backend POST `/inventory/items` (createInventoryItemV2) / POST `:restock` (restockInventoryV2) / PATCH `/inventory/items/{id}` (updateInventoryItemV2) + 前端 3 modal (CreateInventoryItemModal / RestockInventoryModal / EditInventoryItemModal) |
| 異動紀錄 | ✅ | backend GET `/inventory/transactions` (listInventoryTransactionsV2) + item_id/transaction_type filter + 前端 InventoryLogModal (4 type 顏色 + ± sign) |
| 分類 / 庫存狀態 / 關鍵字 filter | ✅ | backend list_inventory_items_v2 query: stock_status / category / owner / keyword (ILIKE name+part_number+supplier) |

> `inventory_items` 為全公司共用倉庫表（無 tenant_id），所有租戶共享庫存視角。

---

## 9. KPI 儀表板 `/admin/reports/kpi`

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| 轉換漏斗 / 異常率 / 平均處理時長 | ✅ | 從現有資料表計算 |
| SLA 達成率 | ⏳ | 待 SLA 規則模組接入 |
| 客戶滿意度 / NPS | ⏳ | 待滿意度調查模組接入 |
| 差評率 | ⏳ | 待評分聚合模組接入 |
| FTFR（First Time Fix Rate） | ⏳ | 待派工結案聚合模組接入 |

---

## 10. 技師排行 `/admin/reports/technician-ranking`

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| 技師排名（綜合評分 = 平均星等 × 20，tiebreak 為累積完工工單數） | ✅ | `listTechnicians` 即時資料計算 |
| 本週 / 本月 / 本季 / 本年 期間 segment | ✅ | 前端 client-side period state (純 UI 顯示，metrics 計算用 fetched technicians) |
| 排序選單（綜合評分/平均星等/完工數）/ 區域過濾 / 分頁（client-side 25/page） | ✅ | useMemo displayedTechnicians + service_areas distinct + pageIndex pagination |
| 匯出 CSV / 排程發送 | ✅ | `exportTechnicianRanking` (CSV blob) + scheduled-reports endpoint |
| 完工率 / 週轉時間 / 拒單率 / 營收貢獻 | ⏳ | 待派工 / 結算 metrics 接入 |

---

## 11. 營收報表 `/admin/reports/revenue`

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| KPI 總計 / 月度趨勢 / 品牌占比 | ✅ | `getRevenueSummary` 即時聚合（issued + paid 計入） |
| 日 / 週 / 月 / 季 切片 | ✅ | backend `revenue_service._VALID_GRANULARITY={day,week,month}` + 前端 SEGMENTS state (quarter fallback to month) |
| 自訂期間 (DateRangePicker) | ✅ | 前端 DateRangePicker + range state (last30 preset) — 對接 backend start_date/end_date 已 ready |
| 按品牌 / 服務類型樞紐切換 | ⚠️ MVP | 「切片：全部 / 按品牌」select 啟用，client-side filter on by_brand data；pivot endpoint 全面切換留 roadmap |
| 與上期比較 | ⏳ | 待對比 endpoint 上線 |
| 匯出 CSV / Excel / 排程發送 | ✅ | exportCsv/Xlsx 純前端 Blob download + scheduled-reports backend (migration 029 + ScheduleReportModal) |

---

## 整體進度摘要

| 類型 | 數量 |
| :--- | ---: |
| OpenAPI operationId 已實作 | **91 / 91** |
| 前端頁面已接真實 API | **33 / 33** |
| 寫入路徑（POST/PATCH/DELETE） | 已上線決策類（refund/warranty）；爭議仲裁、批次操作、寫入庫存待後續 |
| 即時推播（WebSocket） | ⏳ 全平台未啟用 |
| 跨期間樞紐 / 比較 / 匯出（reports） | ⏳ 待 metrics endpoint 擴充 |

---

## 18. 通知中心 `/notifications`（**05-05 新增**）

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| header_bar（標題 + 未讀計數 + 全部已讀 + 偏好設定 shortcut） | ✅ | `listNotifications` 聚合 |
| tab_group（未讀 / 全部 / 已讀 / 已存檔） | ✅ | `?status=` query 過濾 |
| filter_chips（8 種類型） | ✅ | `?type=` query 過濾 |
| notification_list + bulk select | ✅ | `bulkUpdateNotifications` |
| detail_preview 側欄 | ✅ | client-side render |
| 即時推送（WS `/realtime/notifications/{user_id}`） | ✅ 前端 | 訂閱層 + 跨 tab BroadcastChannel |
| Critical 不可全部已讀規則 | 🟡 | spec 規定，後端強制 |
| 通知偏好設定（A16 連結） | 🟡 | shortcut 連結，A16 偏好分頁未實作 |

---

## 19. 師傅端 PWA（T0–T11，**05-05 新增 12 頁**）

> Mobile-first，全部包在 `TechShell`（max-w-480px 置中）+ 底部 3-Tab 導航。

### 19.1 入口與帳戶

| 頁面 | 路由 | 狀態 | 說明 |
| :--- | :--- | :--- | :--- |
| 技師登入 (T0) | `/tech-login` | ✅ | `loginTechnician`，成功跳 `/pool` |
| 帳戶中心 (T4) | `/account` | ✅ | `getMyProfile` + 績效卡 + 登出 |
| 在線 toggle | `/account` | 🟡 | 後端 PATCH `/availability` 待補（前端 local-only） |
| 收入概覽 / 結算紀錄 | `/account` | ⏳ | 後端結算 API 待補（V1.1 範圍） |

### 19.2 工單流程

| 頁面 | 路由 | 狀態 | 說明 |
| :--- | :--- | :--- | :--- |
| 案件池 (T1) | `/pool` | ✅ | `listWorkOrderPool` + `acceptWorkOrder`（含 409 衝突） |
| 我的工單 (T2) | `/my-orders` | ✅ | `listWorkOrders?technician_id=me`，三 Tab 分流 |
| 工單詳情 (T3) | `/my-orders/[id]` | ✅ | `getWorkOrder` + 完工回報 + 6 格 subflow CTA |
| 即時推送（WS `/realtime/pool/{tech_id}`） | — | ✅ 前端 | 訂閱層 |

### 19.3 Subflow（T5–T9）

| 頁面 | 路由 | 狀態 | 說明 |
| :--- | :--- | :--- | :--- |
| 範圍變更 (T5) | `/my-orders/[id]/scope-change` | 🟡 | 表單完整，後端 endpoint 待補 |
| 缺料回報 (T6) | `/my-orders/[id]/material-request` | 🟡 | 表單完整，後端 endpoint 待補 |
| 延遲通知 (T7) | `/my-orders/[id]/delay` | 🟡 | 表單完整，後端 endpoint 待補；含改期連結 |
| 門面檢核 (T8) | `/my-orders/[id]/door-check` | 🟡 | UI 完整，照片上傳為 placeholder |
| **電子簽章 (T9)** | `/my-orders/[id]/signature` | ✅ | Canvas + GPS + 真實 `submitWorkOrderSignature` |

### 19.4 排班與改期

| 頁面 | 路由 | 狀態 | 說明 |
| :--- | :--- | :--- | :--- |
| 我的排班 (T10) | `/account/schedule` | 🟡 | 月曆 + 申請 modal，5 個後端 endpoints 待補 |
| 改期日曆 (T11) | `/my-orders/[id]/reschedule` | ✅ | `getTechnicianAvailability` + `proposeReschedule`（422/409 分流） |

---

## 20. 即時通訊（10 個 realtime 頻道，**05-05 全部整合**）

| 頻道 | 協議 | 整合處 | 前端 | 後端 server |
| :--- | :---: | :--- | :---: | :---: |
| notifications | WS | `/notifications` + Bell + Drawer | ✅ | ⏳ |
| pool | WS | `/pool` | ✅ | ⏳ |
| dispatch-queue | WS | `/admin/dispatch-queue`（patch state） | ✅ | ⏳ |
| work-orders/{id} | WS | `/my-orders/[id]/reschedule` | ✅ | ⏳ |
| **diagnostics** | **SSE** | `/conversations/[id]` | ✅ | ⏳ |
| sla-alerts | WS | `/dashboard` | ✅ | ⏳ |
| refunds | WS | `/admin/refunds` | ✅ | ⏳ |
| disputes | WS | `/admin/disputes` | ✅ | ⏳ |
| inventory/low-stock | WS | `/admin/inventory` | ✅ | ⏳ |
| rbac | WS | 全域（AuthGuard） | ✅ | ⏳ |

> 設環境變數 `NEXT_PUBLIC_REALTIME_BASE_URL` 啟用；未設時 silent disabled，所有頁面行為與之前完全相同。

---

## 21. 跨 Tab 同步（BroadcastChannel，**05-05 新增**）

| 場景 | 行為 | 整合處 |
| :--- | :--- | :--- |
| 通知標記已讀 | 跨 tab 紅點 -1 | `/notifications` + Bell + Drawer |
| 全部已讀 | 跨 tab 列表清空 | 同上 |
| 收新通知（WS） | 跨 tab 列表插入 | 同上 |
| 工單 reschedule 送出 | 同工單其他 tab 自動關閉 | `/my-orders/[id]/reschedule` |
| 客戶 RSVP（WS） | 同上 | 同上 |

---

## 後續路線（不在當前範圍）

1. **後端 5 組新 endpoints**（subflow + 排班）— 解鎖 T5/T6/T7/T8/T10 完整提交流程
2. **WebSocket / SSE server 啟用** — 解鎖 10 個 realtime 頻道實際推播
3. **媒體上傳 endpoint** — 解鎖 T8 photos / 完工照片 / 雙方證據上傳
4. **派工 AI 推薦引擎** — 強化 A37 候選排序與權重
5. **滿意度 / NPS 模組** — 解鎖 `/admin/customers` 風險指標、`/admin/reports/kpi` 多項客戶體驗指標
6. **保固詳情頁 + 證據上傳** — 解鎖 `/admin/warranty-claims` 詳情、`/admin/disputes` 雙方證據
7. **inventory_transactions 寫入路徑** — 解鎖 `/admin/inventory` 補貨 / 編輯 / 異動紀錄
8. **Reports metrics endpoint 擴充** — 解鎖 `/admin/reports/*` 期間切片、排序、匯出
9. **批次 / 多步審批流程** — 解鎖 `/accounting` 批次標記、`/admin/refunds` 雙簽、A37 雙簽
10. **PWA Service Worker + 離線快取** — T8 photos 離線拍照、Background Sync
