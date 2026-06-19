-- ============================================================================
-- Smart Lock AI Support & Service Dispatch SaaS Platform
-- PostgreSQL Schema Definition
-- ============================================================================
--
-- 版本：v1.1
-- 更新日期：2026-02-25
-- 參考文件：
--   - docs/02_project_brief_and_prd.md          (PRD & User Stories)
--   - docs/05_architecture_and_design_document.md (§5.1 數據模型, §5.4 向量索引策略)
--   - docs/06_api_design_specification.md        (API Schema 定義)
--   - docs/08_project_structure_guide.md         (DDD 領域劃分)
--
-- 核心表格群組：
--   [1] users              — 使用者管理 (含 LINE Profile 儲存邏輯)
--   [2] conversations      — 對話 (Chats) Session 管理
--       messages           — 對話訊息記錄
--   [3] problem_cards      — 結構化問題診斷卡
--   [4] manuals            — 產品手冊管理
--       manual_chunks      — 手冊切片 (RAG 語義搜尋用)
--   [5] case_entries       — 案例庫 (三層引擎 L1 向量搜尋)
--   [6] sop_drafts         — SOP 草稿 (自進化知識庫)
--   [V2.0] technicians, work_orders, price_rules, invoices,
--          reconciliations, settlements
--   [V2.0] complaints, scope_changes, material_requests, disputes,
--          dispatch_logs, refund_requests, warranty_claims,
--          appearance_change_consents
--
-- 向量維度：768 (Google text-embedding-004)
-- 向量索引：HNSW (m=16, ef_construction=64, cosine similarity)
-- ============================================================================


-- ============================================================================
-- 系統準備與擴展套件
-- ============================================================================

-- 啟用 UUID 生成函數
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 啟用 pgvector 擴展套件 (用於 AI 向量相似度搜尋，依據 ADR-002)
CREATE EXTENSION IF NOT EXISTS vector;


-- ============================================================================
-- 自動更新 updated_at 的共用 Trigger Function
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- [1] 使用者管理 (User Management)
-- ============================================================================
--
-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ User Profile 儲存邏輯 (LINE ID, Display Name)                          │
-- ├─────────────────────────────────────────────────────────────────────────┤
-- │                                                                         │
-- │ ■ 首次互動 (Follow Event / 第一則訊息)：                                │
-- │   1. LINE Webhook 送來 source.userId (格式: U + 32 位 hex)              │
-- │   2. 呼叫 LINE Get Profile API 取得完整 Profile：                       │
-- │      - displayName  → users.display_name                                │
-- │      - pictureUrl   → users.picture_url                                 │
-- │      - statusMessage→ users.status_message                              │
-- │   3. INSERT INTO users，role = 'line_user'                              │
-- │                                                                         │
-- │ ■ 後續互動：                                                            │
-- │   1. 以 line_user_id 查詢 users 表 (WHERE line_user_id = ?)            │
-- │   2. 若 profile_updated_at 距今 > 24 小時，重新呼叫 Get Profile API     │
-- │      同步 display_name, picture_url, status_message                     │
-- │      (LINE 使用者可隨時更改顯示名稱與大頭貼)                            │
-- │   3. 更新 last_active_at 為當前時間                                     │
-- │                                                                         │
-- │ ■ L3 轉人工 / 派工時：                                                  │
-- │   AI 對話流程中向消費者收集 phone, email, address 等進階資訊            │
-- │   UPDATE users SET phone = ?, email = ?, address = ?                    │
-- │                                                                         │
-- │ ■ 管理員 / 技師帳號：                                                   │
-- │   透過 Admin Panel 建立，line_user_id 可為 NULL                         │
-- │   role 設定為 'admin' / 'reviewer' / 'technician'                       │
-- │                                                                         │
-- │ ■ line_user_id 特性：                                                   │
-- │   - 由 LINE Platform 產生，永久不變                                     │
-- │   - 格式固定為 U + 32 位十六進位字元 (共 33 字元)                       │
-- │   - 同一使用者在不同 LINE Official Account 下有不同 ID                  │
-- │   - 這是辨識消費者身分的唯一依據                                        │
-- └─────────────────────────────────────────────────────────────────────────┘

