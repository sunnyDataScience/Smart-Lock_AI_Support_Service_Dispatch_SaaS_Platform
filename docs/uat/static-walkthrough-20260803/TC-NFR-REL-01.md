# TC-NFR-REL-01 — 中斷與重送下的不遺失、不重複

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務；spool 耐久性測試可離線執行且已跑 |
| 走查時間 | 2026-08-03 16:46（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/lockcore/channels/line_gateway.py:124-139`、`:338-514`、`:558-606`、`:1102-1188`、`agent/tests/test_escalation_spool_durability.py`、`test_spool_flush_bounded.py` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |
| 事實結論 | transfer 與寫入兩條路徑有 spool 落盤與下輪補送，且 4xx 不重試以免壞 payload 永佔佇列；push 送出失敗是唯一無耐久性的路徑——只記 log、不落 spool、不重送。 |

**TC 原文**｜前置：agent transfer、outbox、依賴中斷與重送 fixture｜步驟：在 transfer/push/寫入各階段中斷，再重送 webhook 或恢復服務｜判定基準：不遺失案件、不重複副作用；真承諾一定有 escalation/問題卡；恢復後可對帳｜需求：NFR-Rel-001、NFR-Rel-002、NFR-Rel-003｜旅程：SC-02、SC-03

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 系統 | transfer 轉發失敗（5xx） | `EscalationSpooled` | 不遺失案件 | `line_gateway.py:600-606` | 落 `escalation_spool.jsonl` + `[ESCALATION_ALERT]` |
| 系統 | 下一輪 turn | `SpoolFlushed` | 恢復後補送 | `line_gateway.py:471-514`、`:600` | 先 flush 再送本輪 |
| 系統 | 轉發得到 4xx | `EscalationDropped` | 不重複副作用 | `line_gateway.py:458-463` | 視為終局，回 True 不重試 |
| 系統 | 持久化失敗 | `PersistSpooled` | 不遺失對話 | `line_gateway.py:342-345`、`:379-396` | 落 `persist_spool.jsonl` + `[ARCHIVE_ALERT]` |
| 系統 | push 送出失敗 | `ReplySpooled` | 不遺失 | `line_gateway.py:1173-1174` | **只記 log**，不落 spool、不重送 |
| AI | 真承諾轉接 | `EscalationLogged` | 必有 escalation | `line_gateway.py:801-828` | 兜底補建（詳見 TC-CS-AI-10） |

---

## 走查紀錄

### 步驟 1 — 兩條 spool 的組成

- **動作**：盤點落盤與補送機制
- **預期**：失敗可補送
- **實際**：兩條獨立 spool，形狀與端點不同

| | persist | escalation |
|---|---|---|
| 路徑常數 | `_PERSIST_SPOOL_PATH`（`line_gateway.py:128`，預設 `data/persist_spool.jsonl`） | `_ESCALATION_SPOOL_PATH`（`:374-376`，預設 `data/escalation_spool.jsonl`） |
| POST | `_post_ingest`（`:349-366`）→ `/api/v1/internal/conversations/ingest` | `_post_escalation`（`:443-468`）→ `/api/v1/internal/escalations/ingest` |
| flush | `_flush_persist_spool`（`:399-440`） | `_flush_escalation_spool`（`:471-514`） |
| 告警前綴 | `[ARCHIVE_ALERT]`（`:342-345`） | `[ESCALATION_ALERT]`（`:602-605`、`:505-508`） |

共用寫入函式 `_spool_append`（`:379-396`），全域 asyncio 鎖（`:139`），上限 `_PERSIST_SPOOL_MAX = 500`（`:129`），超限丟最舊並記 ERROR（`:389-393`）。

### 步驟 2 — transfer 失敗的處置

- **動作**：讀轉發失敗分支
- **預期**：不遺失
- **實際**：一致

`agent/lockcore/channels/line_gateway.py:600-606`（節錄）

```python
    await _flush_escalation_spool(base_url, token)
    if not await _post_escalation(base_url, token, payload):
        logger.error("[ESCALATION_ALERT] 轉真人未送達，已落 spool 待補送 ...")
        await _spool_append(payload, _ESCALATION_SPOOL_PATH)
