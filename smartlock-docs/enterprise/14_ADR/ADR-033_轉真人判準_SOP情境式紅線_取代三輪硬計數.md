---
title: "ADR-033: 轉真人判準——SOP 情境式紅線取代三輪硬計數（FR-AGT-03 正典讓步）"
version: 1.0
status: active
owner: 業主
last-updated: 2026-07-22
relates:
  - ./ADR-025_AI話術邊界與永不自轉工單憲章.md   # 紅線觸發即轉、transfer 唯一出口的上位原則
  - ./ADR-008_Agent核心採LockCore.md            # SOP prompt 層（skill）為行為 SSOT 的架構基礎
  - ./ADR-032_Skill熱更新_品牌庫SSOT_workspace_overlay.md  # SOP 迭代發佈路徑
---

# ADR-033: 轉真人判準——SOP 情境式紅線取代三輪硬計數

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（業主裁決 2026-07-22，UAT-0720-01 稽核「3-1 正典讓步」）|
| 層級 | 系統（agent）|
| 關聯 ADR | [ADR-025](./ADR-025_AI話術邊界與永不自轉工單憲章.md)（話術邊界＋永不自轉工單）、[ADR-008](./ADR-008_Agent核心採LockCore.md)、[ADR-032](./ADR-032_Skill熱更新_品牌庫SSOT_workspace_overlay.md) |
| 觸發 | 0720 外部測試（Irene）問「為何沒三輪就轉真人」→ 碼稽核揭露規格正典（FR-AGT-03 三輪硬計數）與現行實作（SOP 情境式紅線）為 Source-of-Truth 衝突，且無任何 ADR/CR 記錄過此演進 |

## Context（脈絡）

正典規格（04_SRS §2.2.2／§3.1 FR-AGT-03、02_BRD §5.7／BR-AI-03、07_Journey_Map stage 4、
08_User_Flow UF-02/UF-10）規定 Clarify gate 硬計數：`clarification_attempts ≥ 3` 未釐清
即升級轉真人，並由確定性規則引擎寫 `rule_triggered_by`（防 KPI gaming）。

實作演進（2026-06 起多輪 UAT 迭代）走向另一條路：`locksmith-cs-sop` SKILL.md Step 3
明文「缺資料一次列給客人……不要用『問三次仍缺就轉真人』這種硬規則」——因為三輪追問
在真實客服對話中體驗差（客人被擠牙膏式追問）、且「一次列齊缺項」收斂更快。現行轉真人
判準＝紅線觸發即轉（明確要求真人／急迫派工／金錢相關／連續兩次不滿，見
`references/handoff-and-dispatch.md`），`transfer_to_human` 為唯一進線出口（FR-AGT-05）
＋gateway deterministic 兜底（CR-0097「案子不蒸發」）。

碼稽核事實：`clarification_attempts`／`clarification_confirmed_at` 欄位與三輪計數器
在 agent／api／DB 全未實作（grep 零命中）；15_SDS 的 L1/L2/L3 三層**分流**（resolution
channel）為現行有效設計，與三輪**計數**是兩件事，不受本裁決影響。

## Decision（裁決）

1. **三輪硬計數（FR-AGT-03 之 `clarification_attempts ≥ 3` 升級規則）廢止**——正典讓步於
   SOP 演進；轉真人判準以 SOP 紅線為準（紅線觸發即轉，不設輪數門檻）。
2. **轉真人判準 SSOT＝`locksmith-cs-sop`**（SKILL.md＋references/handoff-and-dispatch.md）：
   ①明確要求真人 ②急迫派工 ③金錢相關 ④連續兩次不滿；例外三類（保固知識問／流程問／
   複誦 AI 例句）不轉。`transfer_to_human` 唯一出口與 deterministic 兜底（NFR-Rel-003
   案子不蒸發）**不變**。
3. **Clarify gate（「問題釐清了嗎」）降級為話術原則**，非硬性狀態機轉移；缺項採
   「情境式一次列齊」而非逐輪追問。
4. **如實記載**：`clarification_attempts`／`clarification_confirmed_at` 欄位未實作；
   BR-AI-03 的 deterministic 歸因原則（`rule_triggered_by` 不得由 LLM 自報）在「規則引擎
   存在的範圍內」維持——現行確定性層＝reply_guard 出口兜底＋gateway handoff fallback，
   其觸發皆有稽核紀錄（escalation store `is_explicit`／reason）。
5. 正典各檔以**標注**方式記錄本裁決（smartlock-docs 只可新增標注不改寫原文）：
   04_SRS 尾段標注塊、02_BRD §5.7／§6.1、07_Journey_Map stage 表後、08_User_Flow §11。

## Consequences（後果）

- ＋規格與實作的 SoT 衝突銷案；外部測試員（Irene）的「為何一輪就轉」有正式依據可引。
- ＋SOP 迭代自由度保留（ADR-032 熱更新路徑），不被過時硬計數綁死。
- －失去「可稽核的釐清輪次 KPI」：若未來要量測 AI 釐清效率或防 gaming 需求升級，
  需另開 ADR 實作確定性計數器（僅稽核記錄、不閘控行為的折衷亦在該輪評估）。
- －`clarification_*` 欄位在 04_SRS §2.1 ProblemCard entity 中成為文件孤兒（已標注）。

## 重評觸發

- 業主要求釐清輪次 KPI／稽核報表；或多品牌租戶要求可配置的轉真人政策（政策引擎化）。
- LLM 判讀失準率（該自答卻轉真人）在 eval pipeline 超閾值——屆時評估確定性輔助層。
