# Smart Lock 工單系統完成度總覽

> 跨前端 / 後端 / Realtime / Workflow 的整體進度盤點。
> 每次開發完成後更新本文件，保持與 `report/v*.md` 細粒度紀錄同步。

**最後更新：** 2026-05-06（完工 photos UI + admin media gallery）
**對應分支：** `feat/api-media-upload`（pending merge to dev）
**對應 reports：** v1.0.0 → v1.26.0

---

## 總體：**約 91%**

```
███████████████████████████░░  91%
```

| Phase | 04-29 | 05-06 早 | **05-06 晚** | 變化 |
|:---|:---:|:---:|:---:|:---:|
| Phase 5 V2.0 設計（W18–W19）| 85% | 97% | **97%** | — |
| Phase 6 派工 MVP（W20–W24）| 50% | 92% | **97%** | +5%（完工 photos + admin 媒體瀏覽）|
| Phase 7 會計+整合（W25–W29）| 70% | 85% | **89%** | +4%（媒體流端到端打通）|
| Phase 8 UAT 上線（W30–W31）| 0% | 0% | 0% | — |

> Phase 5–7 平均完成度：**約 94%**；含 Phase 8（未啟動）的 V2.0 上線總進度：**約 91%**。

---

## 1. 前端覆蓋（spec 對照）

| 區域 | 完成度 | 說明 |
|:---|:---:|:---|
| **管理員後台**（A0–A37）| **~95%** | 41 admin 頁面已建，僅候選詳情 drawer / SOP 績效真實化等次要項目缺 |
| **技師端 PWA**（T0–T11）| **100%** | 12 頁全完成 + 6 個 subflow + 改期日曆 + 排班 |
| **通知中心**（G1）| **100%** | 全頁面 + Drawer + Bell + BroadcastChannel 跨 tab 同步 |
| **A32 AI 推理**（SSE）| **100%** | 對話頁逐 token 串流面板 |
| **PWA / 桌面 guard** | **100%** | manifest + 4 SVG icon + 桌面顯示 QR Code |

---

## 2. 後端 API（107 REST + 9 WS）

| 模組 | 完成度 |
|:---|:---:|
| 工單狀態機（accept/complete/cancel/assign/escalate/confirm/reschedule）| **100%** |
| 4 個 subflow endpoints（T5–T8：scope-change/material-request/delay/door-check）| **100%** |
| 5 個排班 endpoints（T10）+ admin 審核 3 個 | **100%** |
| Dispute decision | **100%** |
| Refund decision | **100%**（雙簽流程未做）|
| 認證（JWT、tenant、RBAC）| **100%** |
| WebSocket server + ACL（JWT/tenant/RBAC）| **100%** |
| **媒體上傳 endpoint**（upload/get/list-by-wo + media_files 表）| **100%** ✅ |
| Inventory low-stock 背景偵測 | **0%** |
| SLA 引擎 | **0%** |

---

## 3. 即時通訊（10 個頻道前端整合 + 9 個 WS server）

| 頻道 | 前端訂閱 | 後端 server | 後端 publish |
|:---|:---:|:---:|:---:|
| `/realtime/notifications/{user_id}` | ✅ | ✅ | ✅（schedule resolve）|
| `/realtime/pool/{tech_id}` | ✅ | ✅ | ⏳（無觸發 service）|
| `/realtime/dispatch-queue` | ✅ | ✅ | ✅（8 個 wo events）|
| `/realtime/work-orders/{id}` | ✅ | ✅ | ✅（同上）|
| `/realtime/diagnostics/{conv_id}`（SSE）| ✅ | ⏳ | ⏳ |
| `/realtime/sla-alerts` | ✅ | ✅ | ⏳（待 SLA 引擎）|
| `/realtime/refunds` | ✅ | ✅ | ✅ |
| `/realtime/disputes` | ✅ | ✅ | ✅ |
| `/realtime/inventory/low-stock` | ✅ | ✅ | ⏳（待背景 job）|
| `/realtime/rbac` | ✅ | ✅ | ⏳（待權限變更觸發）|

---

## 4. 使用者 Workflow 覆蓋（spec 14 個 Flow）

