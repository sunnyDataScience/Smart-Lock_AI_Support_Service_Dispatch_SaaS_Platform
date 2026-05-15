---
id: SF-DSP-03
title: Technician Compensation
tier: 2
status: accepted
parent_bf: BF-0003-monthly-settlement
trace_to_flow: F-012
related:
  - "../business/BF-0003-monthly-settlement.md"
  - "../../../1-decisions/ADR-0019-pm-alignment-q7.md"
legacy_id: E5x--workflow-dispatch §3
last-synced-with: 4e9658e90324cbceb26f5e5445f481fc5678df1f
sync-source: doc
synced-at: 2026-05-15
---

# SF-DSP-03 — Technician Compensation

> 薪酬 / 分潤計算 SF。屬月結 BF-0003 的 sub-flow。

## §3 技師薪酬/分潤計算 — 對應 F-012（V1.0 月結撥款，Q7=B 待 provider）

### 3.1 分潤結構

```
技師實收 = 工單總價 × 分潤比例 - 扣款項目 + 獎勵項目
```

| 工單類型 | 技師分潤比例 | 說明 |
|---------|-------------|------|
| 一般維修 | 70% | 標準分潤 |
| 安裝工程 | 60% | 零件成本較高，平台抽成較多 |
| 代工服務（客戶自備鎖） | 80% | 無零件成本 |
| 保固維修 | 100% 工資 + 0% 零件 | 零件由品牌出，技師只收工資 |
| 緊急派工（Red_Code） | 70% + 緊急加價 80% | 緊急加價大部分歸技師 |

### 3.2 獎懲規則

```sql
CREATE TABLE technician_adjustments (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    technician_id INTEGER NOT NULL REFERENCES technicians(id),
    work_order_id VARCHAR(20) REFERENCES work_orders(id),
    adjustment_type VARCHAR(30) NOT NULL,
    -- bonus_rating:     高評分獎勵
    -- bonus_speed:      快速完工獎勵
    -- bonus_weekend:    假日加班獎勵
    -- penalty_rework:   返工扣款
    -- penalty_complaint: 客訴扣款
    -- penalty_no_show:  技師未到場扣款
    amount DECIMAL(10,2) NOT NULL,          -- 正=獎勵, 負=扣款
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

| 項目 | 類型 | 金額 | 觸發條件 |
|------|------|------|---------|
| 高評分獎勵 | bonus_rating | +NT$100/單 | 單次評分 >= 4.5 |
| 快速完工 | bonus_speed | +NT$50/單 | 實際工時 < 預估工時 70% |
| 假日加班 | bonus_weekend | +30% 工資 | 六日或國定假日工單 |
| 夜間加班 | bonus_night | +20% 工資 | 18:00 後工單 |
| 返工扣款 | penalty_rework | -NT$500/次 | 7 天內同問題再派工 |
| 客訴扣款 | penalty_complaint | -NT$300/次 | 有效客訴 |
| 未到場 | penalty_no_show | -NT$500/次 | 接單後未到場 |

### 3.3 結算週期與發放

```sql
CREATE TABLE technician_settlements (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    technician_id INTEGER NOT NULL REFERENCES technicians(id),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    total_orders INTEGER NOT NULL DEFAULT 0,
    gross_amount DECIMAL(10,2) NOT NULL DEFAULT 0,     -- 工單總收入
    commission_amount DECIMAL(10,2) NOT NULL DEFAULT 0, -- 分潤金額
    bonus_amount DECIMAL(10,2) NOT NULL DEFAULT 0,      -- 獎勵合計
    penalty_amount DECIMAL(10,2) NOT NULL DEFAULT 0,    -- 扣款合計
    net_amount DECIMAL(10,2) NOT NULL DEFAULT 0,        -- 實發金額
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    -- draft → confirmed → paid
    paid_at TIMESTAMPTZ,
    payment_ref TEXT,                                    -- 匯款單號
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (tenant_id, technician_id, period_start)
);
```

| 結算頻率 | 適用方案 | 發放方式 |
|----------|---------|---------|
| 月結（每月 5 日結算上月） | Starter / Professional | 銀行匯款 |
| 雙週結（每月 1, 15 日） | Business | 銀行匯款 |
| 週結 | Enterprise | 銀行匯款 / 即時支付 |

### 3.4 API Endpoints

| Method | Path | 說明 |
|--------|------|------|
| GET | `/api/v1/technicians/{id}/earnings` | 技師收入明細（按月） |
| GET | `/api/v1/technicians/{id}/settlements` | 結算記錄 |
| POST | `/api/v1/settlements/generate` | 生成月結算單（Admin） |
| PATCH | `/api/v1/settlements/{id}/confirm` | 確認結算（Admin） |
| PATCH | `/api/v1/settlements/{id}/mark-paid` | 標記已發放（Finance） |

---

