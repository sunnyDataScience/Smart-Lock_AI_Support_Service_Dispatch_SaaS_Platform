# 08 專案結構指南 — agent 子系統（LockCore LINE Bot AI 客服）

| 欄位 | 內容 |
|------|------|
| 版本 | v1.0 |
| 日期 | 2026-07-07 |
| 狀態 | 草稿（現況 as-is）|
| 負責人 | Platform Team |
| 適用服務 | agent（LockCore / Cloud Run `smart-lock-agent`）|
| 佐證來源 | `agent/` 整包、`agent/lockcore/VENDOR.md`、`agent/pyproject.toml`、`agent/Dockerfile` |

---

## 1. 設計原則

### 1.1 本子系統實際遵循的原則

| 原則 | 說明 | 實踐情形 |
|------|------|----------|
| 三層引擎分離 | runner（通用迴圈）/ loop（產品狀態機）/ context（prompt 組裝）各司其職 | 完整實踐，`runner.py` 明文「without product-layer concerns」 |
| 供應商抽象 | LLM 多家統一走單一 adapter | 完整實踐，`LiteLLMProvider` 靠 model 字串路由 |
| 知識可攜（Agent Skills 標準）| SKILL.md + references，不綁框架欄位 | 完整實踐，兩 skill 純核心 frontmatter，複製即可用 |
| 工具白名單為邊界 | 客服只開必要工具 | 完整實踐，`CS_TOOL_ALLOWLIST` 6 項 + unregister |
| 記憶隔離 default deny | 讀寫必帶 tenant+user_id | 完整實踐，缺則 raise |
| 機密與設定分離 | 非機密走 toml，機密走 env / Secret Manager | 完整實踐，`app_config.py` 明訂 |
| fork 上游最小核心 | 只複製 AgentLoop 遞移 import closure | 實踐，但帶 fork 維護成本（手動 cherry-pick）|

### 1.2 與理想的差距（技術債）

1. **fork 維護成本**：LockCore 是 fork 非依賴，上游 nanobot bug fix / 安全 patch 需**手動 cherry-pick**（`VENDOR.md`），無自動追蹤。
2. **LINE 路徑與 bus 架構未對齊**：`bus/queue.py:MessageBus` 建了但 LINE gateway 走同步 `_process_message` 直呼，未跑 `loop.run()` → mid-turn 注入 / auto-compact 依賴 bus 的功能在 LINE 路徑不生效（P1 §9 R-04）。
3. **已備未接的模組**：`channels/inbound_debounce.py`（debounce/dedup）、`providers/fallback_provider.py`（failover）皆有實作 + 測試，但 live 路徑未 wire（R-02 / R-03）。
4. **記憶預設後端與生產不符**：`config.toml` commit 值為 sqlite，生產應走 postgres（R-05）。
5. **nanobot 殘留未用模組**：closure 帶進的 `cron/` `pairing/` `apps/cli` `session/webui_turns.py` 等對 LINE 客服非必要（見 §3.3）。

---

## 2. 現有頂層結構

```
agent/
├── config.toml                      # 非機密設定（LLM model / 記憶後端），tomllib 載入
├── .env.example                     # 機密範本（LINE / API 橋接 / POSTGRES_URI）
├── pyproject.toml                   # hatchling build，套件 lockcore，optional extras
├── Dockerfile                       # multi-stage uv build，CMD python scripts/line_gateway.py
├── Dockerfile.dockerignore
├── README.md                        # agent 新架構說明（LockCore 設計依據）
├── lockcore/                        # ★ 核心引擎（fork 自 nanobot，見 §3）
├── scripts/                         # 進入點 + eval/gate 腳本（見 §3.4）
├── tests/                           # pytest 測試（21 個 + 訓練集 xlsx，見 §4）
└── evals/                           # live eval 產出（CSV + LIVE_EVAL_RESULTS_*.md）
```

---

## 3. 原始碼結構分析

### 3.1 LockCore 內部結構（ASCII Tree + 職責）

