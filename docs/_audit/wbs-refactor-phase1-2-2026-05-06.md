---
status: superseded
superseded_by: docs_v2/4-exploration/change-requests/CR-0002-wbs.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

# 重構 WBS — Phase 1-2（V1 上線前後）

- **日期**: 2026-05-06
- **適用期間**: 前端串接期 → V1 上線後 4-6 週
- **總工作量**: 21-27 PD（人天）
- **關鍵路徑**: P1-1 → P1-2 → P2-1 (debounce 拆分)
- **配套**: [refactor-plan-phase1-2-2026-05-06.md](./refactor-plan-phase1-2-2026-05-06.md) / [wbs-refactor-tier1-2026-05-06.md](./wbs-refactor-tier1-2026-05-06.md)

> **狀態圖例**：⬜ pending / 🟡 in-progress / ✅ done / 🔴 blocked / ⏸️ paused

---

## 進度儀表板（Updated: 2026-05-07 00:25 — 還原系列收尾）

| 區段 | 工作量 | 狀態 | 完成度 | 觸發時機 |
|------|------|------|------|---------|
| RP1.C 內部品質 | 5-7 PD | ✅ | **6/6 merged + working tree 還原** | — |
| RP1.D 觀測基建 | 4-5 PD | ✅ | **5/5 merged + working tree 還原** | — |
| RP2 V1 後重構 | 14-19 PD | 🟡 部分先行 | **3/6 子項先行（worktree 並行）**：RP2.2 / 2.3 / 2.6 ✅；RP2.1 / 2.4 / 2.5 待 V1 + E2E ≥ 80% | 等 V1 上線 + E2E ≥ 80% |

**Phase 1 實際月曆時間**：1 天（多 agent 平行）— 遠快於原估 2 週
**Phase 2 預估月曆時間**：4-5 週（V1 後）

### Phase 1 完成總覽
- ✅ **11 個原始 PR 已 merged**：#2 #3 #4 #5 #6 #7 #8 #9 #10 #11 #12
- ✅ **4 個還原 PR 已 merged**：#17 #18 #19 #20（將被 alignment 刪除的產出全數復位）
- 🎯 **dev tip 終態**：架構單一（SKILL.md / `load_skill` 為 canonical），所有 helper 已 wire-up，OTel/structlog 套件就位

> **⚠️ alignment 偏離與處置紀錄**（2026-05-06 22:11 → 2026-05-07 01:05）
>
> 兩筆事後 alignment commit（`8ffcb60` / `56949eb`）曾將 `agent/` 樹對齊到 Zenobia0000 dev tip `2825cbe`，導致 RP1.C.2 / C.3 / C.6 / D.1 / D.2 / D.4 產出於 working tree 上消失（PR 已 merge 進歷史，但檔案系統不可見），且 PR #18 階段發現 Zenobia0000 的 v1.3.4–v1.3.5 期間另外把整個 SKILL.md 架構替換為 `agent/product_info/` mega-doc 架構，造成 tools/prefix/知識庫三者混合錯位。
>
> 採行處置 (a) — 從 sync 前快照 `6c2616c` 外科手術還原 + 補完原本未完成的 wire-up：

### 還原 PR 系列（Updated: 2026-05-07）

