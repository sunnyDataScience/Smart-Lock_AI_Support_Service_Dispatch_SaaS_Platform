---
id: SF-DSP-04
title: Rejection & Reassign Flow
tier: 2
status: accepted
parent_bf: BF-0000-dispatch-overview
trace_to_flow: F-005 / F-004 / F-003
related:
  - "../sub/SF-WO-02-rejection-reassign.md"
  - "../../modules/dispatch-engine.md"
  - "../../../1-decisions/ADR-0022-pm-alignment-q10.md (rollback)"
legacy_id: E5x--workflow-dispatch §4
---

# SF-DSP-04 — Rejection & Reassign

> 技師拒單後的重派 SF。

## §4 拒單重派流程 — 對應 F-005（接單）/ F-004（手動重派）/ F-003（自動）

### 4.1 資料模型

```sql
CREATE TABLE dispatch_attempts (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    work_order_id VARCHAR(20) NOT NULL REFERENCES work_orders(id),
    attempt_num SMALLINT NOT NULL,           -- 1, 2, 3...
    technician_id INTEGER NOT NULL REFERENCES technicians(id),
    match_score DECIMAL(5,4),                -- 媒合分數
    distance_km DECIMAL(6,2),
    pushed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at TIMESTAMPTZ,
    response VARCHAR(20),                    -- accepted | rejected | timeout
    rejection_reason TEXT,                   -- 技師拒絕原因（選填）
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.2 重派狀態機

```
推送技師 #1
    |
    +--[15min 內接受]--> assigned (正常流程)
    |
    +--[15min 逾時 or 拒絕]--> 推送技師 #2 (attempt_num=2)
        |
        +--[15min 內接受]--> assigned
        |
        +--[逾時/拒絕]--> 推送技師 #3 (attempt_num=3)
            |
            +--[接受]--> assigned
            |
            +--[逾時/拒絕]--> 自動升級
                |
                +--[擴大半徑]--> 第 2 輪 (50km, +NT$200)
                |   +--[3 次都失敗]--> 第 3 輪 (80km, +NT$500)
                |       +--[3 次都失敗]--> 轉管理者手動派工
                |
                +--[通知 tenant_admin]--> Admin 介面顯示待手動派工
```

### 4.3 拒單率監控

```python
# 每月定時任務：計算技師拒單率
async def calc_monthly_rejection_rates(tenant_id: str):
    rates = await db.fetch("""
        SELECT technician_id,
               COUNT(*) AS total_pushes,
               COUNT(*) FILTER (WHERE response = 'rejected') AS rejections,
               COUNT(*) FILTER (WHERE response = 'timeout') AS timeouts,
               ROUND(
                 (COUNT(*) FILTER (WHERE response IN ('rejected','timeout'))::numeric
                  / NULLIF(COUNT(*), 0)) * 100, 1
               ) AS rejection_rate
        FROM dispatch_attempts
        WHERE tenant_id = $1
          AND pushed_at >= date_trunc('month', NOW())
        GROUP BY technician_id
    """, tenant_id)

    for r in rates:
        if r["rejection_rate"] > 50:
            await suspend_technician(r["technician_id"], days=7, reason="拒單率超過 50%")
            await notify_admin(f"技師 {r['technician_id']} 因拒單率 {r['rejection_rate']}% 已自動停權 7 天")
        elif r["rejection_rate"] > 30:
            await notify_admin(f"技師 {r['technician_id']} 拒單率 {r['rejection_rate']}%，請關注")
```

### 4.4 業務規則

| 規則 | 說明 |
|------|------|
| BR-DISPATCH-001 | 每輪最多推送 3 位技師（循序，非同時） |
| BR-DISPATCH-002 | 每位技師 15 分鐘接單視窗 |
| BR-DISPATCH-003 | 同一工單不重複推送同一技師 |
| BR-DISPATCH-004 | 月拒單率 > 30% 發警告，> 50% 自動停權 7 天 |
| BR-DISPATCH-005 | Red_Code 工單跳過拒單機制，直接推送 + 電話通知 |
| BR-DISPATCH-006 | 客戶指定技師時，跳過媒合，直接推送該技師 |

---