```
lockcore/                            # = nanobot 套件更名而來（fork）
├── __init__.py
├── LICENSE                          # MIT（© nanobot contributors）
├── VENDOR.md                        # ★ fork 出處、範圍、本地改動紀錄（必讀）
├── app_config.py                    # ★ 本地新增：config 載入 + CS_TOOL_ALLOWLIST
│                                    #   + build_provider/memory/escalation
├── agent/                           # 核心引擎
│   ├── runner.py                    # ★ AgentRunner：通用 tool-using LLM 迴圈
│   ├── loop.py                      # ★ AgentLoop：產品層 Turn 狀態機（8 態）
│   ├── context.py                   # ★ ContextBuilder（本地改：注入 per-user 記憶）
│   ├── skills.py                    # SkillsLoader（預設探索 lockcore/skills/）
│   ├── memory.py                    # nanobot 原生記憶整理（Consolidator/AutoCompact/Dream）
│   ├── autocompact.py               # 上下文自動壓縮
│   ├── subagent.py                  # SubagentManager
│   ├── hook.py / progress_hook.py   # turn hook
│   ├── model_presets.py
│   ├── tools/                       # 工具目錄（大量 nanobot 原生 + 我方 transfer）
│   │   ├── loader.py / registry.py  # 掃描註冊 / 工具登記
│   │   ├── filesystem.py            # read_file/list_dir/write/edit（白名單只留讀）
│   │   ├── search.py                # find_files / grep
│   │   ├── web.py                   # web_search（Vertex grounding）/ web_fetch（砍）
│   │   ├── transfer.py              # ★ 本地新增：transfer_to_human（唯一出口）
│   │   ├── shell.py / exec_session.py / spawn.py / cron.py / message.py
│   │   ├── apply_patch.py / image_generation.py / mcp.py / self.py
│   │   └── sandbox.py / path_utils.py / schema.py / base.py …
│   └── user_memory/                 # ★ 本地新增：per-user 記憶層
│       ├── manager.py               # MemoryManager：build_context_block / record_turn
│       ├── store.py                 # SQLite MemoryStore（FTS5 trigram，CJK）
│       ├── postgres_store.py        # Postgres（schema agent.*，pg_trgm/GIN）
│       ├── provider.py              # _StoreBackedProvider（兩後端同介面）+ prefetch
│       ├── llm_extractor.py         # LLMExtractor（抽第三人稱事實）
│       └── escalation.py            # EscalationStore（轉真人稽核）
├── providers/                       # 供應商層（瘦身 + LiteLLM）
│   ├── base.py                      # LLMProvider / LLMResponse / ToolCallRequest
│   ├── litellm_provider.py          # ★ 本地新增：LiteLLMProvider（單一 adapter）
│   ├── fallback_provider.py         # ⚠ FallbackProvider（存在但未接 live）
│   ├── factory.py                   # _make_provider_core 統一建 LiteLLMProvider
│   ├── registry.py                  # 純 metadata
│   ├── image_generation.py
│   └── openai_responses/
├── channels/                        # 通道層（本地新增）
│   ├── line_gateway.py              # ★ build_webapp → POST /callback + 旁路橋接
│   └── inbound_debounce.py          # ⚠ InboundDebouncer/EventDeduplicator（未接 live）
├── skills/                          # ★ 兩個 builtin skill（Agent Skills 標準）
│   ├── locksmith-product-knowledge/ # 事實層（見 §3.2）
│   └── locksmith-cs-sop/            # 行為層（見 §3.2）
├── bus/                             # 訊息匯流排（建了但 LINE 未用 loop.run）
│   ├── queue.py                     # MessageBus
│   └── events.py                    # InboundMessage
├── command/                         # 指令路由（COMMAND 態用）
│   ├── router.py / builtin.py
├── session/                         # session 管理
│   ├── manager.py / goal_state.py / webui_turns.py
├── config/                          # nanobot 原生 config（loader/paths/schema）
├── templates/                       # ★ 19 個 Jinja2 模板（persona 已改鎖市客服）
│   ├── SOUL.md                      # agent persona（鎖市 LockSmart 客服助理）
│   ├── transfer_human.md            # ★ transfer 回傳的核對表單
│   ├── agent/ · memory/             # dream / compact 等模板
├── security/network.py              # SSRF/network 邊界
├── apps/ · pairing/ · cron/ · utils/  # closure 順帶拉進（客服多數未用，見 §3.3）
```

### 3.2 兩個 builtin skill 結構

