-- ============================================================================
-- Smart Lock AI Support & Service Dispatch SaaS Platform
-- Schema 擴充：工單事件表（取代 service_report append 模式）
-- ============================================================================
--
-- 對應：
--   T5 scope_change / T6 material_request / T7 delay / T8 door_check
--   後續可加：T9 signature / T11 reschedule_proposed 等
--
-- WHY:
--   v1.17.0 起 subflow 事件以 [TAG ts] {json} 文字 prepend 到 service_report，
--   不適合查詢 / 統計 / UI timeline 顯示。本表將事件結構化，service_report
--   仍保留作為「給人看的完工摘要」文字。
--
-- Dependencies: Schema.sql 必須先執行
-- ============================================================================

CREATE TABLE IF NOT EXISTS work_order_events (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id       UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    tenant_id           UUID NOT NULL,
    actor_user_id       UUID REFERENCES users(id) ON DELETE SET NULL,
    event_type          VARCHAR(40) NOT NULL CHECK (
                            event_type IN (
                                'scope_change',
                                'material_request',
                                'delay',
                                'door_check',
                                'signature_submitted',
                                'reschedule_proposed',
                                'schedule_conflict',  -- migration 050
                                'arrival',            -- migration 059 (CR-0053)
                                'reassign',           -- migration 059 (CR-0053)
                                'assign',             -- migration 102 (CR-0165)
                                'supply_arrived',     -- migration 102 (CR-0165)
                                'other'
                            )
                        ),
    payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_wo_events_wo
    ON work_order_events (work_order_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wo_events_tenant_type
    ON work_order_events (tenant_id, event_type, created_at DESC);

COMMENT ON TABLE work_order_events IS
    '工單事件結構化紀錄（取代 service_report append）。可用於 UI timeline、聚合統計、稽核';
COMMENT ON COLUMN work_order_events.payload IS
    '事件型別專屬 payload（依 event_type schema 不同）';
COMMENT ON COLUMN work_order_events.event_type IS
    'scope_change / material_request / delay / door_check / signature_submitted / reschedule_proposed / other';
