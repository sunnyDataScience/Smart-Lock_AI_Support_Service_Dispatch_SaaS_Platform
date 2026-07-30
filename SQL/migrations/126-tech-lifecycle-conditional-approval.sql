-- 126-tech-lifecycle-conditional-approval.sql
-- migrate-targets: brand,tech
--
-- WHY（CR-0195 條件式核准，業主 2026-07-30 裁決選項 3）：
--   核准端原本對 KYC 文件零檢查（technician_lifecycle_service.py:221-230 全鏈不查
--   technician_registration_document），實測 6 個 active 技師 100% 零文件——
--   「先上工後補件」其實已經在發生，只是無人察覺、也無法事後查誰沒補。
--   本 CR 讓「核准時文件未齊」從隱形變成明示：必須顯式帶 conditional + reason，
--   並寫下 onboarding_approved_conditional 事件。
--
-- WHAT：DROP + ADD event_type CHECK，補 'onboarding_approved_conditional'。idempotent。
--
-- ⚠️ 本檔順帶收斂一個既有 drift（CR-0195 §1-9 實測）：
--   105 在**兩個庫的 schema_migrations 都已登記**，但技師庫（lock_tech）的 CHECK
--   實際只有 8 值（止於 kyc_reveal），品牌庫是 10 值——105 對技師庫「登記了卻沒真的套」。
--   所以本檔的 ARRAY 列**完整 11 值**（含 105 的 brand_auth_granted / brand_auth_revoked），
--   套下去會讓兩庫收斂到同一組值域，而不是在 8 值基礎上 +1 造成新的分岔。
--   → 套用後**務必逐庫實測** pg_get_constraintdef，不要只信 schema_migrations。
--
-- 刻意**不加** 'kyc_docs_completed'：§8-D3 業主裁決 (a)「只記錄不設期限，逾期治理另開 CR」，
--   補件完成與否由 technician_registration_document 即時查（S3 的 kyc_docs_complete），
--   不需要第二個事件型別。逾期降級屬懲罰機制，與 CR-0170 同域而該 CR 卡在法務未回。

ALTER TABLE saas.technician_lifecycle_event
    DROP CONSTRAINT IF EXISTS technician_lifecycle_event_event_type_check;
ALTER TABLE saas.technician_lifecycle_event
    ADD CONSTRAINT technician_lifecycle_event_event_type_check CHECK (
        event_type = ANY (ARRAY[
            'onboarding_approved'::text, 'onboarding_rejected'::text,
            'suspended'::text, 'reactivated'::text, 'terminated'::text,
            'rating_threshold_breach'::text, 'cert_expired'::text,
            'kyc_reveal'::text,
            'brand_auth_granted'::text, 'brand_auth_revoked'::text,
            'onboarding_approved_conditional'::text
        ])
    );
