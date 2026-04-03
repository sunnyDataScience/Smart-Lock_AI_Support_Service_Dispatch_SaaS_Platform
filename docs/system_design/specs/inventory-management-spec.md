# GAP #17 -- 物料庫存管理規格書 (Inventory Management)

> 版本：0.1-draft | 狀態：設計中

---

## 1. 概述

智慧門鎖服務營運平台需要完整的物料與零件庫存追蹤機制。技師在現場施工時
消耗的物料（電池、鎖體、電路板、側板、螺絲等）必須即時扣減庫存，並在
庫存低於安全水位時自動觸發通知，確保服務不因缺料而中斷。

本模組與現有的 `material_requests` 表整合，實現從請購到入庫、從領料到
消耗的完整生命週期追蹤。

---

## 2. 資料模型

### 2.1 inventory_items -- 庫存品項主表

| 欄位                 | 型別                          | 說明                                                        |
|----------------------|-------------------------------|-------------------------------------------------------------|
| id                   | UUID PK                       | 品項唯一識別碼                                              |
| part_number          | VARCHAR(50) UNIQUE NOT NULL   | 料號（例：`BAT-AA-PANA-001`）                               |
| name                 | VARCHAR(200) NOT NULL         | 品名（例：Panasonic 3 號鹼性電池）                           |
| category             | VARCHAR(50) NOT NULL          | 類別，見 2.3 列舉                                           |
| brand_compatibility  | JSONB                         | 適用品牌清單，例 `["Dormakaba","AiLock","全品牌"]`           |
| unit_cost            | FLOAT                         | 單位成本（TWD）                                             |
| quantity_on_hand     | INTEGER NOT NULL DEFAULT 0    | 目前庫存數量                                                |
| reorder_point        | INTEGER NOT NULL DEFAULT 5    | 安全庫存水位，低於此值觸發補貨警示                           |
| supplier             | VARCHAR(200)                  | 供應商名稱                                                  |
| created_at           | TIMESTAMPTZ DEFAULT NOW()     |                                                             |
| updated_at           | TIMESTAMPTZ DEFAULT NOW()     |                                                             |

### 2.2 inventory_transactions -- 庫存異動紀錄

| 欄位             | 型別                          | 說明                                             |
|------------------|-------------------------------|--------------------------------------------------|
| id               | UUID PK                       | 異動唯一識別碼                                   |
| item_id          | UUID FK -> inventory_items    | 關聯品項                                         |
| transaction_type | VARCHAR(20) NOT NULL          | `purchase` / `consume` / `return` / `adjust`     |
| quantity         | INTEGER NOT NULL              | 異動數量（正值=入庫，負值=出庫）                  |
| work_order_id    | UUID FK -> work_orders (NULL) | 關聯工單（consume / return 時必填）               |
| technician_id    | UUID FK -> technicians (NULL) | 操作技師                                         |
| notes            | TEXT                          | 備註                                             |
| created_at       | TIMESTAMPTZ DEFAULT NOW()     |                                                  |

### 2.3 category 列舉值

| 值              | 說明                                 |
|-----------------|--------------------------------------|
| lock_body       | 鎖匣 / 鎖體                         |
| battery         | 電池（AA / AAA / CR123A / 鋰電池）   |
| circuit_board   | IC 主機板 / 指紋模組 / 螢幕模組      |
| screw           | 螺絲 / 膨脹螺絲 / 自攻螺絲          |
| side_panel      | 側板（歐規 / 美規 / 韓規 / 日規）    |
| strike_plate    | 受口片                               |
| cable           | 連接排線 / 緊急供電線                 |
| other           | 墊片、矽利康、切割片等               |

---

## 3. 與現有資料表整合

### 3.1 material_requests（已存在）

Schema 定義於 `SQL/Schema.sql`，欄位包含：

- `work_order_id`, `technician_id`
- `items` (JSONB): `[{part_name, spec, qty, estimated_cost}]`
- `status`: requested -> approved -> ordered -> fulfilled -> cancelled
- `source`: company_stock / external_purchase / technician_advance

整合方式：當 `material_requests.status` 轉為 `fulfilled` 時，系統自動
寫入 `inventory_transactions`（transaction_type = `purchase`），更新
`inventory_items.quantity_on_hand`。

### 3.2 work_orders.material_shortage

工單表已有 `material_shortage` 布林欄位。當技師提交 material_request
時自動設為 `true`；當請購完成且技師確認到貨後重設為 `false`。

---

## 4. 核心流程

### 4.1 技師現場消耗物料

```
技師回報消耗 -> InventoryManager.consume_for_work_order()
  -> 逐項扣減 quantity_on_hand
  -> 寫入 inventory_transactions (type=consume, work_order_id)
  -> 檢查 quantity_on_hand < reorder_point
     -> 若低於水位 -> 發送 admin 低庫存通知
```

