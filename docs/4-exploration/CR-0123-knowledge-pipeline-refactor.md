---
id: CR-0123
title: "知識產線 Phase A 重構（CIA 紀錄）"
status: done
date: 2026-07-09
decision: "業主定調定位（素材萃取成 skill + 向真人客服學習迭代）並核准重構；改名 knowledge-pipeline 確認"
---

# CR-0123 知識產線 Phase A 重構

> 事後紀錄型 CIA。命中面向：Architecture boundary。正式決策見
> `smartlock-docs/enterprise/14_ADR/ADR-029`。

## 變更

- 改名 data/ → knowledge-pipeline/（0707 AI #1 收尾；uv workspace/CI/CLAUDE.md/README 同步）
- llms/ 統一 LiteLLM（刪 langchain 適配器群與相依）
- 尾端 silver_to_skill（寫入已刪路徑 agent/skills/data/）→ silver_to_knowledge 雙軌：
  facts 語料（RAG，Phase B 灌 pgvector）/ behavior 候選（HITL，迴路二）/ gdrive 隔離（紅線）
- provenance 強制 + audit_corpus 落地 gate；eval/golden_qa.jsonl（Dormakaba 專家更正種子）

## §8 Human Decisions

- ✅ 定位與重構核准（2026-07-09）；✅ 命名 knowledge-pipeline
- Phase A 路由=來源級確定性規則（LLM 語義 rubric 留 Phase C，屆時 rubric 需業主過目）
- `[待驗證更新]` config 內 gemini-2.5-flash 模型字串（需真跑 LLM 驗證）

## 驗證

實跑 emit_corpus + audit_corpus：facts=862（provenance 完整、bronze 零漂移）、
quarantine=19（gdrive 全隔離）、behavior=0（待迴路二）；audit 曾抓到 13 筆真實血緣漂移
（bronze 改名）→ 後綴比對+別名表修復後全綠。uv sync + import smoke 過。
