# Hypothesis Quality Baseline 標註指南

對齊新需求《AI客服 Harness設計策略》§10.2 過程指標。

## 目標

50 場真實對話人工標註 → 算出 Hypothesize prompt 在四個維度的 baseline，後續 prompt 改動才能用同一份標註當 ground truth 評分。

## 四個維度

每場對話的「Turn N」標一份 ground truth + 拿 Hypothesize 輸出對比，產出四個 0/1 分數：

### 1. Coverage（覆蓋率）

問題：**人類能想到的客戶真實意圖，Hypothesize 輸出有沒有覆蓋？**

判斷：
- 標註者寫 1-3 個「客戶真正想做的事」（自然語言）
- 看 Hypothesize 輸出的 `description` 至少一個是否與標註的任一項**意思一致**
- 完全沒涵蓋 → 0；部分涵蓋（核心意圖對但細節差） → 0.5；完全涵蓋 → 1

範例：
- 客戶說「卡卡的」，人類想到 [門五金鬆動 / 鎖芯卡住 / app 卡頓]
- Hypothesize 輸出只列了「鎖芯卡住」一項 → 0.5（少 2 個 misframe）
- Hypothesize 輸出列了三個方向 → 1

### 2. Calibration（信心校準）

問題：**Hypothesize 給的 confidence 跟人類眼中的「實際可能性」差多少？**

判斷：
- 標註者給「客戶真實意圖」的人類信心估值（0.0-1.0）
- 看 Hypothesize 的 top.confidence 跟標註值距離
- 距離 < 0.15 → 1；0.15-0.30 → 0.5；> 0.30 → 0

範例：
- 客戶清楚問「AS850 加卡步驟」，人類信心 0.9
- Hypothesize 輸出 top.confidence=0.85 → 距離 0.05 → 1
- Hypothesize 輸出 top.confidence=0.5 → 距離 0.40 → 0（過度保守）

### 3. Evidence Quality（證據品質）

問題：**Hypothesize 的 description 是否引用了客戶訊息中的具體字眼？**

判斷：
- 看 description 有沒有從客戶訊息抓關鍵詞（型號、症狀詞、行為詞）
- 完全空泛（「客戶可能在問問題」）→ 0
- 描述有 1 個關鍵詞 → 0.5
- 描述有 2+ 關鍵詞且整合成情境 → 1

### 4. Misframe Detection（誤解識別）

問題：**客戶用詞跨領域時，Hypothesize 有沒有在 likely_misframe 標出潛在誤解？**

判斷：
- 標註者先判斷此 case 是否含 misframe 風險（「卡卡的」「壞了」「電子鎖」等模糊詞 → yes）
- yes case：看 Hypothesize 有沒有填 likely_misframe 且**內容指向人類認為的誤解方向**
  - 完全沒填 likely_misframe → 0
  - 填了但方向錯 → 0
  - 填了且方向對 → 1
- no case（客戶訊息明確）：不評（不計入 misframe rate）

## JSON 標註格式

每場對話一筆，欄位如下：

```json
{
  "case_id": "hq-baseline-001",
  "source_thread_id": "line_user_abc123",
  "turn_index": 2,
  "context": "客戶上輪 AI 問了「您家是哪款電子鎖？」",
  "user_message": "卡卡的",

  "ground_truth": {
    "human_intents": ["門五金鬆動", "鎖芯卡住", "app 操作卡頓"],
    "human_top_confidence": 0.40,
    "human_misframe_required": true,
    "human_misframe_expected": "客戶用『卡卡的』可能跨指三個物理位置（門五金/鎖芯/app）"
  },

  "hypothesize_output": {
    "top_description": "客戶說鎖芯卡住",
    "top_confidence": 0.55,
    "top_likely_misframe": null,
    "all_descriptions": ["客戶說鎖芯卡住"]
  },

  "scores": {
    "coverage": 0.5,
    "calibration": 0.5,
    "evidence_quality": 0.5,
    "misframe_detection": 0
  },

  "notes": "Hypothesize 只列了 1 個方向；confidence 偏高且沒填 misframe"
}
```

## 流程

1. **抽樣 50 場** — 從 `agent_v2/chat_log_pipeline/line_chat/` 隨機（含品牌分布、輪數分布）
2. **過 Hypothesize** — 對每場的某一輪跑 `hypothesize()`，把輸出寫進 `hypothesize_output`
3. **人工填 ground_truth + scores** — 標註者照本指南填
4. **彙整 baseline** — 跑 `hypothesis_quality_baseline.py --report`，得四個維度的平均分

## 通過標準（新需求建議）

- Coverage > 80%
- Calibration > 70%
- Evidence Quality > 75%
- Misframe Detection > 60%（業主強調的能力差距，本指標較低代表 prompt 還要強化）

之後任何 prompt 改動都需要跑同一批 50 場，比較分數變化才能上線。
