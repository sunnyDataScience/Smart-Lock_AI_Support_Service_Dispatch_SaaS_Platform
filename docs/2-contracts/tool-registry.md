---
id: TR-0001
title: Agent Tool / MCP Registry
tier: 2
status: accepted
last-synced-with: dccfc0019fa897a3e5b37c4ae1130e6240190d6b
sync-source: code
synced-at: 2026-05-16
source:
  - "docs/_archive/blueprints/AI鎖匠聊天機器人系統開發藍圖_v2.xlsx#sheet-13"
source-paths:
  - agent/skills/tools.py
  - agent/agent.py
related:
  - "../1-decisions/ADR-0008-product-info-architecture-canonical.md"
  - "../1-decisions/ADR-0028-ai-employee-charter.md"
  - "./events/EVT-0001-domain-event-catalog.md"
  - "./modules/INDEX.md"
---

# Agent Tool / MCP Registry

> 每個工具 = 一張申請單。MCP-style 契約：`name / description / input_schema / output_schema / auth / risk class / audit`。**新工具上線前必須在此表登記**，且通過 [ADR-0028](../1-decisions/ADR-0028-ai-employee-charter.md) 的 Forbidden 清單檢查。

## 1. Registry

| Tool ID | 用途 | Input Schema（簡）| Output Schema（簡）| Auth / Tenant | Risk Class | HITL? | Audit Event | 目前狀態 |
|---|---|---|---|---|---|---|---|---|
| `load_product_info` | 依品牌／型號載入 mega-doc | `{brand, model, problem_hint}` | `{name, content, version}` | tenant + RBAC: agent | L1 低（純讀）| 否 | `skill.loaded(name, version)` | **Production** |
| `update_user_info` | 回寫 `user_facts`（電話／地址／品牌）| `{user_id, facts:{...}}` | `{ok, facts_version}` | tenant + RBAC: agent | L1（PII 寫入）| 否 | `facts.updated(user_id, fields, version)` | **Production** |
| `transfer_to_human` | 轉真人客服 | `{reason, summary, contact, urgency}` | `{handoff_id}` | tenant | L1 | 否（本身就是 HITL 觸發）| `handoff.created(...)` | **Production** |
| `create_problem_card` | 建 ProblemCard | `{conv_id, brand, model, symptom, urgency, media, idempotency_key}` | `{pc_id, status}` | tenant; Outbox | L2 中（寫業務物件）| 建議 V1 草擬 + 人審 | `pc.create_requested` + `pc.created` | **Beta**（背景 fail-soft → 升級 Outbox）|
| `convert_to_work_order` | PC → WO 轉換 | `{pc_id, address_override?, idempotency_key}` | `{wo_id, status}` | tenant; admin api token | L3 高（現場派工）| **Yes V1 必須人審** | `wo.create_requested` + `wo.created` | **禁止 AI 自動呼叫 V1**（per ADR-0028）|
| `query_wo_status` | 查詢工單狀態（擬議）| `{wo_id or user_id}` | `{wo_list}` | tenant + 限 owner / 客服 | L1 | 否 | `wo.read(wo_id)` | P1 規劃 |
| `search_knowledge` | 全文 / 向量檢索（擬議）| `{query, brand?, top_k}` | `{chunks:[{source, score, text}]}` | tenant; citation required | L1 | 否 | `rag.search(query, hits)` | P1 規劃 |
| MCP Server（對外擬議）| 未來開放 partner 整合 | MCP 1.0 spec | MCP 1.0 spec | OAuth + tenant scoping | 依 tool | 依 tool | `mcp.*` events | P2（TR11）|

## 2. Risk Class 定義

| Class | 意義 | 預設限制 |
|---|---|---|
| L1 | 純讀 / 內部寫入（facts、handoff）| AI 可自動執行，需 audit |
| L2 | 寫業務物件（PC 建立）| 必過 idempotency；V1 fail-soft，V2 進 Outbox |
| L3 | 派工 / 現場 / 金錢相關 | **永遠 HITL**；AI 不得自動呼叫，commit 不得改此條而不開 ADR |

## 3. 上線檢查清單（新工具）

1. **登記**：在本表加 row。
2. **Schema lock**：input/output 用 Pydantic / TypedDict 定義；變更 = breaking。
3. **Audit event**：在 [`EVT-0001`](./events/EVT-0001-domain-event-catalog.md) 新增對應事件。
4. **Forbidden 檢查**：對照 [`ADR-0028`](../1-decisions/ADR-0028-ai-employee-charter.md) Forbidden 清單；衝突直接拒。
5. **HITL gating**：L2 / L3 必須在 `safety_gate` 或 `output_validator` 設攔截規則。
6. **Tenant 隔離測試**：跨租戶呼叫必須 404。

## 4. Open items

- `create_problem_card` 從 Beta 升 Production：等 Outbox pattern 落地（待 SRE 拍板，2026 Q3）。
- `convert_to_work_order` 部分自動化：限保固外 / 地址完整 / 緊急類型，V2 評估中（ADR-0028 D01 決議前禁止）。
- MCP Server 對外開放：等 partner 通道與 OAuth 安全審查（TR11）。

## 5. See also

- 原始藍圖：sheet「13 Tool / MCP Registry」
- [`ADR-0028`](../1-decisions/ADR-0028-ai-employee-charter.md) — Tool Permissions 與 Forbidden 清單的上層權威
- 程式碼：`agent/skills/tools.py`（注意：CLAUDE.md 提到的 `agent/agent_tools/tools.py` 是 ADR-0008 cutover 後的目標路徑，但本 branch 實際仍在 `agent/skills/tools.py`；遷移尚未執行，見 `DISC-0001` §6 後續）