| Flow | 完成度 | 缺口 |
|:---|:---:|:---|
| Flow 1 Happy Path | **100%** | — |
| Flow 2 拒單重派 | **100%** | — |
| Flow 3 範圍變更 | **80%** | 客戶核准流程簡化 |
| Flow 4 缺料 | **80%** | 調度員補料 UI |
| Flow 5 延遲通知 | **85%** | LINE Push 實際路徑 |
| Flow 6 退款雙簽 | **50%** | 雙簽流程 |
| Flow 7 爭議 | **95%** | 前端 dispute 證據上傳 UI（後端 endpoint 已備）|
| Flow 8 二次派工 | **70%** | 連環銜接 |
| Flow 9 客訴升級 | **75%** | SLA 自動觸發 |
| Flow 10 門面檢核 | **100%** | T8 + admin 縮圖瀏覽完成端到端 |
| Flow 11 客戶不在場 | **75%** | LINE Flex RSVP |
| Flow 12–14 | **60–80%** | — |

---

## 5. 基礎設施與品質

| 項目 | 狀態 | 對應 Report |
|:---|:---|:---|
| DB 連線池統一（CloudSQL idle 修復）| ✅ | v1.22.1 / v1.23.0 |
| Output validator（品牌型號錯配 + 不重複追問）| ✅ | v1.24.1–v1.24.3 |
| Quick Reply 首訊推論 | ✅ | v1.24.2 |
| OpenAPI / TypeScript types 同步 CI | ✅ | — |
| BroadcastChannel 跨 tab | ✅ | v1.13.0 |
| WS 認證強化（JWT/tenant/RBAC）| ✅ | v1.22.0 |

---

## 主要尚未完成（剩 ~10%）

| 優先級 | 項目 | 工時 |
|:---:|:---|:---|
| ~~**P0**~~ | ~~媒體上傳 endpoint~~ | ✅ **完成 v1.25.0**（2026-05-06）|
| ~~P1~~ | ~~完工 photos 上傳 UI~~ | ✅ **完成 v1.26.0**（2026-05-06）|
| ~~P1~~ | ~~Admin 工單詳情瀏覽 media 縮圖~~ | ✅ **完成 v1.26.0**（2026-05-06）|
| **P0** | 整合測試 / E2E（合約 1.2.7.3）| 1–2 週 |
| **P0** | UAT（合約 1.2.8）| 計畫期程 |
| P1 | Dispute evidence 上傳 UI（前端 admin disputes）| 半天 |
| P1 | Inventory low-stock 背景偵測 job | 半天 |
| P1 | SLA 引擎（quote_expiring / dispatch_delay / response_overdue 自動推送）| 1 週 |
| P1 | Refund 雙簽流程 | 半天 |
| P1 | A37 candidate detail drawer（排班熱力圖）| 半天 |
| P1 | work_order_events 表（取代 service_report append）| 半天 |
| P1 | RBAC 權限變更後端推送（前端 banner 已備）| 半天 |
| P1 | Pool 即時推播觸發（前端訂閱已備）| 半天 |
| P2 | LINE Flex RSVP（Flow 11 客戶端）| 1–2 天 |
| P2 | 計價引擎 GUI / SOP 績效真實化 / 報表 metrics 擴充 | 數天 |

---

## 結論

關鍵剩餘項目集中在：

1. **媒體上傳** — 阻擋 Flow 7（爭議證據）/ Flow 10（門面照片）/ 完工報告 photos 完成的最後一塊
2. **整合測試 / UAT** — 合約 Phase 8 的入口
3. **SLA 引擎** — 自動推送告警的後端基礎建設

建議下一輪開發分支優先處理「媒體上傳 endpoint」，可一次解鎖三個 Flow 的最終 1%。

---

## 維護規則

- 每次合併 PR / 完成一個 milestone 後，**主 agent 必須更新本文件**
- 三大維度同步調整：完成度 % / 模組狀態表 / Workflow 覆蓋表
- 重大 milestone 時更新「最後更新」日期 + Phase 進度表
- 細粒度變更紀錄請在 `report/v*.md`，本文件只保留高階聚合
