-- ============================================================================
-- 123-wo-events-resumed.sql  —— CR-0193 §11（業主 2026-07-30 裁決：補）
-- ============================================================================
-- WHY：
--   122 收斂了 10 個生命週期轉換，但程式化稽核（掃全 services/ 的
--   `UPDATE work_orders SET status=`）另抓到兩處不在原清單內的轉換：
--     scope_change_service.respond_public（客戶用公開連結核可範圍變更）
--     scope_change_service.admin_override（後台強制核可）
--   兩者都把工單推回 status='in_progress'（＝核可後復工），但不落事件。
--
--   現有 'scope_change' 事件記的是**申請**，不是核可復工，語意不同不可兼代。
--   範圍變更後復工是爭議舉證常查的節點（「加價項目何時被同意、誰同意的、
--   何時恢復施工」），缺這一筆等於 timeline 在最需要的地方斷開。
--
-- WHAT：event_type CHECK 追加 'resumed'。
--
-- ⚠️ 同 122：本 migration 必須先於 code 套用（service 寫 'resumed' 而 CHECK
--    未含該值時，INSERT 會 CheckViolation → 核可端點 500。這正是 050/059/102/104
--    四次同類 bug 的成因）。
--
-- ⚠️ idempotency：DROP IF EXISTS + ADD（不可用比對約束定義內容當守衛，見 016 教訓）。
-- ============================================================================

ALTER TABLE work_order_events DROP CONSTRAINT IF EXISTS work_order_events_event_type_check;
ALTER TABLE work_order_events ADD CONSTRAINT work_order_events_event_type_check
    CHECK (event_type IN (
        'scope_change',
        'material_request',
        'delay',
        'door_check',
        'signature_submitted',
        'reschedule_proposed',
        'schedule_conflict',   -- migration 050
        'arrival',             -- migration 059 (CR-0053)
        'reassign',            -- migration 059 (CR-0053)
        'assign',              -- migration 102 (CR-0165)
        'supply_arrived',      -- migration 102 (CR-0165)
        'reject',              -- migration 104 (CR-0166 R1)
        'created',             -- migration 122 (CR-0193)
        'accepted',            -- migration 122 (CR-0193)
        'completed',           -- migration 122 (CR-0193)
        'cancelled',           -- migration 122 (CR-0193)
        'reopened',            -- migration 122 (CR-0193)
        'escalated',           -- migration 122 (CR-0193)
        'confirmed',           -- migration 122 (CR-0193)
        'resumed',             -- migration 123 (CR-0193 §11) 範圍變更核可後復工
        'other'
    ));
