# TC-DISPATCH-03 — 師傅接單事件與工作台同步

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **不一致** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務 |
| 走查時間 | 2026-08-03 16:34（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/routers/work_orders_v2.py`、`api/services/work_order_service.py`、`api/core/event_bus.py`、`api/realtime/event_consumer.py` |
| 優先級 / 路徑類型 | P0 / happy |
| 事實結論 | 判定基準指名的事件 `technician.assignment_accepted` 在 `api`／`web`／`agent`／`SQL` 全數零命中；接單實際發出的是 `work_order.accepted`（topic `workorder.lifecycle`），由 `event_consumer` 消費並更新 `technician_workorder_projection`。 |

**TC 原文**｜前置：師傅 web 收到推播｜步驟：師傅接單｜判定基準：發 technician.assignment_accepted 事件；品牌 api 消費更新狀態；師傅工作台投影同步｜需求：FR-TEC-04、FR-WEB-03｜旅程：SC-02、SC-05、SC-06、SC-10

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 師傅 | 接單 | `technician.assignment_accepted` | 發出該事件 | — | **找不到**該事件名稱 |
| 系統 | 寫事件流 | `WorkOrderEventAppended` | 記錄接單 | `work_order_service.py:1291-1299` | `event_type="accepted"` |
| 系統 | 發布事件 | `work_order.accepted` | 供下游消費 | `work_order_service.py:1325-1327`、`:1009-1025` | topic `workorder.lifecycle` |
| 品牌 API | 消費事件 | `ProjectionUpdated` | 更新狀態 | `api/realtime/event_consumer.py:22`、`:78-92` | 訂閱 `workorder.lifecycle`，upsert 投影表 |

---

## 走查紀錄

### 步驟 1 — 判定基準指名的事件是否存在

- **動作**：全 repo 搜尋事件名稱
- **預期**：程式碼中發出該事件
- **實際**：程式碼零命中，只存在於文件

```
git grep -n "assignment_accepted" -- api web agent SQL
（無輸出）

git grep -ln "technician.assignment_accepted" -- smartlock-docs
smartlock-docs/enterprise/04_SRS.md
smartlock-docs/enterprise/08_User_Flow.md
smartlock-docs/enterprise/15_SDS.md
smartlock-docs/enterprise/20_Test_Cases.md
```

TC 判定基準要求「發 technician.assignment_accepted 事件」，程式碼中不存在此事件名稱。此處僅並陳，不裁定。

### 步驟 2 — 接單實際發出的事件

- **動作**：讀接單流程
- **預期**：定位實際事件名稱
- **實際**：DB 事件流寫 `event_type="accepted"`（`work_order_service.py:1291-1299`）；對外發布為 `work_order.accepted`（`:1325-1327` 呼叫 `_publish_and_return`），topic 為 `TOPIC_WORKORDER_LIFECYCLE = "workorder.lifecycle"`（`api/core/event_bus.py:26`）

接單端點：v2 `api/routers/work_orders_v2.py:441-463`（`POST /tenants/{tenantId}/work-orders/{id}:accept`）、legacy `api/routers/work_orders.py:158-168`；service 層 `work_order_service.py:1217` `accept_order`。

### 步驟 3 — 品牌 API 消費與投影同步

- **動作**：讀 consumer
- **預期**：消費事件並更新投影
- **實際**：`api/realtime/event_consumer.py:22` 訂閱 `("workorder.lifecycle", "commission.accrued")`，`:118-140` 分派 handler，`:78-92` upsert `technician_workorder_projection`

`api/core/event_bus.py:28` 另定義了 `technician.lifecycle` topic 常數，但無 publisher，consumer 亦未訂閱。

### 步驟 4 — 事件發布的耐久性

- **動作**：確認事件是否有 outbox 保底
- **預期**：發布失敗可補送
- **實際**：工單／技師生命週期事件無 outbox。`_publish_and_return` 的發布為 fail-soft（`work_order_service.py:1026-1027` 只記 log）。專案中存在的 outbox 為 `commission_event_outbox`（`SQL/migrations/119`）與 LINE push outbox（`SQL/migrations/111`），不涵蓋此路徑

### 步驟 5 — 執行既有測試

- **動作**：跑 outbox 與接單相關測試
- **預期**：取得執行證據
- **實際**：三個 outbox 測試檔全數通過（含於 25 passed）；接單端到端測試 `test_pool_claim_accept.py`、`test_work_orders_v2_endpoint.py` 需資料庫，本批未執行

```
cd api && python -m pytest tests/test_cr_0175_outbox_idempotency.py \
  tests/test_cr_0172_tech_dispatch_outbox.py tests/test_cr_0017_outbox_worker.py ... -q --tb=no -rf
22 failed, 25 passed in 5.36s
```

`api/tests/` 中找不到針對 `technician.assignment_accepted` 的測試（該事件不存在）。

---

## 觀測到的其他事實

- 文件側對該事件的定義另見 `smartlock-docs/enterprise/17_AsyncAPI.yaml`（AsyncAPI 契約）與 `20_Test_Cases.md`。
- 投影表為 `technician_workorder_projection`，由 consumer upsert 維護。
