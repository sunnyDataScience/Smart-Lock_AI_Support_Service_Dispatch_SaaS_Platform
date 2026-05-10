---
status: superseded
superseded_by: docs_v2/4-exploration/multi-tenant-platform/dispatch-integration.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# Dispatch System Integration Spec

> **文件狀態：設計文件（V2.0 派工模組 + V3.0 多租戶整合）**
> 本文件定義工單系統與現有 AI 客服的三個訊號接觸點。
> 建立日期：2026-04-21

---

## 1. 架構決策：Modular Monolith

工單系統作為新模組加入同一個 FastAPI process，共用同一個 PostgreSQL。

```
agent/
|-- app.py                    # 新增 dispatch API routes
|-- agent.py                  # 不動
|-- dispatch/                 # <-- 新增模組
|   |-- __init__.py
|   |-- models.py             # WorkOrder, Technician dataclasses
|   |-- service.py            # 業務邏輯（建立/指派/完工）
|   |-- matching.py           # 技師媒合（距離、技能、排班）
|   |-- scheduler.py          # 時段管理
|   +-- routes.py             # FastAPI router（Admin Portal 用）
|-- skills/
|   +-- tools.py              # transfer_to_human 改造 + manage_work_order 新增
|-- harness/
|   +-- debounce.py           # run_agent() 注入工單上下文
+-- ...
```

`app.py` 註冊路由：
```python
from dispatch.routes import router as dispatch_router
app.include_router(dispatch_router, prefix="/api/dispatch", tags=["dispatch"])
```

---

## 2. 資料庫 Schema

```sql
-- 工單主表
CREATE TABLE work_orders (
    id VARCHAR(20) PRIMARY KEY,           -- wo_{uuid8}
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    line_user_id TEXT NOT NULL,            -- LINE user ID（推送用）
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    -- pending -> assigned -> en_route -> in_progress -> completed -> closed
    reason TEXT,
    device_brand VARCHAR(50),
    device_model VARCHAR(50),
    phone VARCHAR(30),
    address TEXT,
    technician_id INTEGER REFERENCES technicians(id),
    scheduled_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    source VARCHAR(20) DEFAULT 'ai_agent', -- ai_agent | admin | phone
    conversation_summary TEXT,             -- AI 對話摘要
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 技師表
CREATE TABLE technicians (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(30),
    skills TEXT[],                          -- '{Dormakaba,Chatlock,...}'
    service_area TEXT[],                    -- '{台北市,新北市,...}'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS
ALTER TABLE work_orders ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON work_orders
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

ALTER TABLE technicians ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON technicians
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

### 工單狀態機

```
pending -> assigned -> en_route -> in_progress -> completed -> closed
  |          |                                        |
  +-> cancelled                                       +-> disputed
```

---

## 3. 三個訊號接觸點

### 接觸點 1：Agent -> Dispatch（建立工單）

**現狀**：`transfer_to_human` (`skills/tools.py:167`) 只回傳文字表單，不建立工單。

**改造**：同時寫入 `work_orders` 表。

```python
# skills/tools.py — transfer_to_human 改造概念

@tool
async def transfer_to_human(reason: str) -> str:
    # ... 現有邏輯：讀 facts、組裝表單 ...

    # 新增：建立工單
    from dispatch.service import create_work_order
    work_order = await create_work_order(
        tenant_id=get_tenant_id(),
        user_id=user_id,
        line_user_id=user_id,
        reason=reason,
        device_brand=device_brand,
        device_model=device_model,
        phone=phone,
        address=address,
        source="ai_agent",
        conversation_summary=reason,
    )

    # 審計
    await _audit_storage.log_event(
        event_type="dispatch_decision",
        actor_id=user_id,
        action="work_order.created",
        payload={"work_order_id": work_order.id},
    )

    # 發佈事件
    await publish(DomainEvent(
        event_type="work_order.created",
        tenant_id=get_tenant_id(),
        payload={"order_id": work_order.id, "reason": reason},
    ))

    return form_text  # 回傳給客戶的文字不變
```

### 接觸點 2：Dispatch -> Agent（狀態推送回客戶）

當工單狀態變更，透過 LINE push 通知客戶。

```python
# dispatch/service.py

