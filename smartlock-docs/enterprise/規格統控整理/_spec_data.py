"""Smart Lock enterprise 四書的靜態展示資料。

只放「讀 Markdown 推不出來的人工判斷」：顯示分群、元件投影、codebase 掃描結果、
標籤定義、階段歸屬。需求、NFR、TC、ADR、WBS 一律由生成器讀 enterprise 正典。

2026-07-27 重構後仍被消費的鍵（其餘為既有 QA/術語素材，暫留待重新歸位）：

    GENERATED_ON / CODEBASE_SNAPSHOT   產出日與掃描基線
    SUBSYSTEMS / MODULES               BOM 的 L1 / L2 顯示分群
    MODULE_ARCH / MODULE_STATUS        L2 -> 正式元件、SAD/SDS、路徑、code reality
    COMPONENT_GLOSSARY                 受控標籤字典
    PHASE_BY_ID                        FR -> M1/M2/M3+ 歸屬
    SCENARIOS                          19_Test_Plan 的 TS-01..12 基線

已刪除：
    FR_BUSINESS_COPY   為 65 條 FR 各寫一段 VOC ＝ 把同一段旅程摘要 65 次。
                       旅程語言的唯一來源改為 28_Scenarios.md 的 SC 卡。
    FR_TC_HINTS / NFR_TC_HINTS
                       用字串描述「指定 TC」＝ 命名慣例偽裝成關聯。
                       改為 _relations/rq_verified_by_tc.yaml，一列一條邊。
"""

GENERATED_ON = "2026-07-27"
CODEBASE_SNAPSHOT = {
    "branch": "dev-ding",
    "commit": "e000f1fe",
    "baseline": "ddc6f986",
    "scope": "agent、api、web 四站、knowledge-pipeline/refinery、SQL、infra、scripts 與 enterprise 正典",
}

SUBSYSTEMS = {
    "AGT": {
        "name": "agent（LockCore AI 客服）",
        "short": "AI 客服",
        "component": "line_gateway; AgentLoop / AgentRunner; LiteLLMProvider; MemoryManager + Store / EscalationStore; SkillsLoader + 2 builtin skills; Photo Guide resolver; 記憶 DB",
        "sad": "12_SAD §4.1",
        "sds": "15_SDS §5.1–5.4；附錄",
        "path": "agent/lockcore/; agent/scripts/line_gateway.py",
        "description": "LINE 進線、Turn 編排、知識檢索、記憶、轉真人與 AI 邊界治理。",
    },
    "API": {
        "name": "api（派工營運控制平面）",
        "short": "派工控制",
        "component": "FastAPI dispatch / tech / platform surfaces",
        "sad": "12_SAD §4.2",
        "sds": "15_SDS §4、§6；附錄",
        "path": "api/routers/; api/services/; api/core/; api/realtime/",
        "description": "問題卡、報價、工單、派工、現場存證、金流結算、隱私與稽核。",
    },
    "WEB": {
        "name": "web（多站前端）",
        "short": "多站前端",
        "component": "dispatch-web / tech-web / landing-web / platform-web / LIFF",
        "sad": "12_SAD §4.3",
        "sds": "15_SDS §8；附錄",
        "path": "web/{brand-portal,tech-portal,landing,platform-console}/src/",
        "description": "品牌營運、師傅、平台維運與消費者 LIFF 介面。",
    },
    "DAT": {
        "name": "data-pipeline（資料與 schema）",
        "short": "資料平台",
        "component": "Medallion pipeline / PostgreSQL / pgvector / migrations",
        "sad": "12_SAD §4.6",
        "sds": "15_SDS §3.1、§9；附錄",
        "path": "knowledge-pipeline/pipeline/; knowledge-pipeline/storage/; SQL/",
        "description": "raw→bronze→silver、三庫物理隔離、語義語料、migration 與跨系統同步。",
    },
    "REF": {
        "name": "knowledge-refinery（知識精煉）",
        "short": "知識精煉",
        "component": "Refinery service / HITL review UI / Publisher",
        "sad": "12_SAD §4.4",
        "sds": "15_SDS §9；附錄",
        "path": "knowledge-pipeline/refinery/; knowledge-pipeline/pipeline/",
        "description": "診斷與素材汲取、LLM 事實/行為分流、HITL 審核與雙路發佈。",
    },
    "TEC": {
        "name": "technician-platform（技師共享池）",
        "short": "技師平台",
        "component": "API_SURFACE=tech / OHS / technician web / lock_tech",
        "sad": "12_SAD §4.2、§4.5",
        "sds": "15_SDS §6.1、§7；附錄",
        "path": "api/{main.py,routers/,services/,core/,realtime/}; web/tech-portal/; SQL/tech_authority/",
        "description": "跨租戶技師身分、KYC、品牌授權、媒合、工單投影與結算。",
    },
    "PLT": {
        "name": "00_platform（平台整合層）",
        "short": "平台核心",
        "component": "Casdoor / Kafka / Redis / SigNoz / OPIK / Config Registry",
        "sad": "12_SAD §8–9",
        "sds": "15_SDS §2–3、§10–11",
        "path": "跨系統共用平台；依各正式元件所屬路徑",
        "description": "身分與 License、事件骨幹、可觀測性、模型編排、工單積木與配置治理。",
    },
}

# L2 僅是四書顯示群組，不是新增的追溯主鍵。追溯一律使用 SRS FR ID。
MODULES = {
    "AGT": [
        ("CHN", "通道與 Turn 編排", {"01", "02", "10"}),
        ("RES", "診斷與轉真人", {"03", "04", "05", "09"}),
        ("KNW", "記憶與知識", {"06", "07"}),
        ("GOV", "AI 邊界治理", {"08", "11"}),
    ],
    "API": [
        ("CASE", "問題卡與報價", {"01", "02", "03", "17", "19"}),
        ("WO", "工單與現場", {"04", "08", "09"}),
        ("DISP", "派工與 SLA", {"05", "06", "07"}),
        ("FIN", "付款與結算", {"10", "11", "12"}),
        ("INT", "內部整合與即時通道", {"13", "14", "15"}),
        ("GOV", "隱私與例外審批", {"16", "18"}),
    ],
    "WEB": [
        ("SHELL", "入口、權限與降級", {"01", "02", "07"}),
        ("OPS", "派工營運與報表", {"03", "04"}),
        ("AUD", "稽核治理", {"05"}),
        ("CX", "消費者 LIFF", {"06"}),
    ],
    "DAT": [
        ("MED", "Medallion 知識資料", {"01"}),
        ("SCH", "Schema 與 migration", {"02", "03"}),
        ("RAG", "向量語料", {"04"}),
        ("SYNC", "同步與稽核基座", {"05", "06"}),
    ],
    "REF": [
        ("INTAKE", "素材汲取", {"01"}),
        ("REFINE", "LLM 提煉分流", {"02"}),
        ("HITL", "HITL 審核", {"03", "05"}),
        ("PUB", "Publisher 雙路落地", {"04"}),
    ],
    "TEC": [
        ("ID", "身分、KYC 與生命週期", {"01", "02", "08"}),
        ("MATCH", "OHS 媒合與接單", {"03", "04", "07"}),
        ("PROJ", "工單投影", {"05"}),
        ("SET", "技師結算", {"06"}),
    ],
    "PLT": [
        ("IAM", "身分、RBAC 與 License", {"01", "02", "03"}),
        ("EVT", "事件與即時骨幹", {"04"}),
        ("LLM", "模型編排", {"05"}),
        ("OBS", "可觀測性", {"06"}),
        ("FLOW", "工單積木引擎", {"07"}),
        ("CFG", "Agent 配置與平台治理", {"08", "09"}),
    ],
}

