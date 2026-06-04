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
3. **不准在 lockcore 外再造 LLM provider** —— 多家統一走 `LiteLLMProvider` 用 model 字串路由（`gemini/` / `vertex_ai/` / `ollama_chat/` / `claude-*` / `gpt-4o` 等），不要把 anthropic / google-genai SDK 直接 import 回 agent code。
4. **工具白名單只能在 `lockcore/app_config.py:CS_TOOL_ALLOWLIST` 統一控** —— 目前客服只開 `read_file / list_dir / find_files / grep / web_search / transfer_to_human`。新增工具屬 architecture change，須走 CIA。

**Sourcing rule（CRITICAL — bronze-only，仍適用）**：產品知識 references 內容嚴格源自 `data/storage/bronze/`（YouTube 字幕、website、video transcript）。**PDF (GDrive) 不可信，references 只引 URL 不抄內容。**

> **已 superseded ADR**：本架構重寫使下列 ADR 狀態失效（待補 superseded 標記）：
> - ADR-0008（product-info-architecture-canonical）→ skills/ 結構回歸 Agent Skills 標準
> - ADR-0010（belief-augmented-react）→ Turn Cycle 已刪
> - ADR-0101（product-info-extension-final-spec）→ references 取代 mega-doc

## 非預期工具鏈（agent 推不出來，必讀）

- **Python 用 `uv`，不是 pip** —— `uv sync` 裝 deps；跑任何 script 用 `uv run ...`。`pyproject.toml` 改了就重跑 `uv sync`。
- **Agent 採 hatchling build + optional dependencies** —— `pip install -e ".[dev]"`（base + pytest）/ `.[vertex]`（+ Vertex AI SDK）/ `.[line]`（+ LINE webhook 通道）。
- **Web 用 Node/npm**，與 uv 無關（`cd web && npm install`）。
- **測試走 pytest**（agent 重寫後新建 `agent/tests/`，~13 個測試含 `test_e2e_mock_turn.py` / `test_skills_loaded.py` / `test_tool_allowlist.py` / `test_litellm_provider.py` / `test_line_gateway.py` 等）—— **不再有 quality_check / LLM-as-Judge 套件**（已刪）。
- **Config pattern**：`agent/config.toml` 用 `lockcore/app_config.py:tomllib` 載入；機密（`GEMINI_API_KEY` / `LINE_CHANNEL_*` / `credentials.json`）放 `.env` 或 gitignore 檔，**不入 toml**。
- **永不手動構建 `POSTGRES_URI`** —— 用 `./scripts/deploy/agent.sh --update-db-uri`（自動 URL-encode + round-trip 驗證）。

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
- **7 觸發面向**（命中任一就跑 CIA）：User/Business flow、API contract、Domain model、DB schema、External integration、Test plan、Architecture boundary
- **豁免**：純 typo / 註解 / format / 單一 function 內 bug fix（無 contract 影響）/ tier-3 process doc 編輯
- 觸發即跑 `sunnydata-change-impact-analysis` skill → 產出 CIA 至 `docs/4-exploration/CR-NNNN-<short>.md` → 🛑 等業主裁決 §8「Human Decisions Required」→ 依 §9 順序實作
- 文件衝突或讀到 `status: deprecated`/`superseded` → 停下回報 + **引用具體 ID**（BF-/UF-/API-/TC-/ADR-/CR-），絕不腦補「合理版本」
- 完整規則：`.claude/rules/change-governance.md`（CIA gate、rewrite vs refactor 打分表、6 tier 衝突仲裁）
</important>

<important if="完成一個 step / 準備 commit">
- **三個地方同步更新**（缺一就是 audit trail 斷鏈）：
  1. `docs/_audit/CR-NNNN-*.md` 對應 §8 `### 進度` 區塊 → 補一行 `✅ Sx done（merge <sha>）：<關鍵成果>`
  2. `CHANGELOG.md` `[Unreleased]` 段 → Added / Changed / Decisions 對應條目
  3. 有架構決策 → 新開 ADR（**append-only，舊的標 `status: superseded` + `superseded_by:`，不改舊內容**）
- Commit message 依 type 分層（見 `.claude/rules/git-workflow.md`）：`feat` 三段 WHY/WHAT/IMPACT；`fix` WHY + root cause；`docs`/`chore` 一行夠
- **永不在 `main` / `dev_new_arch` 直接 commit** — 先開 `<type>/<short>` 分支
- **push 由使用者執行**，Claude 只 commit
- 文件 6 tier 規則：`.claude/rules/context-stability.md`
</important>

## 細節路標（漸進式揭露 —— 需要時才展開）

- **指令全集** → `@.claude/docs/commands.md`（setup, run, test, debug, deploy, env, API 工具；**部分內容待同步 lockcore 重寫，2026-06-04**）
- **架構細節** → `@.claude/docs/architecture.md`（request flow 圖、module map、web/api/DB/部署；**agent 部分待同步 lockcore 重寫**）
- **Agent 新架構** → `agent/README.md` + `agent/lockcore/VENDOR.md`（LockCore 設計依據、skill 結構、config 載入機制）
- **開發規則** → `.claude/rules/*`（git-workflow, change-governance, context-stability, testing, security…）
- **文件中樞** → `docs/HOME.md`（5D 框架 + TR gate）

> 維護提醒：本檔是「每次工作階段都載入」的記憶植入，不是 README。新增內容前先問「agent 自己讀 code 能不能發現？」能 → 不要寫進來，放子檔或讓它自己讀。文件過期 agent 就會錯，當基礎建設維護。
