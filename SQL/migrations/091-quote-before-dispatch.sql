-- ═══════════════════════════════════════════════════════════════════════════
-- 091-quote-before-dispatch.sql — 報價先行 gate（WBS 1.2.1 / CR-0128 / ADR-015①②）
--
-- 業主裁決（CR-0128 §8，2026-07-09）：
--   D1a 硬 gate＋本輪補 PC 層報價 UI；D2a 新增 emergency_class 四類；
--   D3a 存量豁免（以 quote_gate_applied 標記 gate 後新單，結案閘只驗標記單）。
--
-- 設計：
--   - problem_cards.emergency_class：急件 carve-out 四類（ADR-015①），NULL＝非急件。
--     與 urgency（low/normal/high/urgent 優先級）不同軸——分類供補審引擎（1.2.2）分流。
--   - work_orders.quote_gate_applied：TRUE＝經報價 gate 開的單（結案硬閘驗 quote）；
--     FALSE（預設）＝gate 上線前存量單，結案僅驗地址（D3a grandfather）。
--   - quote.state 值域擴充（app 層 enforce，見 quote_engine_service._TRANSITIONS）：
--     急件開單時系統自動建 retrospective_audit_only 佔位報價 → 補審完成轉 accepted。
--
-- 慣例：IF NOT EXISTS，可重複套用。落庫：品牌庫。
-- ═══════════════════════════════════════════════════════════════════════════

ALTER TABLE problem_cards
    ADD COLUMN IF NOT EXISTS emergency_class VARCHAR(30);
                        -- 急件 carve-out 四類（ADR-015①；NULL＝非急件走標準報價先行）：
                        -- 'locked_out'      : 門打不開被鎖在外
                        -- 'trapped_inside'  : 人被困屋內
                        -- 'safety_risk'     : 安全風險（瓦斯/幼童/醫療等）
                        -- 'angry_high_risk' : 高風險客訴升級
COMMENT ON COLUMN problem_cards.emergency_class IS
    '急件 carve-out 四類（ADR-015①/CR-0128）；NULL=非急件。急件跳過報價直接開單，事後 4h 補審（1.2.2）';

ALTER TABLE work_orders
    ADD COLUMN IF NOT EXISTS quote_gate_applied BOOLEAN NOT NULL DEFAULT FALSE;
COMMENT ON COLUMN work_orders.quote_gate_applied IS
    '報價先行 gate 標記（CR-0128 D3a）：TRUE=gate 後新單（結案硬閘驗 quote 確認）；FALSE=存量豁免單';

COMMENT ON COLUMN quote.state IS
    'draft → pending_approval → approved → sent → accepted | rejected | expired | superseded；'
    '急件另有 retrospective_audit_only →（補審簽認）accepted（ADR-015①/CR-0128）';

-- 開單 gate 查「PC 最新客戶確認報價」的查詢路徑
CREATE INDEX IF NOT EXISTS idx_quote_problem_card_state ON quote (problem_card_id, state);