# L2 能力群→正式 SAD/SDS 元件的人工投影。
# 元件名稱沿用 12_SAD / 15_SDS 用語；L2 不是新的架構元件或追溯主鍵。
MODULE_ARCH = {
    "AGT.CHN": {
        "component": "line_gateway; Photo Guide resolver; Quote postback message mapper; WebhookIdempotencyStore; AgentLoop; AgentRunner",
        "sad": "12_SAD §4.1",
        "sds": "15_SDS §5.1、§5.3",
        "path": "agent/lockcore/channels/line_gateway.py; agent/lockcore/agent/{loop,runner}.py",
    },
    "AGT.RES": {
        "component": "AgentLoop; AgentRunner; ReplyGuard; SentimentClassifier; ToolRegistry; EscalationStore",
        "sad": "12_SAD §4.1",
        "sds": "15_SDS §5.1、§5.3",
        "path": "agent/lockcore/agent/{loop,runner,tools}/; agent/lockcore/agent/user_memory/escalation.py",
    },
    "AGT.KNW": {
        "component": "ContextBuilder; MemoryManager + Store; SkillsLoader + 2 builtin skills; SkillSync; 記憶 DB",
        "sad": "12_SAD §4.1",
        "sds": "15_SDS §5.1",
        "path": "agent/lockcore/agent/context.py; agent/lockcore/agent/user_memory/; agent/lockcore/skills/",
    },
    "AGT.GOV": {
        "component": "AgentRunner; LiteLLMProvider + FallbackProvider; ToolRegistry; SkillsLoader + 2 builtin skills",
        "sad": "12_SAD §4.1、§9",
        "sds": "15_SDS §5.1、§5.4",
        "path": "agent/lockcore/agent/runner.py; agent/lockcore/providers/; agent/lockcore/agent/tools/; agent/lockcore/skills/",
    },
    "API.CASE": {
        "component": "tenant-scoped routers; Service Layer（problem_card / quote）; Conversation media collector; core/db.py",
        "sad": "12_SAD §4.2",
        "sds": "15_SDS §4.2、§4.6、§6.1",
        "path": "api/routers/; api/services/{problem_card_service,quote_engine_service}.py; api/core/db.py",
    },
    "API.WO": {
        "component": "Service Layer（work_order）; Consent link service; Flow DSL executor; domain blocks / primitives; core/db.py",
        "sad": "12_SAD §4.2、§9",
        "sds": "15_SDS §3.3–3.5、§4.1–4.2、§6.1",
        "path": "api/services/{work_order_service,consent_service}.py; api/routers/work_orders_v2.py; api/core/db.py",
    },
    "API.DISP": {
        "component": "Service Layer（dispatch）; dispatch_service candidate scoring; Redis pub/sub; Kafka; PG Advisory Cron Leader; 分散式排程",
        "sad": "12_SAD §4.2、§8",
        "sds": "15_SDS §6.1、§6.3、§11.1",
        "path": "api/services/{dispatch_service,dispatch_log_service}.py; api/routers/dispatch_v2.py; api/realtime/; api/core/event_bus.py",
    },
    "API.FIN": {
        "component": "Service Layer（invoice / settlement）; core/db.py; Kafka",
        "sad": "12_SAD §4.2、§9",
        "sds": "15_SDS §4.2、§6.1、§7.3",
        "path": "api/services/{invoice_service,settlement_service,reconciliation_service,technician_statement_service}.py; api/core/{db,event_bus}.py",
    },
    "API.INT": {
        "component": "internal_ingest.py; WebSocket 端點; Redis pub/sub; EventBusProducer; Kafka; line_push_service + outbox worker",
        "sad": "12_SAD §4.2",
        "sds": "15_SDS §6.1–6.3、§11",
        "path": "api/routers/internal_ingest.py; api/realtime/; api/services/{line_push_service,line_push_outbox_service}.py; api/core/event_bus.py",
    },
    "API.GOV": {
        "component": "API_SURFACE router filter; Portal Claim Guard; Three-DB Connection Router; DBPoolScopeMiddleware; DEKService + PII blind index + purge ledger; 守衛鏈; core/errors.py; core/idempotency.py; Middleware",
        "sad": "12_SAD §4.2、§9",
        "sds": "15_SDS §6.1、§6.4",
        "path": "api/main.py; api/core/{deps,errors,idempotency,auth,pii_crypto,db}.py",
    },
    "WEB.SHELL": {
        "component": "AuthGuard; appMode gate; rolePolicy",
        "sad": "12_SAD §4.3",
        "sds": "15_SDS §8.1–8.3",
        "path": "web/{brand-portal,tech-portal,landing,platform-console}/src/components/layout/AuthGuard.tsx; 各站 src/lib/{appMode,rolePolicy}.ts",
    },
    "WEB.OPS": {
        "component": "api client; cache; realtime; AuthImage / AuthImageLightbox; ConsentPanel",
        "sad": "12_SAD §4.3",
        "sds": "15_SDS §8.1、§8.3",
        "path": "web/brand-portal/src/{lib/,components/media/AuthImage.tsx,components/work-orders/DispatchOrderView.tsx}",
    },
    "WEB.AUD": {
        "component": "rolePolicy; api client; 型別（api.generated.ts）",
        "sad": "12_SAD §4.3",
        "sds": "15_SDS §8.1",
        "path": "web/{brand-portal,platform-console}/src/lib/{rolePolicy,api}.ts; 各站 src/types/api.generated.ts",
    },
    "WEB.CX": {
        "component": "api client; cache; realtime; AuthImage / AuthImageLightbox; ConsentPanel",
        "sad": "12_SAD §4.3",
        "sds": "15_SDS §8.1、§8.3",
        "path": "web/brand-portal/src/{lib/,components/media/AuthImage.tsx,components/work-orders/DispatchOrderView.tsx,app/consent/}",
    },
    "DAT.MED": {
        "component": "source_to_raw; raw_to_bronze; bronze_to_silver; storage（raw/bronze/silver）",
        "sad": "12_SAD §4.6",
        "sds": "15_SDS §9.1；附錄",
        "path": "knowledge-pipeline/pipeline/; knowledge-pipeline/storage/",
    },
    "DAT.SCH": {
        "component": "SQL/Schema*.sql; forward-only migrations; platform schema; core/db.py",
        "component": "SQL/Schema*.sql; forward-only migrations; migration registry + routed apply; Audit Chain Checkpoint; platform schema; Tech DB router + mirror; core/db.py",
        "sad": "12_SAD §4.2、§4.6",
        "sds": "15_SDS §3.1、§6.1",
        "path": "SQL/Schema*.sql; SQL/migrations/*.sql; SQL/{platform,tech_authority}/; api/core/{db,tech_mirror}.py; api/services/audit_log_service.py",
    },
    "DAT.RAG": {
        "component": "MCP RAG server; 品牌庫 pgvector; rag_manual_chunks / case_entries",
        "sad": "12_SAD §5、§8–9",
        "sds": "15_SDS §5.1、§9.1、§11.3",
        "path": "agent/rag/rag/; SQL/Schema_rag.sql; knowledge-pipeline/refinery/refinery/{publisher,embedding}.py",
    },
    "DAT.SYNC": {
        "component": "Medallion pipeline; Kafka; outbox; provenance / audit",
        "sad": "12_SAD §4.2、§4.6、§8.2",
        "sds": "15_SDS §6.3–6.4、§9.3、§11",
        "path": "knowledge-pipeline/pipeline/silver_to_knowledge/; api/core/event_bus.py; api/realtime/event_consumer.py; api/services/line_push_outbox_service.py",
    },
    "REF.INTAKE": {
        "component": "汲取層; raw_to_bronze; bronze_to_silver",
        "sad": "12_SAD §4.4",
        "sds": "15_SDS §9.1、§9.3",
        "path": "knowledge-pipeline/refinery/refinery/{intake,run_intake,entitlement}.py; knowledge-pipeline/pipeline/{raw_to_bronze,bronze_to_silver}/",
    },
    "REF.REFINE": {
        "component": "提煉分流器; Draft Queue",
        "sad": "12_SAD §4.4",
        "sds": "15_SDS §9.1、§9.3",
        "path": "knowledge-pipeline/refinery/refinery/{refine,store}.py",
    },
    "REF.HITL": {
        "component": "Draft Queue; 審核 UI backend; Casdoor reviewer auth",
        "sad": "12_SAD §4.4",
        "sds": "15_SDS §9.1–9.2",
        "path": "knowledge-pipeline/refinery/refinery/{service,review,oidc}.py; knowledge-pipeline/refinery/static/index.html",
    },
    "REF.PUB": {
        "component": "Publisher; behavior patch artifact; LiveSkill DB ingest; 品牌庫 pgvector; SkillsLoader + 2 builtin skills",
        "sad": "12_SAD §4.4",
        "sds": "15_SDS §9.1、§9.3",
        "path": "knowledge-pipeline/refinery/refinery/{publisher,apply_behavior,embedding}.py; api/routers/internal_skills.py; agent/lockcore/skills/",
    },
    "TEC.ID": {
        "component": "API_SURFACE router filter; self-service routers; 守衛鏈; technician_service; certification/kyc_service; Tech DB router + mirror; lock_tech",
        "sad": "12_SAD §4.2、§4.5",
        "sds": "15_SDS §6.1、§7.1–7.2",
        "path": "api/main.py; api/routers/{technicians_v2,platform_technicians,technician_certifications_v2,technician_lifecycle_v2}.py; api/services/technician_{service,kyc_service,certification_service,lifecycle_service}.py; api/core/{db,tech_mirror}.py; SQL/tech_authority/; web/tech-portal/",
    },
    "TEC.MATCH": {
        "component": "OHS API routers; dispatch_service candidate scoring; schedule_service; WebSocket 端點; 事件層",
        "sad": "12_SAD §4.2、§4.5",
        "sds": "15_SDS §4.4、§7.1–7.2",
        "path": "api/routers/{dispatch_v2,technicians_v2}.py; api/services/{dispatch_service,technician_schedule_service}.py; api/realtime/; web/tech-portal/",
    },
    "TEC.PROJ": {
        "component": "事件層; EventConsumerWorker; technician_workorder_projection; 技師工單 read-model; WebSocket 端點",
        "sad": "12_SAD §4.5、§8.2",
        "sds": "15_SDS §7.1、§7.3、§11.1",
        "path": "api/core/event_bus.py; api/realtime/event_consumer.py; SQL/tech_authority/Schema_cqrs_projection.sql; web/tech-portal/",
    },
    "TEC.SET": {
        "component": "technician settlement services; technician_commission_projection; EventConsumerWorker; Kafka",
        "sad": "12_SAD §4.5、§9",
        "sds": "15_SDS §7.1、§7.3、§11.1",
        "path": "api/services/{technician_commission_service,technician_statement_service,reconciliation_service,reconciliation_v2_service}.py; api/realtime/event_consumer.py; SQL/tech_authority/Schema_cqrs_projection.sql",
    },
    "PLT.IAM": {
        "component": "Casdoor; 平台維運 console; 守衛鏈; License Entitlement Gate; License provisioning",
        "sad": "12_SAD §8.2–8.3、§9",
        "sds": "15_SDS §2.1、§6.1、§11.2",
        "path": "web/platform-console/; api/main.py（API_SURFACE=platform）; infra/casdoor/; web/platform-console/docker-compose.yml",
    },
    "PLT.EVT": {
        "component": "Kafka; Redis pub/sub; WebSocket 端點; 分散式排程",
        "sad": "12_SAD §4.2、§8–9",
        "sds": "15_SDS §6.1、§6.3、§11",
        "path": "api/core/event_bus.py; api/realtime/; web/brand-portal/docker-compose.yml（events profile）",
    },
    "PLT.LLM": {
        "component": "LiteLLMProvider + FallbackProvider; Model Orchestration Layer",
        "sad": "12_SAD §4.1、§9",
        "sds": "15_SDS §2.2、§5.1、§13",
        "path": "agent/lockcore/providers/{litellm_provider,fallback_provider}.py",
    },
    "PLT.OBS": {
        "component": "SigNoz; OPIK; OpenTelemetry; PIIScrubSpanProcessor",
        "sad": "12_SAD §8.2、§9",
        "sds": "15_SDS §12",
        "path": "web/{brand-portal,tech-portal,landing,platform-console}/src/{instrumentation.ts,observability/piiScrub.ts}; agent/lockcore/observability/; knowledge-pipeline/refinery/refinery/observability.py",
    },
    "PLT.FLOW": {
        "component": "Flow DSL executor; domain blocks / primitives; Vertical Pack; FlowEditor",
        "sad": "12_SAD §9",
        "sds": "15_SDS §2.1、§3.2–3.7、§10",
        "path": "待 M4 實作；目前為 SDS 設計元件",
    },
    "PLT.CFG": {
        "component": "Agent Configuration Studio / Config Registry; M18 Config Registry; Skill Revision Registry; Vertical Pack; HITL 審核骨架",
        "sad": "12_SAD §9",
        "sds": "15_SDS §3.2、§10、§13",
        "path": "api/services/config_m18_service.py; api/routers/{config_m18,internal_skills}.py; web/brand-portal/src/components/knowledge-base/（部分落地）",
    },
}

