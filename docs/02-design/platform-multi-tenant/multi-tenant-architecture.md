---
status: superseded
superseded_by: docs_v2/4-exploration/multi-tenant-platform/architecture.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# Multi-Tenant SaaS Platform Architecture

> **文件狀態：設計文件（V3.0 規劃）**
> 以 IBM/Microsoft Enterprise 架構方法論設計，適用於未來多租戶、多供應商合作場景。
> 建立日期：2026-04-21

---

## 1. 商業模型定義

### 現狀 vs 目標

| | 現狀 (V1.0) | 目標 (V3.0) |
|---|---|---|
| 定位 | 一間鎖匠店 + 一個 AI 客服 | N 間鎖匠店都能用的 SaaS 平台 |
| 類比 | 一家公司自用 CRM | Salesforce |
| 租戶 | 單租戶（鎖市） | 多租戶（鎖市、台北鎖王、高雄安鎖...） |
| LINE | 一個官方帳號 | 每個租戶各自的官方帳號 |
| 知識庫 | 單一 config.toml + skills/ | 平台共用 + 租戶客製 |

### 租戶 (Tenant) 定義

每個租戶 = 一家鎖匠供應商，擁有：

- 自己的 LINE 官方帳號
- 自己的技師團隊
- 自己的品牌/定價/服務範圍
- 自己的客戶群
- 自己的 AI 人設和技能 SOP（可客製）
- 自己的後台管理介面

### 平台方擁有

- 共用的 AI 引擎（LLM + ReAct Runtime + Harness）
- 共用的品牌知識庫（OEM 上傳）
- 平台級 Super Admin
- 計費和訂閱管理
- 跨租戶的匿名數據分析

---

## 2. 全域架構

```
+======================================================================+
|                        PLATFORM LAYER (共用)                          |
|                                                                      |
|  +----------+  +----------+  +----------+  +----------+             |
|  | API      |  | Identity |  | Event    |  | Billing  |             |
|  | Gateway  |  | & Access |  | Bus      |  | & Meter  |             |
|  | (路由)   |  | (IAM)    |  | (事件)   |  | (計費)   |             |
|  +----+-----+  +----+-----+  +----+-----+  +----+-----+             |
+======+==============+==============+==============+=================+
|      |      DOMAIN SERVICES (按領域切分，同一 process 部署)           |
|      |                                                               |
|  +---v---------------------------------------------------------------+
|  |                                                                   |
|  |  +-----------+  +------------+  +--------------------+            |
|  |  | Tenant    |  | AI Agent   |  | Dispatch &         |            |
|  |  | Mgmt      |  | Engine     |  | Work Order         |            |
|  |  |           |  |            |  |                    |            |
|  |  | 租戶 CRUD |  | ReAct Core |  | 工單生命週期       |            |
|  |  | 訂閱方案  |  | Skills     |  | 技師媒合           |            |
|  |  | LINE 綁定 |  | Harness    |  | 排班               |            |
|  |  | 品牌設定  |  | Memory     |  | 完工結算           |            |
|  |  +-----------+  +------------+  +--------------------+            |
|  |                                                                   |
|  |  +-----------+  +------------+  +--------------------+            |
|  |  | Knowledge |  | Customer   |  | Financial          |            |
|  |  | Mgmt      |  | Mgmt       |  | Mgmt               |            |
|  |  |           |  |            |  |                    |            |
|  |  | 共用 SOP  |  | user_facts |  | 帳務               |            |
|  |  | 租戶客製  |  | 對話歷史   |  | 發票               |            |
|  |  | OEM 上傳  |  | CRM        |  | 師傅撥款           |            |
|  |  +-----------+  +------------+  +--------------------+            |
|  |                                                                   |
|  |                    FastAPI (同一個 process)                        |
|  +-------------------------------------------------------------------+
|                              |                                       |
+==============================+=======================================+
|                    DATA LAYER                                        |
|                                                                      |
|  +----------------+  +--------+  +---------+  +----------+          |
|  | PostgreSQL     |  | Redis  |  | GCS     |  | pgvector |          |
|  | (RLS by tenant)|  | (cache)|  | (media) |  | (embed)  |          |
|  +----------------+  +--------+  +---------+  +----------+          |
+======================================================================+
|                    FRONTEND LAYER                                     |
|                                                                      |
|  +--------------+  +---------------+  +--------------------------+   |
|  | Platform     |  | Tenant Admin  |  | Technician App           |   |
|  | Super Admin  |  | Portal        |  | (PWA)                    |   |
|  | (平台方)     |  | (各家鎖匠店) |  | (各家技師)               |   |
|  +--------------+  +---------------+  +--------------------------+   |
|                        Next.js (同一套，路由區分)                     |
+======================================================================+
```

---

## 3. 核心決策：不拆微服務

### 為什麼用 Modular Monolith

