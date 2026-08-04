# TC-CS-AI-01 — 派工意圖進線建草擬問題卡

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務；API 端 happy path 測試因無資料庫而失敗（見步驟 7） |
| 走查時間 | 2026-08-03 16:04（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/lockcore/channels/line_gateway.py`、`agent/lockcore/agent/tools/transfer.py`、`api/routers/internal_ingest.py`、`api/services/problem_card_service.py`、`SQL/migrations/032-problem-card-ai-draft.sql` |
| 優先級 / 路徑類型 | P0 / happy |
| 事實結論 | 判定基準的五個環節（驗簽 → Turn → transfer_to_human → ingest → 建卡）在程式碼中連續可追；卡以 `source='ai_line'` 寫入、DB 狀態 `'incomplete'`（API 對外為 `draft`）、`ai_missing_fields` 以清單一次寫入。 |

**TC 原文**｜前置：LINE channel 綁定、agent gateway 運行｜步驟：消費者 LINE 傳「我家的電子鎖打不開了，請派師傅來修」｜判定基準：webhook 驗簽通過 → Turn 執行 → 命中派工意圖 → transfer_to_human 觸發 → /internal/escalations/ingest 建 source=ai_line 草擬問題卡（status=draft、ai_missing_fields 列缺欄）｜需求：FR-AGT-01｜旅程：SC-02、SC-17

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶 | LINE 傳派工訊息 | `WebhookVerified` | 驗簽通過才處理 | `line_gateway.py:1198-1206` | 驗簽失敗回 400，通過才續行 |
| 系統 | 執行 Turn | `TurnStarted` | 一批一輪 | `line_gateway.py:1160-1164` | 記 `esc_before` 後呼叫 `handle_text_turn` |
| AI | 呼叫 transfer_to_human | `EscalationLogged` | 派工意圖命中即轉 | `agent/lockcore/agent/tools/transfer.py:132-156` | 寫入 escalation，帶 reason／is_explicit／snapshot |
| 系統 | 轉發建卡 | `EscalationForwarded` | 本輪有新 escalation 才送 | `line_gateway.py:576-577`、`:443-468` | 比對 id 後 POST `/api/v1/internal/escalations/ingest` |
| API | 建草擬卡 | `ProblemCardDrafted(source=ai_line)` | status=draft、列缺欄 | `api/services/problem_card_service.py:1077-1097` | INSERT `'incomplete'`、`'ai_line'`、`ai_missing_fields` |

---

## 走查紀錄

### 步驟 1 — 驗簽通過

- **動作**：確認 webhook 入口
- **預期**：驗簽通過才進後續
- **實際**：一致（詳見 TC-CS-AI-02）

### 步驟 2 — Turn 執行與建卡基準點

- **動作**：讀合併輪
- **預期**：turn 前記下 escalation 基準
- **實際**：`line_gateway.py:1159-1160` 取 `esc_before = _latest_escalation_id(...)`，`:1162-1164` 呼叫 `handle_text_turn`，後者 `:1001` 進 `loop._process_message`

### 步驟 3 — 派工意圖 → transfer_to_human

- **動作**：讀工具執行
- **預期**：呼叫後寫入 escalation
- **實際**：一致

`agent/lockcore/agent/tools/transfer.py:154-156`

```python
        if self._escalation_store:
            try:
                self._escalation_store.log(self._tenant, user_id, reason, is_explicit, snapshot)
```

`is_explicit` 由 `TRANSFER_KEYWORDS`（`transfer.py:27-36`，含「請師傅來」「派師傅」）判定，供稽核用；`transfer.py:12` 的 docstring 載明工具本身不做 gating。

### 步驟 4 — 轉發到 ingest 的條件與 payload

- **動作**：讀轉發函式
- **預期**：本輪有新 escalation 才送
- **實際**：一致。`line_gateway.py:576-577` 比對 id；payload 組成於 `:558-606`，含 `tenant_id`／`line_user_id`／`session_id`／`reason`／`is_explicit`／`facts_snapshot`

`agent/lockcore/channels/line_gateway.py:443-453`

```python
        async with httpx.AsyncClient(timeout=_PERSIST_TIMEOUT_SEC) as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/api/v1/internal/escalations/ingest",
                json=payload,
                headers=_bridge_auth_headers(token),
            )
