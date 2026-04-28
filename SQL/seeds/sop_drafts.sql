-- ============================================================================
-- Seed: SOP 草稿（用於 GET /sop-drafts 列表與詳情頁展示）
-- ============================================================================
-- 用法：
--   docker cp SQL/seeds/sop_drafts.sql lock_AI:/tmp/
--   docker exec lock_AI psql -U lock -d lock_AI_data -f /tmp/sop_drafts.sql
-- 前置：必須先跑 Schema_api_phase1.sql（補 tenant_id）
-- 前置：建議先跑 problem_cards.sql（讓 source_problem_card_id 有實際 FK 對象）
-- ============================================================================
--
-- 種子內容：5 筆草稿，覆蓋全部 4 個 DB status 與 service 層 mapping：
--   - pending_review (1) → API status='under_review'
--   - approved       (1) → API status='approved'
--   - rejected       (1) → API status='approved' 反例 — wait，rejected 直通
--   - published      (1) → API status='approved'（已發布的終態）
--   - pending_review (1) → 額外一筆給篩選測試
--
-- 期望效果：
--   - GET /sop-drafts → 5 筆 items
--   - ?status=under_review → 2 筆
--   - ?status=approved → 2 筆（approved + published 都會回）
--   - ?status=rejected → 1 筆
--   - steps JSONB 由 service 層轉成 list[{order,title,description}]
-- ============================================================================

BEGIN;

-- 1) 待審核：Yale YDM-7220 離合器故障維修（pending_review）
INSERT INTO sop_drafts (
    id, tenant_id, source_problem_card_id, title, applicable_conditions, steps, notes,
    status, created_at
)
VALUES (
    'bbbb1111-cccc-4ddd-8eee-ffffffff0001'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    NULL,
    'Yale YDM-7220 離合器故障維修 SOP',
    '電子鎖螢幕顯示 E3 錯誤，輸入正確密碼仍無法解鎖',
    '[
        {"order": 1, "title": "確認故障現象", "description": "確認螢幕顯示 E3 錯誤代碼，且輸入正確密碼後無法解鎖"},
        {"order": 2, "title": "拆卸內面板", "description": "使用十字螺絲起子拆卸內面板四個固定螺絲"},
        {"order": 3, "title": "檢查離合器模組", "description": "目視檢查離合器齒輪是否有明顯磨損或變形"},
        {"order": 4, "title": "更換離合器組件", "description": "將新離合器對準安裝孔位，以順時針方向輕轉至卡入定位"},
        {"order": 5, "title": "測試驗證", "description": "重新組裝內面板，輸入密碼測試解鎖功能"}
    ]'::jsonb,
    '注意：拆卸前請先取下電池，避免短路風險',
    'pending_review',
    NOW() - INTERVAL '2 hours'
)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title, steps = EXCLUDED.steps, status = EXCLUDED.status;

-- 2) 待審核：Chatlock 指紋辨識模組清潔（pending_review）
INSERT INTO sop_drafts (
    id, tenant_id, source_problem_card_id, title, applicable_conditions, steps,
    status, created_at
)
VALUES (
    'bbbb1111-cccc-4ddd-8eee-ffffffff0002'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    NULL,
    'Chatlock 指紋辨識模組清潔與校正',
    '指紋多次無法辨識、出現 "請重新嘗試" 訊息',
    '[
        {"order": 1, "title": "確認感應器外觀", "description": "檢查指紋感應器表面是否有油污、灰塵或刮痕"},
        {"order": 2, "title": "使用無酒精濕巾清潔", "description": "以微濕的軟布輕拭感應器表面，禁止使用酒精"},
        {"order": 3, "title": "重新錄入指紋", "description": "進入管理員模式，刪除舊指紋資料後重新錄入"},
        {"order": 4, "title": "驗證辨識率", "description": "連續測試 10 次，辨識率應達 90% 以上"}
    ]'::jsonb,
    'pending_review',
    NOW() - INTERVAL '5 hours'
)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title, steps = EXCLUDED.steps, status = EXCLUDED.status;

