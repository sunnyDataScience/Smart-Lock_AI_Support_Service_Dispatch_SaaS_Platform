# Inter-Agent Messaging Protocol Specification

> GAP #3 -- Contract M5 Milestone
> Version: 0.1.0 (Phase 0 -- In-Memory)
> Status: Draft

---

## 1. Overview

### 1.1 背景與動機

目前系統中的 7 個 Agent（hardware_technician, sales_representative, store_assistant,
app_specialist, manual_librarian, web_researcher, receptionist）透過 LangGraph state
隱式傳遞資訊。此方式有三個結構性限制：

1. **不可稽核**：Agent 之間的訊息交換沒有留下獨立的紀錄，無法追蹤「誰在什麼時候把什麼傳給誰」。
2. **無法水平擴展**：當 Agent 需要跨 process 或跨 service 通訊時，純 state 傳遞無法支撐。
3. **Contract M5 要求**：合約明確要求正式的 inter-agent messaging protocol，包含 escalation
   chain、correlation tracking 與 audit trail。

### 1.2 設計目標

- Phase 0（本文件）：in-memory message bus，與現有 LangGraph state 整合，零破壞性。
- Phase 1：PostgreSQL 持久化，支援離線重播與稽核查詢。
- Phase 2：topic-based routing，支援 pub/sub pattern 與水平擴展。

### 1.3 整合原則

messaging protocol 是 LangGraph state 的**補充層**，不取代現有 state 傳遞機制。
`state["agent_messages"]` 欄位儲存結構化訊息紀錄，與現有 `messages`（LLM 對話歷史）完全分離。

---

## 2. Message Schema

### 2.1 AgentMessage Dataclass

```python
@dataclass
class AgentMessage:
    msg_id: str               # UUID v4, globally unique
    from_agent: str           # sender agent name (e.g. "router", "hardware_technician")
    to_agent: str             # target agent name, or "*" for broadcast
    msg_type: MessageType     # REQUEST | RESPONSE | BROADCAST | ESCALATION | HANDOFF
    payload: dict             # arbitrary structured data
    correlation_id: str       # links request -> response chains
    timestamp: str            # ISO-8601 UTC (e.g. "2026-04-04T08:30:00Z")
    priority: MessagePriority # LOW | NORMAL | HIGH | URGENT
    ttl_seconds: int          # time-to-live; 0 = no expiry
    metadata: dict            # extensible; e.g. {"retry_count": 1, "trace_id": "..."}
```

### 2.2 欄位說明

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `msg_id` | str | auto | 系統自動產生，不可重複 |
| `from_agent` | str | yes | 發送方 agent 名稱 |
| `to_agent` | str | yes | 接收方 agent 名稱，broadcast 時為 `"*"` |
| `msg_type` | MessageType | yes | 訊息類型（見 Section 3） |
| `payload` | dict | yes | 業務資料，schema 由 msg_type 決定 |
| `correlation_id` | str | auto | 第一則 REQUEST 自動產生，後續 RESPONSE 沿用 |
| `timestamp` | str | auto | UTC ISO-8601 |
| `priority` | MessagePriority | no | 預設 NORMAL |
| `ttl_seconds` | int | no | 預設 300（5 分鐘） |
| `metadata` | dict | no | 擴充欄位，預設空 dict |

---

## 3. Message Types

### 3.1 MessageType Enum

| 類型 | 用途 | 典型場景 |
|------|------|----------|
| `REQUEST` | Agent A 向 Agent B 請求資訊或動作 | router 派發任務給 hardware_technician |
| `RESPONSE` | Agent B 回覆 Agent A 的 REQUEST | hardware_technician 回傳診斷結果 |
| `BROADCAST` | 向所有已註冊 Agent 發送通知 | 系統層級公告、context 更新 |
| `ESCALATION` | Agent 無法處理，向上級或專門 Agent 轉交 | app_specialist 轉交 receptionist |
| `HANDOFF` | Agent 間正式移交控制權（含 context） | manual_librarian handoff 給 web_researcher |

### 3.2 MessagePriority Enum

| 等級 | 數值 | 說明 |
|------|------|------|
| `LOW` | 0 | 非即時通知，可延遲處理 |
| `NORMAL` | 1 | 標準優先級 |
| `HIGH` | 2 | 需優先處理 |
| `URGENT` | 3 | 安全相關或客訴，必須立即處理 |

---

## 4. Routing 機制

### 4.1 Direct Routing（Agent-to-Agent）

最基本的 1:1 通訊。`to_agent` 指定明確的 agent 名稱。

```
hardware_technician --[REQUEST]--> manual_librarian
manual_librarian   --[RESPONSE]--> hardware_technician
```

### 4.2 Broadcast Routing

`to_agent = "*"`，message bus 將訊息複製到所有已註冊 Agent 的 inbox。
適用於 context 更新或系統通知。

```
router --[BROADCAST, to="*"]--> all agents
```

### 4.3 Topic-Based Routing（Phase 2）

依 intent category 訂閱主題。例如 `topic="lock_hardware"` 會 route 到
hardware_technician 和 manual_librarian。Phase 0 不實作，預留 `metadata.topic` 欄位。

---

## 5. 與 LangGraph State 整合

### 5.1 State 欄位

在 `GraphState` 中新增：

```python
agent_messages: Annotated[list, _add_or_reset]  # List[dict] serialized AgentMessage
```

### 5.2 AgentMessageBus 與 State 的關係

```
AgentMessageBus._message_log  <-- canonical source of truth
     |
     +--> serialize to state["agent_messages"] at checkpoint boundaries
```

- AgentMessageBus 維護完整的 in-memory message log。
- LangGraph node 結束時，將相關訊息序列化寫入 `state["agent_messages"]`。
- 現有 node 不讀取此欄位，零破壞性。