CREATE TABLE users (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- LINE Profile 欄位
    line_user_id        VARCHAR(255) UNIQUE,            -- LINE Platform User ID (U + 32 hex chars)
    display_name        VARCHAR(255),                   -- LINE 顯示名稱 (可被使用者隨時更改)
    picture_url         VARCHAR(512),                   -- LINE 大頭貼 URL
    status_message      VARCHAR(500),                   -- LINE 狀態訊息

    -- 進階聯絡資訊 (L3 轉人工或派工時收集)
    phone               VARCHAR(50),
    email               VARCHAR(255),
    address             TEXT,                           -- V2.0 派工用地址

    -- 系統欄位
    role                VARCHAR(50) NOT NULL DEFAULT 'line_user',
                        -- 'line_user'   : LINE 一般消費者
                        -- 'admin'       : 總部管理員
                        -- 'reviewer'    : SOP 審核員
                        -- 'technician'  : 維修技師 (V2.0)
                        -- 'dispatcher'  : 派工員 (V2.0；獨立角色，非 customer_service 子權限)
    is_active           BOOLEAN DEFAULT TRUE,           -- 帳號啟用狀態
    last_active_at      TIMESTAMP WITH TIME ZONE,       -- 最後互動時間 (每次對話時更新)
    profile_updated_at  TIMESTAMP WITH TIME ZONE,       -- LINE Profile 最後同步時間

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  users IS '使用者主表：統一管理 LINE 消費者、管理員、審核員、技師四種角色';
COMMENT ON COLUMN users.line_user_id IS 'LINE Platform 唯一使用者 ID (U + 32 hex)，消費者的唯一識別依據';
COMMENT ON COLUMN users.display_name IS 'LINE 顯示名稱，使用者可隨時變更，系統定期同步更新';
COMMENT ON COLUMN users.picture_url IS 'LINE 大頭貼圖片 URL，由 Get Profile API 取得';
COMMENT ON COLUMN users.profile_updated_at IS '最後一次從 LINE Get Profile API 同步 profile 資料的時間';

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- [2] 對話管理 (Conversations / Chats)
-- ============================================================================
--
-- 設計要點：
--   - 一次 Chat Session 對應一筆 Conversation 記錄
--   - 每個 Conversation 包含多個 Messages (1:N)
--   - 每個 Conversation 對應至多一張 ProblemCard (1:1)
--   - session_id 同時作為 Redis Session Cache 的 key
--   - 對話超時策略：30 分鐘無互動 → status 轉為 'expired'
-- ============================================================================

CREATE TABLE conversations (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id          VARCHAR(255) UNIQUE NOT NULL,   -- 對應 Redis session key

    status              VARCHAR(50) NOT NULL DEFAULT 'active',
                        -- 'active'     : 對話進行中
                        -- 'collecting' : 正在收集 ProblemCard 資訊
                        -- 'resolving'  : 三層解決引擎處理中
                        -- 'resolved'   : 已解決 (自助)
                        -- 'escalated'  : 已轉人工 / 已建立派工
                        -- 'expired'    : 對話超時 (30 分鐘無互動)
    channel             VARCHAR(50) DEFAULT 'line',     -- 來源管道: 'line', 'web', 'api'
    context             JSONB,                          -- 多輪對話上下文暫存
                                                        -- {intent, collected_fields, missing_fields,
                                                        --  conversation_summary, turn_count, ...}
    resolution_layer    VARCHAR(10),                    -- 最終解決層級: 'L1', 'L2', 'L3'
    user_feedback       VARCHAR(20),                    -- 消費者回饋: 'helpful', 'not_helpful'
    message_count       INTEGER DEFAULT 0,

    started_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at         TIMESTAMP WITH TIME ZONE,
    expired_at          TIMESTAMP WITH TIME ZONE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  conversations IS '對話 Session 主表 (Chats)：追蹤消費者與 AI 客服的完整對話生命週期';
COMMENT ON COLUMN conversations.session_id IS '對話 session 唯一識別碼，同步作為 Redis Session Cache 的 key';
COMMENT ON COLUMN conversations.context IS '多輪對話上下文 JSON，含已識別意圖、已收集欄位、缺失欄位等';
COMMENT ON COLUMN conversations.user_feedback IS '消費者對 AI 解決方案的回饋 (US-011)';

CREATE TRIGGER trg_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


CREATE TABLE messages (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id     UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,

    role                VARCHAR(50) NOT NULL,
                        -- 'user'       : 消費者訊息
                        -- 'assistant'  : AI 客服回覆
                        -- 'system'     : 系統訊息 (狀態變更、轉接通知等)
    content_type        VARCHAR(50) DEFAULT 'text',
                        -- 'text'       : 純文字
                        -- 'image'      : 圖片 (搭配 Vision AI 分析)
                        -- 'location'   : 位置資訊
                        -- 'flex'       : LINE Flex Message
    content             TEXT NOT NULL,                   -- 訊息內容 (文字 / JSON / URL)
    metadata            JSONB,                          -- 擴展資訊：
                                                        -- {token_usage, latency_ms, image_url,
                                                        --  vision_analysis, line_message_id, ...}

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  messages IS '對話訊息表：記錄每輪對話的完整內容、角色與元資訊';
COMMENT ON COLUMN messages.metadata IS '擴展元資訊 JSON：token 用量、回應延遲、圖片 URL、Vision 分析結果等';


-- ============================================================================
-- [3] 結構化問題診斷卡 (ProblemCard)
-- ============================================================================
--
-- 設計要點：
--   - 每個 Conversation 產生至多一張 ProblemCard (1:1，UNIQUE FK)
--   - AI 從多輪對話中漸進式擷取欄位 (brand, model, symptoms 等)
--   - completeness_score 反映關鍵欄位的填充率 (0.0 ~ 1.0)
--   - 當 ProblemCard 資訊充足 → 觸發三層解決引擎
--   - 生成後以 LINE Flex Message 展示給消費者確認 (US-006)
--
-- ProblemCard 必填欄位 (completeness 計算依據)：
--   brand + symptoms (至少這兩個欄位) → 可觸發解決引擎
--   model, location, door_status, network_status → 補充資訊，提升匹配精度
-- ============================================================================

CREATE TABLE problem_cards (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id     UUID UNIQUE REFERENCES conversations(id) ON DELETE CASCADE,

    -- 電子鎖資訊 (AI 從對話中擷取)
    brand               VARCHAR(100),                   -- 品牌: Yale, Samsung, Gateman, Philips...
    model               VARCHAR(100),                   -- 型號: YDM-4109, SHP-DP609...
    category            VARCHAR(100),                   -- 問題類別: 電池, WiFi, 密碼, 安裝, 故障, 其他
    location            VARCHAR(255),                   -- 地址或區域

    -- 狀態描述
    door_status         VARCHAR(50),
                        -- 'locked_out'           : 被鎖在外面
                        -- 'partially_functional' : 部分功能異常
                        -- 'normal'               : 門鎖正常 (諮詢類)
                        -- 'unknown'              : 未確認
    network_status      VARCHAR(50),
                        -- 'online'  : 連網正常
                        -- 'offline' : 離線
                        -- 'unknown' : 未確認
    symptoms            JSONB,                          -- 症狀 JSON 陣列
                                                        -- ["no_response", "beeping", "battery_low"]
    urgency             VARCHAR(50) DEFAULT 'normal',
                        -- 'low'     : 一般諮詢
                        -- 'normal'  : 標準報修
                        -- 'high'    : 緊急 (被鎖在外)
                        -- 'urgent'  : 非常緊急 (安全問題)
    media_urls          JSONB,                          -- 消費者上傳的圖片/影片 URL 陣列
    intent              VARCHAR(50),
                        -- 'inquiry'   : 諮詢
                        -- 'repair'    : 報修
                        -- 'complaint' : 投訴
                        -- 'other'     : 其他

    -- 診斷狀態
    status              VARCHAR(50) DEFAULT 'incomplete',
                        -- 'incomplete' : 欄位收集中
                        -- 'confirmed'  : 消費者已確認 (Flex Message 確認)
                        -- 'resolved'   : 已解決
                        -- 'escalated'  : 已升級至人工/派工
    completeness_score  FLOAT DEFAULT 0.0,              -- 0.0 ~ 1.0，反映關鍵欄位填充率
    resolution_layer    VARCHAR(10),                    -- 最終解決層級: 'L1', 'L2', 'L3'
    extracted_fields    JSONB,                          -- AI 原始擷取結果 (含各欄位 confidence)

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  problem_cards IS '結構化問題診斷卡 (ProblemCard)：AI 從對話自動擷取，作為三層解決引擎的輸入核心';
COMMENT ON COLUMN problem_cards.completeness_score IS '欄位完整度分數 (0.0~1.0)，至少需要 brand + symptoms 才可觸發解決引擎';
COMMENT ON COLUMN problem_cards.extracted_fields IS 'AI 原始擷取結果 JSON，含各欄位的 confidence score';

CREATE TRIGGER trg_problem_cards_updated_at
    BEFORE UPDATE ON problem_cards
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- [4] 產品手冊管理 (Manuals)
-- ============================================================================
--
-- 手冊處理流程 (Pipeline)：
--   1. 管理員上傳 PDF → INSERT manuals (status='processing')
--   2. 後台非同步解析 PDF (PyMuPDF) → 切片為 manual_chunks
--   3. 對每個 chunk 呼叫 Google Embedding API (text-embedding-004)
--      → 產生 768 維向量 → 存入 manual_chunks.embedding
--   4. 全部完成 → UPDATE manuals SET status='completed', total_chunks=N
--   5. 處理失敗 → UPDATE manuals SET status='failed', error_message='...'
--
-- 管理員可按品牌、型號分類管理手冊 (US-015)
-- 手冊上傳後顯示處理進度 (processing → indexing → completed)
-- ============================================================================

CREATE TABLE manuals (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename            VARCHAR(255) NOT NULL,          -- 原始檔名
    brand               VARCHAR(100) NOT NULL,          -- 適用品牌
    model               VARCHAR(100),                   -- 適用型號 (NULL = 品牌通用手冊)
    file_size_bytes     BIGINT,                         -- 檔案大小 (bytes)
    total_pages         INTEGER,                        -- PDF 總頁數
    total_chunks        INTEGER DEFAULT 0,              -- 切片總數

    status              VARCHAR(50) DEFAULT 'processing',
                        -- 'processing' : PDF 解析中
                        -- 'indexing'   : 向量化索引中
                        -- 'completed'  : 處理完成，可供 RAG 搜尋
                        -- 'failed'     : 處理失敗
    error_message       TEXT,                           -- 失敗時的錯誤訊息
    uploaded_by         UUID REFERENCES users(id) ON DELETE SET NULL,

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  manuals IS '產品手冊 PDF 主表：管理手冊上傳、解析與索引狀態';
COMMENT ON COLUMN manuals.status IS '處理狀態流轉：processing → indexing → completed / failed';


CREATE TABLE manual_chunks (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    manual_id           UUID NOT NULL REFERENCES manuals(id) ON DELETE CASCADE,

    chunk_index         INTEGER NOT NULL,               -- 在該手冊中的切片序號 (從 0 開始)
    source_pdf          VARCHAR(255),                   -- 來源 PDF 檔名
    page_number         INTEGER,                        -- 來源頁碼
    chapter_title       VARCHAR(255),                   -- 章節標題 (解析自 PDF 結構)
    content             TEXT NOT NULL,                   -- 切片文本內容
    token_count         INTEGER,                        -- 文本 token 數 (用於 LLM context 控制)

    embedding           VECTOR(768),                    -- text-embedding-004 向量 (768 維)

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  manual_chunks IS '手冊切片表：PDF 解析後的文本段落，含 768 維向量用於 RAG 語義搜尋';
COMMENT ON COLUMN manual_chunks.embedding IS 'Google text-embedding-004 產生的 768 維向量，用於 L2 RAG 語義搜尋';
COMMENT ON COLUMN manual_chunks.chunk_index IS '切片在手冊中的順序編號，用於還原原始閱讀順序';


-- ============================================================================
-- [5] 案例庫 (Case Entries) — 三層引擎 L1 向量搜尋
-- ============================================================================
--
-- 案例來源：
--   - manual_input  : 管理員手動新增
--   - sop_approved  : SOP 審核通過後自動納入 (US-014)
--   - imported      : CSV 批量匯入歷史案例 (US-015)
--
-- L1 搜尋邏輯：
--   1. ProblemCard 確認後，將問題描述向量化
--   2. 對 case_entries 執行 pgvector cosine similarity 搜尋
--   3. 相似度 >= 0.85 視為命中，取 Top-3 (US-008)
--   4. 命中時 hit_count += 1，回覆步驟化解決方案
-- ============================================================================

CREATE TABLE case_entries (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title               VARCHAR(255) NOT NULL,
    problem_description TEXT NOT NULL,
    solution            TEXT NOT NULL,
    brand               VARCHAR(100),                   -- 適用品牌
    lock_type           VARCHAR(100),                   -- 適用鎖型
    difficulty          VARCHAR(50) DEFAULT 'medium',   -- 'easy', 'medium', 'hard'

    embedding           VECTOR(768),                    -- text-embedding-004 向量 (768 維)

    source              VARCHAR(50) DEFAULT 'manual_input',
                        -- 'manual_input'  : 管理員手動新增
                        -- 'sop_approved'  : SOP 審核通過後自動納入
                        -- 'imported'      : CSV 批量匯入
    approved_by         UUID REFERENCES users(id) ON DELETE SET NULL,
    is_active           BOOLEAN DEFAULT TRUE,           -- 是否啟用 (支援下架)
    hit_count           INTEGER DEFAULT 0,              -- L1 搜尋命中次數

    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  case_entries IS '案例庫：歷史成功案例與解決方案，支援 L1 向量語義搜尋 (閾值 >= 0.85)';
COMMENT ON COLUMN case_entries.embedding IS 'Google text-embedding-004 產生的 768 維向量，用於 L1 語義搜尋';
COMMENT ON COLUMN case_entries.hit_count IS 'L1 搜尋命中次數，用於統計案例使用頻率';

CREATE TRIGGER trg_case_entries_updated_at
    BEFORE UPDATE ON case_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- [6] SOP 草稿 (SOP Drafts) — 自進化知識庫
-- ============================================================================
--
-- 自進化流程 (US-012 ~ US-014)：
--   1. 案件狀態轉為「已解決」且消費者回饋「有幫助」→ 觸發 SOP 生成
--   2. LLM 從對話記錄與 ProblemCard 中提取 → 生成 SOP 草稿 (status='pending_review')
--   3. 管理員審核 → 'approved' 或 'rejected'
--   4. 一鍵發布 → 'published'，SOP 內容向量化後納入 case_entries
--   5. 相似度 >= 0.90 的問題不重複生成 SOP
-- ============================================================================

CREATE TABLE sop_drafts (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_conversation_id      UUID REFERENCES conversations(id) ON DELETE SET NULL,
    source_problem_card_id      UUID REFERENCES problem_cards(id) ON DELETE SET NULL,

    title                       VARCHAR(255) NOT NULL,
    applicable_conditions       TEXT,                   -- 適用條件描述
    steps                       JSONB NOT NULL,         -- SOP 步驟清單 (ordered JSON array)
    notes                       TEXT,                   -- 注意事項 / 警告

    status                      VARCHAR(50) DEFAULT 'pending_review',
                                -- 'pending_review' : 待審核
                                -- 'approved'       : 已核准
                                -- 'rejected'       : 已退回
                                -- 'published'      : 已發布至知識庫
    reviewed_by                 UUID REFERENCES users(id) ON DELETE SET NULL,
    review_comment              TEXT,
    published_as_case_entry_id  UUID REFERENCES case_entries(id) ON DELETE SET NULL,

    created_at                  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    reviewed_at                 TIMESTAMP WITH TIME ZONE
);

COMMENT ON TABLE  sop_drafts IS 'SOP 草稿表：系統從成功案件自動生成，經管理員審核後可發布至案例庫';
COMMENT ON COLUMN sop_drafts.published_as_case_entry_id IS '發布後對應的 case_entries.id，建立 SOP 與案例庫的追溯關係';


-- ============================================================================
-- [V2.0] 技師與派工上下文 (Dispatch)
-- ============================================================================

CREATE TABLE technicians (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    name                VARCHAR(100) NOT NULL,
    phone               VARCHAR(50) NOT NULL,
    email               VARCHAR(255),
    capabilities        JSONB,                          -- 品牌與鎖型技能清單
    service_regions     JSONB,                          -- 可服務的地區清單
    availability        JSONB,                          -- 每週可用時段
    rating              FLOAT CHECK (rating >= 1.0 AND rating <= 5.0),
    completed_orders    INTEGER DEFAULT 0,
    status              VARCHAR(50) DEFAULT 'pending_approval',
                        -- 'pending_approval', 'active', 'inactive', 'suspended'
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_technicians_updated_at
    BEFORE UPDATE ON technicians
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


CREATE TABLE work_orders (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    problem_card_id     UUID REFERENCES problem_cards(id) ON DELETE RESTRICT,
    technician_id       UUID REFERENCES technicians(id) ON DELETE SET NULL,
    created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    status              VARCHAR(50) DEFAULT 'created',
                        -- 'created', 'assigned', 'accepted', 'in_progress',
                        -- 'completed', 'confirmed', 'cancelled'
    priority            VARCHAR(50) DEFAULT 'normal',   -- 'low', 'normal', 'high', 'urgent'
    customer_name       VARCHAR(100),
    customer_phone      VARCHAR(50),
    customer_address    TEXT,
    scheduled_at        TIMESTAMP WITH TIME ZONE,
    accepted_at         TIMESTAMP WITH TIME ZONE,
    started_at          TIMESTAMP WITH TIME ZONE,
    completed_at        TIMESTAMP WITH TIME ZONE,
    service_report      TEXT,                           -- 技師完工回報
    photos              JSONB,                          -- 維修前後照片 URL 陣列
    estimated_price     FLOAT,
    final_price         FLOAT,
    rating              INTEGER CHECK (rating >= 1 AND rating <= 5),
    feedback            TEXT,
    confirmed_at        TIMESTAMP WITH TIME ZONE,
    -- CR-0026 公單標準化欄位（migration 036；全 nullable）
    brand               VARCHAR(100),                   -- 建單時從 problem_cards 複製
    model               VARCHAR(100),
    serial_number       VARCHAR(100),                   -- 序號（綁保固）
    door_type           VARCHAR(50),
    door_thickness      VARCHAR(50),
    is_interior_door    BOOLEAN,
    service_category    VARCHAR(30),                    -- install/warranty_in/warranty_out/repair
    problem_type        VARCHAR(100),
    warranty_status     VARCHAR(30),                    -- in_warranty/out_warranty/not_applicable
    purchase_date       DATE,
    invoice_no          VARCHAR(100),
    completion_status   VARCHAR(40),                    -- M05 Q052 六段（pending_report…closed）
    status_reason       TEXT,                           -- BR-M05-01 狀態變更原因
    parent_work_order_id UUID REFERENCES work_orders(id) ON DELETE SET NULL,  -- BR-M05-02 返修連回
    customer_final_amount NUMERIC(12,2),               -- 對外單一最終金額（成本拆項見 CR-0027）
    tenant_id           UUID,                           -- multi-tenant 預留（CR-0031）；目前 single-tenant
    dispatched_via      VARCHAR(20),                    -- CR-0030 派工來源 manual/platform/auto_match（platform=可計費）
    -- CR-0043 公單欄位 Phase 2（migration 052；全 nullable）
    dealer              VARCHAR(150),                   -- M2.3 購買地點/經銷商
    install_date        DATE,                           -- M2.4 安裝日期（回溯判保固；與 purchase_date 區分）
    rain_exposure       VARCHAR(20),                    -- M2.5 indoor/outdoor_covered/outdoor_exposed
    special_door_surcharge BOOLEAN,                     -- M4.1 特殊門型加價確認旗標
    payment_method      VARCHAR(20),                    -- M5.5 cash/bank_transfer/credit_card/line_pay
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_work_orders_updated_at
    BEFORE UPDATE ON work_orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- [V2.0] 報價與帳務上下文 (Pricing & Accounting)
-- ============================================================================

CREATE TABLE price_rules (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    brand               VARCHAR(100) NOT NULL,
    lock_type           VARCHAR(100) NOT NULL,
    difficulty          VARCHAR(50) NOT NULL,           -- 'easy', 'medium', 'hard'
    base_price          FLOAT NOT NULL,
    labor_cost          FLOAT NOT NULL,
    parts_cost          FLOAT,
    modifiers           JSONB,                          -- 特殊加價規則 (夜間、偏遠等)
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_price_rules_updated_at
    BEFORE UPDATE ON price_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


CREATE TABLE invoices (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id       UUID UNIQUE REFERENCES work_orders(id) ON DELETE RESTRICT,
    invoice_number      VARCHAR(100) UNIQUE NOT NULL,
    amount              FLOAT NOT NULL,
    tax                 FLOAT NOT NULL DEFAULT 0,
    total               FLOAT NOT NULL,
    status              VARCHAR(50) DEFAULT 'draft',    -- 'draft', 'issued', 'paid', 'cancelled'
    line_items          JSONB NOT NULL,                 -- 報價明細清單
    issued_at           TIMESTAMP WITH TIME ZONE,
    paid_at             TIMESTAMP WITH TIME ZONE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_invoices_updated_at
    BEFORE UPDATE ON invoices
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


CREATE TABLE reconciliations (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    technician_id       UUID REFERENCES technicians(id) ON DELETE RESTRICT,
    period_start        TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end          TIMESTAMP WITH TIME ZONE NOT NULL,
    total_orders        INTEGER NOT NULL DEFAULT 0,
    total_revenue       FLOAT NOT NULL DEFAULT 0,
    platform_fee        FLOAT NOT NULL DEFAULT 0,
    technician_payout   FLOAT NOT NULL DEFAULT 0,
    status              VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'approved', 'disputed'
    approved_by         UUID REFERENCES users(id) ON DELETE SET NULL,
    approved_at         TIMESTAMP WITH TIME ZONE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE settlements (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reconciliation_id   UUID REFERENCES reconciliations(id) ON DELETE RESTRICT,
    technician_id       UUID REFERENCES technicians(id) ON DELETE RESTRICT,
    amount              FLOAT NOT NULL,
    currency            VARCHAR(10) DEFAULT 'TWD',
    status              VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'paid', 'failed'
    payment_method      VARCHAR(50) DEFAULT 'bank_transfer',
    paid_at             TIMESTAMP WITH TIME ZONE,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================================
-- [V2.0] 工單異常處理擴展欄位 (Work Order Exception Handling Extensions)
-- ============================================================================

ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS
    rejection_reason    TEXT;                            -- 技師拒單原因

ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS
    scope_change_id     UUID;                           -- 關聯範圍變更申請

ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS
    material_shortage   BOOLEAN DEFAULT FALSE;          -- 缺料標記

ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS
    delay_notified_at   TIMESTAMP WITH TIME ZONE;       -- 延遲通知時間戳

ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS
    dispute_status      VARCHAR(50);                    -- 爭議狀態: 'none','pending','resolved','escalated'

ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS
    rescheduled_from_id UUID REFERENCES work_orders(id);-- 改期前原工單

ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS
    is_rework           BOOLEAN DEFAULT FALSE;          -- 二次派工標記

ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS
    rework_of_id        UUID REFERENCES work_orders(id);-- 原始工單 (二次派工時)

ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS
    cancellation_reason TEXT;                           -- 取消原因

ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS
    appearance_change_consent BOOLEAN;                  -- 門外觀變更客戶同意


-- ============================================================================
-- [V2.0] 客訴管理 (Complaints)
-- ============================================================================
--
-- 客訴處理流程：
--   1. 消費者或系統提交客訴 → status='filed'
--   2. 分派專責人員處理 → assigned_to
--   3. 調查並提出解決方案 → status='proposed'
--   4. 消費者接受/拒絕 → status='accepted'/'rejected'
--   5. 結案 → status='resolved' / 'closed'
--   6. SLA 依嚴重程度設定：critical=4h, high=24h, medium=72h, low=168h
-- ============================================================================

CREATE TABLE complaints (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id       UUID REFERENCES work_orders(id),
    customer_id         UUID REFERENCES users(id),
    category            VARCHAR(50) NOT NULL,           -- 客訴類型: 'service','quality','pricing','attitude','other'
    severity            VARCHAR(50) DEFAULT 'medium',   -- 嚴重程度: 'low','medium','high','critical'
    status              VARCHAR(50) DEFAULT 'filed',
                        -- 'filed'         : 已提交
                        -- 'assigned'      : 已分派
                        -- 'investigating' : 調查中
                        -- 'proposed'      : 已提出方案
                        -- 'accepted'      : 消費者接受
                        -- 'rejected'      : 消費者拒絕
                        -- 'resolved'      : 已解決
                        -- 'closed'        : 已結案
    assigned_to         UUID REFERENCES users(id),      -- 負責處理的管理員
    description         TEXT NOT NULL,                   -- 客訴描述
    resolution          TEXT,                           -- 解決方案描述
    compensation_amount FLOAT,                          -- 補償金額
    compensation_type   VARCHAR(50),                    -- 補償方式: 'refund','discount_code','free_service','none'
    filed_at            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at         TIMESTAMP WITH TIME ZONE,
    sla_deadline        TIMESTAMP WITH TIME ZONE,       -- SLA 期限 (依 severity 計算)
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  complaints IS '客訴管理表：追蹤消費者投訴的完整生命週期，含 SLA 期限與補償機制';
COMMENT ON COLUMN complaints.sla_deadline IS 'SLA 回應期限，依嚴重程度自動設定：critical=4h, high=24h, medium=72h, low=168h';

CREATE TRIGGER trg_complaints_updated_at
    BEFORE UPDATE ON complaints
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- [V2.0] 範圍變更申請 (Scope Changes)
-- ============================================================================
--
-- 設計要點：
--   - 技師到場後發現問題範圍與原 ProblemCard 不同時提出
--   - 保留原始範圍與新範圍的 JSONB 快照，方便比對
--   - 客戶可選擇：繼續施工、改期、取消
--   - 管理員可覆寫客戶決策 (admin_override)
-- ============================================================================

CREATE TABLE scope_changes (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id       UUID NOT NULL REFERENCES work_orders(id),
    technician_id       UUID NOT NULL REFERENCES technicians(id),
    reason              TEXT NOT NULL,                   -- 技師描述的變更原因
    original_scope      JSONB NOT NULL,                 -- 原始 ProblemCard 摘要
    new_scope           JSONB NOT NULL,                 -- 新發現的問題範圍
    original_price      FLOAT NOT NULL,                 -- 原始報價
    new_price           FLOAT,                          -- 重新報價
    status              VARCHAR(50) DEFAULT 'pending',
                        -- 'pending'           : 等待客戶決定
                        -- 'customer_approved' : 客戶同意
                        -- 'customer_rejected' : 客戶拒絕
                        -- 'admin_override'    : 管理員覆寫
    customer_decision   VARCHAR(50),                    -- 客戶決策: 'continue','reschedule','cancel'
    approved_by         UUID REFERENCES users(id),      -- 核准者 (管理員覆寫時)
    photos              JSONB,                          -- 現場照片佐證 URL 陣列
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  scope_changes IS '範圍變更申請表：技師到場後發現實際問題與原始診斷不符時提出變更';
COMMENT ON COLUMN scope_changes.original_scope IS '原始 ProblemCard 範圍快照 JSON，用於變更前後比對';

CREATE TRIGGER trg_scope_changes_updated_at
    BEFORE UPDATE ON scope_changes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- [V2.0] 材料請購 (Material Requests)
-- ============================================================================
--
-- 設計要點：
--   - 技師現場缺料時提出請購
--   - items 為 JSONB 陣列：[{part_name, spec, qty, estimated_cost}]
--   - 審核通過後可追蹤預計到貨時間
--   - 來源區分：公司庫存、外部採購、技師墊付
-- ============================================================================

CREATE TABLE material_requests (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id       UUID NOT NULL REFERENCES work_orders(id),
    technician_id       UUID NOT NULL REFERENCES technicians(id),
    items               JSONB NOT NULL,                 -- 材料清單: [{part_name, spec, qty, estimated_cost}]
    status              VARCHAR(50) DEFAULT 'requested',
                        -- 'requested'  : 已提交
                        -- 'approved'   : 已核准
                        -- 'ordered'    : 已下單
                        -- 'fulfilled'  : 已到貨
                        -- 'cancelled'  : 已取消
    approved_by         UUID REFERENCES users(id),      -- 核准者
    estimated_arrival   TIMESTAMP WITH TIME ZONE,       -- 預計到貨時間
    total_cost          FLOAT,                          -- 材料總成本
    source              VARCHAR(50),                    -- 來源: 'company_stock','external_purchase','technician_advance'
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  material_requests IS '材料請購表：技師現場缺料時提出請購申請，含審核與到貨追蹤';
COMMENT ON COLUMN material_requests.items IS '材料清單 JSON 陣列，每項包含 part_name, spec, qty, estimated_cost';

CREATE TRIGGER trg_material_requests_updated_at
    BEFORE UPDATE ON material_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- [V2.0] 爭議仲裁 (Disputes)
-- ============================================================================
--
-- 設計要點：
--   - 可由消費者或技師提出
--   - 關聯工單或發票
--   - 類型涵蓋：定價、品質、保固、取消費、結算
--   - resolution_amount 正值=補償客戶，負值=扣款
-- ============================================================================

CREATE TABLE disputes (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id       UUID REFERENCES work_orders(id),
    invoice_id          UUID REFERENCES invoices(id),
    filed_by            UUID NOT NULL REFERENCES users(id), -- 提出者 (消費者或技師)
    dispute_type        VARCHAR(50) NOT NULL,           -- 爭議類型: 'pricing','quality','warranty','cancellation_fee','settlement'
    status              VARCHAR(50) DEFAULT 'filed',
                        -- 'filed'        : 已提交
                        -- 'under_review' : 審查中
                        -- 'mediation'    : 調解中
                        -- 'resolved'     : 已解決
                        -- 'escalated'    : 已升級
    description         TEXT NOT NULL,                   -- 爭議描述
    evidence            JSONB,                          -- 佐證資料: [{type, url, description}]
    resolution          TEXT,                           -- 仲裁結果描述
    resolution_amount   FLOAT,                          -- 調整金額 (正=補償客戶, 負=扣款)
    resolved_by         UUID REFERENCES users(id),      -- 仲裁者
    filed_at            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at         TIMESTAMP WITH TIME ZONE,
    sla_deadline        TIMESTAMP WITH TIME ZONE,       -- SLA 處理期限
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  disputes IS '爭議仲裁表：消費者或技師對工單/帳務提出爭議，含佐證資料與仲裁流程';
COMMENT ON COLUMN disputes.resolution_amount IS '調整金額：正值表示補償客戶，負值表示扣款';

CREATE TRIGGER trg_disputes_updated_at
    BEFORE UPDATE ON disputes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- [V2.0] 派工決策日誌 (Dispatch Logs)
-- ============================================================================
--
-- 設計要點：
--   - 記錄每次派工的決策過程與匹配因子
--   - 追蹤自動匹配、手動指派、拒單、超時、重派、級聯等行為
--   - match_factors 記錄各維度匹配分數，便於演算法調優
--   - 無 updated_at (僅追加，不更新)
-- ============================================================================

CREATE TABLE dispatch_logs (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id       UUID NOT NULL REFERENCES work_orders(id),
    action              VARCHAR(50) NOT NULL,           -- 動作: 'auto_match','manual_assign','rejection','timeout','reassign','cascade'
    technician_id       UUID REFERENCES technicians(id),-- 相關技師
    match_score         FLOAT,                          -- 匹配總分
    match_factors       JSONB,                          -- 匹配因子: {brand_score, distance_score, rating_score, availability_score}
    rejection_reason    TEXT,                           -- 拒單原因 (action='rejection' 時)
    timeout_seconds     INTEGER,                        -- 超時秒數 (action='timeout' 時)
    notes               TEXT,                           -- 備註
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  dispatch_logs IS '派工決策日誌表：記錄每次派工匹配、拒單、超時、重派等決策過程';
COMMENT ON COLUMN dispatch_logs.match_factors IS '匹配因子 JSON：含 brand_score, distance_score, rating_score, availability_score';


-- ============================================================================
-- [V2.0] 退款審批 (Refund Requests)
-- ============================================================================
--
-- 設計要點：
--   - 退款流程需經審核鏈簽核
--   - 金額 > 100,000 TWD 時需雙重簽核 (requires_dual_sign=TRUE)
--   - approval_chain 記錄完整簽核歷程：[{role, user_id, decision, decided_at}]
-- ============================================================================

CREATE TABLE refund_requests (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id       UUID REFERENCES work_orders(id),
    invoice_id          UUID REFERENCES invoices(id),
    complaint_id        UUID REFERENCES complaints(id),
    requested_by        UUID NOT NULL REFERENCES users(id), -- 申請者
    amount              FLOAT NOT NULL,                 -- 退款金額
    reason              TEXT NOT NULL,                   -- 退款原因
    status              VARCHAR(50) DEFAULT 'pending',
                        -- 'pending'      : 待審核
                        -- 'csm_approved' : 客服主管核准
                        -- 'ops_approved' : 營運主管核准
                        -- 'dual_signed'  : 雙重簽核完成
                        -- 'executed'     : 已執行退款
                        -- 'rejected'     : 已拒絕
    approval_chain      JSONB,                          -- 簽核鏈: [{role, user_id, decision, decided_at}]
    requires_dual_sign  BOOLEAN DEFAULT FALSE,          -- 金額 > 100,000 TWD 時需雙重簽核
    executed_at         TIMESTAMP WITH TIME ZONE,       -- 退款執行時間
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  refund_requests IS '退款審批表：退款申請與多層簽核流程，金額超過 100,000 TWD 需雙重簽核';
COMMENT ON COLUMN refund_requests.approval_chain IS '簽核鏈 JSON 陣列，記錄每位簽核者的角色、決策與時間';

CREATE TRIGGER trg_refund_requests_updated_at
    BEFORE UPDATE ON refund_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- [V2.0] 保固索賠 (Warranty Claims)
-- ============================================================================
--
-- 設計要點：
--   - 保固起算日以「交屋日」為準，非購買日
--   - is_within_warranty 由系統根據 claim_date 與 warranty_end_date 計算
--   - 保固外客戶可獲折扣報價 (discount_offered)
--   - 驗證來源：建案資料庫、收據、發票
-- ============================================================================

CREATE TABLE warranty_claims (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id       UUID REFERENCES work_orders(id),
    customer_id         UUID NOT NULL REFERENCES users(id),
    device_brand        VARCHAR(100) NOT NULL,          -- 設備品牌
    device_model        VARCHAR(100) NOT NULL,          -- 設備型號
    purchase_date       DATE,                           -- 購買日期
    warranty_start_date DATE NOT NULL,                  -- 保固起算日 (交屋日)
    warranty_end_date   DATE NOT NULL,                  -- 保固到期日
    claim_date          DATE NOT NULL DEFAULT CURRENT_DATE, -- 索賠日期
    is_within_warranty  BOOLEAN NOT NULL,               -- 系統計算：claim_date <= warranty_end_date
    status              VARCHAR(50) DEFAULT 'filed',
                        -- 'filed'    : 已提交
                        -- 'verified' : 已驗證
                        -- 'approved' : 已核准
                        -- 'rejected' : 已拒絕
                        -- 'disputed' : 爭議中
    dispute_reason      TEXT,                           -- 消費者對拒絕結果的爭議理由
    verification_source VARCHAR(100),                   -- 驗證來源: 'project_database','receipt','invoice'
    resolution          TEXT,                           -- 處理結果描述
    discount_offered    FLOAT,                          -- 保固外折扣 (百分比)
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  warranty_claims IS '保固索賠表：追蹤設備保固驗證與索賠流程，保固起算日以交屋日為準';
COMMENT ON COLUMN warranty_claims.warranty_start_date IS '保固起算日以交屋日 (handover date) 為準，非購買日期';
COMMENT ON COLUMN warranty_claims.is_within_warranty IS '系統自動計算：claim_date <= warranty_end_date';

CREATE TRIGGER trg_warranty_claims_updated_at
    BEFORE UPDATE ON warranty_claims
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- [V2.0] 門外觀變更同意書 (Appearance Change Consents)
-- ============================================================================
--
-- 設計要點：
--   - 施工可能造成門外觀變化時 (如韓規側板切割導致門漆起泡)，技師須取得客戶同意
--   - 記錄施工前門面照片 (original_photo_urls)
--   - 同意方式：數位簽名、LINE 訊息確認、口頭錄音
--   - 無 updated_at (同意書一旦建立即為歷史紀錄)
-- ============================================================================

CREATE TABLE appearance_change_consents (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    work_order_id       UUID NOT NULL REFERENCES work_orders(id),
    technician_id       UUID NOT NULL REFERENCES technicians(id),
    customer_id         UUID NOT NULL REFERENCES users(id),
    change_description  TEXT NOT NULL,                  -- 外觀變更描述 (例: "韓規側板切割會造成門漆起泡")
    affected_area       TEXT,                           -- 受影響區域描述
    original_photo_urls JSONB,                          -- 施工前門面照片 URL 陣列
    customer_consented  BOOLEAN,                        -- 客戶是否同意
    consented_at        TIMESTAMP WITH TIME ZONE,       -- 同意時間
    consent_method      VARCHAR(50),                    -- 同意方式: 'digital_signature','line_confirmation','verbal_recorded'
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE  appearance_change_consents IS '門外觀變更同意書：施工可能影響門外觀時，記錄客戶知情同意';
COMMENT ON COLUMN appearance_change_consents.consent_method IS '同意方式：digital_signature=數位簽名, line_confirmation=LINE確認, verbal_recorded=口頭錄音';


-- ============================================================================
-- 建立資料表索引 (參照架構文件 §5.1 表格索引策略)
-- ============================================================================

-- [users] 索引
CREATE INDEX idx_users_line_user_id ON users (line_user_id) WHERE line_user_id IS NOT NULL;
CREATE INDEX idx_users_role ON users (role);

-- [conversations] 索引
CREATE INDEX idx_conv_user_status ON conversations (user_id, status);
CREATE INDEX idx_conv_session ON conversations (session_id);
CREATE INDEX idx_conv_created_at ON conversations (created_at DESC);

-- [messages] 索引
CREATE INDEX idx_msg_conv_created ON messages (conversation_id, created_at);

-- [problem_cards] 索引
CREATE INDEX idx_pc_status ON problem_cards (status);
CREATE INDEX idx_pc_brand_model ON problem_cards (brand, model);
CREATE INDEX idx_pc_created_at ON problem_cards (created_at DESC);

-- [case_entries] 索引
CREATE INDEX idx_ce_brand_active ON case_entries (brand, is_active);

-- [manual_chunks] 索引
CREATE INDEX idx_mc_manual ON manual_chunks (manual_id);
CREATE INDEX idx_mc_manual_chunk ON manual_chunks (manual_id, chunk_index);

-- [sop_drafts] 索引
CREATE INDEX idx_sop_status ON sop_drafts (status);

-- [work_orders] 索引 (V2.0)
CREATE INDEX idx_wo_tech_status ON work_orders (technician_id, status);
CREATE INDEX idx_wo_status_priority ON work_orders (status, priority);

-- [invoices] 索引 (V2.0)
CREATE INDEX idx_inv_wo ON invoices (work_order_id);

-- [reconciliations] 索引 (V2.0)
CREATE INDEX idx_recon_tech_period ON reconciliations (technician_id, period_start);

-- [complaints] 索引 (V2.0)
CREATE INDEX idx_complaints_work_order ON complaints (work_order_id);
CREATE INDEX idx_complaints_customer ON complaints (customer_id);
CREATE INDEX idx_complaints_status ON complaints (status);

-- [scope_changes] 索引 (V2.0)
CREATE INDEX idx_scope_changes_work_order ON scope_changes (work_order_id);

-- [material_requests] 索引 (V2.0)
CREATE INDEX idx_material_requests_work_order ON material_requests (work_order_id);

-- [disputes] 索引 (V2.0)
CREATE INDEX idx_disputes_work_order ON disputes (work_order_id);
CREATE INDEX idx_disputes_invoice ON disputes (invoice_id);

-- [dispatch_logs] 索引 (V2.0)
CREATE INDEX idx_dispatch_logs_work_order ON dispatch_logs (work_order_id);

-- [refund_requests] 索引 (V2.0)
CREATE INDEX idx_refund_requests_work_order ON refund_requests (work_order_id);

-- [warranty_claims] 索引 (V2.0)
CREATE INDEX idx_warranty_claims_customer ON warranty_claims (customer_id);

-- [appearance_change_consents] 索引 (V2.0)
CREATE INDEX idx_appearance_consents_work_order ON appearance_change_consents (work_order_id);


-- ============================================================================
-- 向量索引 (pgvector HNSW, Cosine Similarity)
-- 參照架構文件 §5.4：向量維度 768, m=16, ef_construction=64
-- ============================================================================

CREATE INDEX idx_case_entry_embedding ON case_entries
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_manual_chunk_embedding ON manual_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
