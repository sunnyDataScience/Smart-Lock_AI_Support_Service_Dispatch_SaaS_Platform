---
title: "ADR-013: Flow-as-Blocks 宣告式 DSL + 配置驅動引擎（DSL-first）"
version: 1.0
status: active
owner: 平台架構團隊
last-updated: 2026-07-07
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P010_Flow-as-Blocks_宣告式DSL_DSL-first.md
---

# ADR-013: Flow-as-Blocks 宣告式 DSL + 配置驅動引擎（DSL-first）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 平台級 |
| 關聯 ADR | [ADR-001](./ADR-001_平台核心與領域配置分層.md) · [ADR-014](./ADR-014_AI_Onboarding_Compiler_Block_Ontology.md) · [ADR-015](./ADR-015_工單狀態機核心不變式.md) |

## Context（背景與問題）

各產業工單 / 金流流程不同；平台目標是「積木化、前端拖拉串工作流」快速建置（對標 ServiceTitan、agent builder 類產品，但針對藍領）。需要一種**既能組裝、又能執行、又能被 AI 生成**的流程表達，讓流程成為配置產物而非 code。

## Decision（決策）

自建宣告式 **Flow-as-Blocks** 模型：

1. **Flow DSL（宣告式狀態機）**：`states / transitions / guards / actions / SLA`，作為工單生命週期 + 金流步驟的**資料**。
2. **通用工單引擎**把 DSL 當資料解釋執行——核心不認識產業，行為隨 DSL 變（TRIZ 條件分離）。
3. **積木 = 有契約的型別節點**（input / output / precondition / effect / guard）。**雙層顆粒度**：對外（拖拉 / AI 編譯）暴露**粗顆粒 domain block**（派工 / 技師媒合 / 到府同意 / 報價核准 / 金流收款 / 對帳結算 / 通知 / escalation）；其內部由**細顆粒 primitives**（發通知 / 查技師 / 狀態轉移 / 寫欄位 / 外呼）組成。
4. **逃生艙**：緊耦合走 **plugin SDK**（型別安全 + 審查 + 進 Block Ontology 版本化）、鬆耦合走 **webhook 外呼**；**拒絕 inline code 節點**（任意執行的安全風險 + AI 難靜態驗證）。
5. **拖拉 UI = 薄編輯器**，產出 / 編修 DSL，不含執行邏輯。
6. **DSL 四約束**（皆為第一約束）：**AI 可生成 · 人可編輯 · 引擎可執行 · 可驗證**（匯入檢查積木契約 + 商業不變式）。
7. **執行後端**：flow DSL 自建 + executor 初期自建，**保留 Temporal 為可替換後端**（DSL 與 executor 解耦，未來長流程 / 複雜補償再換後端、DSL 不動）。

### DSL-first（實作鐵律）

- **Phase 1**：工單引擎先配置驅動（DSL 解釋的狀態機）——FDE 先手寫 / 改 DSL。**槓桿在引擎，不在 UI。**
- **Phase 2**：於穩定 DSL 上疊拖拉編輯器 + 積木庫 + 範本。
- ⚠️ 反面教材：先做華麗拖拉 UI、引擎沒抽象化 → UI 產出引擎跑不動。

## Alternatives（考量的選項）

- **A：流程寫死在 code** — 每產業改碼，違反配置化（[ADR-001](./ADR-001_平台核心與領域配置分層.md)）。
- **B：採現成引擎（Temporal / BPMN / Camunda）** — 成熟，但語義通用、藍領貼合度與掌控度較低。
- **C：自建宣告式 flow DSL + 通用引擎解釋執行（採用）** — 掌控度高、藍領原生；代價是需自行設計 DSL 與執行器。

## Consequences（後果）

**正面**：流程 = 配置產物，改流程不改碼；同一引擎支撐所有產業；為 AI 編譯（[ADR-014](./ADR-014_AI_Onboarding_Compiler_Block_Ontology.md)）與拖拉 UI 奠基。
**風險**：DSL 是**皇冠寶石**——設計壞了整條鏈歪；積木契約需嚴謹（AI 組出的流程才安全）；最終一致性語義需前端 / 流程配合。
**影響範圍**：工單引擎、金流 flow、UI 積木；DSL / 積木契約細部設計見 [15_SDS](../15_SDS.md)。locksmith 首個 flow 定義（工單 6 階段 + 金流）作為引擎驗證實例（[ADR-015](./ADR-015_工單狀態機核心不變式.md)）。
**重評觸發**：自建 executor 維運成本過高 → 底層改採 Temporal 執行、DSL 作為其上的藍領語義層（可替換後端顆粒度為開放項，於 SDS 持續評估）。

## Status 附註

- 分期：Phase 1（DSL schema + 積木契約 + 執行引擎 + locksmith 首個 flow 手寫驗證）→ Phase 2（積木庫 v0 + 逃生艙節點 + 拖拉編輯器）。🔜 兩 Phase 均規劃中。
- 碰金流 / 派工的 flow 匯入必過 HITL（[ADR-014](./ADR-014_AI_Onboarding_Compiler_Block_Ontology.md)）。
