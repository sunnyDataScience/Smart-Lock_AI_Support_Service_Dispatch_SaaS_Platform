# TC-DISPATCH-05 — 技師工單投影的欄位最小化

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試，投影相關 7 項全數通過（見步驟 6） |
| 走查時間 | 2026-08-03 18:02（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `SQL/tech_authority/Schema_cqrs_projection.sql`、`SQL/Schema.sql`、`api/realtime/event_consumer.py`、`api/services/work_order_service.py`、`api/core/event_bus.py` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 投影表 `technician_workorder_projection` 共 10 欄，相對品牌側 `work_orders`（51 欄）確為子集，且不含 `customer_name` / `customer_phone` / `customer_address` / `service_report` / `photos` 等敏感欄。TC 判定基準列舉的六項中「地址」以 `district` 取代（非完整地址）、「金額」不在此表（佣金另存 `technician_commission_projection`）、「該技師派工」僅由 `technician_id` 欄承載而無 row 級過濾。另查得此投影表在 `api` 中除 consumer 與測試外無任何讀取端點。 |

**TC 原文**｜前置：技師工單投影（CQRS read-model）｜步驟：比對投影欄位與品牌庫｜判定基準：投影僅含摘要/地址/狀態/時窗/金額/該技師派工；不含品牌敏感全量資料（欄位最小化）｜⚠ 未標註｜P0｜FR-TEC-05｜SC-05、SC-06、SC-13

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 品牌 API | 發布生命週期事件 | `WorkOrderLifecycleEvent` | 欄位最小化 | `services/work_order_service.py:1007-1027` | payload 9 欄（tenant/wo/status/event_type/tech/doc/district/scheduled/occurred） |
| 技師平台 | 消費事件 | `ProjectionUpserted` | 投影僅存摘要 | `realtime/event_consumer.py:75-95` | upsert 9 欄 + `updated_at` |
| 技師 | 讀工作台 | `ProjectionRead` | 只見自己的單 | — | **找不到**讀此投影表的端點 |

---

## 走查紀錄

### 步驟 1 — 投影表的完整欄位

- **動作**：讀 migration／schema 定義
- **預期**：欄位最小化
- **實際**：10 欄

`SQL/tech_authority/Schema_cqrs_projection.sql:10-23`

```sql
CREATE TABLE IF NOT EXISTS technician_workorder_projection (
    work_order_id     UUID PRIMARY KEY,
    tenant_id         UUID NOT NULL,                 -- 租戶標記（防跨租戶外洩）
    technician_id     UUID,                          -- 該工單指派技師（NULL=未派/已退）
    status            VARCHAR(30),
    document_number   VARCHAR(50),
    district          VARCHAR(100),                  -- 地區（非完整地址，最小揭露）
    scheduled_time    VARCHAR(50),
    last_event_type   VARCHAR(50),
    occurred_at       TIMESTAMP WITH TIME ZONE,
    updated_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tech_wo_proj_tech
    ON technician_workorder_projection (technician_id, status);
```

檔頭 `:4-5` 記載設計意圖：「欄位最小化（隱私/最小權限，ADR-017 §投影隱私）：只存投影所需摘要＋租戶標記，不整包複製品牌敏感資料。」

### 步驟 2 — 品牌側工單表的欄位

- **動作**：讀 `work_orders` 定義
- **預期**：可逐欄比對
- **實際**：51 欄，含多項客戶個資與現場資料

`SQL/Schema.sql:462-482`（節錄）

```sql
CREATE TABLE work_orders (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    problem_card_id     UUID REFERENCES problem_cards(id) ON DELETE RESTRICT,
    technician_id       UUID REFERENCES technicians(id) ON DELETE SET NULL,
    created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    status              VARCHAR(50) DEFAULT 'created',
    priority            VARCHAR(50) DEFAULT 'normal',
    customer_name       VARCHAR(100),
    customer_phone      VARCHAR(50),
    customer_address    TEXT,
    scheduled_at        TIMESTAMP WITH TIME ZONE,
    ...
    service_report      TEXT,                           -- 技師完工回報
    photos              JSONB,                          -- 維修前後照片 URL 陣列
    estimated_price     FLOAT,
    final_price         FLOAT,
```

其餘欄位見 `SQL/Schema.sql:483-513`（含 `brand` / `model` / `serial_number` / `door_type` / `warranty_status` / `purchase_date` / `invoice_no` / `customer_final_amount` / `dealer` / `payment_method` / `teaching_note` 等）。

### 步驟 3 — 逐項比對 TC 判定基準列舉的六類

- **動作**：把 TC 列舉項對到投影欄位
- **預期**：六類齊備
- **實際**：

| TC 列舉 | 投影對應欄位 | 事實 |
|---|---|---|
| 摘要 | `document_number`、`last_event_type` | 有；無文字摘要欄 |
| 地址 | `district` | 只有地區，無 `customer_address` |
| 狀態 | `status` | 有 |
| 時窗 | `scheduled_time` | 有（VARCHAR(50)） |
| 金額 | — | **找不到**於本表；`technician_commission_projection.amount`（`Schema_cqrs_projection.sql:31`）為另一張表，來源 topic 為 `commission.accrued` |
| 該技師派工 | `technician_id` | 欄位存在；本表儲存所有租戶所有工單，未依技師分表或分 row 過濾 |

