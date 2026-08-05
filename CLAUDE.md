# CLAUDE.md

給 Claude Code 的工作指引。**原則：只寫「讀 code 推不出來的」—— 非預期工具鏈、歷史包袱、團隊共識、踩過的雷。**
結構概覽、目錄樹、模組職責請 `ls` / 讀 code；細節在 `@.claude/docs/*`（見文末路標）。

## Project Overview

Smart Lock AI Support & Service Dispatch SaaS Platform —— LINE Bot 智慧鎖 AI 客服 agent + Next.js 營運後台。

**Agent 核心於 2026-06-04 完成架構重寫**：捨棄 ReAct (LangGraph) + 自製 skill loader，改為 **LockCore**（fork 自上游 `HKUDS/nanobot` 的最小核心套件，位於 `agent/lockcore/`）+ **Agent Skills 標準**（agentskills.io / Claude Skills，knowledge 與 SOP 都走 `lockcore/skills/{name}/SKILL.md` + `references/`）+ **LiteLLM 統一供應商**（單一 `LiteLLMProvider` 用 model 字串路由 Gemini / Vertex / Ollama / Claude / OpenAI 多家）。per-user 記憶移植自 Hermes，位於 `lockcore/agent/user_memory/`，BUILD/SAVE 接 turn 狀態機。詳見 `agent/README.md` + `agent/lockcore/VENDOR.md`。

**user-facing 文字、註解、文件一律繁體中文**；code identifier 與 git message 可中英混用。

## 🔒 Architecture Lock — LockCore + Agent Skills 標準（必讀，不可違反）

**Agent 核心 = `agent/lockcore/`（fork 自 nanobot）**；知識與 SOP = **Agent Skills 標準** builtin skill（位於 `lockcore/skills/`）。

| 項目 | ✅ 採用（2026-06-04 起 lockcore 架構）| ❌ 失效（2026-06-04 agent 重寫已刪）|
|---|---|---|
| Agent 核心 | `agent/lockcore/` (LockCore fork 自 nanobot) | `agent/app.py` / `agent/agent.py` / `harness/` / `policy.py`（已刪）|
| 知識庫格式 | `lockcore/skills/locksmith-product-knowledge/references/{Brand}/{Model}.md`（Agent Skills 標準） | `agent/product_info/{Brand}/{Model}.md` mega-doc（已刪）|
| Agent tool | `lockcore/agent/tools/` (filesystem / web / shell / cron / message / self) + 工具白名單 `CS_TOOL_ALLOWLIST` | `agent/agent_tools/tools.py` / `agent/skills/tools.py`（已刪）|
| LLM provider | `lockcore/providers/litellm_provider.py`（單一 LiteLLM） | nanobot 各家 provider（已刪）|
| Per-user 記憶 | `lockcore/agent/user_memory/`（移植自 Hermes） | `agent/profiles/` / `agent/memory/`（已刪）|
| Belief-Augmented ReAct (Turn Cycle) | （刪除，roadmap 走 hermes-cs 已收尾為 lockcore 整合） | `agent/belief.py` / `calibrate.py` / `hypothesize.py` / `turn_cycle.py`（已刪）|

**硬性約束：**

1. **不准 fork lockcore 之外另寫 agent 核心** —— LockCore 是 fork 自 nanobot 的單一核心套件（見 `lockcore/VENDOR.md`），所有 agent 行為走 `lockcore/agent/runner.py` + `loop.py` + `context.py`。
2. **不准把 skill 拉到 lockcore/skills/ 之外** —— 兩個 builtin skill (`locksmith-product-knowledge`、`locksmith-cs-sop`) 必須留在 `lockcore/skills/`，且**只用 Agent Skills 標準 frontmatter**（name / description / version / metadata），不綁框架專屬欄位，以保可攜性（複製到 Claude Code / Cursor / nanobot / hermes 直接可用）。
   > **CR-0167 / ADR-032 補充（2026-07-12）**：skill 的**日常迭代 SSOT 已移到品牌庫**（`saas.skill_revision`），由 `SkillSync`（`lockcore/agent/skill_sync.py`）60s 輪詢物化到 `workspace/skills/`，走上游既有 overlay（workspace 優先於 builtin），發佈後 ≤60s 生效**不重佈**。這**不違反本條**：`lockcore/skills/` 的 builtin 原封不動，僅定位改為「出廠範本＋離線保底」（DB 全掛時 fail-soft 回退）。品牌後台「知識庫 > AI 技能」分頁編輯、admin 發佈；落盤仍是標準 SKILL.md + references/，可攜性不變。