# 需求狀態來自 SRS/Roadmap；以下是 2026-07-27 對 commit e000f1fe 的 code reality。
# AS-BUILT = 核心 code 與測試路徑存在；PARTIAL = 需部署參數/事件骨幹/安全窗或尚有設計邊界未收斂；
# TO-BE = 目前只有 SAD/SDS/ADR 設計，不能用「需求已定版」推定已實作。
MODULE_STATUS = {
    "AGT.CHN": "AS-BUILT",
    "AGT.RES": "AS-BUILT",
    "AGT.KNW": "AS-BUILT",
    "AGT.GOV": "AS-BUILT",
    "API.CASE": "AS-BUILT",
    "API.WO": "AS-BUILT",
    "API.DISP": "PARTIAL（Kafka/Redis 依部署設定啟用）",
    "API.FIN": "PARTIAL（跨系統事件依 Kafka 啟用）",
    "API.INT": "PARTIAL（Redis/Kafka 依部署設定啟用）",
    "API.GOV": "AS-BUILT",
    "WEB.SHELL": "PARTIAL（OIDC cookie 與 legacy token 過渡）",
    "WEB.OPS": "AS-BUILT",
    "WEB.AUD": "AS-BUILT",
    "WEB.CX": "AS-BUILT",
    "DAT.MED": "AS-BUILT",
    "DAT.SCH": "AS-BUILT",
    "DAT.RAG": "PARTIAL（RAG_TENANT_ID opt-in）",
    "DAT.SYNC": "PARTIAL（Kafka opt-in）",
    "REF.INTAKE": "PARTIAL（批次 CLI，尚無排程部署）",
    "REF.REFINE": "PARTIAL（服務已落地，部署流程未完整）",
    "REF.HITL": "PARTIAL（OIDC 可用，compose 仍採過渡設定）",
    "REF.PUB": "PARTIAL（LiveSkill 預設路徑需 token；git 為 fallback）",
    "TEC.ID": "AS-BUILT（獨立部署 stack／共用 api codebase）",
    "TEC.MATCH": "PARTIAL（媒合已落地；獨立 OHS 邊界未拆）",
    "TEC.PROJ": "PARTIAL（Kafka opt-in；畫面尚非全由投影供應）",
    "TEC.SET": "PARTIAL（投影與跨品牌事件依 Kafka 啟用）",
    "PLT.IAM": "PARTIAL（Casdoor/config 存在；provisioning 未完整）",
    "PLT.EVT": "PARTIAL（Redis/Kafka opt-in）",
    "PLT.LLM": "AS-BUILT",
    "PLT.OBS": "PARTIAL（instrumentation 已落地；集中 collector/IaC 缺）",
    "PLT.FLOW": "TO-BE（M4 設計）",
    "PLT.CFG": "PARTIAL（M18/LiveSkill 已落地；完整 Studio 未完成）",
}

