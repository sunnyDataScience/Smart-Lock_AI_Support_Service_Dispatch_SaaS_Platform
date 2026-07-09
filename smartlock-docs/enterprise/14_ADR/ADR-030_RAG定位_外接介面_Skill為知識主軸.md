---
title: "ADR-030: RAG-MCP 定位——對外開放介面；我方 Agent 以 Skill 為知識與推理主軸"
version: 1.0
status: active
owner: 業主
last-updated: 2026-07-09
supersedes-partial:
  - ./ADR-010_知識分層_Skill行為驅動_RAG-via-MCP.md  # 僅 Phase 4 cutover 計畫段
---

# ADR-030: RAG-MCP 定位——對外開放介面；Skill 為知識與推理主軸

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（業主裁決 2026-07-09：「這個 RAG 是要做成 MCP 當客戶有自己的資料庫時可以外接用的；我們的 Agent 還是以 skill 為出發，因為 skill 才能完整紀錄回答的推理流程」） |
| 層級 | 平台 |
| 關聯 ADR | 部分取代 [ADR-010](./ADR-010_知識分層_Skill行為驅動_RAG-via-MCP.md)（cutover 段）· [ADR-011](./ADR-011_Agent整合風格三分類.md) |

## Decision（裁決）

1. **RAG-MCP 的首要定位＝對外開放介面**：品牌客戶已有自建知識庫/RAG 時，經 MCP
   標準介面接入平台 agent（平台不重整客戶資料）。我方 `rag/` 服務同時是此介面的
   **參考實作**（給沒有自建 RAG 的品牌用）。
2. **我方 agent 的知識與推理主軸＝Skill（永久，非過渡）**：行為規範、推理流程、
   精選事實住 `lockcore/skills/`（references 為正典事實層）——skill 才能完整記錄
   並版本化「怎麼推理、為什麼這樣答」。
3. **ADR-010 的 Phase 4 cutover 計畫取消**：不存在「RAG 檢索品質過 gate 後切換主路徑」
   ——references 永為主路徑；我方 RAG 語料為**輔助語義查找**（skill 在需要時呼叫的
   工具之一），引用率 gate 轉為衡量此輔助工具品質的指標，非切換開關。
4. ADR-010 的其餘裁決不變：Skill 是駕駛、RAG 是工具；tenant default-deny；
   bronze-only；fail-soft 轉真人。

## Consequences

- 專家知識更正的正確落點＝**references（skill 側）**，RAG 語料隨 `ingest_references` 同步
- 已建的 `rag/` 服務與 agent MCP 接線保留（opt-in；同一介面未來服務外接場景）
- 對外接入規格（品牌自建 RAG 需暴露的 MCP 工具形狀）＝後續 CR 定義 `[待議]`
