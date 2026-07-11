-- 105-tech-lifecycle-brand-auth-events.sql
--
-- WHY（CR-0166 R1-4 品牌授權撤證 API）：
--   technician_brand_auth_service 的 grant/revoke 寫 saas.technician_lifecycle_event
--   event_type='brand_auth_granted'/'brand_auth_revoked'，但 090 的 CHECK 未列 →
--   授/撤證會 CheckViolation。同 020/090 同類 CHECK 追加。
--
-- WHAT：DROP + ADD event_type CHECK，補 brand_auth_granted / brand_auth_revoked。idempotent。
-- ⚠️ 本表在技師權威庫（lock_tech）；split-tech-db.sh 初建 schema 後 migration 不會
--   自動傳播——本檔須同時套品牌庫（投影）與權威庫兩邊。

ALTER TABLE saas.technician_lifecycle_event
    DROP CONSTRAINT IF EXISTS technician_lifecycle_event_event_type_check;
ALTER TABLE saas.technician_lifecycle_event
    ADD CONSTRAINT technician_lifecycle_event_event_type_check CHECK (
        event_type = ANY (ARRAY[
            'onboarding_approved'::text, 'onboarding_rejected'::text,
            'suspended'::text, 'reactivated'::text, 'terminated'::text,
            'rating_threshold_breach'::text, 'cert_expired'::text,
            'kyc_reveal'::text,
            'brand_auth_granted'::text, 'brand_auth_revoked'::text
        ])
    );
