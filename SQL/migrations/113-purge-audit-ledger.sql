-- ═══════════════════════════════════════════════════════════════════════════
-- 113-purge-audit-ledger.sql — two-phase purge 專用稽核帳本（NFR-Priv-008 / FR-API-16）
--
-- WHY：
--   NFR-Priv-008（合約下限）明定 two-phase purge（T0 銷金鑰 + T+30 硬刪）的稽核落
--   `purge_audit.entry`。現況 GDPR forget 兩階段雖有 append-only 稽核，但只落泛用
--   `audit_events`（event_type='compliance'），無規格指定的專用 purge 帳本 → 合約缺口。
--
-- WHAT：
--   建 saas.purge_audit 專表：每筆＝一次 purge 階段動作（soft_delete_t0 / hard_delete_t30），
--   記 crypto_shredded（是否銷 DEK，CR-0176）/ physical_deleted（是否實體刪）/ actor / detail。
--   append-only：immutability trigger 擋 UPDATE/DELETE（比照 098 pricing snapshot）。
--   與 audit_events 併存（defense in depth）——泛用鏈仍記，另落專用帳本供合規稽核。
--
-- IMPACT：
--   純新增表 + trigger，零回歸。gdpr_forget_service soft_delete/hard_delete 各加一筆。
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS saas.purge_audit (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id         UUID,
    subject_user_id   UUID NOT NULL,
    forget_request_id UUID,
    phase             VARCHAR(30) NOT NULL
                      CHECK (phase IN ('soft_delete_t0', 'hard_delete_t30')),
    crypto_shredded   BOOLEAN NOT NULL DEFAULT FALSE,   -- CR-0176：本階段是否銷毀 DEK
    physical_deleted  BOOLEAN,                          -- hard 階段：是否實體刪（vs 匿名化保留）
    actor_user_id     UUID,
    detail            JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_purge_audit_subject ON saas.purge_audit (subject_user_id);
CREATE INDEX IF NOT EXISTS idx_purge_audit_request ON saas.purge_audit (forget_request_id);

COMMENT ON TABLE saas.purge_audit IS
    'NFR-Priv-008 two-phase purge 專用 append-only 稽核帳本（soft_delete_t0 / hard_delete_t30）';

-- append-only：擋 UPDATE/DELETE（owner 亦擋），比照 pricing_snapshot_immutable
CREATE OR REPLACE FUNCTION saas.purge_audit_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'saas.purge_audit is append-only (NFR-Priv-008)：% 不允許', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_purge_audit_append_only ON saas.purge_audit;
CREATE TRIGGER trg_purge_audit_append_only
    BEFORE UPDATE OR DELETE ON saas.purge_audit
    FOR EACH ROW EXECUTE FUNCTION saas.purge_audit_immutable();
