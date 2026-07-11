-- 100-audit-events-append-only.sql
-- CR-0164 A：audit_events 主稽核表補 append-only 物理保護（NFR-Aud-001 合約下限）。
--
-- Root cause：audit_events（承載 financial/dispatch/security 事件）宣稱 append-only
-- （067-audit-hash-chain 加 prev_hash/entry_hash），但從未於 DB 層強制——實查
-- pg_trigger=0，UPDATE/DELETE 可無痕竄改。對照 saas.config_audit(004)/
-- voucher_void_event(010)/pricing_rule_snapshot(098) 皆有 tg_block_mutation。
-- 唯獨主稽核表漏掉物理保護（UAT wave2 F11 live-confirmed）。
--
-- 修：BEFORE UPDATE OR DELETE trigger 一律 RAISE（owner 亦擋）。
--
-- 特權繞過（測試 / 未來 retention purge）：ORIGIN 觸發器在
-- session_replication_role='replica' 下不觸發（PostgreSQL 標準機制）。需 purge
-- 或測試注入時，於該 session 先 SET session_replication_role='replica'（限
-- superuser/具權者），操作後復原。CR-0164 §8-A3：目前 audit 無 purge job、
-- 實質 eternal；未來 retention 分級 purge 走此特權路徑。

CREATE OR REPLACE FUNCTION audit_events_immutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_events is append-only (NFR-Aud-001/CR-0164); use session_replication_role=replica for privileged purge';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events;
CREATE TRIGGER trg_audit_events_append_only
  BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();

COMMENT ON FUNCTION audit_events_immutable() IS
  'CR-0164：audit_events append-only enforce。特權繞過走 session_replication_role=replica。';
