-- ═══════════════════════════════════════════════════════════════════════════
-- 097-requote-requests.sql — OHS 現場報價修正 command 通道(WBS 2.4.3/CR-0144)
--
-- ADR-027:技師平台只發 command(diff 草稿不含金額),品牌報價引擎為唯一權威。
-- 本表 = command 冪等記錄:UNIQUE(tenant_id, request_id) → 重送回放同一結果;
-- 同工單已有 open(received/quoted)修正 → 409(進行中衝突)。
-- 落庫:品牌庫。
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS requote_requests (
    id               BIGSERIAL PRIMARY KEY,
    tenant_id        UUID NOT NULL,
    request_id       VARCHAR(100) NOT NULL,          -- 冪等鍵(技師平台產生)
    work_order_id    UUID NOT NULL REFERENCES work_orders(id) ON DELETE CASCADE,
    technician_id    UUID NOT NULL,                  -- 須等於工單 assignee(403 否則)
    reason           VARCHAR(30) NOT NULL
        CHECK (reason IN ('estimate_error', 'scope_add', 'scope_change')),
    item_diffs       JSONB NOT NULL,                 -- 項目/料件異動草稿(不含金額)
    initiated_via    VARCHAR(30) NOT NULL DEFAULT 'technician_command'
        CHECK (initiated_via IN ('technician_command', 'cs_fallback')),  -- 降級標記
    status           VARCHAR(20) NOT NULL DEFAULT 'received'
        CHECK (status IN ('received', 'quoted', 'closed')),
    created_quote_id UUID,                           -- v+1 quote(supersedes 串鏈)
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, request_id)
);

-- 同工單 open 修正查詢(409 衝突判定)
CREATE INDEX IF NOT EXISTS idx_requote_requests_wo_open
    ON requote_requests (work_order_id)
    WHERE status IN ('received', 'quoted');