```

### 步驟 5 — API 端點與授權

- **動作**：讀路由
- **預期**：端點存在且受保護
- **實際**：一致

`api/routers/internal_ingest.py:129-159`

```python
@router.post(
    "/internal/escalations/ingest",
    operation_id="ingestEscalation", ...)
async def ingest_escalation(
    body: EscalationIngestRequest,
    auth: ServicePrincipalContext = Depends(
        service_credential_required("escalations:write")),
) -> dict:
    tenant_id = _resolve_tenant_id(body.tenant_id)
    assert_tenant_scope(auth, tenant_id)
    result = await problem_card_service.escalation_to_draft_pc(...)
```

### 步驟 6 — 建卡的欄位值

- **動作**：讀 INSERT
- **預期**：`source=ai_line`、`status=draft`、`ai_missing_fields` 列缺欄
- **實際**：`source` 與 `ai_missing_fields` 一致；狀態值 DB 端為 `'incomplete'`

`api/services/problem_card_service.py:1072-1082`

```python
    # CR-0098：LLM 已從對話抽出的 brand/model 自動填入（沒抽到才留空待客服補）；
    # ai_missing_fields 動態剔除已填欄位，前端「待補」徽章才準確。
    filled = {"brand": ai_brand, "model": ai_model}
    missing = [f for f in _AI_DRAFT_MISSING_FIELDS if not filled.get(f)]
    urgency = "high" if is_explicit else "normal"
    cur = await db_module._conn.execute(
        "INSERT INTO problem_cards "
        "  (conversation_id, brand, model, category, symptoms, urgency, intent, status, "
        "   source, ai_missing_fields, idempotency_key, tenant_id, media_urls) "
        "VALUES (%s::uuid, %s, %s, %s, %s::jsonb, %s, 'repair', 'incomplete', "
        "        'ai_line', %s::jsonb, %s, %s::uuid, %s::jsonb) "
```

待補欄位清單 `api/services/problem_card_service.py:830-831`

```python
# CR-0022/ADR-0112：AI 草擬卡預設待補欄位（客服在佇列補全；location 為 convert 前置硬需求）
_AI_DRAFT_MISSING_FIELDS = ["brand", "model", "location"]
```

`missing` 為一次計算出的完整清單（list comprehension），非逐次追加。`location` 不在 `filled` 中，而該 INSERT 也未寫入 location 欄位，故建卡當下 location 確實為空。

Schema 欄位 `SQL/migrations/032-problem-card-ai-draft.sql:14-19`

```sql
ALTER TABLE problem_cards
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'human';
ALTER TABLE problem_cards
    ADD COLUMN IF NOT EXISTS ai_missing_fields JSONB NULL;
```

TC 判定基準寫 `status=draft`，DB 寫入值為 `'incomplete'`（`SQL/Schema.sql:266-270` 定義預設值即 `'incomplete'`），migration 032 檔頭註記兩者為同一狀態的 DB 值與 API 值。

### 步驟 7 — 執行既有測試

- **動作**：跑 API 端建卡測試
- **預期**：取得執行證據
- **實際**：`test_escalation_to_draft_pc.py` 的 happy path 全數失敗，原因為無資料庫

```
cd api && python -m pytest tests/test_escalation_to_draft_pc.py ... -q --tb=no -rf

FAILED tests/test_escalation_to_draft_pc.py::test_escalation_creates_draft_pc
FAILED tests/test_escalation_to_draft_pc.py::test_charter_ai_draft_not_confirmed
...
22 failed, 25 passed in 5.36s
```

失敗訊息為 `503 DB_UNAVAILABLE` / `環境變數 POSTGRES_URI 未設定`。這些檔案沒有 skipif 守衛，故顯示為 failed 而非 skipped。agent 側測試通過（116 passed / 2 skipped）。

---

## 觀測到的其他事實

- 轉發的認證 header 由 `_bridge_auth_headers`（`line_gateway.py:87-90`）決定：有 `AGENT_API_SERVICE_CREDENTIAL` 時送 `X-Service-Credential`，否則送 `X-Internal-Token`。
- 轉發回應碼語意（`line_gateway.py:454-465`）：<400 視為成功；4xx 記 `[ESCALATION_ALERT]` 但視為終局不重試；5xx 或例外回失敗並落 spool（詳見 TC-NFR-REL-01）。
- `urgency` 依 `is_explicit` 取 `high`／`normal`（`problem_card_service.py:1076`）。
