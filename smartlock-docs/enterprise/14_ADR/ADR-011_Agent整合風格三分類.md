---
title: "ADR-011: Agent 整合風格三分類（MCP / HTTP-internal / 不暴露）"
version: 1.0
status: active
owner: agent 系統 tech lead
last-updated: 2026-07-07
upstream:
  - smartlock-docs/agent/P2/04_adr/ADR-005_agent整合風格分類_MCP_vs_HTTP_vs_不暴露.md
---

# ADR-011: Agent 整合風格三分類（MCP / HTTP-internal / 不暴露）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 系統級（agent）|
| 關聯 ADR | [ADR-010](./ADR-010_知識分層_Skill行為驅動_RAG-via-MCP.md) · [ADR-025](./ADR-025_AI話術邊界與永不自轉工單憲章.md) · [ADR-015](./ADR-015_工單狀態機核心不變式.md) |

## Context（背景與問題）

agent 調用後台功能模組 / 外部能力時，若無統一裁決依據，會出現兩種設計錯誤：

- **誤把 MCP 當所有模組互動的標準答案**——把確定性的服務間接線（不含 LLM 決策）也包成 MCP，平白多一層 server、多一次 LLM round-trip，還可能繞過安全白名單。
- **誤把後台寫入端點暴露給 LLM**——違反「AI 永不自轉工單」安全紅線（[ADR-025](./ADR-025_AI話術邊界與永不自轉工單憲章.md)）。

需要一條第一性原則，讓「這個功能該不該給 agent、走 MCP 還是 HTTP」變成機械式判斷。

## Decision（決策）

判斷任一互動屬哪一類，只問：**「呼叫的決定是 LLM 在對話中即時做的，還是程式流程確定要做的，還是根本不該讓 LLM 碰的？」**

| 類別 | 定義 | 誰決定呼叫 | 介面 | 為什麼 |
|---|---|---|---|---|
| **1 — LLM 面向能力** | agent 在對話中「自己發現並決定」要用的能力 | **LLM** | **MCP**（經 `lockcore/agent/tools/mcp.py` 包成 `mcp_<server>_<tool>`）| LLM 要可發現 + 可攜（DB / vendor 耦合封在 server 後）；MCP 工具在 allowlist 剝離之後註冊，不動 `CS_TOOL_ALLOWLIST` 的 6 工具紅線 |
| **2 — 確定性接線** | 通道 / 控制流「確定要做」的服務間整合 | **程式**（if / turn 生命週期）| **直接 HTTP** `/internal/*`（`X-Internal-Token`，fail-closed）| 沒有 LLM 推理；一個 `if(postback 前綴)` 就決定了，包 MCP 純多餘且危險 |
| **3 — 安全紅線後台** | 有副作用、不該由 LLM 觸發的後台寫入 | **人類**（客服 / 營運）| **不暴露給 agent**，留在 api 後面 | 「AI 永不自轉工單」；白名單刻意只有唯讀 / 轉接工具 |

### 一句話判斷規則

> **LLM 要「自己決定何時呼叫」的能力 → MCP。程式流程「確定要做」的整合 → 直接 HTTP `/internal/*`。後台寫入類（建工單 / 派工 / 結算）→ 根本不給 LLM。**

### 三類釘在系統上的實例

1. **類別 1**：RAG 檢索 `search_product_manual` / `search_similar_cases`（[ADR-010](./ADR-010_知識分層_Skill行為驅動_RAG-via-MCP.md)）。
2. **類別 2**：LINE webhook 橋接——**agent `POST /callback` 為 LINE 唯一入站門**（LINE 單 channel 單 webhook URL 的物理約束）；postback 按前綴 deterministic fan-out：`q:*`（報價同意/拒絕）→ agent 本地處理 + 旁路 `POST /internal/quotes/{id}:customer-respond`；`r:*`（改約）/ `s:*`（範圍變更）/ binding → 旁路呼 api 對應 `/internal/*` 端點。旁路 fail-soft：bridge 失敗只 log 不阻斷客人。
3. **類別 3**：工單建立 / 轉換、派工、對帳、結算完全不進 agent 工具面；agent 最多經類別 2 送出「AI 草擬問題卡」，confirm / convert 一律走客服認證端點（[ADR-015](./ADR-015_工單狀態機核心不變式.md)）。

### 為何不「全部走 MCP」

延遲不是主因（本地 MCP 傳輸為次毫秒級）。真正成本：工具 schema 佔 context token（對類別 2 純浪費）；多一次 LLM round-trip（對本來 0 次 LLM 參與的接線是災難）；MCP 註冊繞過工具白名單（對唯讀檢索是優點，對寫入類是**危險**）；多一個要部署保活的 server。

## Alternatives（考量的選項）

- **A：一切能力皆 MCP** — 統一介面表象下，確定性接線多餘化、寫入面繞過白名單。
- **B：一切皆 HTTP 工具** — LLM 面向能力喪失可發現性與可攜性。
- **C：依「誰決定呼叫」三分類（採用）** — 裁決機械化，安全邊界明文。

## Consequences（後果）

**正面**：日後「這功能要不要給 agent / 要不要走 MCP」有固定依據；類別 3 明文禁止暴露，防止漸進式紅線侵蝕。
**風險**：灰色地帶（既像檢索又有副作用）→ 以「是否 LLM 即時決定 + 是否有寫入副作用」兩軸切，有副作用一律降到類別 3 由人類把關；類別 2 使 agent 成為部分流程單點入口 → fail-soft 緩解。
**影響範圍**：agent `line_gateway` postback fan-out、api `/internal/*` 端點面、工具白名單治理。
**重評觸發**：出現「LLM 需即時決定、但有寫入副作用」的需求 → 開新 ADR 補該情境裁決（如人類確認閘 + LLM 建議的 two-phase）；MCP 維運成本過高 → 類別 1 介面退化為 in-process tool（三分法仍成立）。

## Status 附註

- 🔜 規劃中：改約 / 範圍變更 / binding 的 `/internal/*` 端點補齊（延用 quote 旁路先例）。
