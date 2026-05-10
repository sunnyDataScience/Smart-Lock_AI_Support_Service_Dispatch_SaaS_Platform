---
id: SF-DSP-01
title: Technician Scheduling System
tier: 2
status: accepted
parent_bf: BF-0000-dispatch-overview
trace_to_flow: F-003 / F-010
related:
  - "../../modules/dispatch-engine.md"
legacy_id: E5x--workflow-dispatch §1
---

# SF-DSP-01 — Technician Scheduling System

> Dispatch BF 子流程：排班/班表系統。

## §1 技師排班/班表系統 — 對應 F-003（auto dispatch 依賴）/ F-010（衝突改約）

### 1.1 問題

現有 `technicians` 表只有 `is_active BOOLEAN`，無法表達：
- 技師哪些時段可接單（早班/晚班/全天）
- 請假、休假、國定假日
- 夜間/假日 on-call 輪值
- 同時段最大接單數（capacity）

### 1.2 資料模型

```sql
-- 技師週期性排班（每週固定班表）
CREATE TABLE technician_schedules (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    technician_id INTEGER NOT NULL REFERENCES technicians(id),
    day_of_week SMALLINT NOT NULL,          -- 0=Mon, 1=Tue, ..., 6=Sun
    start_time TIME NOT NULL,               -- '09:00'
    end_time TIME NOT NULL,                 -- '18:00'
    schedule_type VARCHAR(20) NOT NULL DEFAULT 'regular',
    -- regular: 一般班 | on_call: 值班 | overtime: 加班
    max_concurrent INTEGER NOT NULL DEFAULT 2,  -- 同時段最大接單數
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (tenant_id, technician_id, day_of_week, start_time)
);

-- 技師例外日（請假、國定假日、臨時加班）
CREATE TABLE technician_day_overrides (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    technician_id INTEGER NOT NULL REFERENCES technicians(id),
    override_date DATE NOT NULL,
    override_type VARCHAR(20) NOT NULL,
    -- leave: 請假 | holiday: 國定假日 | extra: 臨時加班 | blocked: 不可派
    start_time TIME,                        -- NULL = 全天
    end_time TIME,
    reason TEXT,
    approved_by INTEGER,                    -- 管理者 user_id
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (tenant_id, technician_id, override_date, start_time)
);

-- RLS
ALTER TABLE technician_schedules ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON technician_schedules
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

ALTER TABLE technician_day_overrides ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON technician_day_overrides
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

### 1.3 可用性判斷邏輯

```python
async def is_technician_available(
    tech_id: int,
    target_datetime: datetime,
    tenant_id: str,
) -> bool:
    """判斷技師在指定時間是否可接單。"""
    target_date = target_datetime.date()
    target_time = target_datetime.time()
    target_dow = target_datetime.weekday()  # 0=Mon

    # 1. 檢查例外日（請假/blocked 優先）
    override = await db.fetchrow(
        """SELECT override_type FROM technician_day_overrides
           WHERE technician_id = $1 AND override_date = $2
             AND (start_time IS NULL OR (start_time <= $3 AND end_time > $3))
           ORDER BY override_type DESC LIMIT 1""",
        tech_id, target_date, target_time,
    )
    if override:
        if override["override_type"] in ("leave", "holiday", "blocked"):
            return False
        if override["override_type"] == "extra":
            return True  # 臨時加班，可接單

    # 2. 檢查週期性排班
    schedule = await db.fetchrow(
        """SELECT max_concurrent FROM technician_schedules
           WHERE technician_id = $1 AND day_of_week = $2
             AND start_time <= $3 AND end_time > $3
             AND is_active = TRUE""",
        tech_id, target_dow, target_time,
    )
    if not schedule:
        return False  # 該時段無排班

    # 3. 檢查同時段已接單數
    active_count = await db.fetchval(
        """SELECT COUNT(*) FROM work_orders
           WHERE technician_id = $1
             AND status IN ('assigned', 'accepted', 'en_route', 'in_progress')
             AND scheduled_at::date = $2""",
        tech_id, target_date,
    )
    return active_count < schedule["max_concurrent"]
```

### 1.4 API Endpoints

| Method | Path | 說明 |
|--------|------|------|
| GET | `/api/v1/technicians/{id}/schedule` | 查詢技師週排班 |
| PUT | `/api/v1/technicians/{id}/schedule` | 設定整週排班（覆寫） |
| POST | `/api/v1/technicians/{id}/day-override` | 新增例外日（請假/加班） |
| DELETE | `/api/v1/technicians/{id}/day-override/{date}` | 取消例外日 |
| GET | `/api/v1/technicians/available?datetime=...&skill=...` | 查詢指定時段可用技師 |

### 1.5 預設排班（新技師 onboarding）

新技師建立時，自動套用預設排班模板：

| 日 | 時段 | 類型 |
|----|------|------|
| Mon-Fri | 09:00-18:00 | regular |
| Sat | 10:00-17:00 | regular |
| Sun | OFF | — |

管理者可在 Admin Portal 調整。

---

