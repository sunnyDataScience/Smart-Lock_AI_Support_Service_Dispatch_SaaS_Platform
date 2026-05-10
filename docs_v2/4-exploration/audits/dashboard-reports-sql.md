---
title: Dashboard / Reports SQL Spec (Audit)
date: 2026-05-10
status: reference
related:
  - "../../2-contracts/api/openapi.yaml (getKpiReport / getRevenueSummary)"
  - "../../2-contracts/functional-requirements/FR-0021-dashboard-reports.md"
legacy_id: E5x--workflow-dispatch §7
---

# Dashboard / Reports SQL Spec

> F-021 Dashboard / 報表的 SQL + API spec。

## §7 報表 SQL + API — 對應 F-021 Dashboard / 報表

### 7.1 轉換漏斗（Conversion Funnel）

```sql
-- 工單轉換漏斗（指定月份）
SELECT
    COUNT(*) FILTER (WHERE status IN ('inquiring','qualified','created','assigned','accepted',
        'in_progress','scope_changed','material_pending','delayed','completed',
        'rework_required','confirmed','billed','archived','cancelled','disputed'))
        AS total_intake,
    COUNT(*) FILTER (WHERE status NOT IN ('inquiring','cancelled'))
        AS qualified,
    COUNT(*) FILTER (WHERE status NOT IN ('inquiring','qualified','cancelled'))
        AS dispatched,
    COUNT(*) FILTER (WHERE status IN ('in_progress','scope_changed','material_pending',
        'delayed','completed','rework_required','confirmed','billed','archived'))
        AS in_progress,
    COUNT(*) FILTER (WHERE status IN ('completed','confirmed','billed','archived'))
        AS completed,
    COUNT(*) FILTER (WHERE status IN ('billed','archived'))
        AS billed,
    COUNT(*) FILTER (WHERE status = 'cancelled')
        AS cancelled,
    COUNT(*) FILTER (WHERE status = 'disputed')
        AS disputed
FROM work_orders
WHERE tenant_id = $1
  AND created_at >= date_trunc('month', $2::date)
  AND created_at < date_trunc('month', $2::date) + INTERVAL '1 month';
```

### 7.2 技師績效排名

```sql
-- 技師月績效排名
SELECT
    t.id,
    t.name,
    COUNT(wo.id) AS total_orders,
    COUNT(wo.id) FILTER (WHERE wo.status IN ('completed','confirmed','billed','archived'))
        AS completed_orders,
    ROUND(AVG(cr.rating), 2) AS avg_rating,
    ROUND(AVG(EXTRACT(EPOCH FROM (wo.completed_at - wo.created_at)) / 3600), 1)
        AS avg_resolution_hours,
    ROUND(
        (SELECT COUNT(*) FILTER (WHERE response IN ('rejected','timeout'))::numeric
         / NULLIF(COUNT(*), 0) * 100
         FROM dispatch_attempts da
         WHERE da.technician_id = t.id
           AND da.pushed_at >= date_trunc('month', $2::date))
    , 1) AS rejection_rate_pct
FROM technicians t
LEFT JOIN work_orders wo ON wo.technician_id = t.id
    AND wo.created_at >= date_trunc('month', $2::date)
    AND wo.created_at < date_trunc('month', $2::date) + INTERVAL '1 month'
LEFT JOIN customer_ratings cr ON cr.work_order_id = wo.id
WHERE t.tenant_id = $1 AND t.is_active = TRUE
GROUP BY t.id, t.name
ORDER BY avg_rating DESC NULLS LAST, completed_orders DESC;
```

### 7.3 營運 KPI Dashboard

```sql
-- 當月 KPI 總覽
SELECT
    -- 派工效率
    ROUND(AVG(EXTRACT(EPOCH FROM (da.responded_at - da.pushed_at)) / 60), 1)
        AS avg_accept_minutes,
    ROUND(COUNT(*) FILTER (WHERE da.response = 'accepted')::numeric
        / NULLIF(COUNT(*), 0) * 100, 1)
        AS first_match_rate_pct,

    -- 客戶滿意度
    ROUND(AVG(cr.rating), 2) AS avg_customer_rating,
    COUNT(cr.id) FILTER (WHERE cr.rating >= 4)::numeric
        / NULLIF(COUNT(cr.id), 0) * 100 AS satisfaction_pct,

    -- 異常率
    COUNT(wo.id) FILTER (WHERE wo.status = 'disputed')::numeric
        / NULLIF(COUNT(wo.id), 0) * 100 AS dispute_rate_pct,
    COUNT(wo.id) FILTER (WHERE wo.status = 'rework_required')::numeric
        / NULLIF(COUNT(wo.id), 0) * 100 AS rework_rate_pct,

    -- 營收
    SUM(wo.final_price) FILTER (WHERE wo.status IN ('billed','archived'))
        AS monthly_revenue,
    COUNT(wo.id) FILTER (WHERE wo.status IN ('completed','confirmed','billed','archived'))
        AS completed_count

FROM work_orders wo
LEFT JOIN dispatch_attempts da ON da.work_order_id = wo.id AND da.attempt_num = 1
LEFT JOIN customer_ratings cr ON cr.work_order_id = wo.id
WHERE wo.tenant_id = $1
  AND wo.created_at >= date_trunc('month', NOW())
  AND wo.created_at < date_trunc('month', NOW()) + INTERVAL '1 month';
```

### 7.4 客戶評分模型

```sql
CREATE TABLE customer_ratings (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    work_order_id VARCHAR(20) NOT NULL REFERENCES work_orders(id),
    customer_id INTEGER REFERENCES customers(id),
    technician_id INTEGER NOT NULL REFERENCES technicians(id),
    rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    rating_technical SMALLINT CHECK (rating_technical BETWEEN 1 AND 5),
    rating_punctuality SMALLINT CHECK (rating_punctuality BETWEEN 1 AND 5),
    rating_professionalism SMALLINT CHECK (rating_professionalism BETWEEN 1 AND 5),
    comment TEXT,
    collected_via VARCHAR(20) DEFAULT 'line_push',
    -- line_push: LINE 推送評分 | admin_followup: 管理者回訪 | auto_default: 48hr 未評自動 4 分
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (work_order_id)
);
```

收集時機：完工確認後 2 小時推送 LINE 評分卡，48 小時未評分自動填入 4 分。

### 7.5 報表 API Endpoints

| Method | Path | 說明 | 回傳 |
|--------|------|------|------|
| GET | `/api/v1/reports/funnel?month=2026-04` | 轉換漏斗 | 各階段數量 + 轉換率 |
| GET | `/api/v1/reports/technician-ranking?month=2026-04` | 技師績效排名 | 排序後清單 + 分數 |
| GET | `/api/v1/reports/kpi-dashboard` | 當月 KPI 總覽 | 6 項指標 |
| GET | `/api/v1/reports/revenue?from=...&to=...` | 營收報表 | 按日/週/月彙總 |
| GET | `/api/v1/reports/customer-satisfaction?month=...` | 客戶滿意度 | 評分分佈 + 趨勢 |
| GET | `/api/v1/reports/dispatch-efficiency?month=...` | 派工效率 | 接單時間、首次媒合率 |
| POST | `/api/v1/reports/weekly/generate` | 觸發週報生成 | 週報 ID |
| GET | `/api/v1/reports/weekly/{id}` | 查看週報 | 完整週報內容 |

---

