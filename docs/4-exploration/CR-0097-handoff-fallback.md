# CR-0097 — AI 進線「說了轉接卻沒呼叫工具」的兜底

> **狀態**: ✅ 已實作（業主 2026-06-23 實測重現 + 裁決方案 A，同日實作）
> **分支**: `fix/agent-handoff-fallback`（疊於 `feat/sidebar-reorder`）
> **觸發面向**: Architecture boundary（agent channel 層 escalation 行為）+ User flow（進線建卡）

## 1. 背景 / 問題

業主 LINE 實測報修：「門鎖壞了 Chatlock A90 鎖舌卡住 0922371211」（品牌+症狀+電話齊全）。
AI 回了「好的，我已幫您轉接給真人專員處理 🙋」+ 核對資訊，但**問題卡沒生成、後台收不到**。
**重傳一次完全一樣**（穩定重現，非偶發）。

## 2. 根因（log-grounded）

agent log 鐵證（兩次皆同）：

- 只 `iteration 0`、completion=130 tokens、**零工具呼叫**
- AI 直接生成「已轉接真人」**回應文字**，但**沒有實際呼叫 `transfer_to_human` 工具**
- escalation 未新增 → `_forward_escalation_safe` 不觸發 → **沒有任何建問題卡的 POST**

**不是 SOP 沒寫清楚**：`SKILL.md §0` 單一進線鐵律（凡說「已轉接/已安排」必須同輪呼叫
`transfer_to_human`，只說不呼叫=蒸發）+ `booking.md:33` 維修段（收齊型號+症狀+聯絡方式
→ 呼叫工具）都明示。**是 LLM tool-calling 穩定地不遵守**——文字 SOP 壓不住。

> **產品級硬傷**：「進線 → 建問題卡」這個最關鍵起點 100% 依賴 LLM 自覺呼叫工具，
> 而 LLM 不可靠 → 客人報修可能靜默蒸發，後台完全不知道有人來過。

## 3. 決策（§8 業主裁決）

| 方案 | 做法 | 裁決 |
|---|---|---|
| **A** | 話術-行為一致性兜底：偵測「AI 回應承諾轉接 + 本輪未呼叫工具」→ 規則層補 escalation | ✅ **採用** |
| B | 意圖兜底（報修意圖+設備齊全→強制 escalate） | 後續可加（更全面但要意圖判斷）|
| C | 強制 `tool_choice=required` | 否（會誤觸非轉接輪）|

## 4. 實作（守 architecture lock：不加工具 / 不改白名單 / 不 fork 核心）

改在 **channel 層** `lockcore/channels/line_gateway.py`（非 agent 核心 loop）：

- `_HANDOFF_PROMISE_MARKERS` + `_promised_handoff(reply)`：偵測「完成式/指派式」承諾話術
  （已幫您轉接 / 已為您安排 / 專員會聯繫 / 安排師傅技師 …），降低純資訊提及誤判。
- `_apply_handoff_fallback_safe(...)`：turn 後若「escalation 未較 `esc_before` 新增（=沒呼叫
  工具）**且** AI 回應承諾轉接」→ 補一筆 `escalation_store.log(...)`（模擬 `transfer_to_human`
  做的唯一動作），使既有 `_forward_escalation_safe` 仍建 AI 草擬問題卡。
- callback 在 `_persist_turn` 後、`_forward_escalation` 前插入兜底。全程 fail-soft。

**設計取捨**：誤判（純資訊提及承諾詞）寧可多建一張卡（後台可關），也不讓真正的報修靜默
蒸發——漏建卡（客人不見）後果嚴重得多。

## 5. 測試

`test_line_gateway` 新增 6：`_promised_handoff` 正/反例、兜底補卡、已呼叫工具不重複補、
無承諾不補、無 store 不爆。agent 全套 **126 passed**（原 120 + 6）。

## 6. Follow-up

- **監控兜底觸發率**：若頻繁觸發代表 LLM 對某情境穩定不呼叫工具，需回頭調 SOP / 模型 /
  方案 B 意圖兜底。
- 兜底建的卡 `facts_snapshot.fallback=true` + reason 標記，便於後台辨識與統計。
- 部署 agent 後須 live 重測同一句確認問題卡生成。
