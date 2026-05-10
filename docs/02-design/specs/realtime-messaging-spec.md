---
status: superseded
superseded_by: docs_v2/2-contracts/modules/realtime-messaging.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# Real-time Messaging Specification (Admin-Technician In-Platform Chat)

> GAP #7 -- Investor Review Notes 1.5
> Version: 0.1.0 (Phase 0 -- In-Memory)
> Status: Draft

---

## 1. Overview

### 1.1 背景與動機

投資人審查筆記 1.5 明確指出：系統缺少管理員與師傅之間的即時通訊功能。目前所有案件
溝通依賴外部管道（LINE 群組、電話），導致三個結構性問題：

1. **溝通紀錄散落**：案件討論分散在多個 LINE 群組中，無法與工單關聯，事後追溯困難。
2. **角色權限失控**：外部群組無法限制誰能看到哪些案件資訊，違反最小權限原則。
3. **即時性不足**：師傅在現場遇到範圍變更、缺料等異常時，缺乏結構化的即時回報管道。

### 1.2 設計目標

提供平台內建的即時通訊功能，讓管理員與師傅能在工單脈絡下進行結構化溝通：

- 每張工單對應一個專屬頻道，溝通紀錄自動綁定工單。
- 支援文字、圖片（URL）、位置（lat/lng）、系統通知（狀態變更）。
- 訊息持久化至 PostgreSQL，支援離線交付與稽核查詢。
- 水平擴展架構：FastAPI WebSocket + Redis pub/sub。

### 1.3 版本規劃

| 版本 | 範圍 | 說明 |
|------|------|------|
| V1.0 | text + image + system_notification | 核心通訊功能，Phase 0 in-memory / Phase 1 PostgreSQL |
| V2.0 | voice messages, read receipts | 語音訊息、已讀回條、訊息搜尋 |

---

## 2. Architecture

### 2.1 技術選型

| 元件 | 技術 | 說明 |
|------|------|------|
| WebSocket Server | FastAPI `WebSocket` endpoint | 內建 ASGI WebSocket 支援，與現有 API 共用 process |
| Message Broker | Redis pub/sub | 支援多 instance 水平擴展；Phase 0 使用 in-memory fallback |
| Message Store | PostgreSQL `chat_messages` table | 訊息持久化、離線交付、稽核查詢 |
| Push Notification | LINE Messaging API | 師傅離線時透過 LINE push notification 通知 |

### 2.2 架構圖（文字描述）

```
Client A (Admin WebSocket)
    |
    v
FastAPI Instance 1 --- Redis pub/sub --- FastAPI Instance 2
    |                                          |
    v                                          v
Client B (Technician WebSocket)          Client C (Admin WebSocket)
    |                                          |
    +-----------> PostgreSQL <-----------------+
                  chat_messages
```

單一 instance 部署時，Redis pub/sub 可省略，直接使用 in-memory channel registry。
多 instance 部署時，每個 instance 訂閱 Redis channel，接收跨 instance 的訊息廣播。

### 2.3 與現有系統的整合

- **工單模組**：`work_orders.id` 作為 channel 的唯一識別碼。
- **使用者模組**：`users.id` 作為 sender_id，透過 JWT token 驗證身份。
- **權限模組**：僅工單的 assigned admin、assigned technician、customer（唯讀）可加入頻道。
- **狀態變更**：工單狀態變更時，自動發送 system_notification 至對應頻道。

---

## 3. Channel Model

### 3.1 頻道與工單的對應

每張工單（`work_order_id`）對應恰好一個通訊頻道。頻道在工單建立時自動建立，
工單結案後頻道轉為唯讀（僅允許查看歷史訊息）。

### 3.2 參與者角色

| 角色 | 權限 | 說明 |
|------|------|------|
| admin | read + write | 負責該工單的管理員，可發送所有類型的訊息 |
| technician | read + write | 被派工的師傅，可發送所有類型的訊息 |
| customer | read-only | 終端客戶，僅能接收系統通知與查看對話紀錄（V2.0 考慮開放有限的寫入權限）|
| system | write-only | 系統自動發送狀態變更通知 |