3. **不准在 lockcore 外再造 LLM provider** —— 多家統一走 `LiteLLMProvider` 用 model 字串路由（`gemini/` / `vertex_ai/` / `ollama_chat/` / `claude-*` / `gpt-4o` 等），不要把 anthropic / google-genai SDK 直接 import 回 agent code。
4. **內建工具白名單只能在 `lockcore/app_config.py:CS_TOOL_ALLOWLIST` 統一控** —— 目前客服只開 `read_file / list_dir / find_files / grep / web_search / transfer_to_human`。新增內建工具屬 architecture change，須走 CIA。
   > **MCP 例外（2026-07-27 稽核補正，原條文不完整）**：**MCP 工具不受 `CS_TOOL_ALLOWLIST` 約束**，這是 ADR-010 / CR-0125 的刻意設計而非疏漏。原因是**執行時序**：白名單剝離發生在 `AgentLoop.__init__`（同步建構期，`agent/lockcore/agent/loop.py` 的 `_register_default_tools` 之後一次性 unregister），而 MCP 連線發生在事件迴圈啟動後（`line_gateway.py` on_startup → `loop._connect_mcp()`），`agent/lockcore/agent/tools/mcp.py` 全檔無任何 allowlist 檢查，只做 `registry.register(wrapper)`。實測：建構後 6 個工具 → RAG MCP 註冊後 8 個（`mcp_locksmith-rag_search_product_manual` / `mcp_locksmith-rag_search_similar_cases`）。
   >
   > **所以「工具入口有兩條」**：①內建工具走 `CS_TOOL_ALLOWLIST`（本條）②MCP 工具走 `agent/config.toml` 的 `[mcp_servers.*]`＋其 `${ENV}` 是否解得到值（解不到就整個 server 跳過＝RAG 未配置時行為與現狀相同）。**新增 MCP server 或其工具同樣屬 architecture change，須走 CIA**——控制點是 config.toml 的 server 定義，不是白名單常數。守線測試＝`agent/tests/test_mcp_allowlist_boundary.py`（把此時序行為釘住，避免日後靜默漂移）。

**Sourcing rule（CRITICAL — bronze-only，仍適用）**：產品知識 references 內容嚴格源自 `knowledge-pipeline/storage/bronze/`（原 data/，2026-07-09 改名）（YouTube 字幕、website、video transcript）。**PDF (GDrive) 不可信，references 只引 URL 不抄內容。**

> **已 superseded ADR**（2026-06-05 ADR-0107 落地，三 ADR frontmatter 已標 `status: superseded` + `superseded_by: ADR-0107`）：
> - ADR-0008（product-info-architecture-canonical）→ skills/ 結構回歸 Agent Skills 標準
> - ADR-0010（belief-augmented-react）→ Turn Cycle 已刪
> - ADR-0101（product-info-extension-final-spec）→ references 取代 mega-doc
> - **ADR-0107**（lockcore-supersede-product-info-trio，2026-06-05 新立）— governance 層 catch-up，新唯一正典

## 非預期工具鏈（agent 推不出來，必讀）

