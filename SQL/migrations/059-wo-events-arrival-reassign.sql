-- 059-wo-events-arrival-reassign.sql
--
-- WHY（CR-0053 / 審計揪出，同 migration 050 schedule_conflict 同類 bug）：
--   work_order_events_event_type_check 不含 'arrival' 與 'reassign'，但 code 兩處寫入：
--   - record_arrival 寫 event_type='arrival'（submit_door_check_v2 前置閘查此 → 缺則恆 409）。
--   - reassign_order 寫 event_type='reassign'（未包 try/except → 成功改派會 500 CheckViolation）。
--   兩者皆為 CHECK 漏列導致的真 bug；本 migration 補進 CHECK。
--
-- WHAT：DROP + ADD work_order_events_event_type_check，加 'arrival' / 'reassign'。idempotent。

ALTER TABLE work_order_events DROP CONSTRAINT IF EXISTS work_order_events_event_type_check;
ALTER TABLE work_order_events ADD CONSTRAINT work_order_events_event_type_check
  CHECK (event_type IN (
    'scope_change', 'material_request', 'delay', 'door_check',
    'signature_submitted', 'reschedule_proposed', 'schedule_conflict',
    'arrival', 'reassign', 'other'
  ));