### 4.2 低庫存警示

```
定時排程 (cron) 或即時觸發:
  InventoryManager.check_low_stock()
  -> 回傳所有 quantity_on_hand < reorder_point 的品項
  -> 通知管理員（LINE / Email / 系統通知）
```

### 4.3 請購單履行

```
material_requests.status -> 'fulfilled'
  -> InventoryManager.fulfill_material_request(request_id)
  -> 解析 items JSONB，匹配 inventory_items
  -> 寫入 inventory_transactions (type=purchase)
  -> 更新 quantity_on_hand
  -> 重設 work_orders.material_shortage = false
```

### 4.4 退料

```
技師退回未使用物料:
  -> InventoryManager.record_transaction(type=return)
  -> quantity_on_hand 增加
```

---

## 5. 種子資料 (Seed Data)

參考 `docs/Locksmith_Preparation_Checklist/19_各工種常用物料清單.md`：

### 5.1 電池類 (battery)

| part_number       | name                      | reorder_point |
|-------------------|---------------------------|---------------|
| BAT-AA-PANA-001   | Panasonic 3 號鹼性電池     | 20            |
| BAT-AAA-PANA-001  | Panasonic 4 號鹼性電池     | 8             |
| BAT-LITH-001      | 鋰電池（充電式機種用）      | 3             |

### 5.2 鎖體類 (lock_body)

| part_number       | name             | reorder_point |
|-------------------|------------------|---------------|
| LB-GENERIC-001    | 鎖匣（通用規格）  | 2             |
| LB-CLUTCH-001     | 離合器模組        | 2             |
| LB-MOTOR-001      | 馬達模組          | 2             |

### 5.3 電路板類 (circuit_board)

| part_number       | name             | reorder_point |
|-------------------|------------------|---------------|
| CB-IC-001         | IC 主機板         | 2             |
| CB-FP-001         | 指紋感應模組      | 2             |
| CB-SCR-001        | 螢幕模組          | 1             |

### 5.4 側板類 (side_panel)

| part_number       | name         | reorder_point |
|-------------------|--------------|---------------|
| SP-EU-001         | 歐規側板      | 2             |
| SP-KR-001         | 韓規側板      | 1             |
| SP-US-001         | 美規側板      | 1             |
| SP-JP-001         | 日規側板      | 1             |

### 5.5 受口片類 (strike_plate)

| part_number       | name         | reorder_point |
|-------------------|--------------|---------------|
| STR-GENERIC-001   | 受口片        | 3             |

### 5.6 螺絲類 (screw)

| part_number       | name                   | reorder_point |
|-------------------|------------------------|---------------|
| SCR-EXP-M5-001    | 膨脹螺絲 M5x40mm       | 20            |
| SCR-SELF-M4-001   | 自攻螺絲 M4x25mm       | 20            |
| SCR-HINGE-M5-001  | 鉸鏈螺絲 M5x30mm       | 12            |

### 5.7 其他 (other / cable)

| part_number       | name                    | reorder_point |
|-------------------|-------------------------|---------------|
| CBL-CONN-001      | 連接排線                 | 3             |
| CBL-USBC-001      | USB Type-C 緊急供電線    | 1             |
| OTH-SHIM-001      | 墊片（綜合）             | 10            |
| OTH-SILI-001      | 矽利康（透明）           | 1             |
| OTH-BLADE-001     | 砂輪機切割片 4 吋        | 3             |

---

## 6. 報表

### 6.1 月度消耗報表 (Monthly Consumption by Category)

- 輸入：start_date, end_date, group_by (`category` | `item`)
- 輸出：各類別的消耗總量與總成本
- SQL 聚合：`SUM(quantity)` WHERE transaction_type = 'consume'

### 6.2 技師用量報表 (Per-Technician Usage)

- 輸入：start_date, end_date, technician_id (optional)
- 輸出：各技師消耗的品項明細與總成本
- 用途：成本分攤、績效評估、異常偵測

---

## 7. 索引策略

```sql
CREATE INDEX idx_inv_items_category ON inventory_items (category);
CREATE INDEX idx_inv_items_part_number ON inventory_items (part_number);
CREATE INDEX idx_inv_txn_item ON inventory_transactions (item_id);
CREATE INDEX idx_inv_txn_work_order ON inventory_transactions (work_order_id);
CREATE INDEX idx_inv_txn_type_created ON inventory_transactions (transaction_type, created_at);
```

---

## 8. 未來擴充

- V2.0：多倉庫支援（warehouse_id 欄位）
- V2.0：技師車載庫存獨立追蹤
- V3.0：自動補貨下單整合供應商 API
