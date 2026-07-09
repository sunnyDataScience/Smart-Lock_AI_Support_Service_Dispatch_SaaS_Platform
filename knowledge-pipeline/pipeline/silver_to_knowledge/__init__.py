"""silver_to_knowledge — 雙軌知識產出（取代 silver_to_skill，見 ADR-029）。

1. emit_corpus.py  — silver → facts 語料 / behavior 候選 / gdrive 隔離（確定性路由 + provenance）
2. audit_corpus.py — 落地前治理稽核（provenance/紅線/漂移，可入 CI）

行為軌絕不自動寫入生產 skill：候選集供 HITL 精煉（迴路二，WBS 2.3.x）。
facts 語料 schema 對齊 WBS 2.2.1 pgvector 落地。
"""
