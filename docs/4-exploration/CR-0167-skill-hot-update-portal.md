# CR-0167 — Skill 熱更新與品牌後台編輯（LiveSkill）

- **日期**：2026-07-12
- **狀態**：✅ §8 已裁決（2026-07-12），依 §9 實作中
- **觸發面向**：Architecture boundary（agent 知識分發通道）＋ DB schema（新表）＋ API contract（新 endpoint 群）＋ User flow（品牌後台新功能）
- **關聯**：ADR-030（references 永為主路徑）、ADR-0107（lockcore 正典）、WBS 2.2.x（知識語義層）

---

## §1 一句話

Skill（SKILL.md + references）將持續迭代且必須是 agent 回答依據——把 skill 的 **SSOT 從
「綁死在 image」改為「品牌庫 DB + agent workspace overlay 物化同步」**：品牌後台可編輯查看、
人工/自動更新皆即時生效（≤ 輪詢 TTL），**agent 不再為 skill 更新重佈**；image 內 builtin
skill 降級為離線保底層。

## §2 動機

| 現狀 | 痛點 |
|---|---|
| skill 隨 `COPY agent/` 烤入 image（`agent/Dockerfile:44`），載入路徑寫死 `lockcore/agent/skills.py:12` | 改一行知識 = rebuild + push + deploy（3-5 分鐘、需工程師） |
| 知識維護只能走 git | 品牌方/客服主管無法自助維護；自動管線產出也得等 deploy |
| 業主需求 | skill 會一直更新迭代；要以 skill 為回答依據；品牌網站要能編輯查看 |

## §3 現況機制（已查證，設計成立的三個事實）

1. **`SkillsLoader` 無狀態、每次呼叫重讀磁碟**——`load_skill` 每次 `read_text`
   （`skills.py:75-92`）、`build_skills_summary` 每次 `iterdir`（`skills.py:111-142`）。
2. **system prompt 每 turn 重建**（`context.py:105-113`）→ 磁碟上的 skill 檔換了，
   **下一個 turn 立即生效**，不需重啟。
3. **`workspace/skills/` 天生覆蓋 builtin 同名 skill**（`skills.py:61-65`、`85-91`，
   上游 nanobot 機制，fork 內建）→ overlay 層已存在，**lockcore 核心零修改**。
4. 現況 workspace 是 throwaway tempdir（`line_gateway.py:50`），無人放東西進去——正好留給本案用。
5. 紅線不依賴 skill 內容：`reply_guard` 是 runtime 兜底（`reply_guard.py:70`）、
   工具白名單在 `app_config.py:CS_TOOL_ALLOWLIST`——skill 被改壞也繞不過。

## §4 影響面

| 面向 | 變更 |
|---|---|
| **Architecture boundary** | 新元件 `SkillSync`（agent 內背景同步器）；知識分發通道 git+image → DB+overlay 雙層 |
| **DB schema** | 品牌庫新表 `saas.skill_revision` / `saas.skill_bundle` / `saas.skill_audit_log` |
| **API contract** | dispatch surface 新 endpoint 群 `/knowledge-base/skills/*`（CRUD/publish/revisions/rollback）＋ internal ingest |
| **User flow** | 品牌後台 knowledge-base 新「AI 技能（Skills）」分頁：檢視/編輯/diff/版本/發佈/回滾 |
| **不變** | Agent Skills 標準格式（落盤仍是 SKILL.md + references/，可攜性保留）；`SkillsLoader` 一行不改；工具白名單不動；bronze-only 對平台產品知識仍有效 |

## §5 設計

### 5.1 架構總圖

