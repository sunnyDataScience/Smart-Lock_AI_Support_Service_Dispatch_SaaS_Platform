-- 104-wo-events-reject.sql
--
-- WHY（CR-0166 R1-9 技師拒單端點）：
--   reject_order 寫 work_order_events event_type='reject'（對齊 assign/reassign
--   timeline），102 的 CHECK 未列會使拒單 500 CheckViolation。同 050/059/102 同類。
--
-- WHAT：DROP + ADD work_order_events_event_type_check，補 'reject'。idempotent。

ALTER TABLE work_order_events DROP CONSTRAINT IF EXISTS work_order_events_event_type_check;
ALTER TABLE work_order_events ADD CONSTRAINT work_order_events_event_type_check
  CHECK (event_type IN (
    'scope_change', 'material_request', 'delay', 'door_check',
    'signature_submitted', 'reschedule_proposed', 'schedule_conflict',
    'arrival', 'reassign', 'assign', 'supply_arrived', 'reject', 'other'
  ));