```
skills/
├── locksmith-product-knowledge/     # 事實層（version 1.0.0）
│   ├── SKILL.md                     # frontmatter: name/description/version/metadata{tags,brands}
│   │                                #   profile-gating：依 brand+model 讀最小 references
│   │                                #   Domain safety：Philips/Milre 標「資料缺乏聲明」
│   └── references/
│       ├── _common/                 # 跨品牌共用（8 檔）
│       │   ├── store-info.md · dispatch.md · troubleshoot.md · locksmith.md
│       │   ├── door-hardware.md · general-knowledge.md · car-key.md · stamp.md
│       ├── 3E/ · Chatlock/ · Dormakaba/ · Kaadas/ · Milre/ · Philips/
│       │   ├── _brand.md            # 品牌總覽
│       │   └── {Model}.md           # 如 Dormakaba/AS701.md（frontmatter brand/model/description）
│       │                            # Dormakaba 有 ~16 型號；6 品牌共 ~45 個 .md
└── locksmith-cs-sop/                # 行為層（version 1.3.0）
    ├── SKILL.md                     # frontmatter: name/description/version/metadata{tags,pairs-with}
    │                                #   每輪意圖分類 + 紅線決策樹 + 單一進線鐵律
    └── references/
        ├── handoff-and-dispatch.md  # 轉接與派工
        ├── booking.md               # 預約
        └── warranty.md              # 保固
```

> **Sourcing rule（bronze-only）**：references 內容嚴格源自 `data/storage/bronze/`（YouTube 字幕 / website / transcript）；GDrive PDF 不可信，只引 URL 不抄內容。由 `test_cr_0076_agent_gov.py` 治理。

### 3.3 nanobot closure 殘留（客服未用 / 部分用）

| 模組 | closure 進來的原因 | 客服使用狀況 |
|---|---|---|
| `cron/` | config/factory 順帶拉入 | 客服未用（工具白名單無 cron）|
| `pairing/` | 同上 | 客服未用 |
| `apps/cli` | closure 帶入 | 客服未用（生產走 line_gateway）|
| `session/webui_turns.py` | session 模組整包 | 客服未用（無 webui）|
| `agent/subagent.py` | AgentLoop import | 客服未直接用 |
| `bus/queue.py` | line_gateway import 但只建不跑 loop | ⚠ 建了未啟 bus 迴圈（R-04）|
| `agent/tools/*`（write/shell/exec…）| tools 整目錄補齊 | 註冊後被白名單 unregister |

> **未複製**：channels（上游）、api、heartbeat、webui —— 客服不需要（`VENDOR.md`）。

### 3.4 scripts/ 結構

```
scripts/
├── line_gateway.py                  # ★ 生產進入點（LINE webhook）
├── real_turn_demo.py                # Agent demo（真實 turn cycle）
├── eval_reply_quality.py            # 讀 987 題 xlsx 評分（需 .[eval]）
├── forbidden_eval.py                # K8 Forbidden Eval gate
├── governance_checks.py             # 治理檢查
├── grounding_guard.py               # grounding 守衛
├── multiturn_sim_eval.py            # 多輪模擬 eval
└── redline_gate.py                  # 紅線 gate
```

---

## 4. 測試結構

### 4.1 現有測試現況

與 acme 範例（無 tests/ 目錄）不同，agent **有正式 pytest 套件**（`agent/tests/`，21 個 `test_*.py` + 1 個訓練集 xlsx）。主測試入口 `cd agent && pytest`。

