# TC-CS-AI-12 — 四種轉真人條件與三種反例

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務；判定基準的行為面需 live LLM 才可觀察 |
| 走查時間 | 2026-08-03 16:16（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/lockcore/skills/locksmith-cs-sop/`、`agent/lockcore/templates/SOUL.md`、`agent/lockcore/agent/tools/transfer.py`、`agent/lockcore/agent/sentiment.py`、`agent/lockcore/channels/line_gateway.py` |
| 優先級 / 路徑類型 | P0 / boundary |
| 事實結論 | 四種觸發條件、「缺項一次列齊」皆定義在 skill／prompt 層，程式碼中無對應判定邏輯；「連續兩次不滿」找不到程式化計數器，情緒判定存在但與轉真人無耦合；「不因固定輪數誤轉」有反向證據——SKILL.md 與 SOUL.md 明文禁止固定輪數規則，程式碼中亦無該邏輯。 |

**TC 原文**｜前置：準備四種紅線與一般補資料、單次不滿、可回答問題反例｜步驟：逐案進線並觀察轉真人與問題卡｜判定基準：明確要求真人、急迫派工、金錢相關、連續兩次不滿任一命中即轉；三種反例不因固定輪數誤轉；缺項一次列齊｜需求：FR-AGT-03｜旅程：SC-02

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶 | 明確要求真人 | `TransferToHumanRequested` | 命中即轉 | `skills/locksmith-cs-sop/references/handoff-and-dispatch.md:17-30` | prompt 層規則；程式無 gating |
| 客戶 | 急迫派工 | `TransferToHumanRequested` | 命中即轉 | 同上 | 同上 |
| 客戶 | 金錢相關 | `TransferToHumanRequested` | 命中即轉 | 同上＋`reply_guard.py:124-126` | prompt 層＋回覆後金額 regex 兜底 |
| 客戶 | 連續兩次不滿 | `TransferToHumanRequested` | 命中即轉 | `handoff-and-dispatch.md:30` | 僅 SOP 文字；**找不到**程式化計數器 |
| 系統 | 判定情緒 | `SentimentClassified` | （TC 未要求） | `agent/lockcore/agent/sentiment.py:88-108` | 結果只寫入 persist payload，無 escalation 分支讀取 |
| 系統 | 反例不誤轉 | （不應發生）`TransferToHumanRequested` | 不因固定輪數轉 | `SKILL.md:70`、`SOUL.md:14` | 明文禁止硬規則；程式碼無輪數邏輯 |
| AI | 缺資料時提問 | `MissingFieldsListed` | 一次列齊 | `SKILL.md:70-73` | prompt 層規則；agent 側無 missing-fields 組裝函式 |

---

## 走查紀錄

### 步驟 1 — 四種觸發條件的定義位置

- **動作**：找四條件的權威定義
- **預期**：程式碼中有判定邏輯
- **實際**：定義在 skill 文件

`agent/lockcore/skills/locksmith-cs-sop/SKILL.md:33-34`

```
2. **明確要求真人 / 金錢相關(報價·費用·退費·發票·付款) / 急迫派工 / 連續不滿**
   → 呼叫 `transfer_to_human`,**不報價、不追問**。