### 3.3 頻道生命週期

```
work_order created --> channel ACTIVE (read + write)
work_order completed/cancelled --> channel ARCHIVED (read-only)
work_order deleted --> channel DELETED (soft delete, 紀錄保留)
```

---

## 4. Message Types

### 4.1 訊息類型定義

| msg_type | content 欄位格式 | 說明 |
|----------|------------------|------|
| `text` | 純文字字串 | 一般文字訊息 |
| `image` | JSON: `{"url": "https://...", "thumbnail_url": "...", "caption": "..."}` | 圖片訊息，URL 指向 object storage |
| `location` | JSON: `{"lat": 25.0330, "lng": 121.5654, "address": "..."}` | 位置訊息，師傅回報現場座標 |
| `system_notification` | JSON: `{"event": "status_change", "old_status": "...", "new_status": "...", "detail": "..."}` | 系統自動通知，不可由使用者手動發送 |

### 4.2 訊息結構

```python
{
    "msg_id": "uuid-v4",
    "work_order_id": "wo-uuid",
    "sender_id": "user-uuid",
    "sender_role": "admin | technician | system",
    "msg_type": "text | image | location | system_notification",
    "content": "...",         # 依 msg_type 而異
    "metadata": {},           # 擴展欄位
    "timestamp": "2026-04-04T08:30:00Z"
}
```

---

## 5. Message Persistence

### 5.1 PostgreSQL Table: `chat_messages`

```sql
CREATE TABLE chat_messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id   UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    sender_id       UUID NOT NULL REFERENCES users(id),
    sender_role     VARCHAR(20) NOT NULL,               -- 'admin', 'technician', 'system'
    msg_type        VARCHAR(30) NOT NULL,               -- 'text', 'image', 'location', 'system_notification'
    content         TEXT NOT NULL,                       -- plain text or JSON string
    metadata        JSONB DEFAULT '{}',                  -- extensible metadata
    delivered       BOOLEAN DEFAULT FALSE,               -- offline delivery tracking
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  chat_messages IS 'GAP #7: admin-technician real-time chat messages, bound to work orders';
COMMENT ON COLUMN chat_messages.content IS 'text: plain string; image/location/system_notification: JSON string';

CREATE INDEX idx_chat_msg_wo_created ON chat_messages (work_order_id, created_at);
CREATE INDEX idx_chat_msg_sender ON chat_messages (sender_id, created_at);
CREATE INDEX idx_chat_msg_undelivered ON chat_messages (sender_id, delivered) WHERE delivered = FALSE;
```

### 5.2 資料保留政策

- 所有訊息永久保留（不自動刪除），供稽核與爭議處理使用。
- 大量歷史訊息可透過 partitioning（按月分區）優化查詢效能。
- 圖片檔案存放於 object storage（GCS / S3），`chat_messages.content` 僅存 URL。

---

## 6. WebSocket Lifecycle

### 6.1 連線建立

```
Client --> GET /ws/chat/{work_order_id}
           Headers: Authorization: Bearer {jwt_token}
           
Server --> 1. 驗證 JWT token（同 REST API 驗證邏輯）
           2. 檢查使用者是否為該工單的參與者
           3. 檢查工單狀態是否允許即時通訊（ACTIVE）
           4. Accept WebSocket handshake
           5. 將連線註冊至 channel registry
           6. 廣播 system_notification: "{user} joined the channel"
           7. 回傳未讀訊息（離線期間的訊息）
```

### 6.2 訊息收發

```
Client --> WebSocket frame (JSON):
           {"msg_type": "text", "content": "..."}

Server --> 1. 驗證訊息格式（msg_type, content）
           2. Rate limiting 檢查（60 msg/min per user）
           3. 建構完整 ChatMessage（補充 msg_id, sender_id, timestamp）
           4. 持久化至 PostgreSQL
           5. 廣播至所有頻道訂閱者
           6. 離線參與者：標記為 undelivered，觸發 push notification
```

### 6.3 斷線處理

```
Client disconnect --> 1. 從 channel registry 移除連線
                      2. 記錄 last_seen_at
                      3. 廣播 system_notification: "{user} left the channel"
                      4. 後續訊息標記為 undelivered，待重新連線時交付
```

