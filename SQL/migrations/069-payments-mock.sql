-- 069-payments-mock.sql
-- WHY（CR-0070 / TI-FIN-PAY-01~05 / 會議決議5 mock-first）：金流核心 payment 表/服務原為 0
--   （AR/AP/佣金/月結全等一個不存在的 payment 表核銷）。本批依會議 mock-first 授權建
--   payment 子系統骨架：三軌支付 intent/confirm、webhook 冪等、fallback audit、現金爭議。
--   正式 provider 串接（真 Line Pay / Apple Pay 簽章金鑰）由 Sunny 下輪（決議6），故 is_mock。
-- WHAT：payments 表 + 唯一鍵（idempotency_key 防重複 intent；provider_txn_id 防重複 webhook）。
CREATE TABLE IF NOT EXISTS payments (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id        UUID NOT NULL,
    work_order_id    UUID,
    method           TEXT NOT NULL,                       -- cash / apple_pay / line_pay
    amount           NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
    currency         TEXT NOT NULL DEFAULT 'TWD',
    status           TEXT NOT NULL DEFAULT 'pending',     -- pending/confirmed/failed/disputed
    purpose          TEXT NOT NULL DEFAULT 'service',     -- service / deposit(訂金)
    intent_id        TEXT,
    provider_txn_id  TEXT,                                -- webhook 冪等鍵（同 txn 只認一次）
    idempotency_key  TEXT,                                -- intent 冪等鍵（同 key 不重複建）
    attempt_count    INT NOT NULL DEFAULT 1,
    fallback_from    TEXT,                                -- PAY-04：上一次失敗的 method
    is_mock          BOOLEAN NOT NULL DEFAULT true,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at     TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_idempotency
    ON payments (tenant_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_provider_txn
    ON payments (provider_txn_id) WHERE provider_txn_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_payments_work_order ON payments (work_order_id);
COMMENT ON TABLE payments IS 'CR-0070/TI-FIN-PAY mock 金流骨架（is_mock；正式 provider 串接 Sunny 下輪）';

-- PAY-01 payment gate 走 M18 config namespace（payment_gate）：require_payment_for_dispatch
-- 預設不入 active config → assert_payment_gate fallback 不擋；業主要開時走 config 上版治理。
INSERT INTO saas.config_namespace (code, description, json_schema, owner_role_codes)
VALUES ('payment_gate', 'CR-0070 派工前付款閘（PAY-01）',
        '{"type": "object", "properties": {"require_payment_for_dispatch": {"type": "boolean"}}}'::jsonb,
        '{}')
ON CONFLICT (code) DO NOTHING;
