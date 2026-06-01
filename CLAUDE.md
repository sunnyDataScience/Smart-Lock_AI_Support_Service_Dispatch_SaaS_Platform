# CLAUDE.md

給 Claude Code 的工作指引。**原則：只寫「讀 code 推不出來的」—— 非預期工具鏈、歷史包袱、團隊共識、踩過的雷。**
結構概覽、目錄樹、模組職責請 `ls` / 讀 code；細節在 `@.claude/docs/*`（見文末路標）。

## Project Overview

Smart Lock AI Support & Service Dispatch SaaS Platform —— LINE Bot 智慧鎖 AI 客服 agent + Next.js 營運後台。
核心是 ReAct agent（LangGraph），靠 `product_info/` mega-doc 知識庫（每 brand+model 一份自足 mega-doc，**內容嚴格只源自 `data/storage/bronze/`**），外加 Medallion data pipeline。

本 agent 分支另配一個 optional **Belief-Augmented ReAct（Turn Cycle）** 原型 —— Hypothesize → Decide → Execute → Calibrate —— 由 `agent/config.toml` 的 `[turn_cycle].enabled` 控（預設 `false`）。

**user-facing 文字、註解、文件一律繁體中文**；code identifier 與 git message 可中英混用。

## 🔒 Architecture Lock — 知識庫正典（必讀，不可違反）

**正典是 `product_info/` mega-doc，不是 `skills/` SKILL.md。** 詳見 [ADR-0008](docs/1-decisions/ADR-0008-product-info-architecture-canonical.md)。

| 項目 | ✅ 採用（正典）| ❌ 棄用（2026-05-11 A-3b 起）|
|---|---|---|
| 知識庫格式 | `agent/product_info/{Brand}/{Model}.md` mega-doc | `agent/skills/data/.../SKILL.md`（已全刪）|
| Agent tool | `load_product_info(name)` | `load_skill(skill_name)`（已退場）|
| Tool module | `agent/agent_tools/tools.py` | `agent/skills/tools.py` |
| Prompt 區塊 | `[可用產品資料]` | `[可用技能]` |

**硬性約束（前兩條已由 `architecture-lock.sh` hook 機械式攔截，不只是建議）：**

1. **不准在 `agent/` 內 import `skills`** —— `from skills ...` / `import skills` / `from skills.tools ...` 全禁。A-3a 退場 load_skill、A-3b 刪 69 個 SKILL.md，code 已對齊；新 import 會破壞此狀態。
2. **不准重建 `agent/skills/data/*/SKILL.md`** —— 新產品知識一律寫成 `agent/product_info/{Brand}/{Model}.md`。
3. **任何「想改回 skills/」的提案** → 先讀 ADR-0008、到 issue tracker 徵詢，勿直接 force-push。（ADR-0008 曾於 2026-05-09 被 force-push 改標 SUPERSEDED，後續 A-1~A-3b 系列 commit 走回原決議。）

**Sourcing rule（CRITICAL — bronze-only）**：所有 mega-doc 內容嚴格源自 `data/storage/bronze/`（YouTube 字幕、website、video transcript）。**PDF (GDrive) 不可信，mega-doc 只引 URL 不抄內容。**

## 🧪 Experimental Lock — Belief-Augmented ReAct（Turn Cycle）

本 branch 為 Turn Cycle 實驗 fork，67 共同題對打 **89.6% strict / 100% pass+partial / 0 fails**（vs agent-port baseline 83.6% / 1 fail）。詳見 [ADR-0010](docs/1-decisions/ADR-0010-belief-augmented-react.md)。

**硬性約束：**