| 考量 | 微服務 | Modular Monolith |
|------|--------|------------------|
| 團隊規模 | 需要獨立 on-call、獨立部署管線 | 1-3 人團隊最合適 |
| 資料一致性 | 跨服務需要 saga / 最終一致性 | 同一個 DB，一個 transaction |
| 部署複雜度 | N 個 Cloud Run + service mesh | 1 個 Cloud Run |
| 延遲 | 跨服務 HTTP call 50-200ms | 同 process function call 0ms |
| 除錯 | 分散式 tracing 必要 | 單一 log stream |

### 何時才拆微服務

IBM 經驗法則：
- 單一模組的團隊 > 5 人且需要獨立部署節奏
- 單一 DB 的 QPS > 10K 且讀寫比例極端
- 某個 Domain 的 SLA 與其他差距 > 2 個等級

---

## 4. 多租戶隔離策略：Shared DB + Row-Level Security

### 租戶主表

```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(50) UNIQUE NOT NULL,        -- 'locksmart', 'taipei-lockking'
    display_name VARCHAR(200) NOT NULL,      -- '鎖市', '台北鎖王'

    -- LINE 官方帳號綁定（每個租戶一個）
    line_channel_id VARCHAR(100),
    line_channel_secret_encrypted TEXT,       -- AES-256 加密
    line_access_token_encrypted TEXT,         -- AES-256 加密

    -- AI 設定
    agent_persona TEXT,                      -- 客製 AI 人設 (override system.md)
    agent_name VARCHAR(50) DEFAULT 'AI 客服',
    llm_model VARCHAR(100) DEFAULT 'vertex_ai/gemini-2.5-pro',

    -- 業務設定
    supported_brands TEXT[] NOT NULL,         -- '{Dormakaba,Chatlock,Philips}'
    service_areas TEXT[],                     -- '{台北市,新北市}'
    business_hours JSONB,                    -- {"mon": "09:00-18:00", ...}

    -- 訂閱
    plan VARCHAR(30) DEFAULT 'starter',      -- starter | professional | enterprise
    plan_expires_at TIMESTAMPTZ,
    monthly_message_quota INTEGER DEFAULT 1000,
    monthly_message_used INTEGER DEFAULT 0,

    -- 狀態
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Row-Level Security

```sql
-- 所有業務表加 tenant_id + RLS
ALTER TABLE user_facts ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id);
ALTER TABLE user_facts ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON user_facts
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- 同樣套用到：work_orders, technicians, audit_log,
-- user_soft_profiles, conversations 等所有業務表
```

### 為什麼不拆 DB

- 100 個租戶 x 獨立 DB = 100 個 Cloud SQL instance = 成本爆炸
- Shared DB + RLS = 1 個 instance，PostgreSQL 原生保證隔離
- 當某個租戶長到需要獨立 DB 時，再遷移（enterprise 方案升級）

---

## 5. Tenant Context 傳遞

### Tenant Resolver（全鏈路起點）

```python
# platform/tenant_context.py
from contextvars import ContextVar

_current_tenant_id: ContextVar[str] = ContextVar("tenant_id")
_current_tenant: ContextVar[dict] = ContextVar("tenant")

def set_tenant(tenant_id: str, tenant_config: dict):
    _current_tenant_id.set(tenant_id)
    _current_tenant.set(tenant_config)

def get_tenant_id() -> str:
    return _current_tenant_id.get()

def get_tenant_config() -> dict:
    return _current_tenant.get()
```

### LINE Webhook Tenant Resolution

```python
# 方案：統一 webhook 入口，靠 channel_id 反查租戶
# LINE webhook body 包含 destination = channel_id

@app.post("/webhook")
async def line_webhook(request: Request):
    body = await request.body()
    body_json = json.loads(body)

    # LINE webhook body 包含 destination = channel_id
    channel_id = body_json.get("destination", "")

    # 從 channel_id 反查租戶
    tenant = await tenant_registry.resolve_by_channel(channel_id)
    if not tenant:
        raise HTTPException(404, "Unknown LINE channel")

    # 設定租戶上下文（全鏈路帶著走）
    set_tenant(tenant["id"], tenant)

    # 用該租戶的 channel_secret 驗簽
    secret = decrypt(tenant["line_channel_secret_encrypted"])
    parser = WebhookParser(secret)
    events = parser.parse(body.decode(), signature)

    # 設定 PostgreSQL RLS
    await db.execute(f"SET app.current_tenant_id = '{tenant['id']}'")

    # 後續流程完全不變，但所有 DB 操作自動隔離
    ...
```

### Checkpoint 隔離

```python
# 現在：
thread_id = f"line_{user_id}"

