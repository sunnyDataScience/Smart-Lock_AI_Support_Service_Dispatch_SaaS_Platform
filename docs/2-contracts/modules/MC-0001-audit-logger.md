# 稽核日誌完整性規格書 (Audit Log Completeness Specification)

> GAP #13 -- Smart Lock AI Support Service Dispatch SaaS Platform

---

## 1. 概述 (Overview)

本規格定義智慧門鎖服務派遣平台的結構化稽核日誌系統。現有的
`PostgresAuditStorage` 僅記錄對話訊息 (conversation)，不足以滿足
合規與營運分析需求。本規格擴充稽核日誌為七種事件類型，各自具備
獨立的保留期限，並規範 PII 遮蔽策略。

設計目標：

- 所有系統操作皆留下可追溯的稽核軌跡。
- 依事件敏感程度設定差異化保留期限。
- 個人識別資訊 (PII) 在寫入前完成遮蔽。
- 支援多維度查詢：依操作者、目標、事件類型、時間區間。

---

## 2. 事件類型分類 (Event Taxonomy)

系統定義七種稽核事件類型，每種類型對應不同的業務場景與保留期限：

| 事件類型 | 說明 | 保留期限 | 觸發場景 |
|----------|------|----------|----------|
| `conversation` | 對話訊息 | 90 天 | 使用者與 AI agent 的聊天訊息 |
| `tool_invocation` | 工具呼叫 | 90 天 | 每次 tool call，記錄參數與結果摘要 |
| `safety_gate` | 安全閘門事件 | 1 年 | `gate.py` 的攔截、放行、警告事件 |
| `escalation` | 人工轉接事件 | 1 年 | AI 判定需轉接人工客服的事件 |
| `dispatch_decision` | 派工決策 | 2 年 | 派工匹配、指派、拒單、重派等決策 |
| `financial_action` | 財務操作 | 7 年 | 退款、付款、結算、折扣等金流操作 |
| `admin_action` | 管理操作 | 7 年 | 角色變更、系統設定調整、手動覆寫 |

### 2.1 保留期限依據

- 90 天：日常營運資料，查詢頻率高但敏感度低。
- 1 年：安全與合規相關事件，需配合年度稽核。
- 2 年：派工決策涉及服務品質追溯與演算法調優。
- 7 年：財務與管理操作依商業會計法規要求保留。

---

## 3. 稽核條目結構 (Audit Entry Schema)

每筆稽核記錄包含以下欄位：

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| `id` | UUID | Y | 稽核記錄唯一識別碼，自動產生 |
| `event_type` | VARCHAR(50) | Y | 事件類型，見第 2 節 |
| `actor_id` | UUID | Y | 操作者 ID (user / system / agent) |
| `actor_role` | VARCHAR(50) | Y | 操作者角色：`customer`, `technician`, `csm`, `ops`, `admin`, `system`, `agent` |
| `action` | VARCHAR(200) | Y | 操作描述，格式為 `domain.verb`，例如 `refund.approve`, `dispatch.assign` |
| `target_type` | VARCHAR(100) | N | 操作目標類型：`work_order`, `warranty_claim`, `user`, `refund_request` 等 |
| `target_id` | UUID | N | 操作目標 ID |
| `payload` | JSONB | N | 操作詳細資料，PII 已遮蔽 |
| `ip_address` | INET | N | 請求來源 IP |
| `timestamp` | TIMESTAMPTZ | Y | 事件發生時間，預設 `CURRENT_TIMESTAMP` |

### 3.1 建議 SQL 定義

```sql
CREATE TABLE audit_logs (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type   VARCHAR(50)  NOT NULL,
    actor_id     UUID         NOT NULL,
    actor_role   VARCHAR(50)  NOT NULL,
    action       VARCHAR(200) NOT NULL,
    target_type  VARCHAR(100),
    target_id    UUID,
    payload      JSONB,
    ip_address   INET,
    timestamp    TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_event_type ON audit_logs (event_type);
CREATE INDEX idx_audit_logs_actor      ON audit_logs (actor_id);
CREATE INDEX idx_audit_logs_target     ON audit_logs (target_type, target_id);
CREATE INDEX idx_audit_logs_timestamp  ON audit_logs (timestamp);
```

---

## 4. 保留政策 (Retention Policies)

| 事件類型 | 保留天數 | 清理策略 |
|----------|----------|----------|
| `conversation` | 90 | 每日排程刪除過期記錄 |
| `tool_invocation` | 90 | 每日排程刪除過期記錄 |
| `safety_gate` | 365 | 每日排程刪除過期記錄 |
| `escalation` | 365 | 每日排程刪除過期記錄 |
| `dispatch_decision` | 730 | 每週排程刪除過期記錄 |
| `financial_action` | 2555 | 每月排程刪除過期記錄 |
| `admin_action` | 2555 | 每月排程刪除過期記錄 |

### 4.1 清理邏輯

```sql
DELETE FROM audit_logs
WHERE event_type = $1
  AND timestamp < CURRENT_TIMESTAMP - INTERVAL '$2 days';
```

清理作業應在離峰時段執行，避免影響線上查詢效能。
建議使用 `pg_cron` 或應用層排程器。

---

## 5. 查詢模式 (Query Patterns)

### 5.1 依操作者查詢

```sql
SELECT * FROM audit_logs
WHERE actor_id = $1
ORDER BY timestamp DESC
LIMIT $2;
```

用途：追蹤特定使用者或 agent 的所有操作紀錄。

### 5.2 依目標查詢

