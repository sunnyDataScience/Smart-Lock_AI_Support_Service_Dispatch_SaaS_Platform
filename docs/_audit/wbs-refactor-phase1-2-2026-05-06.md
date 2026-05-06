# 重構 WBS — Phase 1-2（V1 上線前後）

- **日期**: 2026-05-06
- **適用期間**: 前端串接期 → V1 上線後 4-6 週
- **總工作量**: 21-27 PD（人天）
- **關鍵路徑**: P1-1 → P1-2 → P2-1 (debounce 拆分)
- **配套**: [refactor-plan-phase1-2-2026-05-06.md](./refactor-plan-phase1-2-2026-05-06.md) / [wbs-refactor-tier1-2026-05-06.md](./wbs-refactor-tier1-2026-05-06.md)

> **狀態圖例**：⬜ pending / 🟡 in-progress / ✅ done / 🔴 blocked / ⏸️ paused

---

## 進度儀表板（Updated: 2026-05-06 19:50）

| 區段 | 工作量 | 狀態 | 完成度 | 觸發時機 |
|------|------|------|------|---------|
| RP1.C 內部品質 | 5-7 PD | ✅ | **6/6 merged** | — |
| RP1.D 觀測基建 | 4-5 PD | 🟡 | **3/5 merged + 2/5 PR open** | — |
| RP2 V1 後重構 | 14-19 PD | 🔴 blocked | 0/6 | 等 V1 上線 + E2E ≥ 80% |

**Phase 1 實際月曆時間**：1 天（多 agent 平行）— 遠快於原估 2 週
**Phase 2 預估月曆時間**：4-5 週（V1 後）

### Phase 1 完成總覽
- ✅ **9 個 PR 已 merged 到 dev**：#2 #3 #4 #5 #6 #7 #8 #9 #10
- 🟡 **2 個 PR 待 merge**：#11（OTel）#12（Opik per-skill）

### PR 索引（依任務）