# 多租戶後：
thread_id = f"{tenant_id}:line_{user_id}"
```

---

## 6. AI Agent 多租戶改造

### 共用 vs 客製分層

| 層級 | 內容 | 隔離度 |
|------|------|--------|
| Platform 共用 | LLM Engine, LangGraph ReAct Runtime, Harness H1-H12 | 共用 |
| Platform 共用 | 通用 Skills (`_common/`) | 共用 |
| Platform 共用 | 品牌原廠 SOP（OEM 上傳） | 共用 |
| Tenant 客製 | System Prompt (AI 人設) | per-tenant |
| Tenant 客製 | 品牌/型號清單 (Quick Reply) | per-tenant |
| Tenant 客製 | 安全關鍵字 | per-tenant |
| Tenant 客製 | 回覆模板 | per-tenant |
| Tenant 客製 | 自訂 Skills / 覆寫 SOP | per-tenant |
| Tenant 客製 | LINE 官方帳號 | per-tenant |
| Tenant 客製 | 技師清單 & 服務範圍 | per-tenant |

### Config 分層（Platform Default + Tenant Override）

```python
async def get_effective_config(tenant_id: str) -> dict:
    """合併 platform default + tenant override。"""
    # 1. Platform default (config.toml)
    base = load_config()

    # 2. Tenant override (from DB, cached in Redis)
    override = await tenant_config_cache.get(tenant_id)

    # 3. Deep merge: tenant wins
    return deep_merge(base.to_dict(), override or {})
```

租戶 override 範例（DB 中 JSONB）：
```json
{
    "safety": {"dangerous_keywords": ["拆開電路板", "撬鎖", "暴力破門"]},
    "quick_reply": {"brands": [{"label": "Yale", "text": "Yale", "models": ["YDM4109"]}]},
    "agent_persona": "你是「鎖王」的 AI 客服，語氣要更正式..."
}
```

### 知識庫三層繼承

```
Platform Knowledge (所有租戶共用)
|
|  skills/data/_common/troubleshoot/       -- 通用故障排除
|  skills/data/_common/dispatch-guide/     -- 通用派工指南
|  skills/data/Dormakaba/_all-models/      -- 品牌原廠 SOP（OEM 上傳）
|
+-- Tenant Knowledge (租戶客製/覆寫)
    |
    |  tenant_skills/{tenant_id}/custom-greeting/   -- 客製迎賓話術
    |  tenant_skills/{tenant_id}/custom-pricing/    -- 客製報價邏輯
    |  tenant_skills/{tenant_id}/override/troubleshoot/  -- 覆寫通用 SOP
    |
    +-- Tenant-Specific Brands
        tenant_skills/{tenant_id}/Yale/             -- 平台沒有但租戶自加

載入優先序：Tenant Override > Platform Brand > Platform Common
```

---

## 7. RBAC 擴展

### 角色層級

```
platform_super_admin        -- 平台方（看所有租戶）
  +-- tenant_admin          -- 鎖匠老闆（看自己租戶）
  |     +-- tenant_reviewer     -- 客服主管（看對話/工單）
  |     +-- tenant_technician   -- 技師（看自己工單）
  |     +-- tenant_readonly     -- 查看者
  |
  +-- B2B 角色（跨租戶）
        +-- brand_oem           -- 品牌原廠（上傳 SOP，看自己品牌數據）
        +-- distributor         -- 經銷商（看區域數據）
        +-- community_admin     -- 社區管委會（看社區工單）
```

### JWT Token 結構

```json
{
    "sub": "user-uuid",
    "tenant_id": "tenant-uuid",
    "role": "tenant_admin",
    "permissions": ["work_orders:read", "work_orders:write", "technicians:manage"],
    "exp": 1714300000
}
```

---

## 8. Event Bus（Domain 間解耦）

### 實作策略

- **Phase 1**：PostgreSQL `LISTEN/NOTIFY`（零基建成本）
- **Phase 2**：換成 Cloud Pub/Sub 或 Redis Streams（規模需要時）

### Domain Event 結構

```python
@dataclass
class DomainEvent:
    event_type: str          # "work_order.created"
    tenant_id: str
    payload: dict
    timestamp: datetime
    correlation_id: str      # 追蹤鏈
```

### 事件流範例

```
客戶 LINE 訊息「門打不開」
    |
AI Agent 診斷後呼叫 transfer_to_human
    |
publish(WorkOrderCreated)
    |
    +-- Handler: 派工模組 -> 開始技師媒合
    +-- Handler: 審計模組 -> 記錄 escalation
    +-- Handler: 計費模組 -> 記錄 billable event
    +-- Handler: 通知模組 -> 推送 tenant_admin

技師完工回報
    |
publish(WorkOrderCompleted)
    |
    +-- Handler: LINE 推送客戶「維修已完成」
    +-- Handler: 帳務建立帳單
    +-- Handler: 知識庫收集 case data (data flywheel)
    +-- Handler: 品牌 OEM 收到品質回報
