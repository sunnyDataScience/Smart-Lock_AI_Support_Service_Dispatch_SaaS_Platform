# E5x — Dispatch Operations

> **文件狀態：設計文件（V2.0 派工營運基礎設施規格）**
> 工單派工系統 7 項營運模組：技師排班、媒合演算法、薪酬分潤、拒單重派、客戶設備主檔、技能體系、報表 API。
> 建立日期：2026-04-22
> 前置文件：[[E5x--work-order-interaction-flows]]

---

## 目錄

| # | 缺失項目 | 嚴重度 | 章節 |
|---|---------|--------|------|
| 1 | 技師排班/班表系統 | HIGH | §1 |
| 2 | 媒合演算法實作規格 | HIGH | §2 |
| 3 | 技師薪酬/分潤計算 | HIGH | §3 |
| 4 | 拒單重派流程 | MEDIUM | §4 |
| 5 | 客戶/設備主檔 | MEDIUM | §5 |
| 6 | 技師技能分類體系 | MEDIUM | §6 |
| 7 | 報表 SQL + API | MEDIUM | §7 |

---

## §1 技師排班/班表系統

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

## §2 媒合演算法實作規格

### 2.1 問題

01-define/E3x--module-breakdown.md 定義了權重（40% 距離 + 30% 技能 + 20% 評分 + 10% 負載），但 02-design 缺乏實作細節。

### 2.2 評分公式

```
total_score = W_dist × distance_score
            + W_skill × skill_score
            + W_rating × rating_score
            + W_load × load_score
            + bonus_same_tech
            + bonus_on_call
```

| 權重 | 代號 | 值 | 說明 |
|------|------|-----|------|
| 距離 | W_dist | 0.35 | 越近越好 |
| 技能 | W_skill | 0.30 | 品牌+型號完全匹配 |
| 評分 | W_rating | 0.20 | 歷史客戶評分 |
| 負載 | W_load | 0.15 | 當天已接單數越少越好 |
| 同一技師加分 | bonus_same_tech | +0.10 | 回頭客偏好同一技師 |
| 值班加分 | bonus_on_call | +0.05 | 當前時段為 on_call 的技師優先 |

### 2.3 各分項計算

```python
def calc_distance_score(distance_km: float) -> float:
    """距離分數：0-1，越近越高。"""
    if distance_km <= 5:
        return 1.0
    elif distance_km <= 15:
        return 0.8
    elif distance_km <= 30:
        return 0.6
    elif distance_km <= 50:
        return 0.3
    else:
        return 0.1  # >50km 仍可派但分數極低


def calc_skill_score(tech_skills: list[str], required_brand: str, required_model: str | None) -> float:
    """技能分數：品牌+型號完全匹配=1.0，僅品牌=0.7，無匹配=0。"""
    if required_model and f"{required_brand}:{required_model}" in tech_skills:
        return 1.0   # 品牌+型號完全匹配
    if required_brand in tech_skills:
        return 0.7   # 僅品牌匹配
    if "GENERAL" in tech_skills:
        return 0.3   # 通用技師
    return 0.0        # 無匹配


def calc_rating_score(avg_rating: float, total_jobs: int) -> float:
    """評分分數：考慮平均分 + 樣本數信心度。"""
    if total_jobs == 0:
        return 0.5  # 新技師給中間值
    confidence = min(total_jobs / 20, 1.0)  # 20 單以上視為可靠
    normalized = (avg_rating - 1) / 4        # 1-5 分映射到 0-1
    return normalized * confidence + 0.5 * (1 - confidence)  # 貝氏平滑


def calc_load_score(active_orders_today: int, max_concurrent: int) -> float:
    """負載分數：今天已接單越少越好。"""
    if max_concurrent == 0:
        return 0.0
    utilization = active_orders_today / max_concurrent
    return max(0, 1.0 - utilization)
```

### 2.4 完整媒合流程

