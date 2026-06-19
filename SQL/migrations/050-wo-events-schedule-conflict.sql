-- 050-wo-events-schedule-conflict.sql
-- CR-0038 階段2 Alpha 執行揪出真 bug：work_order_events_event_type_check 不含 'schedule_conflict'。
--
-- WHY：work_order_service._detect_schedule_conflict_and_publish 偵測到同技師時段衝突時，
--   INSERT work_order_events event_type='schedule_conflict'，但 CHECK 約束只允許
--   scope_change/material_request/delay/door_check/signature_submitted/reschedule_proposed/other
--   → CheckViolation 例外，被 except 吞成 non-fatal log → **排班衝突事件永遠寫不進、WS 不推播**（靜默壞）。
--   test_schedule_conflict_detection 正確抓到（publish await_count=0）。
--
-- WHAT：CHECK 加入 'schedule_conflict'。idempotent（DROP IF EXISTS + ADD）。

ALTER TABLE work_order_events DROP CONSTRAINT IF EXISTS work_order_events_event_type_check;
ALTER TABLE work_order_events ADD CONSTRAINT work_order_events_event_type_check
  CHECK (event_type IN (
    'scope_change', 'material_request', 'delay', 'door_check',
    'signature_submitted', 'reschedule_proposed', 'schedule_conflict', 'other'
  ));
