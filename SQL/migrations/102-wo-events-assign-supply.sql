-- 102-wo-events-assign-supply.sql
--
-- WHY（CR-0165 F9 / 同 050、059 同類 CHECK 漏列 bug）：
--   1. 'assign'：CR-0165 F9 讓 assign_order 補寫 work_order_events（對齊 reassign
--      timeline），CHECK 未列會使手動派工 500 CheckViolation。
--   2. 'supply_arrived'：本輪查證途中發現的既存潛在 bug——mark_supply_arrived
--      （work_order_service.py，admin 標記補料完成端點）寫入 'supply_arrived'，
--      但 059 的 CHECK 未列 → 該端點自建置以來必 500；live 實查 0 筆佐證從未成功。
--
-- WHAT：DROP + ADD work_order_events_event_type_check，補 'assign' / 'supply_arrived'。idempotent。

-- 註：'reject' 於 104-wo-events-reject.sql（CR-0166 R1 技師拒單）再追加。
ALTER TABLE work_order_events DROP CONSTRAINT IF EXISTS work_order_events_event_type_check;
ALTER TABLE work_order_events ADD CONSTRAINT work_order_events_event_type_check
  CHECK (event_type IN (
    'scope_change', 'material_request', 'delay', 'door_check',
    'signature_submitted', 'reschedule_proposed', 'schedule_conflict',
    'arrival', 'reassign', 'assign', 'supply_arrived', 'other'
  ));
