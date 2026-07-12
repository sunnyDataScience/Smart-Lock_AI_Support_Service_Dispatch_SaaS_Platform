-- ═══════════════════════════════════════════════════════════════════════════
-- 106-skill-revisions.sql — Skill 熱更新與品牌後台編輯（CR-0167 / LiveSkill）
--
-- WHY：
--   Skill（SKILL.md + references/）原本隨 image 烤入（agent/Dockerfile COPY agent/），
--   載入路徑寫死 lockcore/agent/skills.py:BUILTIN_SKILLS_DIR。改一行知識 = 重佈 agent。
--   業主需求：skill 持續迭代且為 agent 回答依據、品牌後台能編輯查看、人工/自動更新即時生效。
--   HD-1 裁決：知識所有權歸品牌租戶（開通 LINE 客服才有此功能），完整權限＋版控。
--
-- WHAT：
--   把 skill SSOT 從 image 改為「品牌庫 DB → agent workspace overlay 物化同步」。
--   1. saas.skill_revision — 版本快照（append-only 版控）；files jsonb = {rel_path: content}。
--   2. saas.skill_bundle   — 每租戶目前發佈版本 stamp（SkillSync 只輪詢這張做變更偵測）。
--   3. saas.skill_audit_log — 編輯/發佈/回滾審計（比照 saas.kb_audit_log）。
--
-- 落庫：品牌庫（dispatch surface；agent SkillSync 以 POSTGRES_URI 直讀——HD-3=a）。
-- idempotent：全 CREATE TABLE/INDEX IF NOT EXISTS（可重套，scratch 驗證後標記於 REGISTRY）。
--
-- 語意：
--   - 發佈（publishSkill）：目標 revision status='published'，同 skill 舊 published → 'retired'，
--     skill_bundle.published_stamp += 1。回滾（rollbackSkill）＝舊 version 重新 publish（同機制）。
--   - SkillSync：輪詢 published_stamp，變了才全量拉 status='published' 的 revision 物化到 workspace。
--   - 「至多一個 published/(tenant,skill)」由 partial unique index 硬保證。
-- ═══════════════════════════════════════════════════════════════════════════

-- ── 版本快照（append-only 版控核心）──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saas.skill_revision (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid        NOT NULL,

    -- skill 目錄名（= workspace/skills/<skill_name>/）；Agent Skills 標準目錄名規則
    skill_name      text        NOT NULL,

    -- 單調遞增版本號（per tenant+skill）；版控與 diff 的基準
    version         integer     NOT NULL,

    -- 檔案樹快照：{ "SKILL.md": "...", "references/Brand/Model.md": "..." }
    -- SKILL.md 必存在（發佈驗證閘強制）；references/* 為 read_file 按需讀的知識素材。
    files           jsonb       NOT NULL,

    -- 生命週期：draft（草稿）→ published（生效中）→ retired（曾發佈、被新版取代）
    status          text        NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'published', 'retired')),

    -- 內容來源：brand_edit=品牌後台人工編輯；pipeline_ingest=knowledge-pipeline 自動汲取；
    -- factory_seed=首次編輯 builtin skill 時以出廠內容 seed 的 fork 起點（HD-1 治理註記）。
    source          text        NOT NULL DEFAULT 'brand_edit'
                    CHECK (source IN ('brand_edit', 'pipeline_ingest', 'factory_seed')),

    note            text        NULL,       -- 版本備註（發佈說明 / 汲取來源摘要）
    created_by      uuid        NULL,       -- actor（pipeline_ingest 時為 NULL）
    created_at      timestamptz NOT NULL DEFAULT NOW(),
    published_at    timestamptz NULL,       -- 發佈時間（draft 為 NULL）

    UNIQUE (tenant_id, skill_name, version)
);

-- 至多一個 published/(tenant,skill)——發佈流程的核心不變式（硬保證，非靠 app 邏輯）
CREATE UNIQUE INDEX IF NOT EXISTS uq_skill_revision_published
    ON saas.skill_revision (tenant_id, skill_name)
    WHERE status = 'published';

-- SkillSync 拉取路徑：WHERE tenant_id=? AND status='published'
CREATE INDEX IF NOT EXISTS idx_skill_revision_published
    ON saas.skill_revision (tenant_id, status)
    WHERE status = 'published';

-- 版本歷史（diff / rollback 選單）：最新在前
CREATE INDEX IF NOT EXISTS idx_skill_revision_history
    ON saas.skill_revision (tenant_id, skill_name, version DESC);

COMMENT ON TABLE  saas.skill_revision IS
'CR-0167：skill 版本快照（append-only 版控）；files jsonb={rel_path:content}，含 SKILL.md 與 references/*';
COMMENT ON COLUMN saas.skill_revision.status IS
'draft→published→retired；至多一個 published/(tenant,skill) 由 uq_skill_revision_published 保證';

-- ── 租戶目前發佈版本 stamp（SkillSync 輪詢對象）───────────────────────────────
CREATE TABLE IF NOT EXISTS saas.skill_bundle (
    tenant_id        uuid        PRIMARY KEY,
    -- 每次發佈 / 回滾 +1；SkillSync 比對此值變化決定是否全量重拉（60s TTL，HD-4=a）
    published_stamp  bigint      NOT NULL DEFAULT 0,
    updated_at       timestamptz NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE saas.skill_bundle IS
'CR-0167：每租戶目前發佈版本組 stamp；SkillSync 輪詢此 stamp 做變更偵測（HD-3 DB 直讀 / HD-4 60s）';

-- ── 審計（比照 saas.kb_audit_log）─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saas.skill_audit_log (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         uuid        NOT NULL,
    skill_name        text        NOT NULL,
    action            text        NOT NULL
                      CHECK (action IN ('create_draft', 'update_draft', 'publish',
                                        'rollback', 'retire', 'delete')),
    revision_version  integer     NULL,     -- 動作涉及的 version
    before_state      jsonb       NULL,     -- 操作前快照（create 時 NULL）
    after_state       jsonb       NULL,     -- 操作後快照（delete 時 NULL）
    actor_user_id     uuid        NULL,     -- pipeline_ingest 時 NULL
    actor_role        text        NULL,
    created_at        timestamptz NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_skill_audit_log_tenant_skill
    ON saas.skill_audit_log (tenant_id, skill_name, created_at DESC);

COMMENT ON TABLE saas.skill_audit_log IS
'CR-0167：skill 編輯/發佈/回滾審計；best-effort 寫入（失敗不阻擋主操作，比照 kb_audit_log）';