-- 3) 已核准：藍牙連線故障排除（approved）
INSERT INTO sop_drafts (
    id, tenant_id, source_problem_card_id, title, steps, status,
    reviewed_at, review_comment, created_at
)
VALUES (
    'bbbb1111-cccc-4ddd-8eee-ffffffff0003'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    NULL,
    '藍牙連線故障排除標準流程',
    '[
        {"order": 1, "title": "確認手機藍牙啟用", "description": "在手機設定中確認藍牙已開啟，並重啟一次"},
        {"order": 2, "title": "刪除配對紀錄", "description": "在 App 中刪除舊的鎖具配對，再重新搜尋"},
        {"order": 3, "title": "回復原廠藍牙設定", "description": "在管理員模式下執行藍牙重置（不影響密碼設定）"},
        {"order": 4, "title": "重新配對", "description": "靠近鎖具 1 公尺內，依 App 提示完成配對"}
    ]'::jsonb,
    'approved',
    NOW() - INTERVAL '3 days',
    '步驟清晰，覆蓋常見故障原因，核准發布',
    NOW() - INTERVAL '3 days 4 hours'
)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title, steps = EXCLUDED.steps, status = EXCLUDED.status,
    review_comment = EXCLUDED.review_comment;

-- 4) 已退回：門鎖馬達異音處理（rejected）
INSERT INTO sop_drafts (
    id, tenant_id, source_problem_card_id, title, steps, status,
    reviewed_at, review_comment, created_at
)
VALUES (
    'bbbb1111-cccc-4ddd-8eee-ffffffff0004'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    NULL,
    '門鎖馬達異音處理標準程序',
    '[
        {"order": 1, "title": "辨識異音類型", "description": "區分連續嗡嗡、間歇喀喀、卡卡停頓三類"},
        {"order": 2, "title": "聯絡技師到府", "description": "馬達異音通常需要拆機檢修，請排程技師處理"}
    ]'::jsonb,
    'rejected',
    NOW() - INTERVAL '5 days',
    '步驟過於簡略，缺少現場初步診斷與分流判斷，請補充後再送審',
    NOW() - INTERVAL '5 days 2 hours'
)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title, steps = EXCLUDED.steps, status = EXCLUDED.status,
    review_comment = EXCLUDED.review_comment;

-- 5) 已發布：電池異常耗電診斷（published → API approved）
INSERT INTO sop_drafts (
    id, tenant_id, source_problem_card_id, title, steps, status,
    reviewed_at, review_comment, created_at
)
VALUES (
    'bbbb1111-cccc-4ddd-8eee-ffffffff0005'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    NULL,
    '電池異常耗電診斷與更換流程',
    '[
        {"order": 1, "title": "讀取電池電壓", "description": "管理員模式查詢電池電壓，正常值 6.0V 以上"},
        {"order": 2, "title": "確認使用情境", "description": "詢問每日操作次數、是否啟用 Wi-Fi 模組（耗電大宗）"},
        {"order": 3, "title": "更換鹼性電池", "description": "建議使用知名品牌鹼性電池，避免劣質鋅碳電池"},
        {"order": 4, "title": "重置耗電計數器", "description": "更換後在 App 中執行電池重置，重新統計耗電基準"}
    ]'::jsonb,
    'published',
    NOW() - INTERVAL '7 days',
    '已發布至案例庫，編號 KB-2026-0048',
    NOW() - INTERVAL '7 days 6 hours'
)
ON CONFLICT (id) DO UPDATE SET
    title = EXCLUDED.title, steps = EXCLUDED.steps, status = EXCLUDED.status,
    review_comment = EXCLUDED.review_comment;

COMMIT;

-- 驗證
SELECT id, title, status, jsonb_array_length(steps) AS step_count, created_at
FROM sop_drafts
WHERE tenant_id = '00000000-0000-0000-0000-000000000001'::uuid
ORDER BY created_at DESC;