1. **預設關**：`[turn_cycle].enabled=false`、`fail_open=true`。production deploy 前須維持，避免 dual-dispatch 上線回退類事件重演。
2. **Hypothesize / Decide / Calibrate 不准單獨 import** —— 必須走 `harness/turn_cycle_runner.run_belief_cycle()` 入口。
3. **policy 閾值**（`agent/policy.py` HIGH=0.55 / GAP=0.15）已由 B-fix-v2 調過，調整需附 quality_check 對打數據。見 [Action Policy Thresholds](agent/docs/manuals/action_policy_thresholds.md)。
4. 本 branch 是否進 production 待路線決議（roadmap 走向 hermes-cs，agent-port 暫為 archive 候選）。

## 非預期工具鏈（agent 推不出來，必讀）

- **Python 用 `uv`，不是 pip** —— `uv sync` 裝齊三 module deps；跑任何 script 用 `uv run ...`。`pyproject.toml` 改了就重跑 `uv sync`。
- **Web 用 Node/npm**，與 uv 無關（`cd web && npm install`）。
- **無自動化 unit test 套件** —— 測試靠 `quality_check`（LLM-as-Judge）、CLI（`python main.py`）、或 `/chat` 端點。別找 pytest 套件。
- **Config pattern**：TOML 存環境變數**名稱**（如 `postgres_uri_env = "POSTGRES_URI"`），實際值在 `.env`。
- **永不手動構建 `POSTGRES_URI`** —— 用 `./scripts/deploy/agent.sh --update-db-uri`（自動 URL-encode + round-trip 驗證）。

## 最常用指令（完整清單見 `@.claude/docs/commands.md`）

```bash
uv sync                                                  # 裝/更新所有 deps
cd agent && uv run python main.py                        # Agent CLI（驗證 LLM 連線）
cd agent && uv run uvicorn app:app --reload --port 8000  # Agent server（LINE webhook）
cd agent && uv run python -m quality.quality_check       # LLM-as-Judge eval
curl "http://localhost:8000/chat?q=門打不開"              # 快速測試端點
```

<important if="跑測試 / 評估 agent 品質">
- 唯一的「測試」是 `quality_check`：`cd agent && uv run python -m quality.quality_check`
- `--no-judge` 只跑 keyword match；`--judge-only` 重評既有報告；`--retry-failed` 只重測非 pass；`--turn-cycle` 做 A/B
- 調整 `agent/policy.py` 閾值務必附對打數據（見 Experimental Lock §3）
- 完整指令與 debug 工具：`@.claude/docs/commands.md`
</important>

<important if="部署 / 動 DB / 改環境">
- Deploy 走 `./scripts/deploy/{agent,api}.sh`（Cloud Run，pre-flight → build → push → deploy → health check）
- 動 `POSTGRES_URI` 一律 `--update-db-uri`，永不手動構建
- 環境切換：`./scripts/env/use-local.sh` / `use-gcp.sh`；secrets 在 GCP Secret Manager
- 完整部署/環境指令：`@.claude/docs/commands.md`
</important>

<important if="動 flow / contract / data / architecture">
- 先跑 `sunnydata-change-impact-analysis` skill（硬 gate，見 .claude/rules/change-governance.md）
- 文件衝突或 status: deprecated/superseded → 停下回報，引用具體 ID（BF-/UF-/API-/TC-），勿腦補
</important>

## 細節路標（漸進式揭露 —— 需要時才展開）

- **指令全集** → `@.claude/docs/commands.md`（setup, run, test, debug, deploy, env, API 工具）
- **架構細節** → `@.claude/docs/architecture.md`（request flow 圖、module map、harness 表、web/api/DB/部署）
- **知識庫 & tools** → `@.claude/docs/knowledge-base.md`（product_info 載入機制、目錄結構、3 個 tool、Turn Cycle module 清單）
- **開發規則** → `.claude/rules/*`（git-workflow, change-governance, context-stability, testing, security…）
- **文件中樞** → `docs/HOME.md`（5D 框架 + TR gate）

> 維護提醒：本檔是「每次工作階段都載入」的記憶植入，不是 README。新增內容前先問「agent 自己讀 code 能不能發現？」能 → 不要寫進來，放子檔或讓它自己讀。文件過期 agent 就會錯，當基礎建設維護。
