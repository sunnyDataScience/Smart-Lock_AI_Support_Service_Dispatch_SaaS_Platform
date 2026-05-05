-- ============================================================================
-- Smart Lock AI Support & Service Dispatch SaaS Platform
-- Schema 擴充：技師排班 + online state（T10 我的排班 + PATCH availability）
-- ============================================================================
--
-- 對應 endpoints：
--   GET    /api/v1/technicians/me/schedule?month=YYYY-MM
--   POST   /api/v1/technicians/me/schedule/leave-request
--   POST   /api/v1/technicians/me/schedule/standby-request
--   DELETE /api/v1/technicians/me/schedule/request/{id}
--   PATCH  /api/v1/technicians/me/availability
--
-- Dependencies: Schema.sql / Schema_api_phase1.sql 必須先執行
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1) technicians.online_state ：技師日常在線/離線開關
-- ----------------------------------------------------------------------------
-- 對應 OpenAPI TechnicianAvailability enum：
--   available / busy / offline / on_leave / circuit_breaker_open
-- 與既有 technicians.status（admin 生命週期：pending_approval/active/...）正交。

ALTER TABLE technicians
    ADD COLUMN IF NOT EXISTS online_state VARCHAR(40) DEFAULT 'available'
        CHECK (online_state IN ('available', 'busy', 'offline', 'on_leave', 'circuit_breaker_open'));

COMMENT ON COLUMN technicians.online_state IS
    '技師日常在線狀態（API TechnicianAvailability enum）；與 status 生命週期欄位正交';

-- ----------------------------------------------------------------------------
-- 2) technician_schedule_requests ：休假 / 備勤申請
-- ----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS technician_schedule_requests (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    technician_user_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tenant_id           UUID NOT NULL,
    type                VARCHAR(20) NOT NULL CHECK (type IN ('leave', 'standby')),
    start_date          DATE NOT NULL,
    end_date            DATE NOT NULL,
    reason              TEXT NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    resolver_user_id    UUID REFERENCES users(id) ON DELETE SET NULL,
    resolved_at         TIMESTAMP WITH TIME ZONE,
    resolution_note     TEXT,
    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_date_range CHECK (end_date >= start_date)
);

CREATE INDEX IF NOT EXISTS idx_tech_schedule_user
    ON technician_schedule_requests (technician_user_id, status, start_date);

CREATE INDEX IF NOT EXISTS idx_tech_schedule_tenant
    ON technician_schedule_requests (tenant_id, status, created_at DESC);

CREATE TRIGGER trg_tech_schedule_requests_updated_at
    BEFORE UPDATE ON technician_schedule_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE technician_schedule_requests IS
    '技師休假/備勤申請（T10 我的排班）。pending → approved/rejected by admin；cancelled by self';