### 5.3 Node 使用範例

```python
async def some_agent_node(state: GraphState, config: RunnableConfig):
    bus = get_message_bus(config)
    # send request
    msg = create_message(
        from_agent="hardware_technician",
        to_agent="manual_librarian",
        msg_type=MessageType.REQUEST,
        payload={"query": "FL300 reset procedure"},
    )
    bus.send(msg)
    # ... process ...
```

---

## 6. Sequence Diagrams

### 6.1 Normal Query Flow

```
User          pre_process      router      hardware_technician     merge_answers
  |               |              |                |                     |
  |--question---->|              |                |                     |
  |               |--state------>|                |                     |
  |               |              |                |                     |
  |               |              |--REQUEST------>|                     |
  |               |              |  (via bus)     |                     |
  |               |              |                |--RESPONSE---------->|
  |               |              |                |  (via bus)          |
  |               |              |                |                     |
  |<--answer------|--------------|----------------|---------------------|
```

### 6.2 Escalation Flow

```
User      router      app_specialist      receptionist      merge_answers
  |         |               |                   |                 |
  |-------->|               |                   |                 |
  |         |--REQUEST----->|                   |                 |
  |         |               |                   |                 |
  |         |               |  (cannot handle)  |                 |
  |         |               |--ESCALATION------>|                 |
  |         |               |  priority=HIGH    |                 |
  |         |               |  payload={        |                 |
  |         |               |    reason,        |                 |
  |         |               |    partial_result |                 |
  |         |               |  }                |                 |
  |         |               |                   |--RESPONSE------>|
  |<--------|---------------|-------------------|-----------------|
```

### 6.3 Multi-Agent Collaboration

```
User    router    hardware_technician    manual_librarian    merge_answers
  |       |              |                      |                 |
  |------>|              |                      |                 |
  |       |--REQUEST---->|                      |                 |
  |       |--REQUEST-----|--------------------->|                 |
  |       |              |                      |                 |
  |       |              |--HANDOFF------------>|                 |
  |       |              |  payload={           |                 |
  |       |              |    context,          |                 |
  |       |              |    partial_diagnosis |                 |
  |       |              |  }                   |                 |
  |       |              |                      |                 |
  |       |              |<--RESPONSE-----------|                 |
  |       |              |                      |                 |
  |       |              |--RESPONSE--------------------------->|
  |       |              |                      |--RESPONSE----->|
  |<------|--------------|----------------------|----------------|
```

---

## 7. Correlation Tracking

### 7.1 correlation_id 規則

1. 第一則 `REQUEST` 自動產生新的 `correlation_id`（UUID v4）。
2. 對應的 `RESPONSE` 必須沿用同一個 `correlation_id`。
3. `ESCALATION` 沿用原始 `correlation_id`，確保整條鏈可追蹤。
4. `HANDOFF` 沿用原始 `correlation_id`。
5. `BROADCAST` 使用獨立的 `correlation_id`（與其他 chain 無關）。

### 7.2 查詢 API

```python
bus.get_conversation(correlation_id="abc-123")
# Returns: [REQUEST, RESPONSE, ESCALATION, RESPONSE] -- ordered by timestamp
```

### 7.3 Audit Trail

每條 `AgentMessage` 自帶 `timestamp` 和 `msg_id`，可直接匯出為 audit log。
Phase 1 將寫入 PostgreSQL `agent_message_log` table，支援 SQL 查詢。

---

## 8. Error Handling

### 8.1 Timeout

- 每則訊息有 `ttl_seconds`（預設 300 秒）。
- Phase 0 不實作主動 timeout 檢查（in-memory 無 background worker）。
- Phase 1 引入 background task 掃描過期訊息，產生 timeout RESPONSE。

### 8.2 Agent Unavailable

- `bus.send()` 驗證 `to_agent` 是否在 `registered_agents` 清單中。
- 若目標 Agent 未註冊，拋出 `ValueError` 並記錄 warning log。
- Broadcast 訊息（`to_agent="*"`）不檢查特定 agent 存在性。

### 8.3 Circular Routing Detection

- AgentMessageBus 追蹤同一 `correlation_id` 下的 routing path。
- 若同一 agent 在同一 correlation chain 中出現超過 2 次，判定為 circular routing。
- 檢測到 circular routing 時，`bus.send()` 記錄 error log 並拋出 `RuntimeError`。
- 演算法：從 `_message_log` 中篩選同 `correlation_id` 的訊息，統計 `from_agent` 出現次數。

### 8.4 Payload Validation

- `validate_message()` 檢查必填欄位（from_agent, to_agent, msg_type, payload）。
- `from_agent` 和 `to_agent` 不可為空字串。
- `msg_type` 必須是合法的 `MessageType` enum 值。
- 驗證失敗時拋出 `ValueError`。

---

## Appendix A: Phase Roadmap

| Phase | 範圍 | 儲存層 | 預計時程 |
|-------|------|--------|----------|
| Phase 0 | in-memory bus, basic routing, correlation tracking | `list[AgentMessage]` | M5 |
| Phase 1 | PostgreSQL persistence, audit query API | `agent_message_log` table | M6 |
| Phase 2 | topic-based routing, pub/sub, horizontal scaling | Redis Streams / NATS | M8 |

## Appendix B: 相關檔案

| 檔案 | 用途 |
|------|------|
| `agent/services/messaging/protocol.py` | AgentMessage, MessageType, factory functions |
| `agent/services/messaging/bus.py` | AgentMessageBus class |
| `agent/services/messaging/__init__.py` | Package exports |
| `agent/graph/state.py` | GraphState -- 新增 `agent_messages` 欄位（Phase 0 optional） |