async def update_work_order_status(order_id: str, new_status: str, metadata: dict):
    # 更新 DB
    await _update_status_in_db(order_id, new_status)

    # 推送 LINE 訊息給客戶（用該租戶的 access_token）
    import core.line_bot as line_bot

    templates = {
        "assigned":  "您好，您的維修需求已安排技師 {tech_name}，預計 {eta} 到場。",
        "en_route":  "技師 {tech_name} 已出發前往您的位置。",
        "completed": "維修已完成！如有任何問題歡迎隨時告訴我。",
    }

    msg = templates[new_status].format(**metadata)
    await line_bot.push_message(order.line_user_id, msg)

    # 發佈事件
    await publish(DomainEvent(
        event_type=f"work_order.{new_status}",
        tenant_id=order.tenant_id,
        payload={"order_id": order_id, **metadata},
    ))
```

**關鍵**：直接用現有的 `line_bot.push_message()`，同一個 LINE 官方帳號、同一個客服對話窗。客戶不會感覺到系統切換。

### 接觸點 3：客戶回覆 -> Agent 感知工單上下文

客戶收到工單通知後繼續回覆（如「可以改時間嗎」），Agent 需要知道有進行中的工單。

```python
# harness/debounce.py — run_agent() 改造概念

from dispatch.service import get_active_orders

active_orders = await get_active_orders(user_id)
if active_orders:
    order = active_orders[0]
    order_prefix = (
        f"[進行中工單]\n"
        f"工單編號: {order.id}\n"
        f"狀態: {order.status}\n"
        f"技師: {order.technician_name or '待指派'}\n"
        f"預約時間: {order.scheduled_at or '待確認'}\n\n"
    )
    # 注入到 user message prefix
    # （跟現有 skills_prefix、profile_prefix 一起）
```

新增 tool 讓 Agent 可以操作工單：

```python
@tool
async def manage_work_order(action: str, order_id: str = "", detail: str = "") -> str:
    """管理進行中的工單。可改時間、取消、查詢狀態。

    Args:
        action: "reschedule" | "cancel" | "query"
        order_id: 工單編號
        detail: 補充說明（如新時間）
    """
```

---

## 4. Event Bus 事件清單

| Event Type | 觸發時機 | Handlers |
|------------|----------|----------|
| `work_order.created` | transfer_to_human 建立工單 | 派工媒合、審計、計費、tenant_admin 通知 |
| `work_order.assigned` | 技師被指派 | LINE 推送客戶、審計 |
| `work_order.en_route` | 技師出發 | LINE 推送客戶 |
| `work_order.completed` | 技師完工回報 | LINE 推送客戶、帳務、知識庫 flywheel、OEM 品質回報 |
| `work_order.cancelled` | 客戶或管理者取消 | LINE 推送客戶、審計 |
| `work_order.disputed` | 客戶投訴 | tenant_admin 通知、escalation |

---

## 5. 實作順序

| Phase | 做什麼 | 接觸點 |
|-------|--------|--------|
| **P1** | 建 `work_orders` + `technicians` 表、`dispatch/models.py` + `service.py` | - |
| **P2** | 改造 `transfer_to_human` -> 同時建立工單 | Agent -> Dispatch |
| **P3** | `run_agent()` 注入 `[進行中工單]` 上下文 | 客戶 <-> Agent |
| **P4** | 新增 `manage_work_order` tool | 客戶 <-> Agent |
| **P5** | `dispatch/routes.py` REST API | Admin Portal 用 |
| **P6** | 工單狀態變更 -> LINE push 通知 | Dispatch -> Agent |
| **P7** | Next.js Admin Portal 工單看板 | 前端 |

P1-P4 是核心，做完就能跑。P5-P7 是 UI 層。

---

## 6. 與現有系統的相容性

| 現有元件 | 影響 | 改動量 |
|----------|------|--------|
| `skills/tools.py` transfer_to_human | 新增 create_work_order 呼叫 | ~15 行 |
| `harness/debounce.py` run_agent | 新增工單上下文注入 | ~10 行 |
| `agent.py` build_agent | 新增 manage_work_order tool 到 tools list | 1 行 |
| `storage/postgres_impl.py` | 新增 dispatch_decision event type（已預留） | 0 行 |
| Harness H1-H12 | 完全不動 | 0 行 |
| Skills system | 完全不動 | 0 行 |
| Memory/Checkpoint | 完全不動 | 0 行 |