# 出現於 MODULE_ARCH.component 的每個分號分隔標籤都必須在此有定義。
# 生成器會反向驗證，避免再出現「看到名詞卻不知道到哪裡找」。
COMPONENT_GLOSSARY = {
    "line_gateway": {
        "alias": "LINE 通道閘道",
        "definition": "LINE 通道閘道：接收 webhook、驗證 X-Line-Signature、分派文字/照片/postback，並將文字與核准圖片回覆送回 LINE。",
        "boundary": "只負責通道整合與旁路轉發；不負責主要 AI 推理、定價或開工單。",
    },
    "Photo Guide resolver": {
        "alias": "品牌照片樣本圖解析器",
        "definition": "解析 AI 回覆文末的 photo-guide 標記、剝除內部標記並按設定附加 LINE ImageMessage；目前只核准 Chatlock 安裝前樣本圖。",
        "boundary": "只呈現預先核准的品牌靜態圖片；不讀取或辨識客戶照片，也不允許未設定品牌自行附圖。",
    },
    "Quote postback message mapper": {
        "alias": "報價回覆錯誤話術分類器",
        "definition": "依 QUOTE_EXPIRED、QUOTE_ALREADY_DECIDED、NOT_FOUND、FORBIDDEN 等 API error_code 產生對客戶可理解的 LINE 回覆。",
        "boundary": "只映射終態與錯誤話術；報價狀態機、權限與冪等仍由品牌 API 執行。",
    },
    "WebhookIdempotencyStore": {
        "alias": "LINE webhook 冪等保留庫",
        "definition": "在處理 LINE event 前以 mark-first 方式保留 event ID，重送時直接略過，避免重複回覆或建卡。",
        "boundary": "只治理 webhook 重播；不代替報價、工單與金流 mutation 的 Idempotency-Key。",
    },
    "AgentLoop": {
        "alias": "LockCore runtime（產品層）",
        "definition": "產品層 Turn 狀態機：恢復 session、組上下文、執行、儲存並產生一次回覆。",
        "boundary": "編排一次對話 Turn；不直接實作通用 tool-using LLM 迴圈。",
    },
    "AgentRunner": {
        "alias": "LockCore runtime（通用執行層）",
        "definition": "通用 Agent 執行器：在有界迴圈內呼叫模型、處理 tool calls，並在每輪執行上下文治理。",
        "boundary": "不知道報價、派工等產品流程；產品狀態由 AgentLoop、Skill 與 API 約束。",
    },
    "ReplyGuard": {
        "definition": "Agent 回覆出口守衛：攔截確定金額、錯誤型號、假稱已轉真人等違規輸出，必要時重生或轉人工。",
        "boundary": "是模型輸出的最後安全層；不取代 API 的報價、派工與權限硬閘。",
    },
    "SentimentClassifier": {
        "definition": "在不阻斷主回覆的前提下判定負面情緒並產生告警所需資料。",
        "boundary": "只做情緒分類與旁路告警；不單獨決定報價、派工或工單狀態。",
    },
    "ContextBuilder": {
        "alias": "LockCore runtime（上下文層）",
        "definition": "上下文組裝器：依序組合 identity、Customer Memory、always-skills 與 skill 摘要。",
        "boundary": "只建立模型輸入上下文；不負責永久儲存或模型供應商路由。",
    },
    "LiteLLMProvider + FallbackProvider": {
        "definition": "模型供應商層：以 model 字串路由多家 LLM，並在主供應商失敗時切換備援。",
        "boundary": "處理模型調用、重試與 failover；不承載業務規則或產品決策。",
    },
    "Model Orchestration Layer": {
        "definition": "供應商無關的模型編排層：集中管理路由、fallback、逾時、快取與調用效率。",
        "boundary": "是技術治理層，不是 Agent 產品流程、Skill 或知識庫。",
    },
    "ToolRegistry": {
        "definition": "Agent 工具登錄與白名單：定義哪些工具可被模型呼叫，並治理呼叫邊界。",
        "boundary": "不自行決定何時呼叫工具，也不向模型暴露未登錄的任意程式。",
    },
    "MemoryManager + Store": {
        "alias": "Memory",
        "definition": "長期記憶管理與存儲層：載入/寫回客戶已確認事實，讀寫必須同帶 tenant_id + user_id；預設 SQLite，可配置 PostgreSQL。",
        "boundary": "不等於當次 session 原始對話，不可跨租戶或使用者共用。",
    },
    "EscalationStore": {
        "definition": "轉真人稽核存儲：記錄轉接理由、已知事實快照與必要追溯資料。",
        "boundary": "保證轉人事件不蒸發；不是正式工單庫，也不代替 API 的開單 gate。",
    },
    "SkillsLoader + 2 builtin skills": {
        "alias": "Skills",
        "definition": "Agent 行為規範載入器：載入 product-knowledge 與 cs-sop，定義判斷、查資料、轉真人與紅線。",
        "boundary": "管「怎麼做」；不是長期對話記憶，也不是所有長尾事實的唯一資料庫。",
    },
    "SkillSync": {
        "definition": "輪詢品牌庫已發布的 skill revision，以原子交換同步到 workspace overlay，讓新版本在執行期生效。",
        "boundary": "只同步已發布版本且失敗時保留舊版；不自行核准 draft，也不覆寫平台保護層。",
    },
    "記憶 DB": {
        "alias": "Memory backend",
        "definition": "Agent 長期記憶的永久化後端，設計上使用 Postgres schema agent.*。",
        "boundary": "只存 Agent 記憶與相關稽核；不是品牌業務庫、平台庫或技師權威庫。",
    },
    "tenant-scoped routers": {
        "definition": "以 /tenants/{tid}/... 暴露品牌業務的 FastAPI 路由層，負責 HTTP 入口、輸入驗證與授權依賴。",
        "boundary": "不在 router 堆疊主要 SQL/業務邏輯；租戶與角色檢查交給標準守衛鏈。",
    },
    "Service Layer（problem_card / quote）": {
        "definition": "問題卡與報價服務層：管理診斷卡 gate、報價狀態、版本與不可否認快照。",
        "boundary": "不讓 Agent 或技師端直接定價；品牌 API 仍是報價權威。",
    },
    "Conversation media collector": {
        "alias": "對話照片掛卡器",
        "definition": "AI 建問題卡時反查同一對話近 24 小時內最多 5 張照片，依時間排序附加到 media_urls。",
        "boundary": "只掛接已持久化媒體 URL，採 append-only 且查詢失敗略過；不做任何影像辨識。",
    },
    "Service Layer（work_order）": {
        "definition": "工單服務層：建立工單、驗狀態轉移/gate、寫入時間軸並觸發副作用。",
        "boundary": "不允許 AI 繞過客戶確認與 HITL 直接轉工單。",
    },
    "Consent link service": {
        "alias": "免責同意簽署連結服務",
        "definition": "為工單產生公開簽署 token、保存 token hash 稽核並透過 LINE 推送；無 LINE 綁定時回傳可複製連結。",
        "boundary": "只負責交付簽署入口與稽核；簽署內容、角色/租戶授權與結案 gate 仍由 API 驗證。",
    },
    "Service Layer（dispatch）": {
        "definition": "派工服務層：執行候選查詢、指派、接單 SLA、擴大範圍與狀態更新。",
        "boundary": "不在品牌庫雙寫技師權威資料；媒合應經 OHS 與事件契約。",
    },
    "dispatch_service candidate scoring": {
        "alias": "現行媒合評分器",
        "definition": "現行派工服務直接由技師權威資料評估技能、品牌授權、距離、評分、工作量與公平性，產生候選排序。",
        "boundary": "這是共用 API codebase 的 interim 實作；目標 OHS/MatchingService 獨立服務邊界尚未拆出。",
    },
    "Service Layer（invoice / settlement）": {
        "definition": "帳單、收付、對帳與結算邏輯：管理金額狀態、冪等、reversal 與帳本一致性。",
        "boundary": "Billing 真相留品牌側；跨品牌技師 Settlement 由 technician-platform 匯總。",
    },
    "core/db.py": {
        "definition": "API 資料庫基礎層：管理品牌庫、技師權威庫與平台庫的連線取得、交易邊界及安全 fallback。",
        "boundary": "不放領域流程決策；業務交易應由 service 層調用。",
    },
    "API_SURFACE router filter": {
        "alias": "API 部署面塑形器",
        "definition": "同一 FastAPI codebase 依 API_SURFACE=dispatch/tech/platform 裁切路由與背景 worker，形成三個可獨立部署面。",
        "boundary": "只縮小部署暴露面，不是授權邊界；每個保留端點仍須 RBAC、租戶或平台守衛。",
    },
    "Portal Claim Guard": {
        "alias": "跨 portal token 守衛",
        "definition": "依 token 的 portal claim（或由角色推導）與部署面 ALLOWED_TOKEN_PORTALS 比對，拒絕技師、品牌、平台 token 跨面存取。",
        "boundary": "只隔離 API surface；同一 portal 內仍須由 role_required、租戶與資源規則決定可否存取。未設定 ALLOWED_TOKEN_PORTALS 的本機／測試環境不強制此 guard。",
    },
    "Three-DB Connection Router": {
        "alias": "三庫連線路由",
        "definition": "依資料權威將連線導向品牌庫、lock_tech 或 lock_platform，並可用 DB_URI_STRICT 阻止必要 URI 缺失時啟動。",
        "boundary": "治理資料庫選擇與 fail-closed；不代表 production migration 或 backfill 已完成。",
    },
    "DBPoolScopeMiddleware": {
        "definition": "在 request 生命週期建立與回收資料庫 pool scope，避免跨請求連線狀態滲漏。",
        "boundary": "只治理連線資源生命週期；不決定資料權威或業務交易內容。",
    },
    "DEKService + PII blind index + purge ledger": {
        "alias": "個資密鑰與清除稽核套件",
        "definition": "以每使用者 DEK、blind index 與 append-only purge ledger 支援個資查找、加密、忘卻與清除證據。",
        "boundary": "程式與 migration 存在不等於正式 KEK、backfill 與 production 部署已驗證。",
    },
    "internal_ingest.py": {
        "definition": "Agent 與內部服務使用的 /internal/* 入口，接收對話、轉人與報價回應等旁路資料。",
        "boundary": "只接受 fail-closed 內部憑證；不是 LINE webhook 入站門。",
    },
    "WebSocket 端點": {
        "definition": "經授權的即時推播連線入口，依 channel、技師與租戶將狀態更新送給前端。",
        "boundary": "是即時通知管道，不是業務事件的永久真相；斷線時頁面應可退化為 REST。",
    },
    "Redis pub/sub": {
        "definition": "跨實例的低延遲訊息擴散，用於 WebSocket fan-out、cache 與部分分散式鎖。",
        "boundary": "不保證長期持久與重播；需重播的事件應使用 Kafka 或資料庫。",
    },
    "Kafka": {
        "definition": "持久、可重播的跨系統事件骨幹；現行 producer/consumer 實作 topic 為 workorder.lifecycle、commission.accrued、technician.lifecycle。",
        "boundary": "不代替低延遲同步查詢（OHS/REST），也不代替各領域真相資料庫。",
    },
    "EventBusProducer": {
        "definition": "將受控領域事件序列化並發布到 Kafka；未設定 KAFKA_BOOTSTRAP 時按設計不啟用。",
        "boundary": "只發布已定義 topic 的事件；不保證所有設計中的萬用 wildcard topic 均已實作。",
    },
    "EventConsumerWorker": {
        "definition": "消費 Kafka 工單生命週期與佣金事件，使用 event_consumer_dedup 冪等更新技師 CQRS 投影。",
        "boundary": "需 KAFKA_BOOTSTRAP 才啟動；不把 projection 當成品牌工單或計費的命令真相。",
    },
    "分散式排程": {
        "definition": "跨實例協調 SLA、GDPR 硬刪、自動結案與 LINE outbox 等背景工作，並以鎖避免重複執行。",
        "boundary": "只觸發已定義任務；不把關鍵業務真相只留在 scheduler 記憶體。",
    },
    "PG Advisory Cron Leader": {
        "definition": "以 PostgreSQL advisory lock 選出單一排程 leader，避免多實例重複執行背景工作。",
        "boundary": "只協調任務執行權；不取代任務本身的冪等、重試與稽核。",
    },
    "line_push_service + outbox worker": {
        "definition": "LINE 出站推播與可重試佇列：業務交易先寫 outbox，worker 後送並記錄結果。",
        "boundary": "推播失敗不回滾主業務寫入；不處理 LINE 入站 webhook。",
    },
    "守衛鏈": {
        "definition": "API 授權鏈：get_current_user → require_tenant → role_required，加上 platform admin 與 internal token 邊界。",
        "boundary": "逐端點 deny-by-default enforce；不把前端隱藏按鈕當成安全控制。",
    },
    "core/errors.py": {
        "definition": "API 錯誤標準化元件：將例外轉為 RFC7807 problem+json 相容信封。",
        "boundary": "統一錯誤呈現與分類；不吞掉必須中斷的安全或交易錯誤。",
    },
    "core/idempotency.py": {
        "definition": "Mutation 冪等控制：以 Idempotency-Key 辨識重播，避免重複開單、收款或狀態轉移。",
        "boundary": "只保護重播語意；不代替業務狀態機與資料庫唯一約束。",
    },
    "Middleware": {
        "definition": "FastAPI 橫切處理鏈：處理 CORS、Request ID、版本廢棄等全局請求/回應邏輯。",
        "boundary": "不承載單一領域的核心業務規則。",
    },
    "AuthGuard": {
        "definition": "Web 根佈局的前端路由守衛：先做跨站導向，再檢查 token 與角色存取。",
        "boundary": "只是 UX 層門禁；真正授權必須由 API 守衛鏈 enforce。",
    },
    "appMode gate": {
        "definition": "判斷當前 portal build 是否服務某路徑，不屬於本站的路徑導向對應 portal。",
        "boundary": "是分站與導航控制，不是後端租戶或角色安全邊界。",
    },
    "rolePolicy": {
        "definition": "前端 route→roles 最長前綴政策表，控制導航與無權使用者的安全落點。",
        "boundary": "只提供前端 UX 治理；不代替 API role_required。",
    },
    "api client": {
        "definition": "Web 統一 HTTP client：注入 Bearer、X-Tenant-ID、Idempotency-Key，處理 refresh 與錯誤信封。",
        "boundary": "不在瀏覽器內繞過 API 授權，也不將客戶端狀態當作服務端真相。",
    },
    "AuthImage / AuthImageLightbox": {
        "alias": "需認證媒體縮圖與預覽",
        "definition": "對相對媒體 URL 以 Bearer + X-Tenant-ID fetch 後建立 Blob URL，統一呈現縮圖、錯誤佔位與放大預覽。",
        "boundary": "只在品牌後台呈現受保護圖片；不把 token 放進 img src，也不繞過媒體 API 授權。",
    },
    "ConsentPanel": {
        "alias": "工單免責同意面板",
        "definition": "品牌工作台顯示三段免責同意狀態，並讓授權人員發送或複製客戶簽署連結。",
        "boundary": "是操作與狀態顯示元件；不在前端自行判定簽署有效性或結案。",
    },
    "cache": {
        "definition": "Web GET 請求共享 in-flight 與短期 staleTime 快取，mutation 後可主動失效。",
        "boundary": "是前端效能優化；不是永久資料庫或授權依據。",
    },
    "realtime": {
        "definition": "WebSocket 訂閱層：一 channel 一 socket、處理重連 backoff，未設定時靜默降級。",
        "boundary": "負責前端即時連線生命週期；不是事件持久層。",
    },
    "型別（api.generated.ts）": {
        "definition": "由 OpenAPI 生成的 TypeScript API 型別，使前端在編譯期偵測契約漂移。",
        "boundary": "反映契約但不定義業務真相；不手改生成檔來代替 OpenAPI。",
    },
    "Medallion pipeline": {
        "definition": "離線資料流水線：將素材依 raw→bronze→silver 分層處理，保留來源與可重現性。",
        "boundary": "是 batch 與持久資產，不是長駐即時 API runtime。",
    },
    "source_to_raw": {
        "definition": "收集原始外部素材並原樣落地到 raw 層，保留來源識別與取得資訊。",
        "boundary": "不宣告內容已清洗或可直接用於 Agent 回答。",
    },
    "raw_to_bronze": {
        "definition": "將 raw 影音、網頁或文件轉錄與清洗為可審查的 bronze 素材。",
        "boundary": "只做可追溯轉換；不將未審核內容直接發布至知識庫。",
    },
    "bronze_to_silver": {
        "definition": "將 bronze 去冗、糾錯、語意切塊成 silver，並由程式覆寫 provenance 防止 LLM 幻覺來源。",
        "boundary": "silver 不等於已核可發布；下游仍需提煉、HITL 與 Publisher gate。",
    },
    "storage（raw/bronze/silver）": {
        "definition": "Medallion 各分層的持久檔案資產，保留原始、可審查與結構化中間成果。",
        "boundary": "是 pipeline 資產庫；不等於線上 pgvector 查詢庫。",
    },
    "SQL/Schema*.sql": {
        "definition": "資料庫基底 schema 定義，描述主表、索引與基礎約束。",
        "boundary": "不直接代替已上線環境的 forward-only migration 演進記錄。",
    },
    "forward-only migrations": {
        "definition": "只向前套用、有順序與可稽核性的 SQL schema 變更集。",
        "boundary": "不靠手改 production schema；漂移與重複套用必須由 CI/測試阻擋。",
    },
    "migration registry + routed apply": {
        "alias": "三庫 migration 登記與分流套用",
        "definition": "以 migration 檔頭的 migrate-targets 將 schema 變更分流套用到品牌、技師與平台庫，並各自寫入 schema_migrations，再由 drift-check 對照登記簿。",
        "boundary": "提供受控套用與可檢查性；不代表任何 production 環境已套用或資料 backfill 已完成。",
    },
    "platform schema": {
        "definition": "平台治理庫的獨立 schema，存管理員、品牌申請等跨租戶管理資料。",
        "boundary": "不存單一品牌內的工單、客戶或報價真相。",
    },
    "MCP RAG server": {
        "definition": "以 MCP 工具契約向 Agent 暴露產品手冊與相似案例的租戶授權檢索服務。",
        "boundary": "只負責事實檢索；不定義 Agent 行為，也不允許無 tenant ACL 直查 DB。",
    },
    "品牌庫 pgvector": {
        "definition": "每品牌物理隔離的 PostgreSQL/pgvector，存業務資料與該品牌唯一事實語料。",
        "boundary": "不跨品牌共用記錄；技師權威資料仍在 lock_tech。",
    },
    "rag_manual_chunks / case_entries": {
        "definition": "RAG 的手冊切塊與案例條目，帶租戶/品牌過濾、embedding 與 provenance。",
        "boundary": "是被查找的事實資料；不是 Skill 行為規範或對話 Memory。",
    },
    "outbox": {
        "definition": "與主業務交易同步寫入的待發送記錄，由 worker 重試投遞通知或事件。",
        "boundary": "解耦交易與外部副作用；不代替 Kafka 的跨系統長期事件日誌。",
    },
    "Audit Chain Checkpoint": {
        "alias": "稽核雜湊鏈重基準點",
        "definition": "以受鎖保護的鏈尾快照建立 append-only checkpoint，讓 audit verify 可從已核准的歷史基準後驗證並回報所有後續斷點。",
        "boundary": "只處理既有歷史鏈的非破壞式 re-baseline；不修正未來寫入流程，也不取代 audit event 的內容完整性驗證。",
    },
    "provenance / audit": {
        "definition": "記錄資料來源、處理版本、行為者與時間的可重現與稽核證據。",
        "boundary": "不允許 LLM 自行編造來源，也不把一般顯示日誌當成不可否認稽核鏈。",
    },
    "汲取層": {
        "definition": "知識精煉入口：收集 knowledge_ready 診斷卡與外部產品素材。",
        "boundary": "只撿取符合租戶與完整度 gate 的輸入；不直接發布到 Agent。",
    },
    "提煉分流器": {
        "definition": "將 silver 內容分為「可查找的事實」與「Agent 怎麼做的行為」兩條軌。",
        "boundary": "只產生 draft；未經 HITL 核可不得寫入 pgvector 或 Skill。",
    },
    "Draft Queue": {
        "definition": "事實 draft 與行為 diff 的審核佇列，包含來源、冪等鍵與狀態機。",
        "boundary": "是待審產物，不是已發布知識。",
    },
    "審核 UI backend": {
        "definition": "提供 draft 狀態轉移、diff 呈現、核可、駁回與 re-refine 的 HITL 後端。",
        "boundary": "不自動把 LLM 產物當真相；核可與發布仍是兩個可稽核步驟。",
    },
    "Casdoor reviewer auth": {
        "definition": "Refinery 審核服務可依環境使用 Casdoor RS256 OIDC 驗證 reviewer claims，並保留 HS256 過渡模式。",
        "boundary": "只驗證審核者身分與角色；compose 未提供 OIDC 設定時不可宣稱已完成正式切換。",
    },
    "Publisher": {
        "definition": "核可後的雙軌發布器：事實 embed 後寫 pgvector；行為產生 append-only Skill patch/artifact。",
        "boundary": "只發布 approved draft；不跳過 provenance、tenant 過濾或人審 gate。",
    },
    "behavior patch artifact": {
        "definition": "行為軌核可後產生 target_path + content 的受控 artifact，保存於 draft provenance，交由 apply CLI 消費。",
        "boundary": "artifact 仍不是已發布 skill；必須經 LiveSkill draft/人工發布或明確 git fallback 才生效。",
    },
    "LiveSkill DB ingest": {
        "definition": "apply_behavior 預設呼叫 internal skills ingest，將核可 artifact 以加性合併建立品牌 skill draft，再由後台人工發布。",
        "boundary": "需要 LOCK_API_BASE_URL 與 INTERNAL_API_TOKEN；缺少時只可走明確標示的 git fallback。",
    },
    "self-service routers": {
        "definition": "技師端自助 API：註冊、profile、技能/品牌授權、認證上傳、排班與工作台。",
        "boundary": "只服務已驗證的技師生命週期；不暴露跨租戶品牌內部資料。",
    },
    "technician_service": {
        "definition": "技師身分、技能、品牌授權、停復權與評分等核心領域服務。",
        "boundary": "真相寫入 lock_tech；不雙寫各品牌庫。",
    },
    "certification/kyc_service": {
        "definition": "技師 KYC 與認證申請/審核服務，對敏感欄位加密並控制准入。",
        "boundary": "未核可或已失效認證不得進入媒合候選集。",
    },
    "lock_tech": {
        "definition": "跨品牌技師身分域的獨立權威資料庫，存身分、技能、授權、排班、評分與結算 profile。",
        "boundary": "不存各品牌的完整工單或客戶敏感資料。",
    },
    "OHS API routers": {
        "definition": "品牌 API 查詢技師共享池的同步契約入口，包含技師查詢、媒合、排班與認證查詢。",
        "boundary": "主要做低延遲讀/媒合；指派與接單真相經業務命令及 Kafka 事件收斂。",
    },
    "schedule_service": {
        "definition": "管理技師排班、可用時段、接單後工作量與行程狀態。",
        "boundary": "不直接決定品牌工單狀態；跨系統變更經事件與投影對齊。",
    },
    "事件層": {
        "definition": "technician-platform 的 Kafka producer/consumer 與投影更新層，發技師狀態並收派工、工單與結算事件。",
        "boundary": "只以契約事件跨界；不直接連線或改寫品牌庫。",
    },
    "technician_workorder_projection": {
        "definition": "lock_tech 中由 workorder.lifecycle 事件維護的技師工單最小化投影。",
        "boundary": "只供技師查詢且 Kafka opt-in；不取代品牌工單真相，也尚未證明所有畫面都只讀此投影。",
    },
    "技師工單 read-model": {
        "definition": "由品牌 workorder.* 事件建立的最小化 CQRS 查詢投影，供技師工作台顯示。",
        "boundary": "只複製任務所需欄位；不是工單命令真相，不複製品牌全量敏感資料。",
    },
    "technician_commission_projection": {
        "definition": "lock_tech 中由 commission.accrued 事件維護的技師佣金 CQRS 投影。",
        "boundary": "只在 Kafka consumer 啟用時更新；不等於完整跨品牌 payout 已完成。",
    },
    "technician settlement services": {
        "definition": "現行技師佣金、statement 與 reconciliation 服務集合，提供逐案佣金與對帳視圖。",
        "boundary": "目前為 partial/interim；不宣稱不存在的單一 commission_settlement_service 或完整跨品牌出款已落地。",
    },
    "Tech DB router + mirror": {
        "alias": "技師權威庫路由與相容鏡射",
        "definition": "以 TECH_POSTGRES_URI 將技師身分寫入 lock_tech，並在過渡期按順序鏡射必要相容列到品牌側。",
        "boundary": "lock_tech 才是技師權威；鏡射是 interim 相容機制，不是長期雙寫架構。",
    },
    "Casdoor": {
        "definition": "集中式 IdP 與開通治理：提供 OIDC、租戶 org、角色 claims 與 License subscription。",
        "boundary": "發行身分與角色資訊；資源層授權仍由各 API deny-by-default enforce。",
    },
    "License Entitlement Gate": {
        "definition": "依平台庫 tenant license entitlement 判定租戶是否可使用選購能力；正式環境缺設定應 fail-closed。",
        "boundary": "是應用層授權檢查；不等於部署 per-brand bundle 的 provisioning 自動化。",
    },
    "平台維運 console": {
        "definition": "Super Admin 使用的中央管理前端，處理品牌申請、租戶治理、License 與跨品牌營運視角。",
        "boundary": "不當作單品牌日常派工後台，也不繞過 platform admin 授權。",
    },
    "License provisioning": {
        "definition": "License 核准後部署 per-brand bundle、建品牌庫、綁 LINE channel/設定並做健康檢查。",
        "boundary": "是開通與部署流程；不代替應用內租戶授權與資料隔離。",
    },
    "SigNoz": {
        "definition": "平台系統可觀測性服務，收集 OpenTelemetry metrics、logs、traces 並提供 dashboard 與告警。",
        "boundary": "看服務健康與系統行為；不專職管理 prompt 或模型 eval。",
    },
    "OPIK": {
        "definition": "Agent LLM Ops 工具，追蹤 prompt、LLM trace、token/成本與 eval 品質。",
        "boundary": "專注 AI 調用品質；不代替 SigNoz 的全系統可觀測性。",
    },
    "OpenTelemetry": {
        "definition": "服務不綁供應商的 metrics、logs、traces 儀表化與傳輸標準。",
        "boundary": "是觀測資料契約與傳輸層；不是 dashboard 或業務稽核帳本本身。",
    },
    "PIIScrubSpanProcessor": {
        "definition": "四站 Web 在 trace 匯出前遮蔽 email、電話、地址、token，並將 LINE UID 雜湊化。",
        "boundary": "只治理 observability 出站資料；不代替 API 回應遮蔽、資料庫加密或 GDPR 刪除。",
    },
    "Flow DSL executor": {
        "definition": "讀取 Vertical Pack 的宣告式 flow，驗 guard、執行 block、持久化狀態/事件並掛 SLA timer。",
        "boundary": "只執行可驗證 DSL；拒絕任意 inline code，也不把 UI 編輯器當執行後端。",
    },
    "domain blocks / primitives": {
        "definition": "雙層工單積木：對外是派工/報價/收款等粗顆粒 block，內部由查資料、轉狀態、發事件等 primitive 組合。",
        "boundary": "每顆積木必須有 inputs/preconditions/guards/effects 契約；不允許無法靜態驗證的自由腳本。",
    },
    "Vertical Pack": {
        "definition": "可版本化的產業配置包，組合 field metadata、flow、catalog、knowledge、UI composition 與 blocks。",
        "boundary": "承載產業/品牌差異；不改寫身分、金流、事件等平台不變核心。",
    },
    "FlowEditor": {
        "definition": "對 flow DSL 進行拖拉或表單編輯的薄 UI，輸出仍是可版控、可驗證的 DSL。",
        "boundary": "不直接執行任意程式；金流、派工與同意書仍受保護層及 HITL gate。",
    },
    "Agent Configuration Studio / Config Registry": {
        "definition": "管理 skill、RAG 權限、prompt、品牌設定與版本/分階段發布的中央配置能力。",
        "boundary": "租戶只可改客製層；安全、金額、工具白名單等保護層不可 override。",
    },
    "M18 Config Registry": {
        "definition": "已落地的配置服務與路由，管理受控 namespace、版本、canary 與回復流程。",
        "boundary": "只涵蓋現行 M18 配置能力；不等於完整 FlowEditor 或跨產業 Studio 已完成。",
    },
    "Skill Revision Registry": {
        "definition": "以 skill_revisions 保存品牌 skill draft/published 版本，供 SkillSync 取得已發布內容。",
        "boundary": "版本庫不自行核准內容；發布權限、保護層與稽核仍由 API/後台治理。",
    },
    "HITL 審核骨架": {
        "definition": "共用的 draft→diff→人審→核可/駁回→發布模式，同時支援知識精煉與 AI Onboarding Compiler。",
        "boundary": "AI 只產生 draft；高風險知識或流程未人審不得落地。",
    },
}

