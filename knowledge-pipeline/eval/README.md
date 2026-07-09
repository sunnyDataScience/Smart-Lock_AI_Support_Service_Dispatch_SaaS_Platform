# eval — 知識品質評測

- `golden_qa.jsonl`：專家驗證的黃金問答集（種子=2026-04-14 Dormakaba 專家更正 6 條）。
  **知識落地前的回歸基準**：RAG/skill 任何變更後，agent 對這些題的回答不得退化。
- 擴充規則：每次專家更正、UAT 發現的知識錯誤，修正後**必須**同步加入一條 golden QA。
- Phase B（RAG 落地）後接自動評測：檢索命中 + LLM judge 對答案一致性打分。