- **Python 用 `uv`，不是 pip** —— `uv sync` 裝 deps；跑任何 script 用 `uv run ...`。`pyproject.toml` 改了就重跑 `uv sync`。
- **Agent 採 hatchling build + optional dependencies** —— `pip install -e ".[dev]"`（base + pytest）/ `.[vertex]`（+ Vertex AI SDK）/ `.[line]`（+ LINE webhook 通道）。
- **Web 用 Node/npm**，與 uv 無關；四站台完全獨立（`cd web/<站台> && npm install`，站台=brand-portal/tech-portal/landing/platform-console，各有獨立 lockfile 與 docker-compose.yml）。
- **測試走 pytest**（agent 重寫後新建 `agent/tests/`，~13 個測試含 `test_e2e_mock_turn.py` / `test_skills_loaded.py` / `test_tool_allowlist.py` / `test_litellm_provider.py` / `test_line_gateway.py` 等）—— **不再有 quality_check / LLM-as-Judge 套件**（已刪）。
- **Config pattern**：`agent/config.toml` 用 `lockcore/app_config.py:tomllib` 載入；機密（`GEMINI_API_KEY` / `LINE_CHANNEL_*` / `credentials.json`）放 `.env` 或 gitignore 檔，**不入 toml**。
- **永不手動構建 `POSTGRES_URI`** —— 用 `./scripts/deploy/agent.sh --update-db-uri`（自動 URL-encode + round-trip 驗證）。
- **docs/ 雙版本工作流已退役（2026-07-08 大掃除）** —— tracked 的 `docs/`、`docs_html/` 樹已刪，文件正典= `smartlock-docs/`（純 .md，無 HTML 鏡像）。`scripts/dev/gen_docs_html.py`（原 tools/）僅保留給**未追蹤的報告素材**（如 `docs/20260709/` PPT 素材）本機 regen 用；不要再為一般文件建 docs_html 鏡像。

## 最常用指令（完整清單見 `@.claude/docs/commands.md`）

```bash
uv sync                                                  # 裝/更新所有 deps（含 lockcore base）
cd agent && pip install -e ".[dev]"                      # 裝測試 deps（pytest）
cd agent && pip install -e ".[vertex]"                   # 若用 Vertex AI（gemini-3.x）
cd agent && pip install -e ".[line]"                     # 若接 LINE 通道
cd agent && pytest                                       # 跑全部 unit/integration tests
cd agent && python scripts/real_turn_demo.py             # Agent demo（真實 turn cycle）
cd agent && python scripts/line_gateway.py               # LINE webhook 通道（取代舊 app.py）
```

<important if="跑測試 / 評估 agent 品質">
- 主測試入口：`cd agent && pytest`（agent/tests/ 13 個測試）
- 關鍵測試：`test_e2e_mock_turn.py`（端到端 mock turn）、`test_skills_loaded.py`（skill loader）、`test_tool_allowlist.py`（CS_TOOL_ALLOWLIST 驗證）、`test_litellm_provider.py`（多家 model 字串路由）
- 舊的 quality_check / belief_action_judge / replay_check / hypothesis_quality_baseline 全已刪，**不要嘗試呼叫**
- 完整指令與 debug 工具：`@.claude/docs/commands.md`（待同步更新）
</important>

<important if="部署 / 動 DB / 改環境">
- Deploy 走 `./scripts/deploy/{agent,api}.sh`（Cloud Run，pre-flight → build → push → deploy → health check）
- 動 `POSTGRES_URI` 一律 `--update-db-uri`，永不手動構建
- 環境切換：`./scripts/env/use-local.sh` / `use-gcp.sh`；secrets 在 GCP Secret Manager
- 完整部署/環境指令：`@.claude/docs/commands.md`
</important>

<important if="動 flow / contract / data / architecture">
> **2026-08-05 業主裁決：CIA gate 縮限為「只有跟錢有關的才保留」。**
> 原規則是「命中七面向 → 產出 CIA 文件 → 🛑 停下等業主裁決 → 才實作」。
> 縮限原因：該 gate 讓 UAT 走查查出的 83 個確認缺口中有 75 個卡住無法動工（修復率 9%），
> 對非金流變更而言治理成本超過它防止的風險。
> 既有的 CR-0170/0197/0198/0201～0211 保留為背景分析與決策記錄，不因本裁決作廢。

- **💰 金流類變更 → CIA gate 仍然有效**：退款、結算、傳票／分錄、對帳、報價金額與計費規則、
  發票、技師抽成、金額分層與核准權限（SoD）。這類**仍須產出 CIA 至 `docs/4-exploration/CR-NNNN-*.md`
  → 🛑 停下等業主裁決 §8 → 依 §9 實作**。錢一旦算錯或被錯誤核准，事後補救成本遠高於事前確認。