### 6.4 心跳機制

- WebSocket ping/pong：每 30 秒由 server 發送 ping，client 回覆 pong。
- 連續 3 次無回應（90 秒）視為斷線，執行斷線處理流程。

---

## 7. Offline Handling

### 7.1 離線訊息儲存

所有訊息無論接收者是否在線，均持久化至 PostgreSQL。離線使用者的訊息標記
`delivered = FALSE`，待使用者重新連線時批次交付。

### 7.2 Push Notification（師傅端）

師傅離線時，透過 LINE Messaging API 發送 push notification：

- 觸發條件：師傅不在 WebSocket 頻道內，且收到新訊息。
- 通知內容：「[工單編號] 管理員傳送了新訊息，請開啟平台查看。」
- 頻率限制：同一工單每 5 分鐘最多 1 則 push notification，避免騷擾。
- LINE push notification 僅作為提醒，不包含訊息內容（隱私考量）。

### 7.3 離線訊息交付

使用者重新建立 WebSocket 連線時：

1. 查詢 `chat_messages` 中 `delivered = FALSE` 且 `sender_id != current_user` 的訊息。
2. 按 `created_at` 排序，批次發送至 client。
3. 更新 `delivered = TRUE`。

---

## 8. Security

### 8.1 Authentication

- WebSocket handshake 時透過 `Authorization` header 攜帶 JWT token。
- JWT 驗證邏輯與 REST API 完全相同（共用 auth middleware）。
- Token 過期時，server 主動關閉 WebSocket 連線，client 需重新取得 token 後重連。

### 8.2 Authorization

- 僅工單的 assigned admin、assigned technician、customer 可連線至對應頻道。
- customer 角色僅能接收訊息，不可發送（read-only）。
- system_notification 類型僅系統可發送，使用者端發送此類型訊息將被拒絕。

### 8.3 Rate Limiting

| 限制項目 | 上限 | 說明 |
|----------|------|------|
| 每使用者每分鐘訊息數 | 60 | 超過時返回 error frame，不斷線 |
| 單則訊息 content 長度 | 4,096 characters | text 類型；image/location JSON 上限 1,024 |
| 每工單同時連線數 | 10 | 防止異常大量連線 |

### 8.4 Input Validation

- 所有 `content` 欄位進行 XSS sanitization。
- `image` 類型的 URL 必須符合白名單 domain（platform object storage）。
- `location` 類型的 lat/lng 必須為有效座標範圍。

---

## 9. API Endpoints

### 9.1 WebSocket Endpoint

```
WS /ws/chat/{work_order_id}
Headers: Authorization: Bearer {jwt_token}
```

### 9.2 REST Endpoints（輔助）

| Method | Path | 說明 |
|--------|------|------|
| GET | `/api/v1/chat/{work_order_id}/messages` | 查詢歷史訊息（分頁） |
| GET | `/api/v1/chat/{work_order_id}/participants` | 查詢頻道參與者 |
| POST | `/api/v1/chat/{work_order_id}/upload` | 上傳圖片至 object storage，取得 URL |

### 9.3 歷史訊息查詢參數

| 參數 | 類型 | 說明 |
|------|------|------|
| `limit` | int | 每頁筆數，預設 50，上限 100 |
| `before` | str (ISO-8601) | 查詢此時間之前的訊息，用於向前翻頁 |

---

## 10. 與其他 GAP 的關聯

| GAP | 關聯方式 |
|-----|----------|
| GAP #2 工單異常處理 | 師傅透過 chat 回報延遲、範圍變更、缺料等異常，觸發對應流程 |
| GAP #3 Inter-Agent Messaging | 系統級 agent 間通訊協議，與本規格的人對人通訊互補 |
| GAP #9 報價引擎 | 範圍變更時，管理員在 chat 中發送更新報價供師傅確認 |
| GAP #20 爭議處理 | chat 訊息紀錄作為爭議處理的證據之一 |
| GAP #25 完工證據鏈 | 師傅在 chat 中傳送的現場照片可納入完工證據 |
