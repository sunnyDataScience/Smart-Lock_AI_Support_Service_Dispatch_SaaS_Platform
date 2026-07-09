# rag — RAG 語義層（WBS 2.2.1 / ADR-010）

pgvector 事實語料 + MCP server。**定位（ADR-030）：對外開放介面**——品牌客戶自建知識庫/RAG
經 MCP 接入平台 agent；本服務同時是介面的參考實作。我方 agent 以 **skill 為知識與推理主軸**
（references 永為主路徑），RAG 為 skill 按規範呼叫的輔助工具。
per-brand bundle 元件（ADR-002）：查詢必帶 `tenant_id`（default deny）。

## 組成

| 檔案 | 職責 |
|---|---|
| `SQL/Schema_rag.sql`（repo 根） | `manual_chunks`（手冊事實語料）+ `case_entries`（案例史）；768 維 HNSW cosine |
| `rag/embedding.py` | `embed()` — LiteLLM，`vertex_ai/text-multilingual-embedding-002` |
| `rag/store.py` | upsert / cosine 檢索（tenant + 品牌/型號 gating；case 閾值 ≥ 0.85） |
| `rag/ingest.py` | 灌注 CLI：knowledge-pipeline `facts.jsonl` → `manual_chunks`（冪等 upsert） |
| `rag/server.py` | MCP server（stdio）：`search_product_manual` / `search_similar_cases` |

> ⚠️ embedding 模型勘誤（CR-0124）：ADR-010 原訂 `text-embedding-004`，實測對中文短文本
> 退化（不同輸入回同一向量、相似度全 1.0——英文為主模型）；改用同 768 維 multilingual 版，
> 實測相關 0.8+/無關 0.5 分佈健康。換模型須全量重嵌（`embedding_model` 欄可辨識）。

## 用法

```bash
# 1. 建表（品牌庫 image 已內建 pgvector）
psql "$POSTGRES_URI" -f SQL/Schema_rag.sql

# 2. 灌注（前置：knowledge-pipeline emit_corpus + audit_corpus 全綠）
cd rag
RAG_TENANT_ID=<uuid> POSTGRES_URI=<uri> uv run python -m rag.ingest [--limit N]

# 3. MCP server（stdio；Phase C 由 lockcore mcp_servers 接線）
RAG_TENANT_ID=<uuid> POSTGRES_URI=<uri> uv run python -m rag.server

# 測試
uv run pytest tests -q
```

## 治理

- **bronze-only**：只灌 `facts.jsonl`（經 audit gate）；ingest 內建 gdrive 紅線二次防禦
- **default deny**：無 `RAG_TENANT_ID` 拒啟動／拒查詢
- **fail-soft**：DB/embedding 不可用回 `RAG_UNAVAILABLE`，agent 側 cs-sop 走「不編造、轉真人」
- **無 cutover**（ADR-030 取消 ADR-010 Phase 4）：references 永為主路徑；引用率 gate＝
  輔助工具品質指標，非切換開關

## 後續（Phase C = WBS 2.2.2）

lockcore `mcp_servers` 接線（工具名 `mcp_locksmith-rag_*`，白名單紅線不動）、
語料灌注品牌庫、Skill 重切（行為留 skill、事實入 RAG）、引用率 gate。
`case_entries` 由 Phase D knowledge-refinery（ADR-018）HITL 灌入。
