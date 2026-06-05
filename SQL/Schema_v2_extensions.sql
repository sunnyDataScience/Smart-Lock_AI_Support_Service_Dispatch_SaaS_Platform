-- ============================================================================
-- Smart Lock AI Support & Service Dispatch SaaS Platform
-- Schema V2.0 Extensions
-- ============================================================================
--
-- GAP Coverage:
--   [GAP #16] Dynamic RBAC: roles, permissions, role_permissions
--   [GAP #17] Inventory Management: inventory_items, inventory_transactions
--   [GAP #19] Electronic Signature: digital_signatures
--   [GAP #7]  Real-time Messaging: chat_messages
--   [GAP #13] Audit Log: audit_events (structured taxonomy)
--
-- Dependencies: Schema.sql must be applied first
-- ============================================================================


-- ============================================================================
-- [GAP #16] Dynamic RBAC (Role-Based Access Control)
-- ============================================================================
--
-- Extends the static 4-role system (line_user, admin, reviewer, technician)
-- to a dynamic, configurable RBAC with 6+ roles and granular permissions.
-- users.role VARCHAR remains as-is but references roles.name.
-- ============================================================================

CREATE TABLE IF NOT EXISTS roles (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                VARCHAR(50) UNIQUE NOT NULL,        -- machine-readable: 'admin', 'brand_oem'
    display_name        VARCHAR(100) NOT NULL,              -- human-readable: '系統管理員'
    description         TEXT,
    is_system           BOOLEAN DEFAULT FALSE,              -- system roles cannot be deleted
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  roles IS '動態角色定義表 (GAP #16)：可配置的 RBAC 角色，擴展原有靜態 4 角色';
COMMENT ON COLUMN roles.is_system IS '系統內建角色 (line_user, admin 等) 不可刪除';

CREATE TRIGGER trg_roles_updated_at
    BEFORE UPDATE ON roles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


CREATE TABLE IF NOT EXISTS permissions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resource            VARCHAR(100) NOT NULL,              -- 'work_orders', 'invoices', 'users', etc.
    action              VARCHAR(50) NOT NULL,               -- 'create', 'read', 'update', 'delete', 'export', 'approve'
    description         TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (resource, action)
);

COMMENT ON TABLE  permissions IS '權限定義表：resource + action 組合定義一個具體權限';
COMMENT ON COLUMN permissions.resource IS '資源類型：users, conversations, work_orders, invoices, refunds, complaints, reports, settings';


-- ⚠️ role_permissions 正典在 SQL/Schema_rbac_dynamic.sql（F-019 動態 RBAC：
--    tenant_id / role_name / permission_code / granted；role_service.py 與 rbac_v2 實際使用）。
--    原本此處的 relational 多對多 junction（role_id / permission_id）與正典**同名衝突**：
--    同名 CREATE TABLE 誰先 apply 誰贏，relational 先建會讓 role_service 寫入報
--    `column "permission_code" does not exist`，打爆動態 RBAC 寫入路徑（legacy + v2 同壞）。
--    全 codebase 無任何查詢使用此 relational 版（grep 證實 0 ref、無 seed、無 inbound FK）
--    → 移除以消除 schema 衝突。roles / permissions 兩張定義表保留（未來若改回 relational 可重用）。
--    詳見 docs/_audit/spec-code-gap-audit-2026-06-01.md 衍生發現。


-- Seed default roles
INSERT INTO roles (name, display_name, description, is_system) VALUES
    ('line_user',    'LINE 消費者',     '透過 LINE 使用服務的一般消費者',                   TRUE),
    ('admin',        '系統管理員',      '總部管理員，擁有完整系統存取權限',                  TRUE),
    ('reviewer',     'SOP 審核員',     '負責審核 SOP 草稿與品質管理',                     TRUE),
    ('technician',   '維修技師',       '執行現場維修與安裝的技師',                         TRUE),
    ('dispatcher',   '派工員',         'V2.0 獨立派工角色：負責派遣工單給技師、追蹤派工狀態（F-004 / F-019）', TRUE),
    ('brand_oem',    '品牌原廠',       '品牌原廠人員，查看保固統計與上傳品牌資料',           FALSE),
    ('distributor',  '經銷商',         '經銷商/服務中心，管理區域營運',                     FALSE),
    ('super_admin',  '超級管理員',      '系統擁有者，完整存取 + 系統設定',                  TRUE)
ON CONFLICT (name) DO NOTHING;

-- Seed default permissions
INSERT INTO permissions (resource, action, description) VALUES
    -- Users
    ('users', 'create', '建立使用者帳號'),
    ('users', 'read', '查看使用者資料'),
    ('users', 'update', '修改使用者資料'),
    ('users', 'delete', '刪除使用者帳號'),
    -- Conversations
    ('conversations', 'read', '查看對話紀錄'),
    ('conversations', 'export', '匯出對話紀錄'),
    -- Work Orders
    ('work_orders', 'create', '建立工單'),
    ('work_orders', 'read', '查看工單'),
    ('work_orders', 'update', '修改工單'),
    ('work_orders', 'delete', '刪除工單'),
    ('work_orders', 'approve', '核准工單'),
    ('work_orders', 'export', '匯出工單'),
    -- Invoices
    ('invoices', 'create', '建立發票'),
    ('invoices', 'read', '查看發票'),
    ('invoices', 'update', '修改發票'),
    ('invoices', 'export', '匯出發票'),
    -- Refunds
    ('refunds', 'create', '申請退款'),
    ('refunds', 'read', '查看退款'),
    ('refunds', 'approve', '核准退款'),
    -- Complaints
    ('complaints', 'create', '提交客訴'),
    ('complaints', 'read', '查看客訴'),
    ('complaints', 'update', '處理客訴'),
    -- Reports
    ('reports', 'read', '查看報表'),
    ('reports', 'export', '匯出報表'),
    -- Settings
    ('settings', 'read', '查看系統設定'),
    ('settings', 'update', '修改系統設定')
ON CONFLICT (resource, action) DO NOTHING;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions (role_id);
CREATE INDEX IF NOT EXISTS idx_role_permissions_perm ON role_permissions (permission_id);


-- ============================================================================
-- [GAP #17] Inventory Management
-- ============================================================================

CREATE TABLE IF NOT EXISTS inventory_items (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    part_number         VARCHAR(100) UNIQUE NOT NULL,       -- 料號: 'BAT-AA-001'
    name                VARCHAR(255) NOT NULL,              -- 品名: 'AA 鹼性電池 (4入)'
    category            VARCHAR(100) NOT NULL,              -- 類別: 'battery', 'lock_body', 'circuit_board', 'screw', 'side_panel', 'other'
    brand_compatibility JSONB,                              -- 適用品牌清單: ["Yale", "Samsung", "Philips"]
    unit_cost           FLOAT NOT NULL DEFAULT 0,           -- 單位成本 (TWD)
    quantity_on_hand    INTEGER NOT NULL DEFAULT 0,         -- 現有庫存量
    reorder_point       INTEGER NOT NULL DEFAULT 5,         -- 安全庫存量 (低於此值觸發警示)
    supplier            VARCHAR(255),                       -- 供應商名稱
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  inventory_items IS '庫存品項表 (GAP #17)：追蹤零件與材料的庫存狀態';
COMMENT ON COLUMN inventory_items.reorder_point IS '安全庫存量，quantity_on_hand 低於此值時觸發補貨警示';

CREATE TRIGGER trg_inventory_items_updated_at
    BEFORE UPDATE ON inventory_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


CREATE TABLE IF NOT EXISTS inventory_transactions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    item_id             UUID NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
    transaction_type    VARCHAR(50) NOT NULL,               -- 'purchase', 'consume', 'return', 'adjust'
    quantity            INTEGER NOT NULL,                   -- 正值=入庫, 負值=出庫
    work_order_id       UUID REFERENCES work_orders(id),    -- 關聯工單 (消耗時)
    technician_id       UUID REFERENCES technicians(id),    -- 關聯技師
    notes               TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  inventory_transactions IS '庫存異動紀錄表：追蹤每次入庫/出庫/退貨/調整';
COMMENT ON COLUMN inventory_transactions.quantity IS '正值表示入庫 (purchase/return)，負值表示出庫 (consume)';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_inv_items_category ON inventory_items (category);
CREATE INDEX IF NOT EXISTS idx_inv_items_low_stock ON inventory_items (quantity_on_hand, reorder_point)
    WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_inv_txn_item ON inventory_transactions (item_id);
CREATE INDEX IF NOT EXISTS idx_inv_txn_work_order ON inventory_transactions (work_order_id)
    WHERE work_order_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_inv_txn_created ON inventory_transactions (created_at DESC);


-- ============================================================================
-- [GAP #19] Electronic Signature (Digital Signatures)
-- ============================================================================

CREATE TABLE IF NOT EXISTS digital_signatures (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    signer_id           UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    signer_role         VARCHAR(50) NOT NULL,               -- 簽署者角色: 'line_user', 'technician', 'admin'
    document_type       VARCHAR(100) NOT NULL,              -- 文件類型: 'work_order_completion', 'appearance_change', 'refund_acceptance', 'scope_change'
    document_id         UUID NOT NULL,                      -- 關聯文件 ID (work_order_id, consent_id, refund_id, etc.)
    signature_method    VARCHAR(50) NOT NULL,               -- 簽署方式: 'line_confirmation', 'digital_signature', 'verbal_recorded'
    signature_data      JSONB,                              -- 簽名資料:
                                                            -- line_confirmation: {message_id, confirmed_at}
                                                            -- digital_signature: {image_base64, canvas_dimensions}
                                                            -- verbal_recorded: {recording_url, duration_seconds}
    integrity_hash      VARCHAR(128),                       -- SHA-256 of (signer_id + document_type + document_id + signed_at)
    ip_address          VARCHAR(45),                        -- IPv4 or IPv6
    user_agent          TEXT,                               -- Browser/App User-Agent
    signed_at           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  digital_signatures IS '電子簽收表 (GAP #19)：記錄各類文件的數位簽署紀錄，支援法律不可否認性';
COMMENT ON COLUMN digital_signatures.integrity_hash IS 'SHA-256 完整性雜湊，用於驗證簽署紀錄未被篡改';
COMMENT ON COLUMN digital_signatures.signature_method IS '簽署方式：LINE 確認按鈕 (V1.0)、畫布數位簽名 (V2.0)、口頭錄音 (legacy)';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_digsig_signer ON digital_signatures (signer_id);
CREATE INDEX IF NOT EXISTS idx_digsig_document ON digital_signatures (document_type, document_id);
CREATE INDEX IF NOT EXISTS idx_digsig_signed_at ON digital_signatures (signed_at DESC);


-- ============================================================================
-- [GAP #7] Real-time Chat Messages (Admin-Technician Communication)
-- ============================================================================

CREATE TABLE IF NOT EXISTS chat_messages (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id       UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    sender_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sender_role         VARCHAR(50) NOT NULL,               -- 'admin', 'technician', 'system'
    msg_type            VARCHAR(50) NOT NULL DEFAULT 'text',-- 'text', 'image', 'location', 'system_notification'
    content             TEXT NOT NULL,                       -- 文字內容 or JSON (image: {url}, location: {lat, lng})
    metadata            JSONB,                              -- 擴展資訊
    is_read             BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  chat_messages IS '即時通訊訊息表 (GAP #7)：工單內管理員與技師的即時通訊紀錄';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chat_msg_work_order ON chat_messages (work_order_id, created_at);
CREATE INDEX IF NOT EXISTS idx_chat_msg_sender ON chat_messages (sender_id);
CREATE INDEX IF NOT EXISTS idx_chat_msg_unread ON chat_messages (work_order_id, is_read)
    WHERE is_read = FALSE;


-- ============================================================================
-- [GAP #13] Structured Audit Events
-- ============================================================================
--
-- Extends the basic audit_log table with structured event taxonomy.
-- Seven event types with configurable retention periods.
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_events (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type          VARCHAR(50) NOT NULL,               -- 'conversation', 'tool_invocation', 'safety_gate',
                                                            -- 'escalation', 'dispatch_decision', 'financial_action', 'admin_action'
    actor_id            UUID REFERENCES users(id) ON DELETE SET NULL,
    actor_role          VARCHAR(50),                        -- actor's role at time of event
    action              VARCHAR(100) NOT NULL,              -- specific action: 'create_refund', 'approve_dispatch', etc.
    target_type         VARCHAR(100),                       -- 'work_order', 'refund_request', 'user', etc.
    target_id           UUID,                               -- ID of the affected entity
    payload             JSONB,                              -- event-specific data (PII should be masked)
    ip_address          VARCHAR(45),
    retention_days      INTEGER NOT NULL DEFAULT 90,        -- auto-calculated from event_type
    expires_at          TIMESTAMP WITH TIME ZONE,           -- computed: created_at + retention_days
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  audit_events IS '結構化稽核事件表 (GAP #13)：7 種事件類型 + 依類型的保留期限';
COMMENT ON COLUMN audit_events.retention_days IS '保留天數：conversation=90, safety_gate/escalation=365, dispatch=730, financial/admin=2555';
COMMENT ON COLUMN audit_events.payload IS '事件資料 JSON，PII 欄位應在寫入前遮罩處理';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_events (event_type);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_events (actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_events (target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_expires ON audit_events (expires_at)
    WHERE expires_at IS NOT NULL;

-- ----------------------------------------------------------------------------
-- 9. 負面情緒告警（sentiment_alerts）— customer_service 模組
-- ----------------------------------------------------------------------------
-- AI 在對話中偵測到 negative / very_negative 後寫入；後台監看頁逐筆處理（acknowledged/resolved）。
-- 對應 OpenAPI: SentimentAlert / listSentimentAlerts / updateSentimentAlert。
CREATE TABLE IF NOT EXISTS sentiment_alerts (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id     UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    consumer_message    TEXT,                                                       -- 觸發本次告警的客戶訊息片段
    sentiment_label     VARCHAR(20) NOT NULL,                                       -- negative / very_negative / neutral / positive
    confidence          NUMERIC(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    detected_keywords   TEXT[],                                                     -- 命中的關鍵字陣列
    problem_card_id     UUID REFERENCES problem_cards(id) ON DELETE SET NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',                     -- pending / acknowledged / resolved
    notified_admin_ids  UUID[],                                                     -- 已被通知的管理員清單
    admin_note          VARCHAR(1000),
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_sentiment_label CHECK (sentiment_label IN ('negative','very_negative','neutral','positive')),
    CONSTRAINT chk_sentiment_status CHECK (status IN ('pending','acknowledged','resolved'))
);

COMMENT ON TABLE  sentiment_alerts IS '負面情緒告警：AI 偵測 → 後台逐筆處理 (pending → acknowledged → resolved)';
COMMENT ON COLUMN sentiment_alerts.consumer_message IS '觸發本次告警的客戶訊息（為避免複製整段對話，存擷取片段即可）';
COMMENT ON COLUMN sentiment_alerts.detected_keywords IS '命中關鍵字快照，供後台快速分流（如「退費」「投訴」「律師」）';

-- Indexes — 後台多按 status + created_at DESC 翻頁
CREATE INDEX IF NOT EXISTS idx_sentiment_alerts_status_created ON sentiment_alerts (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sentiment_alerts_conversation  ON sentiment_alerts (conversation_id);
CREATE INDEX IF NOT EXISTS idx_sentiment_alerts_created_desc  ON sentiment_alerts (created_at DESC, id DESC);

-- ----------------------------------------------------------------------------
-- 10. 會計傳票（vouchers）— accounting 模組
-- ----------------------------------------------------------------------------
-- 雙分錄會計憑證：每筆對帳 / 結算 / 退款 / 發票會落在一筆 Voucher。
-- 對應 OpenAPI: Voucher / listVouchers / exportVoucher。
-- 設計：related_entity_type + related_entity_id 弱關聯（不下 FK）以保留
--       帳本即使來源紀錄被刪也仍可審計；amount 採 NUMERIC(14,2) 避免浮點誤差。
CREATE TABLE IF NOT EXISTS vouchers (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id           UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001'::uuid,
    voucher_number      VARCHAR(50) NOT NULL,                                 -- 帳本流水號 e.g. V20260429-0001
    related_entity_type VARCHAR(20),                                          -- reconciliation/settlement/refund/invoice
    related_entity_id   UUID,
    debit_account       VARCHAR(50) NOT NULL,                                 -- 借方科目編號（e.g. 1101 銀行存款）
    credit_account      VARCHAR(50) NOT NULL,                                 -- 貸方科目編號（e.g. 4001 服務收入）
    amount              NUMERIC(14,2) NOT NULL,
    currency            VARCHAR(8) NOT NULL DEFAULT 'TWD',
    posting_date        DATE NOT NULL,                                        -- 入帳日（會計期間維度）
    memo                TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_voucher_entity_type CHECK (
        related_entity_type IS NULL OR
        related_entity_type IN ('reconciliation','settlement','refund','invoice')
    ),
    CONSTRAINT uniq_voucher_number_tenant UNIQUE (tenant_id, voucher_number)
);

COMMENT ON TABLE  vouchers IS '會計傳票（雙分錄）：對應對帳 / 結算 / 退款 / 發票事件，匯出 PDF 用於外部會計系統對接';
COMMENT ON COLUMN vouchers.related_entity_type IS '關聯實體類型，使用弱關聯（不下 FK）以保留審計追溯性';
COMMENT ON COLUMN vouchers.amount IS '金額；NUMERIC(14,2) 避免浮點誤差，支援負數做沖銷';

CREATE INDEX IF NOT EXISTS idx_vouchers_tenant_posting   ON vouchers (tenant_id, posting_date DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_vouchers_related_entity   ON vouchers (related_entity_type, related_entity_id);
CREATE INDEX IF NOT EXISTS idx_vouchers_voucher_number   ON vouchers (voucher_number);


-- ============================================================================
-- [Phase 1.78] family_reviews — SOP 草稿家族覆核
-- ============================================================================
-- 對應 OpenAPI: FamilyReview / createFamilyReview / listFamilyReviews / listPendingFamilyReviews。
-- 設計：sop_drafts.status='approved'（管理員初審通過）後進入待家族覆核佇列；
--       一筆 sop_draft 僅能對應一筆 family_review（unique），重複提交回 409。
--       action 二元：approved / rejected；rejected 不退回 sop_drafts.status，僅留覆核紀錄。
CREATE TABLE IF NOT EXISTS family_reviews (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001'::uuid,
    sop_draft_id    UUID NOT NULL REFERENCES sop_drafts(id) ON DELETE CASCADE,
    action          VARCHAR(20) NOT NULL,
    reviewer_id     UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    comment         TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_family_review_action CHECK (action IN ('approved','rejected')),
    CONSTRAINT uniq_family_review_draft UNIQUE (sop_draft_id)
);

COMMENT ON TABLE  family_reviews IS '家族覆核紀錄：管理員初審通過的 SOP 草稿由家族（代理商/品牌端）二級覆核';
COMMENT ON COLUMN family_reviews.sop_draft_id IS '一筆草稿僅一筆覆核（uniq），重複提交視為衝突';
COMMENT ON COLUMN family_reviews.action IS '覆核結果：approved（通過） | rejected（退回）';

CREATE INDEX IF NOT EXISTS idx_family_reviews_tenant_created ON family_reviews (tenant_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_family_reviews_action         ON family_reviews (tenant_id, action, created_at DESC);


-- ============================================================================
-- llm_usage_log (取代 Opik 角色：token 使用量 + 回覆延遲度量)
-- ============================================================================
--
-- 每筆紀錄對應一次 LLM 呼叫；ReAct agent 一次 ainvoke 內部多次 LLM 呼叫會逐筆寫入。
-- DDL 同步於 agent/storage/postgres_impl.py:build_postgres_storage()，啟動時會以
-- CREATE TABLE IF NOT EXISTS 自動建立。
-- ============================================================================

CREATE TABLE IF NOT EXISTS llm_usage_log (
    id              BIGSERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id         TEXT NOT NULL,
    turn_id         TEXT,                                       -- 同一 user turn 多次 LLM 呼叫共用 uuid
    call_site       VARCHAR(50) NOT NULL,                       -- react_agent_step | memory_compression |
                                                                 -- output_validator | profile_extraction | quality_judge
    model           VARCHAR(100) NOT NULL,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    total_tokens    INTEGER,
    latency_ms      INTEGER,
    success         BOOLEAN NOT NULL DEFAULT TRUE,
    error_type      VARCHAR(50),                                -- timeout | api_error | <ExceptionClass>
    user_question   TEXT,                                       -- 使用者問題原文（react_agent 為當輪 user message；
                                                                 -- 其他 call_site 為餵給 LLM 的提示主文）
    ai_reply        TEXT,                                       -- AI 回覆原文（AIMessage.content / judge verdict JSON）
    metadata        JSONB                                       -- step_index、tool_calls、thread_id 等結構化欄位
);

-- 既有資料表升級
ALTER TABLE llm_usage_log ADD COLUMN IF NOT EXISTS user_question TEXT;
ALTER TABLE llm_usage_log ADD COLUMN IF NOT EXISTS ai_reply      TEXT;

COMMENT ON TABLE  llm_usage_log IS 'LLM 呼叫度量資料（取代 Opik token + latency 紀錄角色）';
COMMENT ON COLUMN llm_usage_log.turn_id IS '同一 user turn 內多次 LLM 呼叫的關聯鍵（例如 ReAct 多 step）';
COMMENT ON COLUMN llm_usage_log.call_site IS '呼叫情境，用於分桶聚合成本';
COMMENT ON COLUMN llm_usage_log.user_question IS '使用者問題原文，不截斷不遮罩（與 audit_log.content 一致）';
COMMENT ON COLUMN llm_usage_log.ai_reply IS 'AI 回覆原文，不截斷不遮罩；對外展示前再呼叫 _mask_pii()';
COMMENT ON COLUMN llm_usage_log.metadata IS '結構化擴充欄位；禁止寫入訊息原文以避免 PII 洩漏';

CREATE INDEX IF NOT EXISTS idx_llm_usage_timestamp ON llm_usage_log (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_llm_usage_user_id   ON llm_usage_log (user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_llm_usage_call_site ON llm_usage_log (call_site, timestamp DESC);

-- ============================================================================
-- 12. LINE Flex push outbox（line_push_outbox）— CR-0017 LINE Flex 重建
-- ============================================================================
-- 業主裁決 (2026-06-05):
--   HD-1: 階段化獨立 LINE bot service
--   HD-2: Outbox table + worker pattern
--   HD-3: api/templates/ Python flex builders
-- 設計：
--   service 端 INSERT outbox row（push_kind + target + payload）；
--   worker process poll status='pending' → render Flex template → push LINE
--   → 結果寫 status='sent' | 'failed' + retry_count + last_error。
--   失敗自動 retry（exponential backoff），超過 max_attempts 標 'dead'。
CREATE TABLE IF NOT EXISTS line_push_outbox (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id       UUID NOT NULL,
    push_kind       VARCHAR(40) NOT NULL,           -- 'reschedule_proposal' | 'scope_change_proposal' | 'schedule_conflict' | ...
    target_line_id  VARCHAR(40),                    -- LINE userId (Uxxxx...) — 可 NULL（worker 從 reference 反查）
    reference_id    UUID,                           -- 對應業務 row（reschedule_proposal.id / scope_changes.id / work_orders.id 等）
    reference_table VARCHAR(40),                    -- 'saas.reschedule_proposal' / 'scope_changes' / 'work_orders' ...
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb, -- 給 Flex builder 的 data
    status          VARCHAR(20) NOT NULL DEFAULT 'pending', -- 'pending' | 'sent' | 'failed' | 'dead'
    attempts        INTEGER NOT NULL DEFAULT 0,
    max_attempts    INTEGER NOT NULL DEFAULT 5,
    next_attempt_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- worker poll 條件：status='pending' AND next_attempt_at <= NOW()
    last_error      TEXT,
    sent_at         TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_push_status CHECK (status IN ('pending','sent','failed','dead')),
    CONSTRAINT chk_push_attempts_nonneg CHECK (attempts >= 0)
);

COMMENT ON TABLE  line_push_outbox IS 'LINE Flex push outbox（CR-0017）：service 寫 row → worker poll 取出 → render Flex → push LINE → 寫狀態回';
COMMENT ON COLUMN line_push_outbox.push_kind IS '推送類型，決定走哪個 Flex builder（reschedule_proposal/scope_change_proposal/schedule_conflict）';
COMMENT ON COLUMN line_push_outbox.next_attempt_at IS 'worker 重試排程點：status=pending AND next_attempt_at <= NOW() 才取出';
COMMENT ON COLUMN line_push_outbox.payload IS 'Flex builder 需要的 data（如 proposed_slots、scope_items、conflict_wo_ids）';

-- Worker poll 主索引
CREATE INDEX IF NOT EXISTS idx_outbox_pending_next
    ON line_push_outbox (next_attempt_at)
    WHERE status = 'pending';
-- tenant + kind 過濾（debug / 監控）
CREATE INDEX IF NOT EXISTS idx_outbox_tenant_kind
    ON line_push_outbox (tenant_id, push_kind, created_at DESC);
-- reference 反查（從業務 row 找出 push 歷史）
CREATE INDEX IF NOT EXISTS idx_outbox_reference
    ON line_push_outbox (reference_table, reference_id)
    WHERE reference_id IS NOT NULL;