# 這是 Roadmap/WBS 的管理投影，不代表 code 已實作。
PHASE_BY_ID = {
    "FR-DAT-04": "M2",
    "FR-REF-01": "M2",
    "FR-REF-02": "M2",
    "FR-REF-03": "M2",
    "FR-REF-04": "M2",
    "FR-REF-05": "M2",
    "FR-TEC-01": "M2",
    "FR-TEC-02": "M2",
    "FR-TEC-03": "M2",
    "FR-TEC-04": "M2→M3",
    "FR-TEC-05": "M3",
    "FR-TEC-06": "M3",
    "FR-TEC-07": "M2",
    "FR-TEC-08": "M2",
    "FR-PLT-01": "M2",
    "FR-PLT-03": "M3",
    "FR-PLT-04": "M1→M3",
    "FR-PLT-05": "M1→M2",
    "FR-PLT-06": "M1",
    "FR-PLT-07": "M4",
    "FR-PLT-08": "M4",
    "FR-PLT-09": "M2→M3",
}

PHASE_OVERVIEW = [
    ["M1", "上線硬化", "單品牌全鏈正確、即時、可稽核", "RBAC enforce、工單狀態機、急件補審、對話存檔、Redis/cron、可觀測、AI eval、SIT/UAT", "27_Product_Roadmap_WBS §3 M1"],
    ["M2", "身分・知識・技師平台", "三條獨立能力線成形", "Casdoor、RAG-via-MCP、knowledge-refinery/HITL、technician-platform、API 收旂", "27_Product_Roadmap_WBS §3 M2"],
    ["M3", "多品牌規模化", "第 2 品牌用標準流程開站", "Kafka/CQRS、對帳閘門、License provisioning、雲端拓撲、開站演練", "27_Product_Roadmap_WBS §4 M3"],
    ["M4", "平台化地基", "把鎖匠版抽象成產業無關引擎", "flow DSL、積木契約、兩層渲染、Vertical Pack、FlowEditor", "27_Product_Roadmap_WBS §4 M4/M5"],
    ["M5", "第 2 產業", "驗證 FDE 四配置面與積木飛輪", "手工 bootstrap 新產業積木，再疊加 AI Onboarding Compiler + HITL", "27_Product_Roadmap_WBS §4 M4/M5"],
]

