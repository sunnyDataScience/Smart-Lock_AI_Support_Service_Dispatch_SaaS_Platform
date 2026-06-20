-- 071-notification-template-approval.sql
-- WHY（CR-0072 / TI-NOTIF-03 / BR-M16-03）：對客通知文案（報價/付款/派工/延遲/完工/RMA/退款）
--   原無模板、無核准 gate —— push_notification 直發、CR-0062 _auto_notify 也直發。BR-M16-03
--   紅線要求「對客 templated 訊息須主管核准後才可發送」。
-- WHAT：notification_template 表（status pending_approval→approved 核准 gate）+ notifications
--   +template_id 追溯。seed 7 類 approved 全域模板。
--   註：CR-0062 _auto_notify 的「內部員工事件 alert（被指派工單/待審核結案）」非對客 templated
--   訊息，維持直發不受 gate（兩條通道分流，避免破壞既有立即通知行為）。
CREATE TABLE IF NOT EXISTS notification_template (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id      UUID,                                  -- NULL = 全域共享主檔
    template_type  VARCHAR(40) NOT NULL
                     CHECK (template_type IN ('quote','payment','dispatch','delay','completion','rma','refund')),
    locale         TEXT NOT NULL DEFAULT 'zh-Hant',
    audience_role  TEXT NOT NULL DEFAULT 'customer',      -- customer/brand/accounting/internal
    title          TEXT NOT NULL,
    body_template  TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending_approval'
                     CHECK (status IN ('pending_approval','approved','rejected')),
    created_by     UUID,
    approved_by    UUID,
    approved_at    TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- 四眼：建立者不可自我核准（DB 硬防）
    CONSTRAINT notif_template_four_eyes
        CHECK (created_by IS NULL OR approved_by IS NULL OR created_by <> approved_by)
);
CREATE INDEX IF NOT EXISTS idx_notif_template_type_status
    ON notification_template (template_type, status);
COMMENT ON TABLE notification_template IS
  'CR-0072/TI-NOTIF-03：對客通知模板 + 主管核准 gate（pending_approval→approved 才可 send）';

ALTER TABLE notifications ADD COLUMN IF NOT EXISTS template_id UUID
    REFERENCES notification_template(id) ON DELETE SET NULL;

-- seed 七類 approved 全域模板（tenant_id NULL）；audience_role 分層供可見性測試
INSERT INTO notification_template (template_type, audience_role, title, body_template, status, approved_at)
SELECT * FROM (VALUES
    ('quote',      'customer',   '報價已產生',   '您的報價 {amount} 已產生，請查看。', 'approved', NOW()),
    ('payment',    'customer',   '付款提醒',     '您有一筆 {amount} 待付款。',         'approved', NOW()),
    ('dispatch',   'customer',   '師傅已派工',   '師傅 {tech} 將於 {time} 到府。',     'approved', NOW()),
    ('delay',      'customer',   '行程延遲通知', '抱歉，您的服務將延遲至 {time}。',     'approved', NOW()),
    ('completion', 'customer',   '完工通知',     '您的工單 {wo} 已完工。',             'approved', NOW()),
    ('rma',        'accounting', 'RMA 處理進度', 'RMA {rma} 狀態更新為 {status}。',     'approved', NOW()),
    ('refund',     'accounting', '退款通知',     '退款 {amount} 已處理。',             'approved', NOW())
) AS v(template_type, audience_role, title, body_template, status, approved_at)
WHERE NOT EXISTS (SELECT 1 FROM notification_template WHERE tenant_id IS NULL);