```sql
SELECT * FROM audit_logs
WHERE target_type = $1 AND target_id = $2
ORDER BY timestamp DESC;
```

用途：查看特定工單、索賠案件的完整操作歷程。

### 5.3 依事件類型查詢

```sql
SELECT * FROM audit_logs
WHERE event_type = $1
  AND timestamp BETWEEN $2 AND $3
ORDER BY timestamp DESC
LIMIT $4;
```

用途：查詢特定時間區間內的安全事件、財務操作等。

### 5.4 複合查詢

```sql
SELECT * FROM audit_logs
WHERE event_type = $1
  AND actor_id = $2
  AND timestamp BETWEEN $3 AND $4
ORDER BY timestamp DESC
LIMIT $5;
```

用途：稽核特定角色在特定時段內的特定類型操作。

---

## 6. PII 遮蔽策略 (PII Masking)

所有寫入 `payload` 的資料必須在寫入前完成 PII 遮蔽：

| 資料類型 | 遮蔽規則 | 範例 |
|----------|----------|------|
| 手機號碼 | 保留前 4 碼，其餘以 X 取代 | `0912-345-678` -> `0912-XXX-XXX` |
| 電子郵件 | 保留首字元與域名，中間以 * 取代 | `user@example.com` -> `u***@example.com` |
| 身分證字號 | 保留首字元，其餘以 X 取代 | `A123456789` -> `AXXXXXXXXX` |

### 6.1 遮蔽實作

遮蔽邏輯以正規表達式 (regex) 實作於應用層，在呼叫 `INSERT` 前執行。
欄位偵測以 key name 匹配：包含 `phone`, `mobile`, `email`, `mail`,
`id_number`, `national_id` 等關鍵字的欄位值自動遮蔽。

---

## 7. 與現有系統的整合

### 7.1 取代現有 PostgresAuditStorage

現有 `agent/storage/postgres_impl.py` 中的 `PostgresAuditStorage` 僅支援
`conversation` 類型。新的 `AuditLogger` 將作為統一稽核介面：

- 現有 `log_message()` 呼叫處改為呼叫 `AuditLogger.log(event_type="conversation", ...)`。
- 新增的六種事件類型由各服務模組在對應操作中呼叫 `AuditLogger.log()`。

### 7.2 各模組整合點

| 模組 | 事件類型 | 觸發時機 |
|------|----------|----------|
| `agent/graph/nodes.py` | `conversation`, `tool_invocation` | 每次對話與工具呼叫 |
| `agent/harness/safety/gate.py` | `safety_gate` | 安全閘門判定 |
| `agent/tools/transfer_human.py` | `escalation` | 轉接人工 |
| `agent/services/dispatch/` | `dispatch_decision` | 派工決策 |
| `agent/services/finance/` | `financial_action` | 退款、付款 |
| `agent/services/warranty/` | `financial_action` | 保固折扣報價 |
| admin API | `admin_action` | 管理操作 |

---

## §X 測試情境與案例 (AuditLogger)

<!-- TC-ID: IT-0069 -->
#### 情境 1: 正常路徑 — conversation 事件寫入後依保留期限可查
*   **Arrange**: 寫入 `conversation` audit entry，actor=u-001。
*   **Act**: 60 天後 GET /audit?event_type=conversation&actor=u-001。
*   **Assert**: 1 筆紀錄可查；91 天後同 query 回 empty（per §2 90-day 保留）。

<!-- TC-ID: IT-0070 -->
#### 情境 2: 正常路徑 — financial_action 7 年保留 + PII 遮蔽
*   **Arrange**: 寫入退款 audit entry，含客戶手機 `0912-345-678`。
*   **Act**: 查詢該 entry。
*   **Assert**: `actor_phone` 顯示 `091*-***-678` (per §3 PII mask)；entry created_at + 7 年仍可查。

<!-- TC-ID: IT-0071 -->
#### 情境 3: 邊界 — 保留期限剛到期當天的查詢
*   **Arrange**: conversation entry，retention=90 天，現在第 90 天 23:59。
*   **Act**: 查詢該 entry。
*   **Assert**: 仍可查 (≤ 期限視為有效)；第 91 天 00:00 起 cleanup job 標 deleted=true。

<!-- TC-ID: IT-0072 -->
#### 情境 4: 邊界 — 同毫秒寫入多筆 idempotency
*   **Arrange**: 同一 actor 在 1ms 內呼叫 audit_log() 5 次（相同 event_type / target_id）。
*   **Act**: 5 個並發 INSERT。
*   **Assert**: 5 筆紀錄都寫入（audit 不去重，每筆 timestamp 微秒級不同 + UUID 唯一）；無 deadlock。

<!-- TC-ID: IT-0073 -->
#### 情境 5: 異常處理 — Audit DB 寫入失敗時整 transaction rollback
*   **Arrange**: financial_action 寫入過程中 mock audit DB connection drop。
*   **Act**: 呼叫 refund.execute()。
*   **Assert**: refund 不執行（status 保留 csm_approved，executed_at 為 null）；error_log 含 `audit.write_failed.tx_rollback`。

<!-- TC-ID: IT-0074 -->
#### 情境 6: 業務規則 — admin_action 不可被任何 role 刪除 (append-only)
*   **Arrange**: super_admin 嘗試 DELETE FROM audit_logs WHERE event_type='admin_action'。
*   **Act**: 執行 DELETE。
*   **Assert**: raise `append_only_violation`；audit_logs 仍含原紀錄 + 新增 `audit.tamper_attempt` 事件 (actor=super_admin)。