```

回應碼語意（`:454-465`）：<400 成功；4xx 記告警但視為終局回 True（不重試，避免壞 payload 永佔 spool）；5xx 或例外回 False 並落 spool。

### 步驟 3 — 補送的觸發時機與界限

- **動作**：確認補送何時發生、是否有界
- **預期**：恢復後可補送且不拖垮單輪
- **實際**：補送靠「下一輪 turn 觸發 flush」（`_persist_turn_safe:338`、`_forward_escalation_safe:600` 皆先 flush 再送本輪），無指數退避重試器

persist flush 有界：`_SPOOL_FLUSH_MAX_PER_TURN`（`:134`，預設 5）與 `_SPOOL_FLUSH_BUDGET_SEC`（`:135`，預設 3.0），`:414-424` 逐筆檢查上限與截止時間，剩餘原封保留。

escalation flush 為完整迴圈（`:494-502`），無批次或時間上限。兩者共用同一把 process 全域鎖（`:139`）。

### 步驟 4 — push 失敗的處置

- **動作**：讀回覆送出的失敗分支
- **預期**：不遺失
- **實際**：reply 失敗會改用 push 兜底（`line_gateway.py:1102-1115`）；push 也失敗時只記 log

`agent/lockcore/channels/line_gateway.py:1173-1174`（節錄）——`logger.exception` 之後無 spool 寫入，亦無重送。訊息本身仍會經 persist 路徑寫入供客服查看。

TC 判定基準寫「在 transfer/push/寫入各階段中斷…不遺失案件」，transfer 與寫入兩條有 spool，push 送出這條沒有。此處僅並陳，不裁定。

### 步驟 5 — 「真承諾一定有 escalation/問題卡」

- **動作**：確認承諾落地的保證
- **預期**：承諾必有 escalation
- **實際**：由兜底機制保證（詳見 TC-CS-AI-10）；補建後由同輪轉發送出，轉發失敗則落 spool

### 步驟 6 — 「恢復後可對帳」

- **動作**：找對帳依據
- **預期**：有可查詢的殘留狀態
- **實際**：spool 為 JSONL 檔案，可逐筆檢視；告警前綴 `[ESCALATION_ALERT]`／`[ARCHIVE_ALERT]` 可供日誌檢索。API 側另有 outbox 的 `status='dead'` 與 `replay_hint` SQL（詳見 TC-EXC-01）。找不到跨兩側的統一對帳報表

### 步驟 7 — 執行既有測試

- **動作**：跑 spool 耐久性與有界補送測試
- **預期**：通過
- **實際**：通過

```
cd agent && python -m pytest tests/test_line_gateway.py tests/test_escalation_spool_durability.py \
  tests/test_spool_flush_bounded.py tests/test_sentiment.py \
  tests/test_fallback_reply_no_handoff.py tests/test_cr_0086_ai_intake_live.py -q -rs

116 passed, 2 skipped in 6.33s
```

`test_escalation_spool_durability.py` 6 項涵蓋：5xx 落 spool 不遺失、下輪 flush 後刪除、flush 再失敗要保留、部分成功只留失敗者（防重複建卡）、4xx 終局不佔 spool、5xx 可重試。`test_spool_flush_bounded.py` 4 項涵蓋批次上限、時間預算中斷、截斷後不掉件且順序正確、失敗項保留（at-least-once）。

---

## 觀測到的其他事實

- 專案中無 `outbox` 命名的 agent 側實作（grep 零命中）；API 側 outbox 為 `commission_event_outbox`（`SQL/migrations/119`）與 LINE push outbox（`SQL/migrations/111`）。
- `_handover_active_safe`（`line_gateway.py:517-544`）、`_persist_turn_safe`、`_forward_escalation_safe`、`_apply_handoff_fallback_safe` 全為 fail-soft，失敗不中斷主流程。
- 工單／技師生命週期事件的 Kafka 發布無 outbox 保底（詳見 TC-DISPATCH-03 步驟 4）。