```

`agent/lockcore/skills/locksmith-cs-sop/references/handoff-and-dispatch.md:17-30` 逐條展開（急迫派工列舉「現在就派師傅來／馬上叫修／趕快派人來／請師傅來」；第 30 行為「客戶連續兩次不滿,或重複要求 → 轉真人。」）。同義重述另見 `skills/locksmith-product-knowledge/references/_common/dispatch.md:46-47`。

程式側只有關鍵字表 `agent/lockcore/agent/tools/transfer.py:27-36`，且僅用於標記 `is_explicit`（`transfer.py:54-57`、`:142`），`transfer.py:12` 的 docstring 載明不做 gating。

### 步驟 2 — 「連續兩次不滿」的偵測

- **動作**：搜尋連續不滿的計數邏輯
- **預期**：有跨輪計數器
- **實際**：**找不到**。`agent/` 內「連續兩次不滿」僅 3 處命中，全為 markdown

### 步驟 3 — 情緒判定是否與轉真人耦合

- **動作**：追情緒判定結果的去向
- **預期**：可能作為不滿偵測的輸入
- **實際**：未耦合。`_classify_sentiment_safe`（`line_gateway.py:288-305`）→ `agent/lockcore/agent/sentiment.py:88-108`；結果只掛進 persist payload 的 `sentiment_label`／`confidence`／`keywords`（`line_gateway.py:334-337`），供 API 端寫告警。`_run_merged_turn`（`:1177-1188`）中 `sentiment_payload` 只傳給 `_persist_items`，無任何 escalation 或 transfer 分支讀取，亦無跨輪負面計數狀態

### 步驟 4 — 「不因固定輪數誤轉」

- **動作**：搜尋固定輪數轉真人的邏輯
- **預期**：不存在
- **實際**：不存在，且有反向明文規定

`agent/lockcore/skills/locksmith-cs-sop/SKILL.md:70`（節錄）與 `agent/lockcore/templates/SOUL.md:14`

```
不採「一次只問一條、問三次再轉真人」的硬規則
```

搜尋 `輪數`／`三次`／`turn_count`／`consecutive` 在業務路徑無命中（`consecutive` 僅出現在 provider 訊息合併與 fallback circuit breaker，與轉真人無關）。

### 步驟 5 — 「缺項一次列齊」

- **動作**：找 missing fields 的組裝邏輯
- **預期**：agent 側有程式化組裝
- **實際**：**找不到**程式化組裝；規則在 prompt 層

`agent/lockcore/skills/locksmith-cs-sop/SKILL.md:70-73`（節錄）

```
- **缺資料時,把該情境所有缺的關鍵項目「一次列給客人」**(條列、簡短、易回);不要每次只問一條再等回覆…
```

必抓欄位清單在 `SKILL.md:69`，細節於 `references/booking.md`。agent 側唯一的結構化欄位是工具參數 `brand`／`model`／`symptom`（`transfer.py:63-68`）與 gateway 的確定性補抽函式。

API 端另有一份待補欄位清單 `api/services/problem_card_service.py:830-831`，以 list comprehension 一次算出（詳見 TC-CS-AI-01 步驟 6）——該處針對的是問題卡欄位，非對客提問。

### 步驟 6 — 執行既有測試

- **動作**：跑紅線結構守線測試
- **預期**：取得執行證據
- **實際**：`test_cr_0074_redline.py` 通過（驗 SKILL.md 決策樹、白名單、`TRANSFER_KEYWORDS` 覆蓋、`_PRICE_RE` 單一來源等結構面）；行為面測試 `test_cr_0086_ai_intake_live.py` 因缺 Vertex 憑證 skip

```
cd agent && python -m pytest ... tests/test_cr_0086_ai_intake_live.py -q -rs

SKIPPED [1] tests\test_cr_0086_ai_intake_live.py:62: 需 Vertex 憑證（GOOGLE_APPLICATION_CREDENTIALS / credentials.json）才跑 live AI E2E
SKIPPED [1] tests\test_cr_0086_ai_intake_live.py:70: 需 Vertex 憑證（GOOGLE_APPLICATION_CREDENTIALS / credentials.json）才跑 live AI E2E
116 passed, 2 skipped in 6.33s
```

本 TC 的判定基準（逐案進線觀察是否轉真人）需 live LLM 才能取得行為證據，本批未執行。

---

## 觀測到的其他事實

- `agent/scripts/multiturn_sim_eval.py` 以 LLM 評分間接量測多輪行為；`agent/scripts/real_turn_demo.py:78` 註明「缺資料情境:應『一次列出』門照片/品牌型號/聯絡方式」。
- 情緒判定失敗時走關鍵詞 fallback（`agent/lockcore/agent/sentiment.py:23-28` 的 `_ESCALATION_KEYWORDS`），該 fallback 同樣不觸發轉真人。