```
tests/
├── test_app_config.py               # config.toml 載入器（離線）
├── test_litellm_provider.py         # LiteLLMProvider 映射（monkeypatch acompletion）
├── test_e2e_mock_turn.py            # ★ 端到端 mock turn：BUILD 注入記憶+skill → 假 LLM → SAVE 寫回 → 跨 user 隔離
├── test_integration_context_memory.py # ContextBuilder DI 注入 MemoryManager + 隔離 + 向後相容
├── test_skills_loaded.py            # 兩 skill 是 builtin、SkillsLoader 預設探索得到
├── test_tool_allowlist.py           # ★ 客服工具裁剪（白名單）
├── test_transfer_to_human.py        # transfer 工具 + EscalationStore（離線）
├── test_memory.py                   # ★ per-user 記憶：跨 user/tenant 隔離、default deny、CJK 檢索
├── test_memory_postgres.py          # Postgres 後端同介面（需真 POSTGRES_URI 否則 skip）
├── test_llm_extractor.py            # LLM 記憶抽取器（mock provider）
├── test_line_gateway.py             # LINE webhook 路徑（真簽章 + patch reply API）
├── test_web_search_vertex.py        # web_search 預設 Vertex grounding + 政策
├── test_dream_no_skill_creation.py  # Dream 已拔掉自動建 skill（無 write_file）
├── test_cr_0074_redline.py          # ★ AI 安全紅線（不報價/不折扣/NTD 不複誦 → transfer）
├── test_cr_0076_agent_gov.py        # RAG bronze-only 來源治理 + KPI gate
├── test_cr_0077_debounce.py         # 進線 1.5s debounce + 24h dedup（純邏輯 fake clock）
├── test_cr_0080_eval_scoring.py     # eval 評分/聚合純函式（mock judge）
├── test_cr_0081_forbidden_eval.py   # K8 Forbidden Eval gate（純判定）
├── test_cr_0086_ai_intake_live.py   # AI 進線 E2E（需 Vertex 憑證，否則 skip）
├── test_cr_0087_skill_loop_compliance.py # SKILL frontmatter 合規 + loop 有界迭代
└── AI_Blue_鎖匠AI客服_987題核心訓練集_v1_20260602.xlsx  # eval 訓練集
```

### 4.2 測試覆蓋觀察

- **強項**：記憶隔離、工具白名單、AI 紅線、來源治理、skill 載入、e2e mock turn 皆有守。
- **缺口對照**：`test_cr_0077_debounce.py` 測 debounce 純邏輯，但 debounce **未接 live**（R-02）→ 測試綠燈不代表 live 路徑生效。
- 舊 quality_check / belief_action_judge / replay_check 已刪（CLAUDE.md 述），不在此目錄。

---

## 5. 命名慣例

### 5.1 目錄命名

| 層級 | 命名風格 | 範例 |
|------|----------|------|
| 頂層模組 | `snake_case` 功能名詞 | `agent/`, `providers/`, `channels/`, `skills/` |
| skill 目錄 | `kebab-case`（Agent Skills 標準）| `locksmith-product-knowledge/`, `locksmith-cs-sop/` |
| references 品牌 | `PascalCase` 品牌名 | `Dormakaba/`, `Chatlock/`, `Philips/` |
| references 共用 | `_` 前綴 | `_common/`, `_brand.md` |

### 5.2 檔案命名

| 類型 | 慣例 | 範例 |
|------|------|------|
| 引擎模組 | `{role}.py` | `runner.py`, `loop.py`, `context.py` |
| 工具檔 | `{domain}.py`，內含 `{Name}Tool` class | `transfer.py` → `TransferToHumanTool` |
| provider | `{vendor}_provider.py` | `litellm_provider.py`, `fallback_provider.py` |
| 記憶 store | `{backend}_store.py` | `store.py`（sqlite）, `postgres_store.py` |
| skill 內容 | `SKILL.md` + `references/{Brand}/{Model}.md` | `Dormakaba/AS701.md` |
| 測試 | `test_{module}.py` / `test_cr_{NNNN}_{topic}.py` | `test_memory.py`, `test_cr_0074_redline.py` |

### 5.3 識別碼慣例

| 類型 | 慣例 | 範例 |
|------|------|------|
| 工具 name | `snake_case` 動詞-名詞 | `read_file`, `transfer_to_human`, `web_search` |
| Turn 狀態 | `UPPER_SNAKE_CASE` | `RESTORE`, `BUILD`, `RUN`, `SAVE` |
| 記憶 kind | `snake_case` 白名單 | `profile`, `preference`, `fact`, `issue`, `dispatch` |
| model 字串 | `vendor/model` litellm 慣例 | `vertex_ai/gemini-3.1-flash-lite` |
| 常數 | `UPPER_SNAKE_CASE` | `CS_TOOL_ALLOWLIST`, `_LINE_TEXT_LIMIT` |

---

## 6. 重構建議

依「風險低 → 效益高」排序。

