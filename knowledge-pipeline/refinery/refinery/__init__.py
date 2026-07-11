"""knowledge-refinery — 診斷對話汲取 + 提煉分流 + Draft Queue（WBS 2.3.1 / CR-0139）。

ADR-018 五步管線的 ①②半部：
  汲取層（intake）  ── 直連品牌 DB 撿 knowledge_ready=TRUE 的問題卡 + 1:1 對話逐字稿
  提煉分流器（refine）── LLM 把卡 spine + 對話分流成兩軌 draft（事實 case_entry / 行為 behavior）
  Draft Queue（store）── 落 knowledge_drafts 表（pending_review），供 2.3.2 HITL 審核 UI 消費

治理紅線：
  - HITL 硬 gate：本套件**只產 draft，絕不寫入** pgvector 語料或 skill（落地屬 2.3.2 Publisher）
  - tenant default-deny：REFINERY_TENANT_ID 未設即拒絕（比照 rag/ RAG_TENANT_ID）
  - 不得編造：draft 內容嚴格源自卡欄位與對話逐字稿，provenance 全程可溯
"""
