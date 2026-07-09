"""smart-lock-rag — RAG 語義層（ADR-010：Skill 是駕駛，RAG 是工具）。

模組：
  embedding.py — embed() 統一介面（LiteLLM，text-embedding-004，768 維）
  store.py     — pgvector 存取（upsert / cosine 檢索；WHERE 必帶 tenant_id）
  ingest.py    — 灌注 CLI：knowledge-pipeline facts.jsonl → manual_chunks
  server.py    — MCP server（search_product_manual / search_similar_cases）
"""
