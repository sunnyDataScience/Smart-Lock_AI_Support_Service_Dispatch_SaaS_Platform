# TC-CS-AI-10 — 承諾轉接未呼叫工具的兜底補建

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務；兜底語料測試可離線執行且已跑 |
| 走查時間 | 2026-08-03 16:10（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `agent/lockcore/channels/line_gateway.py:610-701`、`:792-834`、`:1183-1188` |
| 優先級 / 路徑類型 | P0 / 例外 |
| 事實結論 | 兜底機制存在：偵測「AI 回覆承諾轉接且本輪未新增 escalation」後補寫一筆，由同輪的轉發函式建卡；補建的 reason 為固定字串，snapshot 帶 `fallback: True`。 |

**TC 原文**｜前置：LLM 回覆聲稱「將為您轉接」但未呼叫工具｜步驟：檢查 escalation 表｜判定基準：兜底機制補建 escalation（承諾轉接必落地，案子不得蒸發）｜需求：FR-AGT-05、FR-AGT-09｜旅程：SC-02、SC-10

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| AI | 回覆承諾轉接但未呼叫工具 | （缺漏）`EscalationLogged` | 承諾必落地 | `line_gateway.py:801-806` | 三道守門後判定需補建 |
| 系統 | 判定是否為真承諾 | `HandoffPromiseDetected` | 完成式一律算；未完成式受抑制規則 | `line_gateway.py:669-701` | 位置感知比對，hedge／否定／問句三種抑制 |
| 系統 | 補寫 escalation | `EscalationLogged(fallback)` | 補一筆讓建卡續行 | `line_gateway.py:814-828` | reason 固定字串、`is_explicit=False`、snapshot `fallback: True` |
| 系統 | 轉發建卡 | `ProblemCardDrafted` | 補建後同輪送出 | `line_gateway.py:1183-1188` | 兜底緊接轉發，順序固定 |

---

## 走查紀錄

### 步驟 1 — 兜底的三道守門

- **動作**：讀補建函式的進入條件
- **預期**：只在「有回覆、本輪未呼叫工具、且判定為承諾」時補建
- **實際**：一致

`agent/lockcore/channels/line_gateway.py:801-806`

```python
    if esc is None or not (reply or "").strip():
        return
    if _latest_escalation_id(esc, tenant, user_id) > before_id:
        return  # 本輪 AI 已正常呼叫工具 → 不重複補
    if not _promised_handoff(reply):
        return  # AI 沒承諾轉接 → 不兜底
```

### 步驟 2 — 承諾判定邏輯

- **動作**：讀 `_promised_handoff`
- **預期**：能區分真承諾與條件句提議
- **實際**：逐句掃描，完成式標記一律成立；未完成式標記逐個出現位置檢查，三種抑制條件

`agent/lockcore/channels/line_gateway.py:684-701`

```python
    for sentence in _SENTENCE_RE.findall(reply):
        if not sentence.strip():
            continue
        if any(m in sentence for m in _DEFINITIVE_HANDOFF_MARKERS):
            return True
        for marker in _SOFT_HANDOFF_MARKERS:
            start = 0
            while (idx := sentence.find(marker, start)) >= 0:
                start = idx + 1
                if any(h in sentence[:idx] for h in _HANDOFF_HEDGE_MARKERS):
                    continue  # 條件句提議（條件前置）
                clause = _clause_at(sentence, idx)
                if any(n in clause for n in _HANDOFF_NEGATION_MARKERS):
                    continue  # 否定該動作
                if _is_interrogative(clause):
                    continue  # 徵詢客戶同意
                return True
    return False
```

四張標記表：

- `_DEFINITIVE_HANDOFF_MARKERS`（`:614-618`）13 項完成式，例：`"已幫您轉接"`、`"已派師傅"`
- `_SOFT_HANDOFF_MARKERS`（`:622-628`）20 項未完成式，例：`"專員會"`、`"安排師傅"`
- `_HANDOFF_HEDGE_MARKERS`（`:632-636`）17 項條件語氣，**僅在 marker 之前出現才抑制**
- `_HANDOFF_NEGATION_MARKERS`（`:639-641`）6 項否定，**子句級**比對（`_clause_at` `:653-660`）

問句抑制由 `_is_interrogative`（`:663-666`）判定，句子切分 `_SENTENCE_RE`（`:650`）保留句末標點。

### 步驟 3 — 補建時寫入的內容

- **動作**：讀補建的 `esc.log` 呼叫
- **預期**：可辨識為兜底來源
- **實際**：一致

`agent/lockcore/channels/line_gateway.py:814-828`

```python
        esc.log(
            tenant, user_id,
            "[兜底] AI 承諾轉接但未呼叫 transfer_to_human（CR-0097）",
            False,
            {"user_input_excerpt": (user_text or "")[:200],
             "assistant_excerpt": (reply or "")[:200],
             "fallback": True, "brand": fb_brand, "model": fb_model,
             "symptom": fb_symptom, "phone": fb_phone},
        )
```

品牌／型號／症狀／電話由 `_extract_brand_model`（`:715-732`）、`_clean_symptom`（`:751-765`）、`_extract_phone`（`:776-789`）確定性補抽。

### 步驟 4 — 補建與建卡的順序

- **動作**：確認補建是否來得及讓本輪建卡
- **預期**：補建先於轉發
- **實際**：一致——`line_gateway.py:1183-1185` 呼叫 `_apply_handoff_fallback_safe`，`:1186-1188` 才呼叫 `_forward_escalation_safe`；後者以 `esc_before` 比對，故補建的那筆會被視為新增而送出

### 步驟 5 — 執行既有測試

- **動作**：跑承諾語料與兜底端到端測試
- **預期**：通過
- **實際**：通過。`agent/tests/test_line_gateway.py:110-130` 為真承諾 15 例、`:132-164` 為反例 22 例，`:216-255` 為兜底端到端

```
cd agent && python -m pytest tests/test_line_gateway.py tests/test_escalation_spool_durability.py \
  tests/test_spool_flush_bounded.py tests/test_sentiment.py \
  tests/test_fallback_reply_no_handoff.py tests/test_cr_0086_ai_intake_live.py -q -rs

116 passed, 2 skipped in 6.33s
```

---

## 觀測到的其他事實

- 相容別名 `_HANDOFF_PROMISE_MARKERS`（`line_gateway.py:646-648`）為兩表合集，僅供舊 import，判定不走它。
- 系統兜底話術本身不得誤觸此機制，由 `test_fallback_reply_no_handoff.py` 守線；`_FALLBACK_REPLY`（`line_gateway.py:49-56`）的文字避開了 soft marker。turn 失敗時另一處固定話術（`line_gateway.py:1167`）含「專員與您」字樣，該字樣在 `_SOFT_HANDOFF_MARKERS` 表中（詳見 TC-AGT-TURN-01）。
