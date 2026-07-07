---
title: "ADR-012: Agent Configuration Studio（品牌自服務調校診斷系統）"
version: 1.0
status: active
owner: 平台架構團隊
last-updated: 2026-07-07
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P013_Agent_Configuration_Studio_品牌自服務.md
---

# ADR-012: Agent Configuration Studio（品牌自服務調校診斷系統）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 平台級 |
| 關聯 ADR | [ADR-001](./ADR-001_平台核心與領域配置分層.md) · [ADR-010](./ADR-010_知識分層_Skill行為驅動_RAG-via-MCP.md) · [ADR-009](./ADR-009_Model_Orchestration_Layer.md) · [ADR-005](./ADR-005_四方RBAC模型與enforce.md) · [ADR-018](./ADR-018_知識精煉獨立服務.md) |

## Context（背景與問題）

診斷系統的三類配置——skill、RAG 知識庫權限、system prompt——若只有 FDE 能調，品牌無法自主迭代客服品質、FDE 成為瓶頸。開放品牌前端自服務則帶來核心張力：**自服務賦權 vs 安全/品質**——品牌改 prompt / skill 可能移除 escalation / domain-safety 或注入問題指令，直接影響真實客戶對話。

## Decision（決策）

建 **Agent Configuration Studio**（品牌 dispatch web 的自服務調校介面）+ 集中 **Agent Config Registry** + 治理：

### Skill Registry
- 集中可匯入 skill 庫（Agent Skills 標準 SKILL.md，版本化）+ per-brand 啟用集。
- 品牌前端：從庫匯入 skill、編輯其**客製層**；tenant-scoped。受保護的 `locksmith-cs-sop`（domain-safety）品牌不可破壞。

### RAG 知識庫權限管理
- **RAG Source Registry**：可檢索語料 / DB 目錄（品牌自有 `manual_chunks` / `case_entries`、共享產業語料）。
- 品牌前端設定該 agent 可檢索哪些語料（開/關、優先序）。
- **強制點**：權限於 **MCP-RAG 查詢時 enforce**——`WHERE tenant_id` + 語料 ACL；**跨租戶隔離平台鎖死、品牌不可 override**，品牌只在自身允許範圍內開關。

### 系統提示詞管理
- per-brand system prompt 版本化（屬 Model Orchestration 編排配方，[ADR-009](./ADR-009_Model_Orchestration_Layer.md)）。
- 品牌前端編輯客製層；版本化 + 回滾 + OPIK eval（改動前後比對，[ADR-007](./ADR-007_可觀測性分層_SigNoz_OPIK.md)）。

### 安全護欄（受保護層 + 客製層兩層合成）

| 層 | 內容 | 誰可動 |
|---|---|---|
| **受保護層（平台鎖死）** | escalation 規則、domain-safety（不編造 / 轉真人）、合規語氣、租戶 / 資料邊界 | 品牌**不可移除 / override** |
| **客製層** | 品牌語氣、產品重點、FAQ、開場白 | 品牌可編輯 |

- 合成順序保證受保護層恆生效（與 RAG 弱檢索由 cs-sop domain-safety 兜底同一原則）。
- **高風險改動**（接近受保護邊界）→ 選配 **HITL 審核**（複用 refinery 審核骨架，[ADR-018](./ADR-018_知識精煉獨立服務.md)）。

### 治理
- **RBAC**：可編輯者 = Casdoor 租戶 Admin（[ADR-005](./ADR-005_四方RBAC模型與enforce.md)）。
- **版本化 + 回滾 + 稽核**：所有配置變更留版本與 audit。
- **eval gate**：prompt / skill 改動經 OPIK eval，回歸不過可擋 / 告警。

## Alternatives（考量的選項）

- **A：FDE 專屬（不開放）** — 安全，但品牌無法自主迭代、FDE 成瓶頸。
- **B：全開放前端編輯（無護欄）** — 賦權最大，但安全 / 品質失控。
- **C：Studio + 分層保護 + 版本化 + RBAC + 選配 HITL（採用）** — 自服務但受治理。

## Consequences（後果）

**正面**：品牌自主快速迭代客服；skill / 知識 / prompt 成 first-class 可管理資產；與 registry / 版本化 / HITL 既有模式自洽。
**風險**：自服務擴大攻擊面與品質風險 → 分層保護 + eval gate + 版本回滾 + audit + 選配 HITL 緩解；prompt injection 經配置 → 輸入驗證 + 受保護層前置。
**影響範圍**：新增 Agent Config Registry（集中）+ Studio UI（品牌 dispatch web）+ agent runtime 載入 per-brand 配置；MCP-RAG 加語料 ACL。
**重評觸發**：品牌濫用 / 事故頻發 → 收緊為「改動一律 HITL」；skill 生態成熟 → 開放跨品牌 skill 市集。

## Status 附註

- 🔜 規劃中：Registry → 兩層合成機制（agent runtime）→ 語料 ACL → Studio UI → RBAC + audit + eval gate，依序落地。