```
品牌後台 Skill 管理頁                knowledge-pipeline（自動）
  列表/編輯/diff/版本/發佈/回滾        silver_to_knowledge 產出 references
        │                                  │
        ▼                                  ▼
  api：/knowledge-base/skills/*（角色閘門＋frontmatter/大小驗證＋審計）
        │ 發佈 = skill_bundle.published_version 前移
        ▼
  品牌庫  saas.skill_revision（版本快照，append-only）
          saas.skill_bundle（tenant 目前發佈版本 = version stamp）
        │
        ▼  SkillSync：啟動全量拉 ＋ TTL 輪詢 version stamp（預設 60s）
  agent   原子物化：寫 tmp 目錄 → os.rename 換裝
        ▼
  workspace/skills/<name>/{SKILL.md, references/…}   ← overlay 覆蓋 builtin 同名
        ▼
  SkillsLoader（不改）→ 下一 turn 生效
```

### 5.2 兩層 skill 分工

| 層 | 位置 | 更新方式 | 角色 |
|---|---|---|---|
| **builtin 保底層** | `lockcore/skills/`（image 內，git 版本控制） | 隨 deploy | 離線保底＋平台紅線 SOP 基準；DB 全掛時 agent 照常服務 |
| **DB 迭代層** | 品牌庫 → 物化到 `workspace/skills/` | 品牌後台編輯／pipeline 自動 ingest → 發佈 | 日常迭代主通道，**不重佈** |

同名覆蓋規則 = 上游 overlay 語意；「品牌方能否覆蓋平台 skill」見 HD-1。

### 5.3 DB schema（品牌庫）

```sql
-- 版本快照（append-only；files = {rel_path: content}，含 SKILL.md 與 references/*）
CREATE TABLE saas.skill_revision (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id    uuid NOT NULL,
  skill_name   text NOT NULL,
  version      integer NOT NULL,
  files        jsonb NOT NULL,
  status       text NOT NULL DEFAULT 'draft',   -- draft | published | retired
  note         text,
  created_by   uuid,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, skill_name, version)
);

-- tenant 目前生效版本組（SkillSync 只輪詢這張的 stamp）
CREATE TABLE saas.skill_bundle (
  tenant_id         uuid PRIMARY KEY,
  published_stamp   bigint NOT NULL DEFAULT 0,  -- 每次發佈 +1；SkillSync 比對用
  updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE saas.skill_audit_log ( ... 對齊 saas.kb_audit_log 樣式 ... );
```

發佈 = 目標 revision `status='published'`（同 skill 舊 published 轉 retired）＋ stamp +1。
回滾 = 舊 revision 重新 publish（同一機制，無特例）。

### 5.4 API（dispatch surface；操作角色見 HD-5）

| operationId | 路由 | 說明 |
|---|---|---|
| `listSkills` | GET `/knowledge-base/skills` | DB skill ＋ builtin 唯讀鏡像（標 source） |
| `getSkill` | GET `/knowledge-base/skills/{name}` | 檔案樹＋內容（最新 revision 或指定 version） |
| `saveSkillDraft` | PUT `/knowledge-base/skills/{name}` | 存 draft revision |
| `publishSkill` | POST `/knowledge-base/skills/{name}/publish` | 驗證閘（見 5.6）→ 發佈 |
| `listSkillRevisions` | GET `/knowledge-base/skills/{name}/revisions` | 版本歷史（diff 用） |
| `rollbackSkill` | POST `/knowledge-base/skills/{name}/rollback` | 回滾至指定 version |
| `ingestSkillRevision` | POST `/internal/skills/ingest` | pipeline 自動通道（INTERNAL_API_TOKEN） |

### 5.5 agent 端 SkillSync（唯一新元件，lockcore 核心不動）

- 新檔 `lockcore/agent/skill_sync.py`（預估 ~150 行）＋ `line_gateway` 啟動接線。
- 啟動：拉 published bundle → 物化 `workspace/skills/`；失敗 → log warning，
  **fail-soft 走 builtin**（對齊 RAG `RAG_UNAVAILABLE` 哲學）。
- 背景：asyncio task 每 TTL 秒查 `skill_bundle.published_stamp`，變了才全量重拉。
- 原子換裝：寫 `workspace/.skills-tmp-<stamp>/` → `os.rename` swap，turn 進行中讀檔不撕裂。
- 多實例：各實例獨立輪詢，最終一致（差距 ≤ TTL）；Cloud Run in-memory fs，skill 體積小無虞。
- 拉取通道 DB 直讀 vs 走 API：見 HD-3。

