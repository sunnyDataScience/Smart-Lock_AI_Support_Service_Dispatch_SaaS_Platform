# TC-CS-AI-04 — 客戶顯式要求真人客服

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務；agent 側測試可離線跑（21 passed，見步驟 6）；API 側測試需資料庫，無 DB 時 failed 而非 skipped |
| 走查時間 | 2026-08-03 17:05（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/lockcore/agent/tools/transfer.py`、`agent/lockcore/agent/user_memory/escalation.py`、`agent/lockcore/channels/line_gateway.py`、`api/services/problem_card_service.py`、`api/routers/problem_cards_v2.py`、`web/brand-portal/src/app/problem-cards/page.tsx`、`web/brand-portal/src/components/problem-cards/ProblemCardsTable.tsx` |
| 優先級 / 路徑類型 | P0 / happy |
| 事實結論 | 「我要找真人客服」命中 `TRANSFER_KEYWORDS` 的 `"找真人"`，`is_explicit` 判為 True；escalation 同時寫入 `reason` / `is_explicit` / `facts_snapshot` 三欄；後台佇列以 `source='ai_line'` 篩選並在表格渲染「AI 草擬」badge 與待補欄位 hint，卡片路徑完整可追。 |

**TC 原文**｜前置：對話進行中｜步驟：客戶輸入「我要找真人客服」｜判定基準：escalation 記 is_explicit=true + facts_snapshot；後台待轉佇列出現卡片｜需求：FR-AGT-04、FR-AGT-05、FR-AGT-09｜旅程：SC-03、SC-10

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶 | LINE 輸入「我要找真人客服」 | `HumanRequestReceived` | 顯式要求即轉 | `agent/lockcore/agent/tools/transfer.py:27-36` | `"找真人"` 在 `TRANSFER_KEYWORDS` 內 |
| AI | 呼叫 transfer_to_human | `EscalationLogged(is_explicit=true)` | 記稽核 | `transfer.py:140-156` | `is_explicit` 由 `_is_explicit_transfer_request(user_text)` 得出，連同 snapshot 寫入 |
| 系統 | 落 escalation 表 | `EscalationPersisted` | tenant+user_id default deny | `agent/lockcore/agent/user_memory/escalation.py:47-55`、`:62-85` | 表含 `is_explicit INTEGER` 與 `facts_snapshot TEXT`；`_require_scope` 缺一即拒 |
| 系統 | 旁路 POST ingest | `EscalationForwarded` | 本輪有新 escalation 才送 | `agent/lockcore/channels/line_gateway.py:590-597` | payload 帶 `is_explicit` 與 `facts_snapshot` |
| API | 建卡＋翻對話狀態 | `ProblemCardDrafted` / `ConversationEscalated` | 進待人工 | `api/services/problem_card_service.py:976-980`、`:1074-1082` | 對話翻 `escalated`（API `waiting_human`）；卡 `source='ai_line'`、`urgency='high'` |
| 客服 | 開後台佇列 | `QueueCardVisible` | 依來源篩選 | `api/routers/problem_cards_v2.py:66`、`web/.../problem-cards/page.tsx:229-238` | `source` query 參數 + 下拉「AI 草擬（待轉工單）」 |

---

## 走查紀錄

### 步驟 1 — 「我要找真人客服」是否命中顯式關鍵字

- **動作**：讀關鍵字表與判定函式
- **預期**：輸入命中 → `is_explicit=True`
- **實際**：一致。`"找真人"` 為 `TRANSFER_KEYWORDS` 第一組成員，`"我要找真人客服"` 為其超字串，`any(kw in text ...)` 成立

`agent/lockcore/agent/tools/transfer.py:26-31`

```python
# 「客戶顯式要求轉真人」關鍵字。兩類:(a) 直接要人工;(b) 金錢相關(業主硬規則,一律轉真人)。
TRANSFER_KEYWORDS: tuple[str, ...] = (
    # 直接要求人工
    "轉真人", "找真人", "找專員", "找人工", "人工客服",
    "幫我轉接", "我不要跟機器人", "讓我跟人說話", "請師傅來", "派師傅",
```

`agent/lockcore/agent/tools/transfer.py:54-57`

```python
def _is_explicit_transfer_request(text: str) -> bool:
    if not text:
        return False
    return any(kw in text for kw in TRANSFER_KEYWORDS)
```

判定所吃的 `text` 來自 `set_context` 寫入的 `metadata["user_input"]`（`transfer.py:109-116`），且該 ContextVar 只在 metadata 帶 `user_input` 時更新，同 turn 內後續空 metadata 呼叫不會洗掉當前訊息。

### 步驟 2 — escalation 是否同時記 is_explicit 與 facts_snapshot

- **動作**：讀工具的 execute
- **預期**：兩者一起寫入
- **實際**：一致。snapshot 為 dict，含 `facts_block` / `user_input_excerpt` / `brand` / `model` / `symptom` 五鍵

`agent/lockcore/agent/tools/transfer.py:140-156`

```python
        user_id = self._user_id.get() or "anonymous"
        user_text = self._user_input.get()
        is_explicit = _is_explicit_transfer_request(user_text)

        facts_block = self._facts_block(user_id)
        snapshot = {
            "facts_block": facts_block,
            "user_input_excerpt": user_text[:200],
            # CR-0098：LLM 從對話抽出的結構化裝置/症狀 → 旁路帶給 API 自動填問題卡。
            "brand": (brand or "").strip()[:100],
            "model": (model or "").strip()[:100],
            "symptom": (symptom or "").strip()[:200],
        }

        if self._escalation_store:
            try:
                self._escalation_store.log(self._tenant, user_id, reason, is_explicit, snapshot)
```

### 步驟 3 — escalation 儲存 schema

- **動作**：讀 store
- **預期**：欄位存在且可回讀
- **實際**：一致。`is_explicit` 存 INTEGER（`1 if is_explicit else 0`），`facts_snapshot` 存 JSON 字串；`_row` 回讀時轉回 bool / dict

`agent/lockcore/agent/user_memory/escalation.py:47-55`

```sql
            CREATE TABLE IF NOT EXISTS escalation(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant TEXT NOT NULL,
                user_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                is_explicit INTEGER NOT NULL DEFAULT 0,
                facts_snapshot TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL
            );
```

### 步驟 4 — 轉發到 API 時兩欄是否保留

- **動作**：讀 gateway 轉發 payload
- **預期**：`is_explicit` 與 `facts_snapshot` 原樣帶出
- **實際**：一致

`agent/lockcore/channels/line_gateway.py:590-597`

```python
    payload = {
        "tenant_id": tenant,
        "line_user_id": user_id,
        "session_id": f"{tenant}:{user_id}",
        "reason": rec.reason or "",
        "is_explicit": bool(rec.is_explicit),
        "facts_snapshot": snapshot,
    }
```

request model 對應欄位存在於 `api/models/internal.py:56-63`（`is_explicit: bool = False`、`facts_snapshot: dict | None = None`）。

### 步驟 5 — 後台待轉佇列是否出現卡片

- **動作**：讀 API 篩選與前端渲染
- **預期**：佇列可依來源撈出該卡並顯示
- **實際**：一致。卡以 `source='ai_line'` 落庫、`urgency` 因 `is_explicit=True` 取 `high`；同一次呼叫把對話翻成 `escalated`（API `waiting_human`），客服發訊框才可用

`api/services/problem_card_service.py:1074-1082`

```python
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

`api/services/problem_card_service.py:976-980`

```python
    await db_module._conn.execute(
        "UPDATE conversations SET status = 'escalated', updated_at = NOW() "
        "WHERE id = %s::uuid AND status IS DISTINCT FROM 'escalated'",
        (conv_id,),
    )
```

`api/services/problem_card_service.py:184-187`

```python
    # CR-0022：後台「待轉 WO 佇列」依來源篩 AI 草擬卡（source=ai_line）
    if source:
        where.append("pc.source = %s")
        args.append(source)
```

`web/brand-portal/src/app/problem-cards/page.tsx:229-238`

```tsx
          {/* CR-0022：來源篩選 — 「AI 草擬」即 LINE agent 轉真人待客服人審轉工單的佇列 */}
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
          >
            <option value="">{tFilters("source")}</option>
            <option value="ai_line">AI 草擬（待轉工單）</option>
            <option value="human">客服手建</option>
          </select>
```

`web/brand-portal/src/components/problem-cards/ProblemCardsTable.tsx:100-113`

```tsx
              {card.source === "ai_line" && (
                <span
                  className="mr-2 rounded px-[6px] py-[2px] text-[10px] font-semibold align-middle"
                  style={{ color: "#7C3AED", backgroundColor: "#F3E8FF" }}
                  title={
                    card.ai_missing_fields && card.ai_missing_fields.length > 0
                      ? tTable("aiDraftPendingTitle", { fields: ... })
                      : tTable("aiDraftReviewTitle")
                  }
                >
                  {tTable("aiDraftChip")}
                </span>
              )}
```

### 步驟 6 — 執行既有測試

- **動作**：跑 agent 側轉接相關測試與 API 側建卡測試
- **預期**：取得執行證據
- **實際**：agent 側 21 passed；API 側 9 failed / 2 passed，失敗原因為無資料庫

```
cd agent && python -m pytest tests/test_transfer_to_human.py tests/test_sentiment.py \
  tests/test_cr_0074_redline.py -q -rs
21 passed in 3.09s

cd api && python -m pytest tests/test_escalation_to_draft_pc.py -q --tb=no -rf
FAILED tests/test_escalation_to_draft_pc.py::test_escalation_creates_draft_pc
FAILED tests/test_escalation_to_draft_pc.py::test_escalation_flips_conversation_to_waiting_human
FAILED tests/test_escalation_to_draft_pc.py::test_list_cards_source_filter
...
9 failed, 2 passed in 2.76s
```

API 側失敗訊息為 `環境變數 POSTGRES_URI 未設定` → `AttributeError: 'NoneType' object has no attribute 'execute'`（`api/core/db.py` 記 ERROR）。該檔無 skipif 守衛，故顯示為 failed 而非 skipped。

---

## 觀測到的其他事實

- 工具 docstring 明載「不做 gating」（`transfer.py:12`），`is_explicit` 只作稽核欄位，不決定是否轉接；是否呼叫 `transfer_to_human` 由 LLM 依 description 白名單（`transfer.py:76-87`）決定。
- CR-0097 兜底路徑（`line_gateway.py:794-828`）在「AI 回覆承諾轉接但本輪未呼叫工具」時會補寫一筆 escalation，該路徑的 `is_explicit` 為寫死的 `False`（`line_gateway.py:818`），snapshot 另帶 `fallback: True`、`assistant_excerpt` 兩鍵。
- `_facts_block` 在無 memory store 或查無 facts 時回傳固定字串「(目前尚未掌握您的聯絡與裝置資訊)」（`transfer.py:118-130`），故 `facts_snapshot.facts_block` 恆非空字串。
- 建卡走 24h 冪等視窗（`problem_card_service.py:1026-1039`）與同對話 active 卡併入（`:1043-1070`）；重複轉真人時回既有卡而非新增卡。