ARCH_CHOICES = [
    ["AC-01", "平台核心 vs 領域配置", "六大不變原語由核心掌握，產業差異放進 Vertical Pack 四配置面", "降低跨產業客製對核心的污染", "ADR-001 / 12_SAD §1.3"],
    ["AC-02", "per-brand 物理隔離", "每品牌一套 bundle 與 DB；技師、IdP、事件骨幹為集中共用", "隔離強，但 provisioning/運維成本必須自動化", "ADR-002 / ADR-020"],
    ["AC-03", "Casdoor 統一身分與 License", "OIDC org=租戶，role claim 供 API enforce，subscription 當開通閘門", "跨品牌關鍵單點，需 HA 與 fail-soft", "ADR-004 / ADR-005"],
    ["AC-04", "Kafka + Redis + 讀寫分離", "Kafka 負責持久可重播，Redis 負責 WS fanout/cache/lock，Postgres 分離熱讀", "需 schema 契約、冪等、reconcile 與演練", "ADR-006"],
    ["AC-05", "Skill 行為 + RAG-via-MCP 事實", "Skill 定義怎麼做；pgvector 為唯一長尾事實語料，經 MCP 檢索", "須保持 provenance、租戶 ACL 與 references 同源", "ADR-010 / ADR-030"],
    ["AC-06", "Flow-as-Blocks DSL-first", "流程是資料，guard→block→持久化/事件/SLA；拒絕 inline code", "引擎、契約與靜態驗證先於拖拉 UI", "ADR-013 / ADR-014"],
    ["AC-07", "AI 永不自轉工單", "AI 只能診斷、草擬問題卡與轉人；報價/開單/金流需決定性 gate 與 HITL", "合約與金錢風險的上線紅線", "ADR-025 / 04_SRS FR-AGT-11"],
    ["AC-08", "報價快照不可否認", "已送出報價綁 immutable content-addressable snapshot，修改以 v+1 串鏈", "防止定價規則改動回溯污染與爭議", "ADR-026 / FR-API-02/03"],
    ["AC-09", "技師只發 requote command", "技師可提交項目 diff 但無定價權；品牌 API 為報價唯一權威", "跨系統需 tenant route、冪等與降級", "ADR-027 / FR-TEC-07"],
    ["AC-10", "契約三分層", "執行期匯出為型別 SSOT，OpenAPI/AsyncAPI 為對外投影，文件為解釋", "程式與文件 drift 必須在 CI 擋下", "ADR-031"],
]

GLOSSARY = [
    ["per-brand bundle", "每個品牌獨立部署的 web/api/agent/DB/Redis/RAG 組合", "品牌間物理隔離，開新品牌等於再供應一套"],
    ["集中共用平台", "Casdoor、SigNoz、technician-platform、Kafka、平台 console", "跨品牌管理的共用地基，需視為關鍵單點"],
    ["ProblemCard", "AI/客服在正式報價與工單前的結構化診斷卡", "案件先收旂完整，才可進報價/工單"],
    ["Clarify gate", "AI 回答後主動確認是否已釐清", "不把「有幫助」誤當「問題已解決」"],
    ["Flow-as-Blocks", "宣告式狀態機 + 有契約的領域積木", "用配置組流程，金流/派工/同意書仍受強制 gate 保護"],
    ["Vertical Pack", "field metadata + flow + catalog + knowledge + UI composition + blocks", "一個產業的可版本化配置包"],
    ["OHS API", "品牌 API 查詢技師共享池的同步媒合契約", "品牌不直連技師庫，指派/接單改走事件"],
    ["CQRS 投影", "品牌工單是 command 真相，技師平台維護最小化 read model", "技師看得到必要工單，但不複製品牌全量敏感資料"],
    ["HITL", "Human-in-the-loop 人工審核閘門", "知識、金流、派工、同意書等高風險產出不可直接上線"],
    ["Skill 行為驅動", "Skill 存 SOP、紅線與檢索程序", "管「怎麼做」，不把長尾事實全塞進 prompt"],
    ["RAG-via-MCP", "透過 MCP server 查 pgvector 唯一事實語料", "事實可更新、可分租戶授權，agent 不與 DB 綁死"],
    ["SigNoz / OPIK", "系統 OTel 可觀測 / Agent LLM Ops", "一個看服務健康，一個看 prompt、trace 與 eval 品質"],
    ["SoD", "Initiator / Approver / Executor 任二相同即拒絕", "敏感金流與審批不能一人包辦"],
]

TEST_STRATEGY = [
    ["Risk-based", "先驗金錢、授權、跨租戶、合約紅線與工單主流", "P0 未結清不可發布；其他依衝擊與替代路徑排序"],
    ["Shift-left", "需求評審就以驗收表逐條對齊", "在寫 TC 前先清理待確認門檻與 ID 衝突"],
    ["Contract-first", "OpenAPI / AsyncAPI / OHS / internal API 經 consumer-driven test", "跨庫不靠 FK，跨服務更需要 schema、冪等與失敗契約"],
    ["State-transition", "對 Quote / WorkOrder / Onsite / Payment 以狀態轉移測試", "每條法定轉移、非法轉移、guard、超時與冪等都要有證據"],
    ["Observability-as-evidence", "實際 SLI、audit hash、trace 與 reconcile 是驗收證據", "不用「畫面有出現」取代事件、帳本與稽核正確性"],
]

TEST_TYPES = [
    ["階段", "Unit / Component", "函式、類別、guard、parser、pricing 規則與狀態轉移單元", "RD 主責，CI 每次合併必跑"],
    ["階段", "Integration / Contract", "agent→api internal、api→OHS、Kafka consumer、DB migration", "RD + QA；正反例、冪等、timeout、版本相容"],
    ["階段", "System / E2E", "LINE→問題卡→報價→工單→派工→現場→結算", "QA 主責，以完整使用者旅程驗證"],
    ["階段", "UAT", "合約紅線、品牌營運、技師、消費者與平台治理", "業務 Owner 簽核，QA 提供證據"],
    ["類型", "Security / Privacy", "RBAC、SoD、服務憑證、工具白名單、PII、GDPR、租戶隔離", "P0；必含權限負例與 fail-closed"],
    ["類型", "Performance / Resilience", "LINE latency、OHS、WS、outbox、Kafka lag、單點失敗", "k6/chaos/replay；記錄 p95/p99 與降級行為"],
    ["方法", "Boundary / Decision table", "0.85 completeness、5/10/20km、500/2000 金額階梯、5/10/30min SLA", "準備門檻前、等於門檻、門檻後資料；逐組執行並核對狀態、金額、事件與 audit"],
    ["方法", "Mutation / Negative", "偽造 token、重放、跨租戶 ID、非法狀態、schema drift", "修改一個輸入或前置條件後重跑主流，確認 guard fail-closed 且不產生副作用"],
]

BUG_LEVELS = [
    ["P0 / Blocker", "金錢錯帳、授權繞過、跨租戶洩漏、合約紅線、工單主流無替代路徑", "任一 open → Release/UAT Fail", "立即止血、留 audit，需 root cause + regression"],
    ["P1 / Major", "主流斷點、審計斷鏈、SLA 引擎失效，有昂貴手動替代", "未結 → 至多 Conditional Pass", "需明確修復日與補償控制"],
    ["P2 / Normal", "次要功能、UX、非阻斷效能偏差", "可進 backlog，不得掩蓋 KPI 紅線", "依影響版本排程"],
    ["P3 / Minor", "文案、非核心外觀、無任務影響的不一致", "不阻發布", "批次收旂處理"],
]

ENVIRONMENTS = [
    ["Local / CI", "每次 commit / PR", "unit、lint、typecheck、schema diff、migration drift、AI eval dry", "快速回饋；不放真實 PII"],
    ["Integration", "契約或跨服務變更", "internal/OHS/OpenAPI/AsyncAPI、DB migration、outbox/Kafka/Redis", "固定 fixture + 可重建三庫"],
    ["Staging / SIT", "里程碑測試", "全鏈場景、RBAC 矩陣、效能、chaos、回歸", "拓撲近似 production，資料去識別"],
    ["UAT", "業務簽核", "S1–S5 旅程、K1/K3/K8、合約與稽核報表", "業務 Owner 簽名；紀錄版本、資料集與證據"],
    ["Production smoke", "發布後", "health、登入、LINE webhook、關鍵讀路徑、告警", "禁止破壞性測試；異常立即 rollback"],
]

STLC = [
    ["1. Requirement review", "確認使用者行為、前後條件、量化門檻與例外", "驗收控制表 + 待裁定清單"],
    ["2. Test analysis", "將前線需求轉成風險、端到端場景與可判定的測試項目", "⑧必測行為 + ⑨場景 + ⑩執行清單"],
    ["3. Test design", "對邊界、決策、狀態、權限與逾時寫可重現步驟", "前置資料 + 步驟 + 預期結果"],
    ["4. Execution", "保存版本、輸入、log/trace/audit、實測值與截圖", "SIT/UAT 證據包 + defect"],
    ["5. Closure", "QA Lead 確認覆蓋與追溯，清理缺口並取得簽核", "追溯健康報告 + 簽核"],
]

