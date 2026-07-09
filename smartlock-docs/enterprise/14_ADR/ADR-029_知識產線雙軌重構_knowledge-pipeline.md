---
title: "ADR-029: 知識產線雙軌重構 — data/ 改名 knowledge-pipeline + facts/behavior 分軌 + provenance 治理"
version: 1.0
status: active
owner: DT（knowledge-pipeline）tech lead
last-updated: 2026-07-09
upstream:
  - ./ADR-010_知識分層_Skill行為驅動_RAG-via-MCP.md
  - ./ADR-018_知識精煉獨立服務.md
  - ./ADR-019_Medallion分層數據架構.md
---

# ADR-029: 知識產線雙軌重構 — knowledge-pipeline

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted（業主 2026-07-09 定調產線定位並核准重構：「將專業領域的人…的資料萃取成 skill，作為 agent 日後回答的依據；還要透過學習真人客服的應對方式持續新增或迭代」；改名 knowledge-pipeline 業主確認） |
| 層級 | 系統級（knowledge-pipeline，原 data/） |
| 關聯 ADR | [ADR-010](./ADR-010_知識分層_Skill行為驅動_RAG-via-MCP.md) · [ADR-018](./ADR-018_知識精煉獨立服務.md) · [ADR-019](./ADR-019_Medallion分層數據架構.md) |

## Context（背景與問題）

data/ 自 2026-06-04 agent 重寫後嚴重脫節：尾端 `silver_to_skill` 寫入
`agent/skills/data/`（已刪路徑，產線斷頭）、產出格式「每 skill 一個 SKILL.md」已被
`references/{Brand}/{Model}.md` 正典取代、LLM 走 langchain 適配器群（agent 已統一
LiteLLM）、命名「Data」被 0707 會議點名混淆。同時 ADR-010 已裁決知識分層（行為→
Skill、事實→RAG），產線卻只有單一 skill 軌。

## Decision（決策）

1. **改名 `knowledge-pipeline/`**（0707 AI #1 收尾）：它是知識產線，非資料庫也非模型訓練。
2. **Medallion 骨架保留**（ADR-019 不變）：raw/bronze/silver 三層與各來源處理器沿用；
   bronze-only 紅線繼續有效。
3. **尾端重寫為 `silver_to_knowledge` 雙軌**（對齊 ADR-010）：
   - Phase A 路由＝**以來源定軌的確定性規則**（可稽核）：youtube/video/website → **facts**；
     line_chat → **behavior**；gdrive → **quarantine**（紅線機器化：內容不落語料，只留參照）。
     語義級細分（同一影片內行為句/事實句分離）留 Phase C 的 LLM rubric。
   - facts → `storage/corpus/facts.jsonl`（schema 對齊 WBS 2.2.1 pgvector 表，Phase B 直接灌入）
   - behavior → `behavior_candidates.jsonl`（**絕不自動寫生產 skill**；HITL 精煉，迴路二輸入）
4. **Provenance 強制**：每 chunk 帶 bronze 檔路徑 + sha256 + 確定性 chunk id（冪等）；
   `audit_corpus` 為落地前 gate（provenance 完整、bronze 未漂移、紅線零違規、id 唯一），可入 CI。
5. **LLM 統一 LiteLLM**：langchain 適配器群刪除，`llms/provider.py` 以 model 字串路由多家
   （與 agent LiteLLMProvider 同哲學）；介面 `get_llm/get_vision_llm` 相容，呼叫端零改動。
6. **評測先行**：`eval/golden_qa.jsonl` 以專家更正（2026-04-14 Dormakaba 六條）為種子；
   規則＝每次專家更正/UAT 知識錯誤修正必須同步補一條 golden QA；Phase B 起接自動回歸。
7. **舊尾端刪除**：`silver_to_skill/` 整組（分類/草稿/審核）＝死碼，查 git；
   `references/` 內容維持鎖定，產線不寫入（迴路一的 references 更新屬 Phase C 人審流程）。

## 產出資料 schema（facts.jsonl，schema_version=1）

```json
{"schema_version": 1, "id": "sha256[:16]", "text": "...", "brand": "Dormakaba",
 "model": "general", "category": "troubleshoot", "source_type": "video",
 "source": "Dormakaba 鎖舌卡住排除.txt", "chunk_index": "1",
 "provenance": {"bronze_path": "storage/bronze/video/....txt",
                 "bronze_sha256": "...", "emitted_at": "..."}}
```

## Consequences（後果）

- ✅ 首跑實測：facts=862（provenance 100% 完整、bronze 零漂移）、quarantine=19（gdrive
  全數隔離＝紅線落實）、behavior=0（等迴路二對話餵入）
- ✅ 依賴瘦身：langchain-core/langsmith/三組 per-provider extras 移除
- ✅ 稽核抓到並修復真實血緣漂移（bronze 改名後 silver source 指標過期——後綴比對＋別名表）
- ⚠️ behavior 軌目前空集：歷史 line_chat 在 silver 全被判 irrelevant；迴路二（1.2.4 對話
  存檔驗證 → 2.3.1 knowledge_ready 汲取）是行為軌的正式供給線
- ⚠️ config 內 bronze_to_silver 各來源 llm_model 仍為 gemini-2.5-flash `[待驗證更新]`
  （更新需真跑 LLM 驗證，另輪處理）

## 重評觸發

- Phase B（2.2.1）pgvector 落地時：facts schema 若需擴欄（embedding 版本、tenant 維度）開 schema_version=2
- Phase C（2.2.2）語義級 rubric 上場時：路由規則自來源級升語義級，需業主過 rubric