- **其餘高風險面向 → 直接實作，不產 CIA、不停下等裁決**：User/Business flow、API contract、
  Domain model、DB schema、External integration、Test plan、Architecture boundary。
  動到這些仍要格外小心，但那是「做得更仔細」而不是「停下來」。
- 取代 gate 的自我要求（非金流類）：先查清現況再改（不靠印象，要打開實際 `檔案:行號` 確認）、
  新增測試須驗證過「對修復前的版本會紅、修復後會綠」、跑全套要對基線比對失敗清單、
  commit message 寫清 WHY 與影響範圍、破壞性變更明確標記
- 文件衝突或讀到 `status: deprecated`/`superseded` → 停下回報 + **引用具體 ID**（BF-/UF-/API-/TC-/ADR-/CR-），絕不腦補「合理版本」（這條與 CIA 無關，仍然有效）
- 相關規則：`.claude/rules/change-governance.md`（Source of Truth 衝突仲裁、rewrite vs refactor 打分表、6 tier 分層）
</important>

<important if="完成一個 step / 準備 commit">
- **三個地方同步更新**（缺一就是 audit trail 斷鏈）：
  1. `docs/4-exploration/CR-NNNN-*.md` 對應 §8 `### 進度` 區塊 → 補一行 `✅ Sx done（merge <sha>）：<關鍵成果>`（舊 `docs/_audit/` 已依 0707 決議清除，歷史查 git）
  2. `CHANGELOG.md` `[Unreleased]` 段 → Added / Changed / Decisions 對應條目
  3. 有架構決策 → 新開 ADR（**append-only，舊的標 `status: superseded` + `superseded_by:`，不改舊內容**）
- Commit message 依 type 分層（見 `.claude/rules/git-workflow.md`）：`feat` 三段 WHY/WHAT/IMPACT；`fix` WHY + root cause；`docs`/`chore` 一行夠
- **`main` / `master` 永不直接 commit**；`dev` / `dev-ding` 採風險分級：L0 低風險小改可直接建立原子 commit，L1/L2 才開 `<type>/<short>` 短命分支，詳見 `.claude/rules/git-workflow.md`（`dev_new_arch` 已收斂，僅留雲端備份）
- **push、PR、merge 與遠端分支刪除須使用者明確授權**；使用者說「上傳 GitHub／上推」只代表 push，不自動包含 PR 或 merge
- 文件 6 tier 規則：`.claude/rules/context-stability.md`
</important>

## 細節路標（漸進式揭露 —— 需要時才展開）

- **指令全集** → `@.claude/docs/commands.md`（setup, run, test, debug, deploy, env, API 工具；2026-06-05 quality_check 段已標廢棄 + pytest 取代）
- **架構細節** → `@.claude/docs/architecture.md`（request flow 圖、module map、web/api/DB/部署；2026-06-05 agent module 段已標 superseded by ADR-0107，指向 agent/README.md + lockcore/VENDOR.md）
- **Agent 新架構** → `agent/README.md` + `agent/lockcore/VENDOR.md`（LockCore 設計依據、skill 結構、config 載入機制）
- **開發規則** → `.claude/rules/*`（git-workflow, change-governance, context-stability, testing, security…）
- **文件中樞** → `smartlock-docs/README.md`（企業文件集：平台級 ADR-P* + 各子系統 SAD + enterprise 00–27 正典；2026-07-08 起為唯一文件主線。tracked `docs/` 樹已整棵清除——歷史 ADR 0001-0115 與舊 CR/CIA 查 git；OpenAPI 機讀 SSOT = `api/openapi.yaml`）

> 維護提醒：本檔是「每次工作階段都載入」的記憶植入，不是 README。新增內容前先問「agent 自己讀 code 能不能發現？」能 → 不要寫進來，放子檔或讓它自己讀。文件過期 agent 就會錯，當基礎建設維護。