| PR | 階段 | 範圍 | merged |
|----|------|------|--------|
| [#17](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/17) | **A** helper modules | `agent/core/{pg_pool,content_utils,logging_config,tracing}.py` 從 `6c2616c` 還原 + `tests/unit/core/` 4 檔 + app.py 軟性 OTel import + debounce.py 加 structlog logger + lint fix `# allow-direct-conn` | 2026-05-06 14:57 |
| [#18](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/18) | **C** skills 為 canonical | `agent/skills/` 整目錄還原（67 SKILL.md + `__init__.py` + `tools.py`，含 RP1.C.6 immutable + RP1.D.3 Opik 雙軌寫入）、agent.py 回 skills 架構、main.py 縮回 LLM smoke、刪 `agent/agent_tools/`、`harness/debounce.py` + `quality/quality_check.py` import path 改 `skills.tools`、`config.toml` 加 `[skills]`、`core/config.py` AppConfig 加 `skills` 欄位 | 2026-05-06 15:00 |
| [#19](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/19) | **B+D** wire-up + build | content_utils 接通：debounce.py / quality_check.py / memory_manager.py 移除 inline `_extract_text*` 改用 `extract_text(...)`（memory_manager 走 `include_media_placeholder=True, fallback_to_repr=False`）；Dockerfile multi-stage uv build 還原；`agent/pyproject.toml` 還原；刪 `agent/requirements.txt`；`uv sync` 拉齊 OTel/structlog 25.5.0 等 deps | 2026-05-06 15:15 |
| [#20](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/20) | cleanup | debounce.py / quality_check.py 4 條 prefix 注入路徑改用 `filter_skills` + `get_skills()`；新增 `skills.tools.get_skills()` getter（避免 `_skills` 重綁後 stale reference）；字串 `load_product_info` → `load_skill`、`[可用產品資料]` → `[可用技能]`、`[已參考: ...]` → `[已參考技能: ...]`；刪 `agent/product_info/`（42 檔，304 KB）；usage_guide.md 改寫 SKILL.md 章節；harness_comparison.md 註記還原；刪 product_info_authoring_guide.md；web/lib/api.ts 補 `loginTechnician` stub 解 dev branch web build 紅燈 | 2026-05-06 16:05 |

**還原驗證**（dev tip `513c830`）：
- `agent/` 殘留 `product_info` refs：0（除 `agent/docs/manuals/harness_comparison.md` 的歷史對照註記，刻意保留）
- syntax check：debounce.py / quality_check.py / skills/tools.py / api.ts 全綠
- `tests/unit/core/` 25/25 passed in 0.15s
- skills smoke：8 brand 全 `_brand_has_skills=True`，`NotABrand=False`；`filter_skills(Chatlock,AI-99)=29`、`(Dormakaba,None)=14`、`(None,None)=7`
- Docker Build Smoke Test 從 FAILURE → **SUCCESS**（dev branch run `25446688235`，2m40s）— web build 紅燈解決

**仍需後續關注**：
- 304 KB `agent/product_info/*.md` mega-doc 內容已隨退場；若後續發現特定型號操作步驟只在 mega-doc 有，需從 `6c2616c` 還原並重新編成 SKILL.md
- `loginTechnician` 為 stub（delegate 到 admin `login()`），實作專屬 `/api/v1/auth/tech-login` 端點時換掉
- quality_check 跑全測需實際 LLM credentials（`VERTEX_PROJECT_ID` 等），未在還原 session 範圍內驗證

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
| RP1.D.2 | [#11](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/11) | chore(observability): OpenTelemetry tracing middleware | ✅ merged |
| RP1.D.3 | [#12](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/12) | chore(observability): Opik per-skill cost attribution | ✅ merged |
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
| **還原系列 (#17–#20)** | 1) **PR-level cherry-pick 失敗**：`94dbd21` 等 patch 因 Zenobia0000 已將 `_extract_text` 改名為 `_extract_text_from_content` 造成 3 檔 merge conflict，改用檔案級 `git checkout 6c2616c -- <path>` 外科手術 / 2) **stale reference 陷阱**：`set_skills()` 用 `global` 重綁 `_skills`，呼叫端 `from skills.tools import _skills` 拿到 module 載入時的空 list reference，新增 `get_skills()` getter 修正 / 3) **架構錯位偵測**：原以為 PR #18 已將 skills 改為 canonical，實際 production debounce.py 的 4 條 prefix 注入路徑仍引用 `product_info`，造成 LLM 看到的清單與 `tools=[load_skill]` 不一致，PR #20 補完 / 4) **lint rule 配合**：pg_pool helper 集中管理連線本身就需要 `AsyncConnection.connect()`，加 `# allow-direct-conn` 標記豁免 / 5) **連帶解 web 紅燈**：`tech-login/page.tsx` import 從未實作的 `loginTechnician`，補 stub delegate 到 `login()`，dev Docker Build Smoke 從 FAILURE → SUCCESS |

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
| RP1.C.2.4 | `memory/postgres_saver.py` **N/A**（已用 `AsyncConnectionPool` — lint rule 推薦的 pool 模式比 pg_pool helper 的單連線+cache 更優；defer 原因消失） | — | — | — | — | — | ✅ N/A |
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
| RP1.D.1.2 | `app.py` 全面替換 9 處 print → structlog（PR #22 — defer 解除） | 0.5 PD | RP1.D.1.1 | 低 | — | ✅ |
| RP1.D.1.3 | `harness/debounce.py` 部分替換（7 處結構化事件示範） | 0.5 PD | RP1.D.1.1 | 低 | — | ✅ |
| RP1.D.1.4 | 其餘 harness 漸進替換（PR #22：97 → 14 prints，86% 替換；剩 14 為 debounce.py 多行 pretty-printer，刻意保留） | 0.5 PD | RP1.D.1.1 | 低 | — | ✅ |
| **RP1.D.2** | **OpenTelemetry middleware（ConsoleSpanExporter）** | 0.5 PD | — | 低 | [#11](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/11) | ✅ |
| RP1.D.2.1 | 加 OTel SDK + instrumentation-fastapi 依賴 | 0.25 PD | — | 低 | — | ✅ |
| RP1.D.2.2 | `agent/core/tracing.py` + auto-instrumentation + line_user_id span | 0.25 PD | RP1.D.2.1 | 低 | — | ✅ |
| **RP1.D.3** | **Opik cost attribution per-skill** | 0.5 PD | — | 低 | [#12](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/12) | ✅ |
| RP1.D.3.1 | `skills/tools.py:load_skill` 加 ContextVar + opik_context | 0.25 PD | — | 低 | — | ✅ |
| RP1.D.3.2 | `harness/debounce.py` 注入 invoke metadata；正式環境驗證 dashboard 分桶 | 0.25 PD | RP1.D.3.1 | 低 | — | ✅ |
| **RP1.D.4** | **Dockerfile multi-stage uv build（含 docs 範本對齊）** | 0.5 PD | — | 低 | [#5](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/5) | ✅ |
| RP1.D.4.1 | production Dockerfile 早已升級（commit `84be0f5`，比範本更成熟） | 0.25 PD | — | 低 | — | ✅ |
| RP1.D.4.2 | `docs/04-deliver/E9--... §7.3` 範本對齊 production 實作 | 0.15 PD | — | 低 | — | ✅ |
| RP1.D.4.3 | 本地 build 驗證：agent 792 MB / api 245 MB / `/docs` 200 OK | 0.1 PD | RP1.D.4.1-2 | 低 | — | ✅ |
| **RP1.D.5** | **Health endpoint 擴充（6 項檢查）** | 0.5 PD | — | 低 | [#10](https://github.com/Zenobia000/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/pull/10) | ✅ |
| RP1.D.5.1 | `_timed_check` helper（asyncio.wait_for + try/except + latency） | 0.25 PD | — | 低 | — | ✅ |
| RP1.D.5.2 | facts_db / audit_db / memory_db / llm（不發實際請求）/ media_storage / skill_registry | 0.25 PD | — | 低 | — | ✅ |

**RP1.D 小計**：4-5 PD

### RP1 完工驗收（Definition of Done — Updated 2026-05-07）

PR 合併歷史 + working tree 雙重達標：

- [x] `rg 'except.*:\s*pass$' agent/ api/` 回傳 0 行（PR #3）
- [x] `agent/core/pg_pool.py`、`content_utils.py` 兩個模組存在於 working tree + 25/25 單測通過（PR #17 還原）
- [x] `SQL/Schema_harness_migration.sql` 含 user_facts 完整 schema（PR #6）
- [x] `memory/__init__.py` 無 if/else fast-path（PR #7）
- [x] structlog 在 debounce.py 可見（PR #9 + #19 wire-up）；`uv sync` 後實際載入 structlog 25.5.0
- [x] OpenTelemetry middleware 啟用（ConsoleExporter）— PR #11 + #17 還原 `core/tracing.py` + #19 還原 pyproject 拉齊 OTel SDK
- [x] Dockerfile multi-stage uv build（PR #5 docs 對齊 + #19 working-tree 還原）
- [x] `/health` 回傳所有 backend 狀態（PR #10，6 項檢查）
- [x] Opik per-skill 成本分桶（PR #12 + #18 隨 skills/ 整目錄還原；雙軌寫入 ContextVar + opik_context 已在 6c2616c snapshot）
- [x] quality_check baseline 不退步（content_utils 16 單測 + pg_pool 9 單測 + 67 個 skill 載入一致）
- [x] Production 架構單一（PR #20）：`tools=[load_skill, ...]` + `[可用技能]` prefix + `agent/skills/data/` 三者一致，無 `product_info` 殘留
- [x] dev branch CI 全綠（Docker Build Smoke `25446688235` 2m40s success）

> 2026-05-06 22:11 起的 alignment 偏離已由 PR #17 #18 #19 #20 還原系列收斂；working tree 與 PR 歷史已重新一致。

---

## RP2 — Phase 2 詳細任務表（V1 上線後）

### 觸發條件（必須全滿足）

| 前置條件 | 狀態 | 備註 |
|---------|------|------|
| V1 上線且穩定運行 ≥ 2 週 | ⬜ | — |
| Phase 1（RP1.C + RP1.D）全部完成 | ✅ | PR #2-#22 + alignment 還原系列收斂於 dev tip `7d3b515` |
| Playwright E2E 主路徑覆蓋率 ≥ 80% | ⬜ | Track A 交付 |
| LINE flow E2E（debounce / multimodal / Quick Reply）有自動化測試 | ⬜ | — |
| 真實流量 baseline 量測（QPS、p50/p95 latency） | ⬜ | — |

**先行啟動的獨立子項**（2026-05-07，worktree 並行）：RP2.2 / RP2.3 / RP2.6 為「無共享檔案衝突 + 與 RP2.1 拆分無依賴」的解耦/收斂任務，作為 RP2.1 的前置障礙清除提前執行。詳見下方狀態表 + `report/v1.38.0.md`。

### RP2 任務表

| WBS ID | 任務 | 工作量 | 依賴 | 風險 | 分支 | 狀態 |
|--------|------|------|------|------|------|------|
| **RP2.1** | **debounce.py 拆分（最大重構）** | 5-8 PD | RP1 完工 + 觸發條件 | 高 | `refactor/harness-debounce-decomposition` | 🔴 |
| RP2.1.1 | 抽 `BufferStore` 類別（封裝 user_buffers + _pending_messages） | 1.5-2 PD | — | 高 | — | 🔴 |
| RP2.1.2 | 抽 `harness/quick_reply.py`（H_QR 邏輯獨立） | 1.5-2 PD | RP2.1.1 | 高 | — | 🔴 |
| RP2.1.3 | 抽 `harness/orchestrator.py`（agent_and_reply 編排） | 1.5-2 PD | RP2.1.2 | 高 | — | 🔴 |
| RP2.1.4 | debounce.py 縮減為純 timer 合併（≤ 200 行） | 0.5-1 PD | RP2.1.3 | 中 | — | 🔴 |
| RP2.1.5 | 每 PR 驗證：E2E + quality_check + 灰度（5%→100%） | 全程 | — | 高 | — | 🔴 |
| **RP2.2** | **Skill→harness 反向耦合修復**（PR #23 worktree 平行） | 1 PD | — | 中 | `refactor/rp22-skill-harness-decoupling` | ✅ |
| RP2.2.1 | 抽 `agent/core/brand_match.py`（含 match_brand/match_model + infer_brand_from_text） | 0.5 PD | — | 中 | — | ✅ |
| RP2.2.2 | `skills/tools.py:10` 改從 core import | 0.25 PD | RP2.2.1 | 中 | — | ✅ |
| RP2.2.3 | `harness/line_ui_factory.py` 同步改用 core（保留 re-export 向下相容） | 0.25 PD | RP2.2.1 | 中 | — | ✅ |
| **RP2.3** | **Harness→agent 反向耦合修復**（PR #24 worktree 平行） | 1 PD | — | 中 | `refactor/rp23-harness-agent-decoupling` | ✅ |
| RP2.3.1 | `app.py` init() 注入 `system_prompt_getter` 給 harness | 0.5 PD | — | 中 | — | ✅ |
| RP2.3.2 | `harness/debounce.py` 移除 `from agent import` 直接 import | 0.25 PD | RP2.3.1 | 中 | — | ✅ |
| RP2.3.3 | 驗證 `rg "from agent" agent/harness/` 0 行 | 0.25 PD | RP2.3.2 | 中 | — | ✅ |
| **RP2.4** | **11 elif → dispatch table** | 1-2 PD | RP2.1 | 中 | `refactor/quick-reply-state-machine` | 🔴 |
| RP2.4.1 | 建 `BrandModelState` enum + dispatch table | 0.5 PD | — | 中 | — | 🔴 |
| RP2.4.2 | `_quick_reply_intercept` 改用 dispatch | 0.5-1 PD | RP2.4.1 | 中 | — | 🔴 |
| RP2.4.3 | E2E 完整覆蓋 5 種狀態 | 0.25 PD | RP2.4.2 | 中 | — | 🔴 |
| **RP2.5** | **content block schema 統一** | 2-3 PD | RP2.1 | 中 | `refactor/content-block-normalization` | 🔴 |
| RP2.5.1 | 建 `Block` dataclass | 0.5 PD | — | 低 | — | 🔴 |
| RP2.5.2 | webhook 入口 normalize | 0.5 PD | RP2.5.1 | 中 | — | 🔴 |
| RP2.5.3 | 移除內部 isinstance 分支 | 1-2 PD | RP2.5.2 | 中 | — | 🔴 |
| **RP2.6** | **except Exception 收斂**（PR #25 worktree 平行；46 處 narrowed，超出標稱 11 處） | 2 PD | RP1.C.1 | 低 | `refactor/rp26-exception-narrowing` | ✅ |
| RP2.6.1 | harness 22 處（debounce 11 / data_correction 4 / llm_metrics 3 / profile_updater 2 / output_validator 1 / memory_manager 1） | 0.75 PD | — | 低 | — | ✅ |
| RP2.6.2 | data pipeline 16 處跨 13 檔（source_to_raw / raw_to_bronze / bronze_to_silver / silver_to_skill 全 layer） | 0.5 PD | — | 低 | — | ✅ |
| RP2.6.3 | api/services 4 處（auth_service 3 + family_review_service 1） | 0.5 PD | — | 低 | — | ✅ |
| RP2.6.4 | 額外：agent/quality/quality_check.py 5 處個別精準型別 | 0.25 PD | — | 低 | — | ✅ |
| RP2.6.5 | 整體驗證：syntax 全綠 + 全 codebase except Exception 從 ~108 → 62（剩 62 多為 scripts / `# noqa: BLE001`） | 0.25 PD | RP2.6.1-4 | 低 | — | ✅ |

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
