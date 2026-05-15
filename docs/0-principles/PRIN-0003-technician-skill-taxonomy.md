---
title: Technician Skill Taxonomy (Appendix)
tier: 0
status: active
related:
  - "glossary.md §3 師傅分級"
  - "../2-contracts/modules/MC-0005-dispatch-engine.md"
legacy_id: E5x--workflow-dispatch §6
---

# Technician Skill Taxonomy

> 媒合演算法依賴的技能分類體系。

## §6 技師技能分類體系 — 對應 F-003（媒合演算法依賴）

### 6.1 技能代碼結構

```
{BRAND}                    -- 品牌級（通用維修）
{BRAND}:{MODEL}            -- 型號級（特定型號）
{BRAND}:INSTALL            -- 安裝認證
{BRAND}:ADVANCED           -- 進階維修（主機板級）
GENERAL                    -- 通用技能（所有品牌基礎）
EMERGENCY                  -- 緊急開鎖認證
```

### 6.2 技能主檔

```sql
CREATE TABLE skill_definitions (
    code VARCHAR(50) PRIMARY KEY,            -- 'Dormakaba', 'Dormakaba:DP850', 'Dormakaba:INSTALL'
    display_name VARCHAR(100) NOT NULL,      -- '多瑪凱拔 - DP850 專修'
    category VARCHAR(30) NOT NULL,           -- brand | model | install | advanced | general | emergency
    brand VARCHAR(50),                       -- FK 概念，非強制
    requires_certification BOOLEAN DEFAULT FALSE,
    certification_validity_months INTEGER,    -- 認證有效月數（NULL=永久）
    description TEXT
);

-- 技師-技能關聯（含認證日期）
CREATE TABLE technician_skills (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    technician_id INTEGER NOT NULL REFERENCES technicians(id),
    skill_code VARCHAR(50) NOT NULL REFERENCES skill_definitions(code),
    certified_at DATE,                       -- 認證日期
    expires_at DATE,                         -- 到期日（NULL=永久）
    certified_by VARCHAR(100),               -- 認證機構/講師
    proficiency_level SMALLINT DEFAULT 3,    -- 1-5（1=初級, 5=專家）
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE (tenant_id, technician_id, skill_code)
);
```

### 6.3 預置技能清單

| 代碼 | 名稱 | 類別 | 需認證 |
|------|------|------|--------|
| GENERAL | 通用電子鎖基礎 | general | 否 |
| EMERGENCY | 緊急開鎖 | emergency | 是 (12 個月) |
| Dormakaba | 多瑪凱拔通用 | brand | 否 |
| Dormakaba:DP850 | DP850 專修 | model | 否 |
| Dormakaba:INSTALL | 多瑪凱拔安裝認證 | install | 是 (24 個月) |
| Dormakaba:ADVANCED | 多瑪凱拔進階維修 | advanced | 是 (12 個月) |
| Chatlock | Chatlock 通用 | brand | 否 |
| Chatlock:AI-99 | AI-99 專修 | model | 否 |
| Philips | Philips 通用 | brand | 否 |
| ... | （依品牌/型號展開） | ... | ... |

### 6.4 認證到期提醒

```python
# 每日定時任務
async def check_expiring_certifications(tenant_id: str):
    expiring = await db.fetch("""
        SELECT ts.*, t.name AS tech_name, sd.display_name AS skill_name
        FROM technician_skills ts
        JOIN technicians t ON t.id = ts.technician_id
        JOIN skill_definitions sd ON sd.code = ts.skill_code
        WHERE ts.tenant_id = $1
          AND ts.expires_at BETWEEN NOW() AND NOW() + INTERVAL '30 days'
          AND ts.is_active = TRUE
    """, tenant_id)

    for cert in expiring:
        days_left = (cert["expires_at"] - date.today()).days
        await notify_admin(
            f"技師 {cert['tech_name']} 的 {cert['skill_name']} 認證將於 {days_left} 天後到期"
        )
```

---

