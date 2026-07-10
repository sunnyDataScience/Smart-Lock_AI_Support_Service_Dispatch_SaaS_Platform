-- ═══════════════════════════════════════════════════════════════════════════
-- 095-case-entries-merge-shape.sql — case_entries 併形(WBS 2.3.2 / CR-0140 D1)
--
-- 業主裁決 2026-07-10(CR-0139 §8-1 → B 併形):
--   Schema.sql 的 kb-v2 case_entries(title/problem_description/solution)為唯一正典;
--   Schema_rag.sql 曾另定義 rag 形狀(symptom/resolution/source_problem_card_id),
--   因 CREATE TABLE IF NOT EXISTS 於真實庫 no-op 形成潛在缺陷(rag 查詢 SQL ERROR)。
--   本 migration 把 rag 形狀缺的欄併進 kb 表;rag 查詢改讀 kb 欄名(別名輸出不變)。
--
-- source 欄值域追加 'refinery'(knowledge-refinery Publisher 核可寫入;無 CHECK 約束,
-- 僅註釋層值域)。embedding 由 refinery 首寫(api 從不寫向量,embedding_status 恆
-- 'processing');embedding_model 記錄模型名,換模型重嵌時可辨識舊向量。
-- 落庫:品牌庫。
-- ═══════════════════════════════════════════════════════════════════════════

-- Phase D 溯源:核可案例 → 來源 knowledge_ready 問題卡(ADR-018)
ALTER TABLE case_entries
    ADD COLUMN IF NOT EXISTS source_problem_card_id UUID REFERENCES problem_cards(id) ON DELETE SET NULL;

-- 向量模型溯源(rag 檢索與 Publisher 共用 RAG_EMBED_MODEL,預設 multilingual-002/768)
ALTER TABLE case_entries
    ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_case_entries_source_pc
    ON case_entries (source_problem_card_id)
    WHERE source_problem_card_id IS NOT NULL;