TEST_STAGES = [
    ["SIT-1 子系統", "各服務功能與契約穩定", "Unit/component 綠；資料庫可重建", "P0/P1 契約測試全綠，無 blocker"],
    ["SIT-2 跨系統", "LINE、internal API、OHS、WS、outbox/Kafka、三庫同步", "SIT-1 通過；類 production 拓撲", "TS-01–TS-12 P0 通過，reconcile/hash 無差異"],
    ["UAT", "業務旅程與合約驗收", "SIT-2 通過；業務 Owner/資料集到位", "P0=0；K1/K3/K8 等門檻通過；簽核"],
    ["Release candidate", "只做回歸與發布演練，不再大幅探索", "UAT Pass/Conditional 且例外有補償控制", "rollback <30min 演練、smoke 通過、告警正常"],
]

RESPONSIBILITIES = [
    ["Requirement / acceptance review", "PM/BA", "QA+RD", "主鍵唯一、關鍵字可測、例外與門檻無歧義", "驗收控制表裁定"],
    ["Unit / component", "RD", "QA 抽驗", "函式、guard、狀態機、parser、pricing、migration", "CI report"],
    ["API / contract", "RD", "QA", "OpenAPI/AsyncAPI/internal/OHS，正反例+版本+冪等", "contract report"],
    ["System / E2E", "QA", "RD+OPS", "以 TS 場景驗證跨服務與主流", "SIT evidence"],
    ["NFR / chaos", "QA+OPS", "RD", "效能、可用、降級、告警、回復、容量", "benchmark + drill"],
    ["UAT / sign-off", "Business Owner", "PM+QA", "業務適用性與合約紅線", "22_UAT 簽核"],
]

SCENARIOS = [
    ["TS-01", "LINE AI 自助與轉真人", "P0", "驗簽進線→Turn→案例/RAG→Clarify；急件/紅線必轉人", "品牌 LINE channel、知識與 internal token 可用", "送文字/照片/急件/假簽章/重送→對話、問題卡、escalation 對帳", "Functional / Security / Resilience"],
    ["TS-02", "問題卡→報價→開單", "P0", "驗證 completeness、報價快照、LIFF 確認與 AI 永不自轉工單", "一般案件與保固/建案 fixture", "草擬卡→補齊→quote v1→送客→確認→CS 1-click→WO created", "State / Boundary / Security"],
    ["TS-03", "自動派工與技師接單", "P0", "驗證 OHS 品牌/技能/距離/可用性過濾、接單 SLA 與即時投遞", "已 created 工單，有/無合格技師資料", "5→10→20km 媒合→指派→技師接/拒/逾時→品牌狀態與投影對帳", "Contract / State / Timeout"],
    ["TS-04", "現場、加價、requote 與結案", "P0", "驗證 500/2000 階梯、同意 fallback、quote v+1、三件套與急件補審", "技師為 assignee，工單 in_progress", "到場→施工→三種加價邊界→客戶接/拒→存證→結案 gate", "Boundary / Decision / State"],
    ["TS-05", "收款、退款、帳本與結算", "P0", "證明冪等、SoD、reversal、borrow=lend 與品牌 Billing/平台 Settlement 邊界", "已完工工單、支付/退款/月結 fixture", "收款→對帳→退款分層→月結→commission event→reconcile", "Ledger / SoD / Idempotency"],
    ["TS-06", "技師註冊、KYC 與生命週期", "P0", "未核可/停權技師不得入候選池，品牌授權 fail-closed", "Casdoor 與技師平台可用", "註冊→敏感文件→審核→品牌授權→排班→停權/復權", "Lifecycle / Security / Privacy"],
    ["TS-07", "知識精煉 HITL 閉環", "P0", "bronze-only→事實/行為分流→人審→pgvector/skill；未核可零落地", "診斷素材、refinery、審核 UI 與 Publisher 可用", "汲取→提煉→diff→核可/拒絕→雙路發佈→來源/租戶對帳", "Data quality / HITL / Provenance"],
    ["TS-08", "租戶、OIDC、RBAC 與 License 開通", "P0", "驗證單一身分、四方角色、deny-by-default 與 per-brand provisioning 邊界", "Casdoor / platform console / 三個 API surface 可用", "品牌申請→核准→org/License→bundle/建庫/綁 LINE→角色矩陣負測", "Security / Provisioning / Isolation"],
    ["TS-09", "資料、migration 與 audit 可重現", "P0", "三庫不 fallback、migration 無 drift、pipeline 冪等、hash chain 可驗", "乾淨與升級路徑 DB fixture", "從空庫/舊版套 migration→重套→注入 drift→跑 raw/bronze/silver→驗 hash", "Migration / Reproducibility / Mutation"],
    ["TS-10", "安全、隱私與合約紅線", "P0", "橫向驗證 prompt/tool、PII、GDPR、影像禁用、Family review、跨租戶", "權限矩陣、對抗題庫、retention/legal-hold fixture", "全端點矩陣→攻擊/跨租戶→forget/legal hold→影像 double gate→Family review", "Security / Compliance / Adversarial"],
    ["TS-11", "效能、容量、降級與可觀測", "P1", "量測 LINE/OHS/WS/outbox p95/p99，服務單點失敗時能降級與告警", "類 production 拓撲與 SigNoz/OPIK 可用", "階梯壓測→斷 LLM/Redis/Kafka/OHS/Casdoor→觀察降級、lag、alert、recovery", "Performance / Chaos / Observability"],
    ["TS-12", "Flow/Vertical Pack/Agent Config 治理", "P1", "DSL 靜態驗證、保護層不可 override、staged rollout/eval/rollback 有稽核", "Flow engine / Config Registry 與範例 pack 可用", "匯入 pack→非法 DSL→高風險 HITL→canary→SLO halt→rollback→audit 對帳", "Schema / Policy / Rollout"],
]

DOMAIN_TEST_META = {
    "AGT": ("AI 客服", "轉人不得蒸發、AI 金額/影像紅線", "驗簽、知識命中、Clarify、急件、記憶隔離、dedup", "用正常、假簽章、重送、急件與對抗訊息驅動 LINE 流程；核對 Turn、問題卡、轉人、記憶與 audit", "TS-01、TS-10"),
    "API": ("派工控制", "報價/工單/金流狀態錯誤會產生合約與錯帳", "狀態轉移、金額階梯、SLA、冪等、SoD、audit", "以 API fixture 建立各狀態；送合法/非法轉移、邊界金額、重送、越權與 timeout；核對 HTTP、DB、事件、帳本與 audit", "TS-02–TS-05、TS-10"),
    "WEB": ("多站前端", "前端 gate 不可被當成唯一授權邊界", "APP_MODE 路由、RBAC UX、WS 降級、LIFF、a11y", "用 Playwright 依 APP_MODE/角色走主流，再注入 403、斷網與 WS 中斷；核對路由、操作 gate、提示、後端狀態與 axe 結果", "TS-02、TS-03、TS-08、TS-11"),
    "DAT": ("資料平台", "庫路由、provenance 或 migration drift 會導致隱性污染", "三庫隔離、重套、重跑、bronze-only、hash chain", "以固定 raw/DB fixture 重跑 pipeline/migration，注入 tenant/schema/provenance 變異；比較筆數、hash、來源、drift 與 audit", "TS-07、TS-09、TS-10"),
    "REF": ("知識精煉", "未核可或錯來源知識落地會放大 AI 幻覺", "事實/行為分流、diff、HITL、Publisher、Family review", "用核可、拒絕、重複、錯來源與錯租戶素材跑 intake→diff→HITL→Publisher；對帳 pgvector、skill、git 與 provenance", "TS-07、TS-10"),
    "TEC": ("技師平台", "跨品牌身分與投影易誤放行/過度暴露", "KYC、品牌授權、OHS、接單、CQRS、requote、settlement", "建立有效/未核可/停權技師與多品牌 fixture，跑註冊、媒合、接拒單、requote、投影與結算；核對授權、事件、SLA 與資料最小化", "TS-03、TS-04、TS-06"),
    "PLT": ("平台核心", "集中單點與可編輯配置會放大全品牌 blast radius", "OIDC/RBAC、License、Kafka/Redis、observability、DSL、Config rollout", "以租戶×角色×License 矩陣跑正常與越權操作，再中斷共用元件或推送非法配置；核對 fail-closed、降級、告警、rollback 與 audit", "TS-08、TS-11、TS-12"),
}

NFR_DOMAIN_META = {
    "PERF": ("效能・可用・容量", "設計目標未實測或共用單點未演練", "p95/p99、錯誤率、重播、降級、容量與 SLA 邊界", "依基準、目標與尖峰三段負載執行 k6/浸泡，再逐一中斷依賴；保存 p95/p99、錯誤率、降級、告警與恢復時間", "TS-11"),
    "SEC": ("安全・隱私", "租戶越權、AI 越權、PII 外洩屬上線紅線", "OIDC/RBAC/SoD、加密、tool sandbox、GDPR、retention、投影最小化", "以租戶×角色×資源矩陣執行允許/拒絕案例，加入偽造 token、跨租戶、prompt/tool 攻擊與 GDPR 流程；核對 deny、零副作用及 audit", "TS-08、TS-10"),
    "OPS": ("品質・稽核・維運", "缺乏 provenance/audit/rollback 時無法證明系統正確", "OTel、hash chain、bronze-only、migration、CI、a11y、DORA", "用固定 fixture 重跑、重套與故障恢復，對帳 hash/provenance/trace/報表；再執行 CI 掃描、a11y 人工抽測與 rollback 演練", "TS-07、TS-09–TS-11"),
}

