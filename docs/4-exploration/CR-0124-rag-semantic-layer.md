---
id: CR-0124
title: "RAG 語義層 Phase B（CIA 紀錄）"
status: done
date: 2026-07-09
decision: "業主指示繼續 Phase B（WBS 2.2.1）；架構依 ADR-010 既定規格實作"
---

# CR-0124 RAG 語義層（embed + pgvector + MCP server）

> 依 ADR-010 Phase 1 規格實作。命中面向：Architecture boundary（新 rag/ 服務）
> + DB schema（新 manual_chunks / case_entries 表，additive）。

## 交付

- `SQL/Schema_rag.sql`：manual_chunks + case_entries（768 維 HNSW cosine；
  additive 新表，走 Schema_*.sql glob apply 鏈）
- 新頂層 `rag/`（uv workspace member）：embedding.py（LiteLLM）/ store.py
  （tenant default-deny + 品牌/型號 gating + case 閾值 0.85）/ ingest.py
  （facts.jsonl 冪等灌注 + gdrive 紅線二次防禦）/ server.py（FastMCP 兩工具 + fail-soft）
- 單元測試 5 項（rag/tests）；agent 接線留 Phase C（ADR-010 Phase 3）

## ⚠️ ADR-010 勘誤（實證）

ADR-010 規格 `text-embedding-004` 對**中文短文本退化**：不同輸入回同一向量
（「門鎖警報」vs「咖啡」cosine=1.0000，英文正常 0.27——它是英文為主模型），
導致檢索全部 similarity=1.0 失效。**改用 `vertex_ai/text-multilingual-embedding-002`**
（同 768 維，schema 不動）：相關 0.82／無關 0.54，分佈健康。
ADR-010 為 accepted 文件（append-only 不改內文），勘誤以本 CIA + rag/README 記載，
待下次 ADR-010 重評時正式吸收。

## 驗證（臨時 pgvector 容器 5440，未碰 UAT 庫）

- 建表 → 全量灌注 862 chunk（860 相異向量）→ 重跑冪等（零重複）
- 語義品質：「門關起來鎖不上一直警報」→ 0.806 命中關鎖失敗排除 chunk；
  「怎麼恢復原廠設定」→ 命中「Dormakaba 需請技師初始化」（對齊 golden QA #6）
- 已知語料缺口：「面板閃兩下」專家事實尚未入語料（僅 golden QA）——Phase C 補強項
- MCP 兩工具註冊 ✓、case 空集 ✓、fail-soft RAG_UNAVAILABLE ✓
- 單元測試 5 passed；uv sync 過

## §8 Human Decisions

- ✅ Phase B 開工（業主 2026-07-09）
- embedding 模型勘誤＝工程實證裁量（同維度替換，可逆）
- 品牌庫實際建表與灌注時機：隨下次 schema apply（本機 db-init / 雲端 apply-schema-prod）
  ——UAT 期間不主動對 5433 動 DDL
