-- ============================================================================
-- 018-line-bindings.sql — CR-0013 Stage 1: LINE 主動綁定 (HD-03=b)
-- ============================================================================
-- 目的：消費者主動把 LINE userId 綁到既有 users 帳號的審計表。
--
-- HD-03=(b) 決議：客戶主動綁（rich menu「綁定」流程 + 新表 line_bindings）
--   - 不取代 users.line_user_id（FR-0044 既有自動關聯仍生效）
--   - 區分 bind_method='auto' (wo 建立時自動同步) vs 'manual' (rich menu 觸發)
--   - 保留 unbound_at 給日後解綁需求
--   - link_token 一次性，TTL 由 service 端 (24h 對齊 HD-04=a)
-- ============================================================================

CREATE TABLE IF NOT EXISTS saas.line_binding (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid        NOT NULL REFERENCES saas.tenant(id),
  user_id             uuid        NOT NULL,           -- users.id（公共 user 表 plain ref）
  line_user_id        text        NOT NULL,

  bind_method         text        NOT NULL CHECK (bind_method IN ('auto', 'manual')),
  -- auto = wo 建立時 customers.line_user_id 自動填入；manual = rich menu 啟動的 link_token 流程

  bound_at            timestamptz NOT NULL DEFAULT NOW(),
  unbound_at          timestamptz NULL,               -- 解綁時間（軟刪）

  -- manual binding 用：link_token hash（避免明文存 token）
  link_token_hash     text        NULL,

  -- 帶 source LINE userId 反查；查 binding 用
  created_at          timestamptz NOT NULL DEFAULT NOW(),
  updated_at          timestamptz NOT NULL DEFAULT NOW(),

  -- 同 tenant 內一個 LINE userId 只能綁一個 active user
  -- 解綁後 (unbound_at IS NOT NULL) 允許重新綁定（partial unique index）
  CONSTRAINT line_binding_user_consistent
    CHECK (user_id IS NOT NULL AND line_user_id IS NOT NULL)
);

-- 同 tenant + line_user_id active 唯一（解綁後允許新建）
CREATE UNIQUE INDEX IF NOT EXISTS line_binding_tenant_line_unique_active
  ON saas.line_binding(tenant_id, line_user_id)
  WHERE unbound_at IS NULL;

-- 反查 user → active binding（user 可能多 LINE 帳號但同一時間只一個 active）
CREATE INDEX IF NOT EXISTS line_binding_user_active_idx
  ON saas.line_binding(tenant_id, user_id)
  WHERE unbound_at IS NULL;

-- link_token 查詢用（主動 binding 流程）
CREATE INDEX IF NOT EXISTS line_binding_token_hash_idx
  ON saas.line_binding(link_token_hash)
  WHERE link_token_hash IS NOT NULL;

COMMENT ON TABLE saas.line_binding IS
  'CR-0013 HD-03=b 消費者 LINE 主動綁定審計表。'
  '不取代 users.line_user_id（FR-0044 自動關聯路徑仍生效），'
  '本表額外記錄 manual binding（rich menu「綁定」流程）與 audit。';

COMMENT ON COLUMN saas.line_binding.bind_method IS
  '''auto'' = wo 建立時 customers.line_user_id 自動同步；'
  '''manual'' = rich menu 啟動的 link_token 24h 一次性流程';