### 步驟 4 — 事件 payload 的欄位

- **動作**：讀 publisher 送出的欄位集合
- **預期**：與投影一致
- **實際**：9 欄，與投影欄位一一對應

`api/services/work_order_service.py:1007-1027`

```python
    # 欄位最小化（隱私）：不整包送敏感資料，只送投影所需摘要。
    try:
        from core.event_bus import TOPIC_WORKORDER_LIFECYCLE, publish_event
        await publish_event(
            TOPIC_WORKORDER_LIFECYCLE,
            {
                "tenant_id": tenant_id,
                "work_order_id": wo_id,
                "status": order.get("status"),
                "event_type": event_type,
                "technician_id": order.get("technician_id"),
                "document_number": order.get("document_number"),
                "district": order.get("district"),
                "scheduled_time": order.get("scheduled_time"),
                "occurred_at": order.get("updated_at"),
            },
            key=wo_id,
        )
```

consumer 端 upsert 同一組欄位：`api/realtime/event_consumer.py:77-95`

```python
    await conn.execute(
        "INSERT INTO technician_workorder_projection "
        "  (work_order_id, tenant_id, technician_id, status, document_number, "
        "   district, scheduled_time, last_event_type, occurred_at) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (work_order_id) DO UPDATE SET "
        "  technician_id = EXCLUDED.technician_id, status = EXCLUDED.status, "
        ...
```

### 步驟 5 — 投影的讀取端

- **動作**：搜尋讀此表的程式碼
- **預期**：師傅工作台讀投影
- **實際**：僅 consumer 與測試命中，無 router／service 讀取

```
git grep -rln "technician_workorder_projection" -- SQL api web
SQL/tech_authority/Schema_cqrs_projection.sql
api/realtime/event_consumer.py
api/tests/test_cr_0166_event_backbone.py
```

投影建表時機為 consumer 啟動（`api/realtime/event_consumer.py:35-41` `ensure_schema`），且整條 consumer 為 opt-in（`:26-27`）：

```python
def enabled() -> bool:
    return bool(os.getenv("KAFKA_BOOTSTRAP"))
```

### 步驟 6 — 執行既有測試

- **動作**：跑投影測試
- **預期**：取得執行證據
- **實際**：第一輪無資料庫時投影 upsert 三個測試失敗；建立本機測試庫後重跑，同三項仍失敗，失敗原因由「無連線」改為「技師庫三張表不存在」

第一輪（無資料庫）：

```
cd api && python -m pytest tests/test_cr_0166_event_backbone.py -q --tb=line
ERROR    api.db:db.py:48 環境變數 POSTGRES_URI 未設定
D:\...\api\tests\test_cr_0166_event_backbone.py:42: AttributeError: 'NoneType' object has no attribute 'execute'
FAILED tests/test_cr_0166_event_backbone.py::test_workorder_projection_upsert
FAILED tests/test_cr_0166_event_backbone.py::test_workorder_projection_status_progression
FAILED tests/test_cr_0166_event_backbone.py::test_commission_projection_upsert
3 failed, 4 passed in 0.38s
```

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0166_event_backbone.py -q -p winloop_plugin --tb=no
3 failed, 4 passed in 0.42s
```

失敗的是同三項（`test_workorder_projection_upsert`、`test_workorder_projection_status_progression`、`test_commission_projection_upsert`），原因為 `technician_workorder_projection`、`technician_commission_projection`、`event_consumer_dedup` 三張表在測試庫中不存在。

第三輪（補套投影 schema 後）：

```
docker exec -i smartlock-test-db psql -U lock -d lock_scratch_test < SQL/tech_authority/Schema_cqrs_projection.sql
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0166_event_backbone.py -q -p winloop_plugin
7 passed in 0.55s
```

該三張表的 DDL 位於 `SQL/tech_authority/Schema_cqrs_projection.sql`，而本測試檔取用的連線是 `core.db` 的品牌連線 `db_module._conn`（`api/tests/test_cr_0166_event_backbone.py:37-45`、`:61`、`:73`），非技師庫連線 `tech_conn`；在 `TECH_POSTGRES_URI` 未設的單庫 fallback 下（`api/core/db.py:244`），投影表即落於品牌庫。將該 SQL 套用至品牌測試庫後，本檔 7 項全數通過，投影 upsert 與 `event_consumer_dedup` 去重均取得實跑證據。

> 更正：本文件在第二輪原記為「需 `scripts/db/split-tech-db.sh` 建技師庫、本次未建」。該敘述不正確——`split-tech-db.sh` 搬的是技師身分域表（`users`／`technicians`／`technician_skill` 等，見該腳本 `:23`），不含本處三張投影表，且本測試檔並不經由技師庫連線讀取。實際所缺僅為上述 schema 檔未套用。

---

## 觀測到的其他事實

- `smartlock-docs/enterprise/04_SRS.md:355`（FR-TEC-05）記載投影應含「摘要/地址/狀態/時窗/金額，欄位最小化」，與 TC 判定基準同源。
- `api/core/event_bus.py:28` 定義 `TOPIC_TECHNICIAN_LIFECYCLE = "technician.lifecycle"`，consumer 訂閱清單（`realtime/event_consumer.py:22`）不含此 topic。
- 事件發布為 fail-soft（`services/work_order_service.py:1026-1027` 只記 log），工單生命週期事件無 outbox 保底。