```python
async def match_technician(
    tenant_id: str,
    work_order: WorkOrder,
    target_datetime: datetime,
) -> list[dict]:
    """回傳排序後的候選技師清單（最多 5 位）。"""

    # 1. 篩選：該租戶、有技能、有排班、可接單
    candidates = await db.fetch(
        """SELECT t.*, 
              AVG(r.rating) AS avg_rating, 
              COUNT(r.id) AS total_jobs,
              COUNT(wo.id) FILTER (WHERE wo.status IN ('assigned','accepted','en_route','in_progress')
                AND wo.scheduled_at::date = $3) AS active_today
           FROM technicians t
           LEFT JOIN customer_ratings r ON r.technician_id = t.id
           LEFT JOIN work_orders wo ON wo.technician_id = t.id
           WHERE t.tenant_id = $1 AND t.is_active = TRUE
           GROUP BY t.id""",
        tenant_id, work_order.device_brand, target_datetime.date(),
    )

    # 2. 過濾：排班可用性
    available = []
    for tech in candidates:
        if await is_technician_available(tech["id"], target_datetime, tenant_id):
            available.append(tech)

    # 3. 評分
    scored = []
    for tech in available:
        distance_km = await calc_distance(tech["service_area"], work_order.address)
        score = (
            0.35 * calc_distance_score(distance_km)
            + 0.30 * calc_skill_score(tech["skills"], work_order.device_brand, work_order.device_model)
            + 0.20 * calc_rating_score(tech["avg_rating"] or 3.0, tech["total_jobs"])
            + 0.15 * calc_load_score(tech["active_today"], 2)
        )
        # 加分項
        if await is_same_technician(work_order.line_user_id, tech["id"]):
            score += 0.10
        scored.append({"technician": tech, "score": round(score, 4), "distance_km": distance_km})

    # 4. 排序，回傳 Top 5
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:5]
```

### 2.5 擴展搜索半徑

依 supplement §23.2 OP-09：

| 輪次 | 半徑 | 加價 | 等待時間 |
|------|------|------|---------|
| 第 1 輪 | 30 km | 無 | 5 分鐘 |
| 第 2 輪 | 50 km | +NT$200 車馬費 | 5 分鐘 |
| 第 3 輪 | 80 km | +NT$500 車馬費 | 5 分鐘 |
| 無人接單 | — | — | 轉管理者手動派工 |

### 2.6 緊急派工（Red_Code）

觸發條件：客戶被鎖門外、幼童反鎖、瓦斯爐開著。

| 項目 | 規則 |
|------|------|
| 偵測 | AI 分類 confidence >= 0.9 且 intent = RED_CODE |
| 媒合 | 跳過排班限制，直接推送最近的 on_call 技師 |
| 加價 | 緊急加價 NT$500 |
| SLA | 30 秒內推送技師、15 分鐘內接單 |
| 通知 | 同步推送 tenant_admin |

---

## §3 技師薪酬/分潤計算

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

## §4 拒單重派流程

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

## §5 客戶/設備主檔

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

## §6 技師技能分類體系

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

## §7 報表 SQL + API

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

## §8 新增表彙總

本文件新增的所有資料表：

| 表名 | 章節 | 用途 |
|------|------|------|
| `technician_schedules` | §1 | 週期性排班 |
| `technician_day_overrides` | §1 | 例外日（請假/加班） |
| `dispatch_attempts` | §4 | 派工推送記錄 |
| `customers` | §5 | 客戶主檔 |
| `customer_devices` | §5 | 客戶設備檔 |
| `skill_definitions` | §6 | 技能代碼主檔 |
| `technician_skills` | §6 | 技師-技能關聯 |
| `technician_adjustments` | §3 | 獎懲記錄 |
| `technician_settlements` | §3 | 結算記錄 |
| `customer_ratings` | §7 | 客戶評分 |

所有表均含 `tenant_id UUID NOT NULL REFERENCES tenants(id)` + RLS policy，確保多租戶就緒。

---

## §9 與現有系統的整合點

| 現有元件 | 整合方式 | 改動量 |
|----------|---------|--------|
| `skills/tools.py` transfer_to_human | 建立工單時查 `customers` + `customer_devices` 自動帶入 | ~10 行 |
| `skills/tools.py` update_user_info | 同步寫入 `customers` 表 | ~5 行 |
| `harness/debounce.py` run_agent | 注入 `[進行中工單]` + 設備保固狀態 | ~15 行 |
| `profiles/manager.py` | 雙寫：update_fact 同時更新 customers | ~10 行 |
| `storage/postgres_impl.py` | 新增 dispatch_decision, settlement 事件類型 | ~5 行 |
| `config.toml` | 新增 `[dispatch]` section（媒合權重、SLA、分潤比例） | 新增 section |