### 5.6 發佈驗證閘（publish 時強制）

1. frontmatter 符合 Agent Skills 標準（name/description/version/metadata；YAML 可解析）。
2. `SKILL.md` 大小預算（進 prompt 的部分；建議 ≤ 16KB，超標拒發）。
3. skill name 合法性（目錄名規則；禁止 path traversal，`rel_path` 白名單字元）。
4. 平台 skill 保護（依 HD-1 裁決的閘門）。
5. （後續強化，非本輪）golden QA smoke eval 過門檻才可發佈。

### 5.7 治理對齊

- **Architecture Lock 條目 2**（skill 不出 lockcore/skills/）：builtin 留在原位不動；
  `workspace/skills/` 是上游標準 overlay 機制非新發明——落地時新開 **ADR-032** 明文化雙層架構（ADR-031 已被契約工件三分層占用），
  並於 CLAUDE.md 該條加註 overlay 說明（catch-up，不是推翻）。
- **bronze-only**：平台產品知識 references 仍僅由 pipeline 從 bronze 產出（自動 ingest 通道），
  品牌方對其唯讀或需審核（HD-1）；品牌自建 skill 來源=品牌方、責任歸屬品牌方，於 UI 標示區隔。
- **審計**：每次 save/publish/rollback 寫 `skill_audit_log`；agent turn log 記當前 bundle stamp
  （追溯「這個回答用的是哪版知識」）。

## §6 風險與緩解

| 風險 | 緩解 |
|---|---|
| 品牌方改壞 skill → agent 亂答 | 發佈驗證閘＋版本回滾一鍵＋紅線在 runtime（reply_guard/白名單）不受 skill 影響＋builtin 保底 |
| DB 不可用 | SkillSync fail-soft：續用上次物化版或 builtin，agent 不中斷 |
| 多實例版本不一致 | 最終一致 ≤ TTL（60s）；客服場景可接受 |
| 知識不再與 git 綁定、審計斷鏈 | revision append-only＋audit_log＋turn 記 stamp；重大版本仍可回寫 git（人工節奏） |
| prompt 膨脹 | SKILL.md 大小預算閘；references 走 read_file 按需讀不進 prompt |

## §7 測試計畫

- **api**：CRUD/publish/rollback pytest（含驗證閘拒發 case、角色閘門、tenant 隔離）。
- **agent**：`test_skill_sync.py`（物化原子性、stamp 輪詢、fail-soft）＋
  擴充 `test_e2e_mock_turn.py`（workspace overlay 蓋掉 builtin 後，回答依據改變）。
- **web**：編輯→發佈→（本機 agent）下一 turn 生效的 Playwright happy path。
- **UAT**：品牌後台改一條 FAQ → LINE 問 → 60s 內新答案。

## §8 Human Decisions Required 🛑

| # | 問題 | 業主裁決（2026-07-12） |
|---|---|---|
| HD-1 | 平台 skill 品牌方權限？ | **(c) 完全開放**——「agent 本來就是品牌方開通 LINE 客服才有的功能，知識是品牌自己要根據品牌維護的，要有完整權限」；搭配品牌內部角色權限（→HD-5）＋**必須有版控** |
| HD-2 | pipeline 自動 ingest 後？ | **(a) 進 draft，人工發佈（HITL）** |
| HD-3 | SkillSync 拉取通道？ | **(a) DB 直讀** |
| HD-4 | 輪詢 TTL？ | **(a) 60s**（預設，未異議） |
| HD-5 | 編輯/發佈角色？ | **(a) 編輯=OPS_ROLES、發佈=admin** |

