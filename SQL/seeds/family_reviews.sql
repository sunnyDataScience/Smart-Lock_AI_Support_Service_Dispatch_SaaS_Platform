-- ============================================================================
-- Smart Lock AI Support & Service Dispatch SaaS Platform
-- Family Reviews Seed (Phase 1.78)
-- ============================================================================
--
-- Apply (idempotent):
--   docker cp SQL/seeds/family_reviews.sql lock_AI:/tmp/
--   docker exec lock_AI psql -U lock -d lock_AI_data -f /tmp/family_reviews.sql
--
-- 對應 sop_drafts 的兩筆 status='approved' 草稿：
--   - bbbb...0002 (Chatlock 指紋辨識模組) → 不 seed family review，留作待覆核 pending demo
--   - bbbb...0003 (藍牙連線故障排除)     → seed 一筆 rejected 覆核，作為歷史紀錄 demo
-- ============================================================================

BEGIN;

INSERT INTO family_reviews (
    id, tenant_id, sop_draft_id, action, reviewer_id, comment, created_at
) VALUES
    (
        'eeee1111-aaaa-4bbb-8ccc-dddddddd0001'::uuid,
        '00000000-0000-0000-0000-000000000001'::uuid,
        'bbbb1111-cccc-4ddd-8eee-ffffffff0003'::uuid,
        'rejected',
        'c782bcfe-89bb-40b3-94b3-8c73d7bd0961'::uuid,
        '步驟 3 缺少藍牙模組韌體版本檢查，且未涵蓋 iOS 18.x 的 BLE 連線新限制；建議補強後重新送審。',
        NOW() - INTERVAL '1 day'
    )
ON CONFLICT (id) DO NOTHING;

COMMIT;
