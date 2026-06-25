---
title: 「診斷引擎 / FMEA 分層信心診斷」文件溯源 + Source-of-Truth 衝突盤點
status: active
tier: _audit
created: 2026-06-25
owner: 啟恆 / Sunny 裁決
method: 7-agent fan-out workflow（CR/audit、templates/tiers、agent-lockcore、api/web、xlsx 正典模組地圖、會議記錄+PDF 六語料平行翻找）+ 主 agent 獨立抽驗三個承重引用（spec 01「不做 AI auto diagnosis」、UI 規格 fmea_chain required、懸空引用檔不存在）
sources:
  - web/src/components/problem-cards/{FmeaDiagnosisCard,ResolutionTimeline}.tsx（寫死假元件，本次改誠實空狀態）
  - docs/ui/web_design_spec_prompt_pipeline/pages/04_admin_problem_cards.md（UI 規格 required）
  - docs/_source/01-workorder-erp.md L421（M20 AI Ops：不做 AI auto diagnosis）
  - docs/architecture/adr/ADR-0010-belief-augmented-react.md（superseded by ADR-0107，引擎已刪）
  - 20260617資料/01-workorder-erp-final-spec-20260520.xlsx（M01–M20 模組地圖正典）
  - 20260617資料/02-phased-test-plan-...xlsx（TI-RES-01 / TI-M03-02）
---

> ⚠️ 本文件為 `_audit` 稽核軌跡：回答業主 2026-06-25「診斷引擎模組有文件提及嗎」之溯源結果，並登記一處 **Source-of-Truth 衝突**（§4）待裁決。問題卡頁前端假元件已於同日改誠實空狀態（branch `fix/pc-diagnosis-honest-empty`）。

# 「診斷引擎 / FMEA 分層信心診斷」文件溯源

## 1. 緣起

問題卡詳情頁 `/problem-cards/[id]` 有兩個元件顯示「AI 分層信心診斷」：
- **FMEA 診斷推理鏈**（`FmeaDiagnosisCard`）：Symptom→Failure→Failure Mode→Defect 四層
- **解決嘗試歷程**（`ResolutionTimeline`）：L1 45% → L2 78% → L3 92% 信心升級

業主察覺兩者皆寫死（每張卡顯示同一條「離合器」假診斷 + 假信心分數），且後端無真資料（`problem_cards.attempts=[]`、`confidence_score` 硬寫 `None`）。頁面免責橫幅自承「待診斷引擎模組接入」。遂溯源：這個「診斷引擎」在文件裡到底有沒有、是什麼。

## 2. 直答

**有提及，但沒有任何一份「現行（active）正式規格」把它定義成診斷引擎本體。** 它分裂成四種性質，且關鍵真相是：**「L1/L2/L3 信心診斷」正是 2026-06-04 lockcore 重寫時被刪掉的 Belief-Augmented ReAct / Turn Cycle —— 後端引擎刪了，前端示意元件沒拆。**

它**從未被列為任何 M0x 待建模組**：M01–M20 正典模組地圖（xlsx + 會議記錄 + PDF 皆查無），最接近的是 M03 AI 分診（48%）；而 spec 01 M20 反向明令「不做 AI auto diagnosis」。

## 3. 證據表（依 spec > plan > deleted > passing 排序）