**HD-1 治理註記**：知識所有權歸品牌租戶——builtin 兩個 skill 定位改為「出廠範本＋離線保底」，
品牌首次編輯某 builtin skill 時，以其現行內容 seed 為 revision 1（fork 起點）。bronze-only
紅線的適用範圍限縮為「平台出廠與 pipeline 自動 ingest 的內容」；品牌方自行編輯的內容責任
歸品牌方，UI 以來源標示區隔。§5.6 驗證閘第 4 條（平台 skill 保護）作廢。

## §9 Suggested Implementation Order

1. **S1 DB + API**：schema（migration）＋ `/knowledge-base/skills/*` CRUD/publish/驗證閘 ＋ pytest ＋ openapi.yaml。
2. **S2 agent SkillSync**：`skill_sync.py` ＋ gateway 接線 ＋ fail-soft ＋ tests（本機 docker 驗 overlay 生效）。
3. **S3 品牌後台 UI**：Skills 分頁（列表/編輯器/diff/歷史/發佈/回滾）＋ Playwright。
4. **S4 自動通道＋治理收尾**：pipeline ingest ＋ ADR-032 ＋ CLAUDE.md 加註 ＋ CHANGELOG/completion-status ＋ agent 重佈一次（此後 skill 更新不再重佈）。

### 進度

- ✅ **S1 DB+API done**（merge `b8fd000f`）：migration 106（`skill_revision`/`skill_bundle`/`skill_audit_log`）＋`skill_service` publish/rollback 狀態機＋發佈驗證閘＋`skills_v2` router；8 pytest 綠（scratch 5490）。
- ✅ **S2 agent SkillSync done**（merge `8889856c`）：`skill_sync.py`（60s 輪詢→物化 workspace overlay，原子 symlink＋fail-soft，lockcore 核心零改動）＋gateway 接線＋`seed_builtin_skills.py`；5 pytest 綠含 DB 往返。
- ✅ **S3 品牌後台 UI done**（merge `cb9f6b33`）：知識庫「AI 技能」分頁（列表/編輯器/版本歷史/發佈/回滾）；i18n parity＋tsc 0。
- ✅ **對抗式 review + 修正 done**（merge `20aad757`）：6 維度 review 16 raw→8 confirmed 全修（並發雙 draft/publish 競態→advisory lock＋draft unique index＋409；skill_name traversal 錨定 version_dir；path collision 拒發＋per-skill 隔離；`$`→`\Z`；poll clamp；前端唯讀非草稿版本＋防多餘發佈）；測試增至 api 11＋agent 8。
- ✅ **pipeline ingest 接線 done**（CR-0168，merge `e29c18cb`）：refinery 行為軌改走 `/internal/skills/ingest`（merge draft）取代 git+重佈；後端 ingest merge 加性模式＋refinery 雙路徑（`LOCK_API_BASE_URL`+`INTERNAL_API_TOKEN`→ingest／否則 git fallback）；api 14＋refinery 7 綠。
- ✅ **品質保證回歸測試 done**（merge `9161601e`）：`test_builtin_roundtrip_byte_identical`——builtin 走 DB→SkillSync→SkillsLoader 後位元組級不變（sha256 逐檔＋`load_skill` 等價），鎖死「回答依據不因搬進 Postgres 而漂移」；agent 測試增至 9。
- ✅ **UAT UI 驗證 done**（本機 5433 重建 stack）：套 migration 106＋seed 兩 builtin（cs-sop 4 檔／product-knowledge 46 檔，draft/出廠範本）→ 品牌後台『知識庫 > AI 技能』列表＋編輯器＋版本歷史＋發佈鈕 live 實測（登入→分頁→編輯器渲染真實 SKILL.md）；api `/api/v1/knowledge-base/skills` 回真資料。
- ⏳ **S4 剩餘**：ADR-032＋CLAUDE.md＋CHANGELOG/completion-status/WBS done；**僅剩 agent 重佈一次**（使用者執行 `./scripts/deploy/agent.sh`＋帶 `LOCK_API_BASE_URL`+`INTERNAL_API_TOKEN`，此後 skill 更新不重佈）＋**全鏈 UAT**（品牌後台改 FAQ→LINE 問→60s 新答，需重佈後）。