```

---

## 9. 後台三級 Portal

### 路由結構（同一套 Next.js）

| 路由 | 角色 | 功能 |
|------|------|------|
| `/platform-admin` | 平台 Super Admin（你） | 租戶管理、全域 SOP、OEM 審核、跨租戶分析、計費、監控 |
| `/admin` | 租戶管理者（各家鎖匠老闆） | 對話記錄、技師管理、工單看板、AI 客製、品牌設定、帳務報表 |
| `/tech` | 技師 PWA（各家技師） | 待接工單、導航、完工回報、收入明細 |

### 資料隔離保證

- API 層：JWT 中的 `tenant_id` 自動過濾
- DB 層：PostgreSQL RLS 兜底
- UI 層：Next.js middleware 驗證 tenant context

---

## 10. LINE 訊號串接（與現有客服整合）

```
LINE Platform
|
|  鎖市 OA        台北鎖王 OA      高雄安鎖 OA
|  (channel A)    (channel B)     (channel C)
|
+--------+---------------+---------------+
         |
    POST /webhook  (統一入口)
         |
    Tenant Resolver (channel_id -> tenant_id)
         |
    +----+----+
    |    |    |
    A    B    C    <-- set_tenant()
    |    |    |
    +----+----+
         |
    現有 Harness H1-H12   <-- 完全不動
         |
    ReAct Agent            <-- 完全不動
    (skills = platform + tenant custom)
         |
    LINE Bot Reply
    (用該租戶的 access_token 回覆)
```

### 現有程式碼改造量

| 改動點 | 改什麼 | 影響範圍 |
|--------|--------|----------|
| `app.py` webhook | 加 Tenant Resolver（~10 行） | 入口 |
| `core/line_bot.py` | `access_token` 從 tenant config 拿 | LINE 發送 |
| `harness/debounce.py` run_agent | `thread_id` 加 tenant 前綴 | checkpoint 隔離 |
| `skills/tools.py` | `load_skills` 加 tenant overlay | 技能過濾 |
| `config.toml` | 變成 platform default，tenant 從 DB 讀 | 設定 |
| 所有 DB 表 | 加 `tenant_id` + RLS | 資料隔離 |

**現有 Harness (H1-H12) 完全不動。**

---

## 11. 實作路線圖

| Phase | 內容 | 時程估算 |
|-------|------|----------|
| **Phase 0** Foundation | tenants 表、TenantResolver middleware、PostgreSQL RLS、所有表加 tenant_id、thread_id 加 tenant 前綴、驗證現有「鎖市」作為 tenant_id=1 跑通 | 2-3 weeks |
| **Phase 1** Multi-LINE | webhook 統一入口 + channel_id 路由、line_bot.py 動態 access_token、後台租戶綁定 LINE channel UI | 1-2 weeks |
| **Phase 2** Tenant Admin Portal | Next.js /admin 路由、JWT + tenant_id claim、對話記錄（tenant-scoped）、品牌/型號/服務範圍設定、AI 人設客製化、技師 CRUD | 3-4 weeks |
| **Phase 3** Dispatch | work_orders 表 + 生命週期、transfer_to_human 建立工單、技師媒合 + LINE 通知、完工回報、Event Bus (PG LISTEN/NOTIFY) | 3-4 weeks |
| **Phase 4** Platform Admin | /platform-admin 路由、租戶管理 CRUD、訂閱方案 + 用量計費、跨租戶匿名分析、系統監控 dashboard | 2 weeks |
| **Phase 5** B2B Integration | Brand OEM API（已有 spec）、Distributor API、Community Admin API、Webhook 通知 | 2-3 weeks |

---

## 12. 成本與規模估算

| 規模 | 租戶數 | 架構 | 月成本估算 |
|------|--------|------|-----------|
| 起步 | 1-10 | 現在 + tenant_id | ~$100-200 |
| 成長 | 10-100 | + Redis cache + read replica | ~$500-1000 |
| 規模 | 100-500 | + Cloud Pub/Sub + CDN + 多 replica | ~$2000-5000 |
| 拆分 | 500+ | 按 Domain 拆微服務 + K8s | 視流量 |

---

## 13. 核心設計原則（IBM/Microsoft）

1. **Design for isolation, deploy as monolith** — 用 `tenant_id` + RLS 在同一個 DB 裡做完隔離。Domain Boundary 畫清楚，程式碼放在不同 module，部署在同一個 process。

2. **Event-driven at domain boundaries** — Domain 之間用 Event Bus 通訊（PostgreSQL NOTIFY 起步，規模大了換 Pub/Sub）。Domain 內部直接 function call。

3. **Platform default + Tenant override** — 所有設定兩層：平台預設值 + 租戶覆寫值。知識庫也是：共用 SOP + 租戶客製 SOP。新租戶零設定即上線，老租戶可深度客製。