### 建議一：接線已備模組（優先順序 1）

**現況問題**：`inbound_debounce.py`（debounce/dedup）、`fallback_provider.py`（failover）已實作 + 有測試，但 live 路徑未 wire → 測試綠燈但生產不生效。

**具體行動**：
1. `build_webapp` callback 接 `InboundDebouncer`（1.5s 合併）/ `EventDeduplicator`（24h dedup）。
2. `app_config.build_provider` 改建 `FallbackProvider` + fallback presets。

**預期效益**：連發訊息合併、重送去重、供應商中斷有自動 fallback（消除 R-02 / R-03）。

### 建議二：修正 health check 對齊（優先順序 2）

**現況問題**：deploy 打 `/health` 但 code 無此路由 → deploy health gate 誤報 FAILED。

**具體行動**：`build_webapp` 加 `app.router.add_get("/health", health)` 回 200（可帶 provider/DB 狀態）。

**預期效益**：deploy 不再誤報；Cloud Run readiness 有明確端點（消除 R-01）。

### 建議三：釐清 bus vs 同步路徑（優先順序 3）

**現況問題**：`MessageBus` 建了但 LINE 走同步 `_process_message`，mid-turn 注入 / auto-compact 不生效，架構意圖不明。

**具體行動**：二選一並文件化 ——
- (a) LINE 路徑接 `loop.run()` bus 迴圈，啟用 mid-turn 注入 / auto-compact；或
- (b) 明確確立「單 webhook = 單 turn」為刻意設計，移除誤導性的 bus 建構。

**預期效益**：消除 R-04 的架構歧義；新進開發者不再困惑。

### 建議四：瘦身 nanobot closure 殘留（優先順序 4）

**現況問題**：`cron/` `pairing/` `apps/cli` `webui_turns.py` 等客服未用模組仍在 closure。

**具體行動**：評估移除未用模組（需驗證 import closure 不斷）；或於 `VENDOR.md` 標記「保留供上游 cherry-pick 對齊」。

**預期效益**：縮小攻擊面與 fork 維護面。

### 建議五：建立上游同步 runbook（優先順序 5）

**現況問題**：上游 nanobot bug fix / 安全 patch 需手動 cherry-pick，無流程。

**具體行動**：`VENDOR.md` 補「上游同步 runbook」（訂閱上游 release、比對 closure 模組 diff、cherry-pick 驗測）。

**預期效益**：安全修補不再延遲（消除 E-05）。

---

## 7. 演進路線

### Phase 1：接線與對齊（低風險，1-2 週）

| 任務 | 行動 | 驗收標準 |
|------|------|----------|
| 接 debounce/dedup | callback wire `InboundDebouncer`/`EventDeduplicator` | 連發合併、重送去重（live 驗）|
| 修 health check | 加 `GET /health` 路由 | deploy health gate 通過 |
| 接 failover | `build_provider` 建 `FallbackProvider` | 主供應商中斷有 fallback |
| 記憶持久化確認 | 生產確認 `backend="postgres"` 覆蓋 | 重啟後記憶不流失 |

**風險評估**：低（多為接既有已測模組）。

### Phase 2：架構釐清（中風險，2-4 週）

| 任務 | 行動 | 驗收標準 |
|------|------|----------|
| bus vs 同步決策 | 接 bus 或移除誤導建構 + 文件化 | 架構意圖明確、測試對齊 |
| closure 瘦身 | 移除未用模組 | import closure 不斷、映像變小 |
| PII log 遮罩 | 統一過濾層 | log 無明文 PII |

### Phase 3：治理健壯化（Q3）

| 任務 | 行動 | 驗收標準 |
|------|------|----------|
| 上游同步 runbook | `VENDOR.md` 補流程 + 訂閱上游 | 安全 patch 有追蹤 |
| 多租戶 resolve_identity | 依官方帳號反推 tenant | 一 agent 服務多品牌 |
| OPIK 觀測落地 | 接入 trace 或移除 secret | LLM turn 可觀測 / secret 無空掛 |
| 知識來源收斂 | references ↔ pgvector 同步或擇一 | 單一知識真相源 |

---

*文件結尾 — agent 專案結構指南 v1.0 / 2026-07-07*
