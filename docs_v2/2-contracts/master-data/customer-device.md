---
id: MD-CUSTOMER-DEVICE
title: Customer / Device Master Data
tier: 2
status: accepted
related:
  - "./brand-model.md"
  - "../modules/problem-card-engine.md"
legacy_id: E5x--workflow-dispatch §5
---

# Customer / Device Master Data

> 客戶與設備主檔 master data spec。

## §5 客戶/設備主檔 — 對應 F-001 / F-002（PC 主檔）/ cross-cutting

### 5.1 問題

現有 `user_facts` 是扁平 KV 結構，無法表達：
- 一個客戶有多台電子鎖
- 每台鎖的安裝日期、保固到期、維修歷史
- 客戶偏好技師

### 5.2 資料模型

```sql
-- 客戶主檔（從 user_facts 升級）
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    line_user_id TEXT,                       -- LINE user ID（可為空，電話客戶）
    name VARCHAR(100),
    phone VARCHAR(30),
    address TEXT,
    preferred_technician_id INTEGER REFERENCES technicians(id),
    risk_level VARCHAR(20) DEFAULT 'normal', -- normal | high_risk (2次 no-show)
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (tenant_id, line_user_id)
);

-- 設備檔（一個客戶可以有多台鎖）
CREATE TABLE customer_devices (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    brand VARCHAR(50) NOT NULL,
    model VARCHAR(50),
    serial_number VARCHAR(100),
    installation_date DATE,
    warranty_end_date DATE,
    location_description TEXT,               -- '前門', '後門', '辦公室'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- work_orders 新增 FK
ALTER TABLE work_orders ADD COLUMN customer_id INTEGER REFERENCES customers(id);
ALTER TABLE work_orders ADD COLUMN device_id INTEGER REFERENCES customer_devices(id);
```

### 5.3 與現有 user_facts 的關係

```
user_facts (V1.0, 保留)          customers + devices (V2.0, 新增)
├── device_brand    ──────────►  customer_devices.brand
├── device_model    ──────────►  customer_devices.model
├── phone           ──────────►  customers.phone
└── address         ──────────►  customers.address

遷移策略：
1. V2.0 啟動時，從 user_facts 自動生成 customers + customer_devices 記錄
2. V1.0 AI Agent 繼續用 user_facts（低改動）
3. V2.0 Dispatch 用 customers + customer_devices（結構化查詢）
4. 雙寫：update_user_info tool 同時更新兩邊
```

### 5.4 保固驗證邏輯

```python
async def check_warranty(device_id: int) -> dict:
    """檢查設備保固狀態。"""
    device = await db.fetchrow(
        "SELECT * FROM customer_devices WHERE id = $1", device_id
    )
    if not device or not device["warranty_end_date"]:
        return {"status": "unknown", "message": "無保固資訊"}

    today = date.today()
    days_remaining = (device["warranty_end_date"] - today).days

    if days_remaining > 0:
        return {"status": "active", "days_remaining": days_remaining}
    elif days_remaining >= -90:
        return {"status": "grace_period", "days_expired": abs(days_remaining)}
    else:
        return {"status": "expired", "days_expired": abs(days_remaining)}
```

---

