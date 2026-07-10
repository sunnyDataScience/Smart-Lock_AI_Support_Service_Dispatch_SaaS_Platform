---
title: "ADR-010: 知識分層 — Agent Skills 行為驅動 + RAG-via-MCP 檢索（從屬非收斂）"
version: 1.0
status: active
owner: agent 系統 tech lead
last-updated: 2026-07-10
upstream:
  - smartlock-docs/agent/P2/04_adr/ADR-004_RAG-via-MCP檢索能力與Skill行為驅動分工.md
  - smartlock-docs/agent/P2/04_adr/ADR-003_Agent_Skills_標準與_filesystem_references.md
---

# ADR-010: 知識分層 — Agent Skills 行為驅動 + RAG-via-MCP 檢索（從屬非收斂）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 系統級（agent）|
| 關聯 ADR | [ADR-008](./ADR-008_Agent核心採LockCore.md) · [ADR-011](./ADR-011_Agent整合風格三分類.md) · [ADR-018](./ADR-018_知識精煉獨立服務.md) · [ADR-019](./ADR-019_Medallion分層數據架構.md) · [ADR-012](./ADR-012_Agent_Configuration_Studio.md) |

## Context（背景與問題）

agent 的知識有兩種本質不同的東西，混在一起就會既不可攜也不可治理：

- **行為規範**：agent「該怎麼想、依什麼紅線、在什麼時機去查什麼」——策略層，須隨版本控管、跨框架可攜。
- **事實語料**：海量、動態、獨立更新的逐型號手冊事實與案例史——被查找的資料，需要語義檢索。

分工的第一性原則：**Skill 是駕駛，RAG 是它按規範呼叫的工具之一**——兩者是從屬關係，不是需要收斂的兩套競品知識系統。

## Decision（決策）

### 分工定義

> **Skill 承載「策略 + 少量必備、須隨行為版本控管的精選知識」；RAG 承載「海量、動態、獨立更新的完整事實語料」，由 Skill 在對的時機透過 MCP 呼叫。**

| 面向 | **Skill（行為驅動）** | **RAG via MCP（檢索能力）** |
|---|---|---|
| 角色 | HOW 怎麼行為 + WHEN/WHERE 何時查哪 | WHAT 語料裡寫什麼（隨查隨取）|
| 內容 | `locksmith-cs-sop` 全部；`locksmith-product-knowledge` 的 SKILL.md + `_common` + `_brand` + domain-safety + 檢索程序 | 逐型號完整手冊事實（`manual_chunks`）+ 案例史（`case_entries`）|
| 進入 context | 漸進式揭露（摘要 → 需要時讀全文）| runtime 工具呼叫（MCP）|
| 檢索方式 | 不需要（它就是 context）| 語義 768 維 HNSW cosine（text-embedding-004）|
| 可攜性 | 高（純核心 frontmatter）| agent 端可攜——DB 耦合封在 MCP server 後 |
| 真相源角色 | 行為 + 精選事實 | **完整事實（唯一語料）** |

### Skill 層（Agent Skills 標準）

- **兩個 builtin skill**（`lockcore/skills/`）：`locksmith-product-knowledge`（事實精選層，references `{Brand}/{Model}.md` + `_brand.md` + `_common/*.md`，6 品牌）與 `locksmith-cs-sop`（行為層：每輪意圖分類 + 紅線決策樹 + 單一進線鐵律）。
- **純核心 frontmatter**（name / description / version / metadata），不綁框架欄位 → 複製到 Claude Code / Cursor / nanobot 直接可用。
- **漸進式揭露 + profile-gating**：依 brand + model 只載最小 references 集，省 token。

### RAG 層（MCP server，暴露兩工具）