| WBS | PR | 標題 | 狀態 |
|-----|-----|------|------|
| RP1.C.1 | [#3](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/3) | fix: silent except 7 處加 log（實際 8 處） | ✅ merged |
| RP1.C.2 | [#8](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/8) | refactor(core): 抽 pg_pool.py（連帶清第 4 處 data_correction） | ✅ merged |
| RP1.C.3 | [#4](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/4) | refactor(core): 抽 content_utils.py（3 份等價合併 + 1 保留） | ✅ merged |
| RP1.C.4 | [#6](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/6) | refactor(profiles,sql): user_facts schema → SQL 檔 | ✅ merged |
| RP1.C.5 | [#7](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/7) | refactor(memory): 統一走 dict registry | ✅ merged |
| RP1.C.6 | [#2](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/2) | refactor(skills): Skill 物件 immutable 化 | ✅ merged |
| RP1.D.1 | [#9](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/9) | chore(logging): structlog 結構化日誌配置 | ✅ merged |
| RP1.D.2 | [#11](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/11) | chore(observability): OpenTelemetry tracing middleware | 🟡 PR open |
| RP1.D.3 | [#12](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/12) | chore(observability): Opik per-skill cost attribution | 🟡 PR open |
| RP1.D.4 | [#5](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/5) | docs(deploy): E9 §7.3 Dockerfile 範本對齊 production | ✅ merged |
| RP1.D.5 | [#10](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/10) | feat(health): /health 擴充 6 項檢查 | ✅ merged |

### 重大發現與超出範圍交付

| 任務 | 額外交付 |
|------|---------|
| RP1.C.1 | WBS 標稱 7 處，實際發現並修了 **8 處**（postgres_impl.py 有 2 處） |
| RP1.C.2 | 順手清第 4 處 `_ensure_conn` 重複（`harness/data_correction.py`），未來不再被審計到 |
| RP1.C.3 | 識別「3 份等價 + 1 份不同抽象層」(`_extract_text_from_items` 處理 buffer media placeholder)，後者按計畫保留；新增 16 個單測（含新舊行為等價驗證） |
| RP1.C.5 | 順手修了原 `close_checkpointer` 的無害 bug（`else` 分支對 `"memory"` type 誤呼叫 `close_sqlite_conn()`） |
| RP1.D.1 | 發現 Python module/package 陷阱：建 `agent/__init__.py` 會 shadow `agent.py`，改用 `core/logging_config.py` module 載入時自動觸發 |
| RP1.D.2 | OTel exporter 自動回退（OTLP 套件沒裝時 fallback Console 不 crash）；FastAPI auto-instrumentation 自動帶 `http.method`/`route`/`status` 等 attrs 不必手動加 |
| RP1.D.3 | 發現 LangChain `tool.invoke()` 會 `copy_context()` 隔離 ContextVar；採**雙軌寫入**（ContextVar + `opik_context.update_current_trace`）解決 |
| RP1.D.4 | production Dockerfile 早已升級且**比範本更成熟**（uv 釘版 0.11、`UV_NO_PROGRESS=1`、兩階段 layer COPY、cache mount）；本 PR 改為反向操作 — 把 docs E9 §7.3 範本對齊 production |

---

## WBS 總覽

```
RP 重構計畫（Phase 1-2）
├── RP1 Phase 1 — V1 上線前可全做（並行 Track A 前端串接）
│   ├── RP1.C Track C：後端內部品質
│   │   ├── RP1.C.1 Silent except 全面修復（CRITICAL）
│   │   ├── RP1.C.2 抽 agent/core/pg_pool.py（HIGH）
│   │   ├── RP1.C.3 抽 agent/core/content_utils.py（HIGH）
│   │   ├── RP1.C.4 user_facts schema 抽到 SQL 檔（MEDIUM）
│   │   ├── RP1.C.5 memory dict registry 統一（MEDIUM）
│   │   └── RP1.C.6 Skill 物件 immutable 化（LOW）
│   └── RP1.D Track D：觀測 + 基建
│       ├── RP1.D.1 結構化日誌（structlog）
│       ├── RP1.D.2 OpenTelemetry tracing middleware
│       ├── RP1.D.3 Opik cost attribution per-skill
│       ├── RP1.D.4 Dockerfile multi-stage uv build
│       └── RP1.D.5 Health endpoint 擴充
└── RP2 Phase 2 — V1 上線後（CRITICAL 重構）
    ├── RP2.1 debounce.py god-class 拆分（最大）
    │   ├── RP2.1.1 抽 BufferStore（封裝 user_buffers + pending）
    │   ├── RP2.1.2 抽 harness/quick_reply.py（H_QR 獨立）
    │   ├── RP2.1.3 抽 harness/orchestrator.py（編排核心）
    │   └── RP2.1.4 debounce.py 縮減（純 timer 合併）
    ├── RP2.2 Skill→harness 反向耦合修復
    ├── RP2.3 Harness→agent 反向耦合修復
    ├── RP2.4 11 elif 狀態機 → dispatch table
    ├── RP2.5 content block schema 統一
    └── RP2.6 except Exception 收斂為具體型別
```

---

## RP1 — Phase 1 詳細任務表（V1 上線前可全做）

### RP1.C — Track C：後端內部品質

| WBS ID | 任務 | 工作量 | 依賴 | 風險 | 分支（實際） | PR | 狀態 |
|--------|------|------|------|------|------|-----|------|
| **RP1.C.1** | **Silent except 修復（實際 8 處）** | 1-2 PD | — | 低 | `fix/silent-except-cleanup` | [#3](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/3) | ✅ |
| RP1.C.1.1-7 | 6 個檔案 7+ 處統一加 logger.warning + exc_info=True | — | — | 低 | — | — | ✅ |
| **RP1.C.2** | **抽 agent/core/pg_pool.py + 連帶清第 4 處 data_correction** | 1-2 PD | — | 中 | `refactor/pg-pool-extraction` | [#8](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/8) | ✅ |
| RP1.C.2.1 | 建 `agent/core/pg_pool.py` + 9 個單測 | 0.5 PD | — | 中 | — | — | ✅ |
| RP1.C.2.2 | `profiles/manager.py` 改用 helper（+ data_correction.py 同形清理） | 0.25 PD | RP1.C.2.1 | 中 | — | — | ✅ |
| RP1.C.2.3 | `storage/postgres_impl.py` 改用 helper | 0.25 PD | RP1.C.2.1 | 中 | — | — | ✅ |
| RP1.C.2.4 | `memory/postgres_saver.py` **刻意不接入**（AsyncPostgresSaver 連線特殊） | — | — | — | — | — | ⏸️ defer |
| RP1.C.2.5 | 驗證：25/25 全 unit suite 全綠 | 0.25 PD | RP1.C.2.2-4 | 中 | — | — | ✅ |
| **RP1.C.3** | **抽 agent/core/content_utils.py** | 0.5 PD | — | 低 | `refactor/content-utils-extraction` | [#4](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/4) | ✅ |
| RP1.C.3.1 | 建 `extract_text(content) -> str` + 16 單測（含新舊行為等價驗證） | 0.25 PD | — | 低 | — | — | ✅ |
| RP1.C.3.2 | 3 處等價合併（debounce ×2 / memory_manager / quality_check）；`_extract_text_from_items` 保留（不同抽象層） | 0.25 PD | RP1.C.3.1 | 低 | — | — | ✅ |
| **RP1.C.4** | **user_facts schema → SQL 檔** | 0.5 PD | — | 低 | `refactor/user-facts-schema-to-sql` | [#6](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/6) | ✅ |
| RP1.C.4.1 | `SQL/Schema_harness_migration.sql` 加 CREATE TABLE user_facts | 0.25 PD | — | 低 | — | — | ✅ |
| RP1.C.4.2 | `profiles/manager.py` 移除 dynamic CREATE（user_soft_profiles 仍 runtime 建表，列 follow-up） | 0.1 PD | RP1.C.4.1 | 低 | — | — | ✅ |
| RP1.C.4.3 | 部署備註：新環境必須先跑 SQL 檔（既有部署不影響） | 0.15 PD | RP1.C.4.1-2 | 低 | — | — | ✅ |
| **RP1.C.5** | **memory dict registry 統一** | 0.5 PD | — | 低 | `refactor/memory-registry-unification` | [#7](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/7) | ✅ |
| RP1.C.5.1 | `build_in_memory_saver()` builder + 註冊 MEMORY_REGISTRY | 0.25 PD | — | 低 | — | — | ✅ |
| RP1.C.5.2 | 移除 if/else fast-path + 順手修 close_checkpointer 無害 bug | 0.15 PD | RP1.C.5.1 | 低 | — | — | ✅ |
| RP1.C.5.3 | 驗證：unknown backend 拋 ValueError、行為等價 | 0.1 PD | RP1.C.5.2 | 低 | — | — | ✅ |
| **RP1.C.6** | **Skill immutable 化** | 0.15 PD | — | 極低 | `refactor/skill-immutable` | [#2](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/2) | ✅ |
| RP1.C.6.1 | `_parse_skill_md()` 擴充參數，建構時傳入 brands/models | 0.1 PD | — | 極低 | — | — | ✅ |
| RP1.C.6.2 | 驗證：load_skills() 載入 67 skills（一致） | 0.05 PD | RP1.C.6.1 | 極低 | — | — | ✅ |

**RP1.C 小計**：5-7 PD

### RP1.D — Track D：觀測 + 基建

| WBS ID | 任務 | 工作量 | 依賴 | 風險 | PR | 狀態 |
|--------|------|------|------|------|-----|------|
| **RP1.D.1** | **結構化日誌（structlog）基礎建設** | 1-2 PD | — | 低 | [#9](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/9) | ✅ |
| RP1.D.1.1 | 加 `structlog>=24.4` 依賴 + `agent/core/logging_config.py` | 0.25 PD | — | 低 | — | ✅ |
| RP1.D.1.2 | `app.py` 全面替換（**留給後續 PR**，避免與 D.5 衝突） | 0.5 PD | RP1.D.1.1 | 低 | — | ⏸️ defer |
| RP1.D.1.3 | `harness/debounce.py` 部分替換（7 處結構化事件示範） | 0.5 PD | RP1.D.1.1 | 低 | — | ✅ |
| RP1.D.1.4 | 其餘 harness 漸進替換 | 0.5 PD | RP1.D.1.1 | 低 | — | ⏸️ defer |
| **RP1.D.2** | **OpenTelemetry middleware（ConsoleSpanExporter）** | 0.5 PD | — | 低 | [#11](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/11) | 🟡 |
| RP1.D.2.1 | 加 OTel SDK + instrumentation-fastapi 依賴 | 0.25 PD | — | 低 | — | 🟡 |
| RP1.D.2.2 | `agent/core/tracing.py` + auto-instrumentation + line_user_id span | 0.25 PD | RP1.D.2.1 | 低 | — | 🟡 |
| **RP1.D.3** | **Opik cost attribution per-skill** | 0.5 PD | — | 低 | [#12](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/12) | 🟡 |
| RP1.D.3.1 | `skills/tools.py:load_skill` 加 ContextVar + opik_context | 0.25 PD | — | 低 | — | 🟡 |
| RP1.D.3.2 | `harness/debounce.py` 注入 invoke metadata；正式環境驗證 dashboard 分桶 | 0.25 PD | RP1.D.3.1 | 低 | — | 🟡 |
| **RP1.D.4** | **Dockerfile multi-stage uv build（含 docs 範本對齊）** | 0.5 PD | — | 低 | [#5](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/5) | ✅ |
| RP1.D.4.1 | production Dockerfile 早已升級（commit `84be0f5`，比範本更成熟） | 0.25 PD | — | 低 | — | ✅ |
| RP1.D.4.2 | `docs/04-deliver/E9--... §7.3` 範本對齊 production 實作 | 0.15 PD | — | 低 | — | ✅ |
| RP1.D.4.3 | 本地 build 驗證：agent 792 MB / api 245 MB / `/docs` 200 OK | 0.1 PD | RP1.D.4.1-2 | 低 | — | ✅ |
| **RP1.D.5** | **Health endpoint 擴充（6 項檢查）** | 0.5 PD | — | 低 | [#10](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/10) | ✅ |
| RP1.D.5.1 | `_timed_check` helper（asyncio.wait_for + try/except + latency） | 0.25 PD | — | 低 | — | ✅ |
| RP1.D.5.2 | facts_db / audit_db / memory_db / llm（不發實際請求）/ media_storage / skill_registry | 0.25 PD | — | 低 | — | ✅ |

**RP1.D 小計**：4-5 PD

### RP1 完工驗收（Definition of Done）

- [x] `rg 'except.*:\s*pass$' agent/ api/` 回傳 0 行（PR #3）
- [x] `agent/core/pg_pool.py`、`content_utils.py` 兩個模組存在 + 有單測（25/25 全綠）
- [x] `SQL/Schema_harness_migration.sql` 含 user_facts 完整 schema（PR #6）
- [x] `memory/__init__.py` 無 if/else fast-path（PR #7）
- [x] structlog 在 debounce.py 可見（PR #9，app.py 替換 defer 至下一 PR）
- [ ] OpenTelemetry middleware 啟用（ConsoleExporter）— PR #11 待 merge
- [x] Dockerfile multi-stage uv build 上 staging 通過（PR #5，本地 build OK）
- [x] `/health` 回傳所有 backend 狀態（PR #10，6 項檢查）
- [ ] Opik per-skill 成本分桶 — PR #12 待 merge
- [x] quality_check baseline 不退步（pg_pool / content_utils 25 單測 + skill 67 載入一致）

---

## RP2 — Phase 2 詳細任務表（V1 上線後）

### 觸發條件（必須全滿足）

| 前置條件 | 狀態 | 備註 |
|---------|------|------|
| V1 上線且穩定運行 ≥ 2 週 | ⬜ | — |
| Phase 1（RP1.C + RP1.D）全部完成 | ⬜ | — |
| Playwright E2E 主路徑覆蓋率 ≥ 80% | ⬜ | Track A 交付 |
| LINE flow E2E（debounce / multimodal / Quick Reply）有自動化測試 | ⬜ | — |
| 真實流量 baseline 量測（QPS、p50/p95 latency） | ⬜ | — |

### RP2 任務表

| WBS ID | 任務 | 工作量 | 依賴 | 風險 | 分支 | 狀態 |
|--------|------|------|------|------|------|------|
| **RP2.1** | **debounce.py 拆分（最大重構）** | 5-8 PD | RP1 完工 + 觸發條件 | 高 | `refactor/harness-debounce-decomposition` | 🔴 |
| RP2.1.1 | 抽 `BufferStore` 類別（封裝 user_buffers + _pending_messages） | 1.5-2 PD | — | 高 | — | 🔴 |
| RP2.1.2 | 抽 `harness/quick_reply.py`（H_QR 邏輯獨立） | 1.5-2 PD | RP2.1.1 | 高 | — | 🔴 |
| RP2.1.3 | 抽 `harness/orchestrator.py`（agent_and_reply 編排） | 1.5-2 PD | RP2.1.2 | 高 | — | 🔴 |
| RP2.1.4 | debounce.py 縮減為純 timer 合併（≤ 200 行） | 0.5-1 PD | RP2.1.3 | 中 | — | 🔴 |
| RP2.1.5 | 每 PR 驗證：E2E + quality_check + 灰度（5%→100%） | 全程 | — | 高 | — | 🔴 |
| **RP2.2** | **Skill→harness 反向耦合修復** | 1 PD | RP2.1 | 中 | `refactor/skill-harness-decoupling` | 🔴 |
| RP2.2.1 | 抽 `agent/core/brand_match.py`（含 match_brand/match_model） | 0.5 PD | — | 中 | — | 🔴 |
| RP2.2.2 | `skills/tools.py:10` 改從 core import | 0.25 PD | RP2.2.1 | 中 | — | 🔴 |
| RP2.2.3 | `harness/line_ui_factory.py` 同步改用 core | 0.25 PD | RP2.2.1 | 中 | — | 🔴 |
| **RP2.3** | **Harness→agent 反向耦合修復** | 1 PD | RP2.1 | 中 | `refactor/harness-agent-decoupling` | 🔴 |
| RP2.3.1 | `app.py` init() 注入 `get_system_prompt` 給 harness | 0.5 PD | — | 中 | — | 🔴 |
| RP2.3.2 | `harness/debounce.py:24` 移除直接 import | 0.25 PD | RP2.3.1 | 中 | — | 🔴 |
| RP2.3.3 | `pydeps` 圖驗證無反向 | 0.25 PD | RP2.3.2 | 中 | — | 🔴 |
| **RP2.4** | **11 elif → dispatch table** | 1-2 PD | RP2.1 | 中 | `refactor/quick-reply-state-machine` | 🔴 |
| RP2.4.1 | 建 `BrandModelState` enum + dispatch table | 0.5 PD | — | 中 | — | 🔴 |
| RP2.4.2 | `_quick_reply_intercept` 改用 dispatch | 0.5-1 PD | RP2.4.1 | 中 | — | 🔴 |
| RP2.4.3 | E2E 完整覆蓋 5 種狀態 | 0.25 PD | RP2.4.2 | 中 | — | 🔴 |
| **RP2.5** | **content block schema 統一** | 2-3 PD | RP2.1 | 中 | `refactor/content-block-normalization` | 🔴 |
| RP2.5.1 | 建 `Block` dataclass | 0.5 PD | — | 低 | — | 🔴 |
| RP2.5.2 | webhook 入口 normalize | 0.5 PD | RP2.5.1 | 中 | — | 🔴 |
| RP2.5.3 | 移除內部 isinstance 分支 | 1-2 PD | RP2.5.2 | 中 | — | 🔴 |
| **RP2.6** | **except Exception 收斂** | 2 PD | RP1.C.1 | 低 | `refactor/exception-narrowing` | 🔴 |
| RP2.6.1 | harness 5 處改具體型別 | 0.75 PD | — | 低 | — | 🔴 |
| RP2.6.2 | data pipeline 3 處改具體型別 | 0.5 PD | — | 低 | — | 🔴 |
| RP2.6.3 | api/auth_service 3 處改具體型別 | 0.5 PD | — | 低 | — | 🔴 |
| RP2.6.4 | 整體驗證 | 0.25 PD | RP2.6.1-3 | 低 | — | 🔴 |

**RP2 小計**：14-19 PD

### RP2 完工驗收

- [ ] `agent/harness/debounce.py` ≤ 200 行
- [ ] `harness/orchestrator.py` / `buffer.py` / `quick_reply.py` 各自獨立、職責單一
- [ ] `pydeps` 圖無反向 import
- [ ] 11 elif 狀態機改為 dispatch table
- [ ] content block 統一為 `Block` dataclass
- [ ] 全程 E2E 不退步、quality_check 不退步
- [ ] 灰度發布完成（5% → 25% → 100%），無異常告警

---

## 依賴圖（DAG）

```
RP1.C.1 ──┐
          ├──► RP1 完工 ──► RP2.1 ──► RP2.1.1 ──► RP2.1.2 ──► RP2.1.3 ──► RP2.1.4
RP1.C.2 ──┤                 ▲          │
RP1.C.3 ──┤                 │          ├──► RP2.2 (skill→harness 解耦)
RP1.C.4 ──┤                 │          ├──► RP2.3 (harness→agent 解耦)
RP1.C.5 ──┤              触发条件:      ├──► RP2.4 (state machine)
RP1.C.6 ──┘              V1 上线 + E2E  └──► RP2.5 (block schema)
                            >=80%
RP1.D.1 ──┐                                    RP1.C.1 ──► RP2.6 (except 收斂)
RP1.D.2 ──┤
RP1.D.3 ──┼──► RP1 完工 (與 RP1.C 並行)
RP1.D.4 ──┤
RP1.D.5 ──┘
```

關鍵路徑：**RP1.C.1 → RP1.C.2 → V1 上線 → RP2.1 → RP2.2/3/4/5/6**

---

## 追蹤儀表板模板（每週更新）

```
週報 — Refactor Phase 1-2
日期：YYYY-MM-DD

進度：
- RP1.C: X/24 子任務完成 (Y%)
- RP1.D: X/13 子任務完成 (Y%)
- RP2:   X/26 子任務完成 (Y%) [若已啟動]

本週完成：
- [ ] RP1.C.X.X — <任務名> (PR #XXX)
- [ ] RP1.D.X.X — <任務名> (PR #XXX)

下週計畫：
- [ ] RP1.C.X.X — <任務名>

阻塞項：
- 無 / [描述]

風險：
- 無 / [描述]
```

---

## 與 tier1 計畫的銜接點

| 本 WBS 項 | 對應 tier1 WBS 項（見 wbs-refactor-tier1） |
|----------|---------------------------------------|
| RP1.C.2 pg_pool | RT-A.1.5 multi-tenant connection pool |
| RP1.C.5 memory dict registry | RT-A.3 tenant-aware registry |
| RP1.D.1 結構化日誌 | RT-A.* 全程 tenant_id log context |
| RP1.D.2 OTel middleware | RT-A.* tenant_id trace span |
| RP1.D.3 Opik per-skill | RT-A.* per-tenant cost |
| RP2.1 debounce 拆分 | RT-A.* tenant context 注入點 |
| RP2.2/2.3 反向耦合修復 | RT-B.2 BrandAdapter hexagonal 邊界 |
