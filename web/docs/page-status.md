# 前端頁面功能狀態（給業主看的版本）

本文件彙整各頁面**目前已上線的真實功能**與**待後端模組接入的功能**，避免逐頁在 UI 上顯示「待接入」黃條，影響展示體驗。

更新日期：2026-04-29
對應 commit：dev branch（91/91 operationId 已實作）

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
| 即時推播（WebSocket `/realtime/dispatch-queue`） | ⏳ | 待派工 AI 推薦引擎接入 |
| 候選技師清單（`listDispatchCandidates`） | ⏳ | 同上 |
| 一鍵指派（`assignDispatch`） | ⏳ | 同上 |

---

## 2. 客戶主檔 `/admin/customers`

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| 客戶清單（顯示名稱 / 電話 / 地址 / 累積對話 / 工單數 / 最近服務時間） | ✅ | `listCustomers`（LINE 使用者主檔） |
| 風險等級指標 | ⏳ | 待風險評分模組接入 |
| 滿意度指標 | ⏳ | 待 NPS / 滿意度調查模組接入 |
| 偏好技師 | ⏳ | 待派工歷史聚合模組接入 |
| 保固狀態 | ⏳ | 待保固註冊模組接入 |
| 設備數 | ⏳ | 待設備主檔模組接入 |

---

## 3. 月結算總覽 `/accounting`

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| 對帳列表 | ✅ | `listReconciliations` 即時資料 |
| 結算列表 | ✅ | `listSettlements` 即時資料 |
| 核准對帳 | ✅ | `approveReconciliation`（同時建立對應結算） |
| 期間選擇器（月份 / 季別） | ⏳ | 待 period filter endpoint 擴充 |
| 批次確認 / 標記已付 | ⏳ | 待批次操作 endpoint 接入 |
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
| 補貨 / 編輯 | ⏳ | 待 `inventory_transactions` endpoint 接入 |
| 異動紀錄 | ⏳ | 同上 |

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
| 本週 / 本季 / 本年 期間切片 | ⏳ | 待 metrics endpoint 上線 |
| 排序選單 / 區域過濾 / 匯出 CSV / 分頁 | ⏳ | 同上 |
| 完工率 / 週轉時間 / 拒單率 / 營收貢獻 | ⏳ | 待派工 / 結算 metrics 接入 |

---

## 11. 營收報表 `/admin/reports/revenue`

| 區塊 | 狀態 | 資料來源 |
| :--- | :--- | :--- |
| KPI 總計 / 月度趨勢 / 品牌占比 | ✅ | `getRevenueSummary` 即時聚合（issued + paid 計入） |
| 日 / 週 / 季 切片 | ⏳ | 待後端 granularity 擴充 |
| 自訂期間 | ⏳ | 同上 |
| 按品牌 / 服務類型樞紐切換 | ⏳ | 待 pivot endpoint 上線 |
| 與上期比較 | ⏳ | 待對比 endpoint 上線 |
| 匯出 / 排程發送 | ⏳ | 待 export 路徑接入 |

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

## 後續路線（不在當前範圍）

1. **派工 AI 推薦引擎** — 解鎖 `/admin/dispatch-queue` 即時推播 + 候選技師清單 + 一鍵指派
2. **滿意度 / NPS 模組** — 解鎖 `/admin/customers` 風險指標、`/admin/reports/kpi` 多項客戶體驗指標
3. **保固詳情頁 + 證據上傳** — 解鎖 `/admin/warranty-claims` 詳情、`/admin/disputes` 雙方證據
4. **inventory_transactions 寫入路徑** — 解鎖 `/admin/inventory` 補貨 / 編輯 / 異動紀錄
5. **Reports metrics endpoint 擴充** — 解鎖 `/admin/reports/*` 期間切片、排序、匯出
6. **批次 / 多步審批流程** — 解鎖 `/accounting` 批次標記、`/admin/refunds` 雙簽