| 來源檔 | ref | 原文節錄 | kind |
|---|---|---|---|
| docs/ui/.../pages/04_admin_problem_cards.md | L146-154, 255, 283 | `timeline_node ... required ... L1/L2/L3 ... 信心分數 ConfidenceBadge`；`fmea_chain: FlowDiagram / required / 四層 Symptom→Failure→Failure Mode→Defect`；GET 含 `resolution_attempts, fmea_chain`（**親驗，無 superseded frontmatter＝仍 active**）| **spec** |
| docs/ui/.../assembly/06_admin_problem_cards_integrated.md | L174-191, 304 | 展示 FMEA 診斷鏈與解決嘗試歷程；empty:「尚未產生 FMEA 推理鏈」 | **spec** |
| docs/ui/.../pages/15_admin_customers_and_diagnostics.md | L393-415, 824 | `state_machine_trace` 對齊 `diagnostic-state-machine-spec` 10 狀態；`hypothesized_fms`+confidence；「第 {n}/3 輪」 | **spec**（懸空引用）|
| docs/architecture/api/openapi.yaml | L5842 | `resolution_layer` enum `[case_library, rag, human]`（L1/L2/L3）| **spec** |
| docs/_audit/CR-0004-track-b-build-with-cia-grounded.md | L43, 139-142 | `saas.problem_card ADD COLUMN resolution_layer CHECK(L1/L2/L3) NULLABLE`（HD-2）| **spec** |
| 20260617資料/02-phased-test-plan.xlsx | sheet3 / TI-RES-01 | 解決方案引擎建議 v2（L1 FAQ / L2 RAG / L3 escalation）；純 DB 不打 LLM；不出 final quote | **spec** |
| 20260617資料/02-phased-test-plan.xlsx | sheet3 / TI-M03-02 | ProblemCard 狀態機 incomplete→confirmed→resolved；`resolve_layer` 限 L1/L2/L3 | **spec** |
| 20260617資料/02-phased-test-plan.xlsx | sheet3 / TI-RES-01 末欄 | `resolution_layer` 持久化 HD-2 follow-up **未測** | **plan** |
| docs/_source/01-workorder-erp.md | L421 | M20 AI Ops：`AI forbidden decisions ... 不做 AI auto diagnosis`（**親驗**）| **plan**（反向禁止）|
| docs/_archive/prd/SOW-0001-2026-q1.md | L77 | 診斷推理引擎 (task_decompose)：Tier 2 FMEA 四層因果鏈 | **deleted** |
| docs/architecture/ARCH-0001-architecture-overview.md | L406-407, 801 | 故障樹 `agent/config/fault_trees/`；`task_decompose` | **deleted** |
| docs/architecture/adr/ADR-0010-belief-augmented-react.md | frontmatter + L21 | superseded：刪除 belief\*.py / calibrate.py / hypothesize.py / turn_cycle.py 全部（→ ADR-0107）| **deleted** |
| docs/architecture/adr/ADR-0006-llm-model-selection.md | L150 | 由 harness「L1 diagnostic engine」prompt 補償 | **deleted** |
| CLAUDE.md | L25, 38 | Belief-Augmented ReAct (Turn Cycle) 已刪；ADR-0010 superseded | **deleted** |
| web/src/components/problem-cards/FmeaDiagnosisCard.tsx | （改前）L11-53 | `nodes` 寫死「離合器」四層；無 props | **passing**（假元件，本次已改）|
| web/src/components/problem-cards/ResolutionTimeline.tsx | （改前）L13-41 | `steps` 寫死 L1 45%/L2 78%/L3 92%；無 props | **passing**（假元件，本次已改）|
| api/services/problem_card_service.py | L101, L256-283 | `confidence_score` 硬寫 None；`resolve_card` 僅單一 enum 人工填，無引擎/無分層信心/無 attempts | **passing** |
| docs/_audit/module-completion-audit-M01-M20-20260624.md | L60-79 | M01–M20 模組地圖**無「診斷引擎」獨立模組**（最近 M03 48%）| **passing** |
| `diagnostic-state-machine-spec`（被 page 15 引用）| — | `find docs -iname "*diagnostic-state-machine*"` **零命中**：被引用的規格檔不存在 | **缺檔/deleted** |
| 20260617資料/01-...spec.xlsx ＋ 會議記錄.md ＋ 整合分析報告.pdf | 全文 | 模組地圖、會議、PDF 皆**無**「診斷引擎/FMEA 信心診斷」；「分層」7 處皆為退款金額分層 | **none** |

## 4. 🛑 Source-of-Truth 衝突（待業主裁決）

三方互相矛盾：

| 來源 | 立場 |
|---|---|
| **UI 設計稿** `04/06_admin_problem_cards`（tier-2，無 superseded） | `fmea_chain` / `resolution_attempts` / L1-L3 信心 列為 **required** |
| **spec 01** `01-workorder-erp` M20 AI Ops（正典模組地圖） | **不做 AI auto diagnosis** |
| **引擎本體** | 屬已刪的 Belief-Augmented ReAct（ADR-0010 superseded by ADR-0107），新 lockcore 架構從未重建 |
| **前端** | 寫死假 L1/L2/L3 信心在演 |

依 `change-governance` 規則，此衝突須由業主裁決何者為正典，AI 不腦補。

## 5. 「L1/L2/L3」是兩個不同的東西（勿混淆）

1. **`resolution_layer`（仍活著）** = 解決**管道**分層：L1 case_library / L2 rag / L3 human。CR-0004 / TI-RES-01 / openapi 合約欄位，與「信心分數」無關，僅結案時人工填單一 enum；持久化 HD-2 **未測**。
2. **FMEA 分層信心診斷 + `hypothesized_fms` + confidence + n/3 輪 + 10 狀態機（已刪）** = 真正的「信心診斷引擎」，＝已刪的 Belief-Augmented ReAct 衍生物。
3. **前端混合錯誤**：`ResolutionTimeline` 把（1）的管道標籤硬接（2）的 confidence 百分比，拼成「分層信心診斷」的視覺幻象。

## 6. 處置

- **A（已做，本文件同分支）**：`FmeaDiagnosisCard` / `ResolutionTimeline` 兩個寫死元件改**誠實空狀態**（「尚未產生 FMEA 診斷鏈／尚無解決嘗試紀錄（診斷引擎未啟用）」），移除離合器假診斷與 45/78/92 假信心；頁面免責橫幅更正（關聯對話與工單為即時資料，非示意）。
- **B（待業主裁決）**：UI 規格（required）vs spec 01（不做 AI 診斷）的正典衝突 —— 標 UI 規格 superseded，或開 CR 正式立「信心診斷」為新模組。
- **C（高成本，非補完）**：真要做信心診斷引擎＝推翻 spec 01 紅線 + 走 lockcore 重建（不復活已刪 belief/turn_cycle），屬架構重審、跨 sprint。

> 另：`resolution_layer` 三層管道（真實、部分落地）持久化是 HD-2 未測 follow-up，與本案的「信心診斷引擎」是不同議題，可獨立補測。