- `search_product_manual(brand, model, query)` → embed(query) → `ORDER BY embedding <=> %(qvec)s::vector LIMIT k` on `manual_chunks`（tenant / brand / model 過濾）。
- `search_similar_cases(symptom, brand?, model?)` → 同法查 `case_entries`（相似度 ≥ 0.85、`is_active` / `deleted_at IS NULL`）。
- cosine query 的 `WHERE` **必帶 `tenant_id`** + 語料 ACL（[ADR-012](./ADR-012_Agent_Configuration_Studio.md)），default deny。
- MCP 工具註冊在 `CS_TOOL_ALLOWLIST` 剝離之後（`mcp_<server>_<tool>`），不動 6 工具白名單紅線（[ADR-011](./ADR-011_Agent整合風格三分類.md) 類別 1）。

### 治理鐵律

- **pgvector 為唯一事實語料**：agent（經 MCP）與後台 web/api 共用同一語料；灌注來源經 knowledge-refinery HITL（[ADR-018](./ADR-018_知識精煉獨立服務.md)）。
- **bronze-only sourcing（CRITICAL）**：語料內容嚴格源自 Medallion bronze 層（[ADR-019](./ADR-019_Medallion分層數據架構.md)）；GDrive PDF 不可信，只引 URL 不抄內容。
- **domain-safety 兜底**：RAG 對稀薄品牌回空 / 低信心 → cs-sop 走「不編造、轉真人」；RAG 不可用時 fail-soft 同語義。

## Alternatives（考量的選項）

- **A：全部知識塞 Skill（filesystem-only）** — 可攜、零 DB 依賴，但非語義檢索（grep）準確率有上限、海量事實 bundle 肥大。
- **B：全部知識塞向量 DB** — 語義檢索強，但行為規範不可版本化、可攜性喪失、embedding 後原文難稽核。
- **C：Skill 行為驅動 + RAG-via-MCP 從屬分工（採用）** — 可攜性與語義檢索兼得，職責零重疊。

## Consequences（後果）

**正面**：單一事實語料（無雙系統漂移）；Skill 瘦身為精選 + 檢索程序（~1650 行）；可攜性保住（MCP 邊界）；侵入性小（白名單與紅線測試 `test_cr_0074_redline.py` 不動）。
**風險**：agent 新增 runtime 依賴（MCP server + pgvector 可用性）→ fail-soft 轉真人；embedding API 成本 / 延遲；語料灌注管線依賴 refinery 落地。
**影響範圍**：MCP-RAG server（per-brand bundle 內元件，[ADR-002](./ADR-002_per-brand授權部署.md)）、`embed()` helper、CS `AgentLoop` 接 `mcp_servers`、`agent/pyproject.toml` 加 `mcp` SDK。
**重評觸發**：RAG 檢索準確率 / 延遲不敷客服需求 → 調 chunk 策略 / embedding 模型 / hot-set 回填 skill；MCP server 維運成本過高 → RAG 併回進程內工具。

## Status 附註

- 分期：Phase 1 RAG 語義層（embed + 兩 cosine query + MCP server）→ Phase 2 語料灌注 → Phase 3 接線 + Skill 重切 → Phase 4 測試 + cutover。🔜 各 Phase 規劃中，昂貴階段 gate 在業主同意。
- **Cutover 原則**：filesystem references 保留為 fallback，直到 RAG 檢索品質通過 gate 才切換 gating 主路徑。
- **2026-07-10 業主裁決勘誤（實證推翻，code 不回退）**：①本文 embed 模型 text-embedding-004 對中文短文本退化（相似度趨 1.0，CR-0124 勘誤）——as-built＝`RAG_EMBED_MODEL` env，預設 `vertex_ai/text-multilingual-embedding-002`（768 維，CR-0140 D3 一致性）；②`search_similar_cases` 門檻 ≥0.85 係 004 設想——multilingual-002 下真改寫 sim≈0.743 恆不命中，as-built＝`RAG_CASE_SIM_THRESHOLD` env 預設 **0.70**（CR-0148）。
- **2026-07-10 補注**：cutover 已由 ADR-030（2026-07-09 業主裁決）取消——references 永為主路徑、RAG 引用率轉輔助品質指標；本文分期之 Phase 4 cutover 不再適用。