# QA 主視圖使用的可執行語言。舊 DOMAIN_TEST_META 保留給架構/治理附錄，
# 不得再把單純名詞串當成「QA 測試條件」。
DOMAIN_QA_CHECKS = {
    "AGT": (
        "1. 有效簽章應受理；錯誤簽章應拒絕且不建案。\n"
        "2. 可命中知識的問題應引用正確來源；無法回答時應詢問或轉人，不得編造。\n"
        "3. 缺項應依情境一次列齊；明確要求真人、急迫派工、金錢相關或連續兩次不滿時，應建立後台案件並轉真人，不採固定三輪計數。\n"
        "4. 不同品牌/客戶不得讀到對方對話與記憶。\n"
        "5. 同一事件重送不得重複回覆、建案或轉人。",
        "準備正常/錯誤簽章、可/不可命中問題、急件、跨品牌與重送輸入；逐組核對回覆、後台案件、轉人紀錄與重複資料數。",
    ),
    "API": (
        "1. 允許的狀態變更應成功，非法順序應拒絕且資料不變。\n"
        "2. 499/500/2000/2001 元與 5/10/20 公里等邊界值應落在正確規則。\n"
        "3. 同一請求重送只能有一次實際效果。\n"
        "4. 未授權角色與申請/核准同人情境應被拒絕。\n"
        "5. API 結果、資料庫狀態、事件、帳本與稽核紀錄應一致。",
        "先以正常資料完成一次主流，再每次只改一個條件：非法狀態、邊界值、重送、錯角色或逾時；比對操作前後資料與帳本。",
    ),
    "WEB": (
        "1. 不同站點模式只應進入對應頁面。\n"
        "2. 每個角色只看到可用功能；手動呼叫被隱藏功能的 API 仍應被拒絕。\n"
        "3. 斷網、403 與即時連線中斷時應顯示可理解提示，不可顯示假成功。\n"
        "4. 關鍵頁面應可用鍵盤操作，無關鍵無障礙錯誤。",
        "用 Playwright 以各站點模式與角色完成主流；再斷網、中斷即時連線、注入 403 並手動呼叫無權 API；核對畫面、後端狀態與無障礙掃描。",
    ),
    "DAT": (
        "1. 每類資料只能寫入指定資料庫，不可自動改走其他庫。\n"
        "2. 同一升級與同一輸入重跑後，資料筆數與內容應一致。\n"
        "3. 正式知識只能來自受控原始層，每筆資料必須查得到來源。\n"
        "4. 版本差異與稽核紀錄竄改必須可偵測。",
        "使用固定輸入與空庫/舊版庫各跑一次，再重跑一次；刻意更改租戶、資料庫連線、來源標記、版本與稽核紀錄；比對路由、筆數、hash 與告警。",
    ),
    "REF": (
        "1. 不同內容類型應分到正確審核流程。\n"
        "2. 核可前正式知識庫新增數必須為 0；拒絕後也不得發佈。\n"
        "3. 重送同一來源不得產生重複知識。\n"
        "4. 錯租戶與錯來源的素材應被拒絕。\n"
        "5. 需覆核內容必須 100% 進入指定審核。",
        "用核可、拒絕、重複、錯來源與錯租戶素材完成一輪匯入→差異比對→人審→發佈；核對正式知識庫、版本庫、來源與審核紀錄。",
    ),
    "TEC": (
        "1. 未核可、未受品牌授權、已停權或非排班時段的技師不得入候選池。\n"
        "2. 接單、拒單與逾時必須在品牌端與技師工作台同步。\n"
        "3. 技師只能提出加價事由，不能自行定價。\n"
        "4. 技師工作台只顯示作業所需的最少資料。\n"
        "5. 品牌計費與平台結算差額必須為 0。",
        "建立已核可/未核可/已停權與不同品牌技師，完成註冊、媒合、接拒單、加價與結算；核對候選池、兩端狀態、顯示欄位與帳務差額。",
    ),
    "PLT": (
        "1. 每種角色與品牌只能執行授權內操作，錯誤或過期憑證應拒絕。\n"
        "2. 未取得有效授權的品牌不得開站或使用服務。\n"
        "3. 中斷共用依賴時，系統應明確降級、告警且不污染資料。\n"
        "4. 不合法或超越安全邊界的設定不得發佈。\n"
        "5. 新設定指標異常時必須停止擴大並回復上一版。",
        "以兩個品牌×各角色×有效/無效授權執行正反例；再逐一中斷共用依賴與發佈不合法設定；核對拒絕、降級、告警、回復版本與稽核紀錄。",
    ),
    "PERF": (
        "1. 在基準、目標、尖峰三段負載下量測速度與錯誤率。\n"
        "2. 持續負載期間不可出現記憶體或連線數持續上升。\n"
        "3. 中斷單一依賴時應降級與告警，不得全面雪崩。\n"
        "4. 依賴恢復後，堆積請求與資料應能正確補處理。\n"
        "5. 實測值必須逐項比對文件闀檻。",
        "鎖定版本、資料集與壓測腳本；先跑三段負載，再逐一中斷依賴；保存 p95/p99、錯誤率、降級回應、告警與復原時間。",
    ),
    "SEC": (
        "1. 每種角色必須同時有允許與拒絕案例。\n"
        "2. 錯品牌 ID、偽造/過期憑證與跨品牌存取必須被拒絕，且資料不變。\n"
        "3. AI 被誘導時不得擅自定價、派工、辨識影像或呼叫未授權工具。\n"
        "4. 敏感資料不得出現於非必要 API、畫面、log 與技師投影。\n"
        "5. 個資刪除、保留與稽核應符合規則。",
        "建立品牌×角色×資源矩陣執行正反例；加入錯誤憑證、跨品牌 ID、AI 對抗輸入、個資刪除與法定保留；核對拒絕、資料零變更與稽核紀錄。",
    ),
    "OPS": (
        "1. 同一輸入重跑後，輸出筆數、內容與來源應一致。\n"
        "2. 資料庫升級從空庫與舊版都能完成，重套不失敗。\n"
        "3. 稽核紀錄被更改時必須可偵測。\n"
        "4. 回滾演練必須在規定時間內恢復，並不遺失已確認資料。\n"
        "5. CI、無障礙與發佈指標必須依各自闀檻裁定通過與否。",
        "用固定資料執行重跑、資料庫重套、稽核竄改與回滾演練；比對輸出 hash、來源、trace、報表與恢復時間；再執行 CI 與無障礙掃描。",
    ),
}

SCENARIO_PASS_CRITERIA = {
    "TS-01": "正常訊息有回覆且只處理一次；錯誤簽章不建案；缺項依情境一次列齊，命中明確真人、急迫派工、金錢或連續兩次不滿任一紅線即建立後台案件並轉真人。",
    "TS-02": "未完整資料不得報價；報價與規則快照一致；只有客服明確操作能開單；拒絕或越權不改變狀態。",
    "TS-03": "候選者全數符合品牌、技能、距離與可用條件；接/拒/逾時正確同步；無候選者時進入待處理並告警。",
    "TS-04": "加價落在正確審批層級；技師無法直接定價；客戶拒絕時不套用新價；存證缺一不得結案。",
    "TS-05": "同一請求只有一筆帳；退款保留原交易與反轉紀錄；同一人不能申請又核准；兩端帳務差額為 0。",
    "TS-06": "只有已核可、已授權且在排班中的技師出現在候選池；停權立即生效；敏感原文件不出現在一般 API、log 或畫面。",
    "TS-07": "只有核可內容被發佈；拒絕、錯來源與錯租戶內容落地數為 0；重送不重複；來源、審核人與版本可查。",
    "TS-08": "允許的操作成功；錯品牌、錯角色與無效憑證操作被拒絕且資料無變更；品牌間不得看到對方資料。",
    "TS-09": "空庫與舊版升級結果一致；重套與重跑不重複；不走錯庫；版本差異與稽核竄改均觸發失敗或告警。",
    "TS-10": "未授權與跨品牌操作全數被拒絕且零副作用；AI 不執行金額、派工與影像辨識紅線；刪除、保留與覆核符合規則。",
    "TS-11": "各指標達到 NFR 闀檻；依賴失敗時沒有全面 5xx 或資料污染；降級、告警與 trace 可查；恢復後堆積資料能補處理。",
    "TS-12": "不合法或越界設定發佈數為 0；高風險設定未核可不上線；異常時停止擴大並恢復上一版；審核與發佈紀錄可查。",
}

ARCH_RISKS = [
    ["架構", "R-01", "Casdoor /集中共用元件為跨品牌單點", "全品牌登入、派工或治理受阻", "HA+備份；per-brand bundle fail-soft；演練", "12_SAD §12"],
    ["架構", "R-02", "Kafka schema 治理與消費者相容", "投影、結算或通知靜默失敗", "schema registry + consumer-driven contract + replay", "12_SAD §12"],
    ["架構", "R-04", "品牌自服務配置擴大攻擊面與品質風險", "全品牌 AI 行為或內容劣化", "保護層 + eval gate + staged rollout + rollback + audit", "12_SAD §12 / ADR-012"],
    ["架構", "R-06", "技師平台/OHS 是派工關鍵依賴", "全品牌無法自動媒合", "OHS SLO + cache/queue 降級待裁定 + 契約測試", "12_SAD §12 / 05_NFR Failure Modes"],
    ["契約", "CT-01", "FR-TEC 主鍵碰撞已治理", "報價修正保留 FR-TEC-07；排班生命週期改為 FR-TEC-08", "生成器驗證 FR 全數唯一，QA 映射以新鍵輸出", "04_SRS:355-356"],
    ["契約", "CT-02", "21_Traceability 聲稱使用 SRS FR，主表卻是 FR-0001 舊鍵", "FR→TC 無法直接 join，覆蓋率易被高估", "新增 SRS FR 欄或將舊鍵明確降級為 legacy display", "21_Traceability §2"],
    ["契約", "CT-03", "20_Test_Cases 已建立 171 筆 QTM 正式 SRS REQ→TC 鍵", "97 筆詳細 TC 的舊 FR/來源欄不再承擔現行追溯", "QTM 列數與唯一鍵納入生成驗證；無 QTM 視為文件遺漏", "20_Test_Cases §2.1"],
    ["實作", "IM-01", "文件中既有🔜規劃中文字，又有 2026-07-21 codegraph 標注已落地", "直接以關鍵字統計會誤判實作率", "四書僅表示「需求定版/規劃訊號」，實作完成以 WBS/code/SIT 證據另對帳", "05_NFR 末段 / 27_Roadmap"],
    ["實作", "IM-02", "technician-platform 是獨立部署 stack，但後端共用 api codebase", "若仍寫成待確認的獨立 codebase，SAD/SDS 與程式無法對回", "Current 標 API_SURFACE=tech + lock_tech；Target OHS 邊界另列 To-Be", "12_SAD §4.5 / 15_SDS §7"],
    ["契約", "CT-04", "consents:send-link 已回填 api/openapi.yaml 與 16_API_Spec", "靜態契約與 runtime 仍須以 SIT runtime OpenAPI export 驗證", "G2 匯出 schema 並驗 operationId/response；未有環境輸出不可標 production-ready", "api/routers/work_orders_v2.py / api/openapi.yaml / 16_API_Spec"],
    ["部署", "DP-01", "Redis/Kafka/RAG/OIDC/Refinery/Observability 多項為 code-present 或 opt-in", "檔案存在會被誤判為 production 已啟用", "Code reality 用 PARTIAL；以部署 env、migration、SIT 與 dashboard 證據升級狀態", "Codebase現況掃描_2026-07-27"],
    ["驗收", "QA-01", "部分 SRS/NFR 仍含 [待確認] 量化門檻", "測試可執行但無法客觀判定 pass/fail", "由 PM/Architect 在 UAT 前將門檻、量測點、資料集與 owner 定版", "04_SRS / 05_NFR"],
]

# QTM 正式映射所指定的 TC；詳細 TC 舊來源欄只作歷史稽核。
