---
title: "ADR-009: Model Orchestration Layer（供應商無關，LiteLLM 實作）"
version: 1.0
status: active
owner: 平台架構團隊
last-updated: 2026-07-10
upstream:
  - smartlock-docs/00_platform/P2/04_adr/ADR-P008_Model_Orchestration_Layer_供應商無關.md
  - smartlock-docs/agent/P2/04_adr/ADR-002_LiteLLM_統一供應商.md
---

# ADR-009: Model Orchestration Layer（供應商無關，LiteLLM 實作）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 平台級 |
| 關聯 ADR | [ADR-001](./ADR-001_平台核心與領域配置分層.md) · [ADR-008](./ADR-008_Agent核心採LockCore.md) · [ADR-010](./ADR-010_知識分層_Skill行為驅動_RAG-via-MCP.md) · [ADR-007](./ADR-007_可觀測性分層_SigNoz_OPIK.md) |

## Context（背景與問題）

跨產業重用是平台真需求：模型調用若綁單一供應商 SDK，換家即改碼；各產業診斷系統又需要不同的編排配方（prompt / 檢索 / tool 序列 / fallback / eval）。客服場景還有成本 / 延遲導向的切換需求：生產走 Vertex AI（GCP 部署、grounding、企業 SLA）、離線開發走本機 Ollama、品質比較走 Claude / GPT。

## Decision（決策）

模型調用抬升為**平台能力層 Model Orchestration Layer**（供應商中立、FDE per-industry 可調的配置面之一，[ADR-001](./ADR-001_平台核心與領域配置分層.md)）：

1. **供應商 = 配置**：model 字串 + credential；code 不依賴任何家 SDK（鐵律：不把 anthropic / google-genai SDK import 回 agent code）。
2. **編排配方 = 配置**：prompt / skill 行為 / RAG 檢索 / tool 序列 / fallback / eval，皆 per-industry / per-brand 可調。
3. **調用效率在本層**：批次、快取、串流、平行工具呼叫、逾時 / 重試——供應商中立地最佳化。
4. **多供應商 failover**：`FallbackProvider` 承接主模型故障走備援（🔜 規劃中，`build_provider` 接線）。
5. **eval 掛 OPIK**（[ADR-007](./ADR-007_可觀測性分層_SigNoz_OPIK.md)，dev 必開 / prod 可關）。

**實作 = LiteLLM 單一 adapter（`lockcore/providers/litellm_provider.py`）**：

- **model 字串前綴路由**：`vertex_ai/` / `gemini/` / `ollama_chat/` / `claude-*` / `gpt-4o` / `bedrock/*` / `azure/*` / `openrouter/*`；切換供應商只改 `agent/config.toml` 的 model 字串。
- 生產預設 `vertex_ai/gemini-3.1-flash-lite`（temperature 0.7 / max_tokens 4096）。
- **Vertex 特化**（`app_config.build_provider`）：`GOOGLE_APPLICATION_CREDENTIALS` ADC、`extra_body["vertex_project"]` + `VERTEX_PROJECT_ID`、`vertex_location`（`gemini-3.x → global`，其餘 `us-central1`；deploy 注入 `VERTEX_LOCATION=asia-northeast1`）。
- **錯誤 sentinel**：`chat` 失敗不 raise，回 `LLMResponse(content="[litellm error] …", finish_reason="error")`；LINE 層攔截轉友善話術，技術錯誤不外洩給客人。
- 記憶抽取器 `LLMExtractor` 共用同一 provider。

## Alternatives（考量的選項）

- **A：LiteLLM 留在 agent 內部細節** — 已解 SDK 耦合，但編排配方、調用效率、eval 分散，非平台一等公民。
- **B：抬升為平台 Model Orchestration Layer（採用）** — 供應商 = 配置、配方 = 配置，集中治理。
- **C：綁定單一供應商 SDK / 各家各寫 adapter** — 貼合但鎖死；多家 adapter（~3.7k 行）維護成本高且格式漂移。

## Consequences（後果）

**正面**：換供應商零改碼；診斷系統 model 編排成為可配置產物；統一錯誤語義（sentinel 單一防線）；維護面收斂為 1 份 adapter。
**風險**：抽象層可能遮蔽特定供應商獨門功能 → 保留「原生逃生艙」（進階功能經配置直通）；litellm 版本升級風險；新呼叫端若忘判讀 sentinel 可能外洩技術錯誤。
**影響範圍**：agent runtime、knowledge-refinery、MCP-RAG（embedding）皆走本層；`agent/pyproject.toml` 依賴 `litellm>=1.70`，Vertex 走 `.[vertex]` extra。
**重評觸發**：某供應商獨門能力成關鍵競爭力且無法抽象 → 局部深綁 + 隔離；litellm 出現無法繞過的 breaking change。

## Status 附註

- 🔜 規劃中：`FallbackProvider` 接線（多供應商 failover）、調用效率能力（快取/批次/平行工具）收斂至本層、per-industry 編排配方納入 Vertical Pack。
- 2026-07-10：`FallbackProvider` 類別已存在（`lockcore/providers/fallback_provider.py`）唯 `build_provider` 未接線——接線排程待業主。
