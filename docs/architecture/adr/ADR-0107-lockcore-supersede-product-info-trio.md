---
id: ADR-0107
title: LockCore + Agent Skills 標準取代 product_info trio（ADR-0008 / 0010 / 0101 superseded）
status: Accepted
date: 2026-06-05
deciders: [sunny@funngo.ai (2026-06-04 architecture rewrite), Imding1211 (2026-06-05 ADR governance)]
supersedes:
  - ADR-0008
  - ADR-0010
  - ADR-0101
related:
  - agent/lockcore/VENDOR.md
  - agent/README.md
  - CHANGELOG.md (2026-06-05 Unreleased entry "Agent 核心架構重寫")
  - feat/agent-update branch (commit 0f037f45)
  - docs/_audit/flow-11-agent-rewrite-impact.md
  - docs/_audit/CR-0017-line-flex-push-rebuild-cia.md
source_trade_off: 業主拍板（2026-06-04，feat/agent-update 直接 BUILD post-hoc 補 CIA）
eternal_transient: Eternal (agent 核心 = LockCore 不可動) / Transient (lockcore 內部演化 / 工具白名單可配置)
---

# ADR-0107 — LockCore + Agent Skills 標準取代 product_info trio

## Context

2026-06-04 業主於 `feat/agent-update` 分支完成 agent 核心一次性重寫（commit `0f037f45`，刪 200+ 檔，新增 178 檔 lockcore 結構）。架構從「ReAct + LangGraph + 自製 skill loader + product_info mega-doc + Belief-Augmented ReAct (Turn Cycle) + quality_check LLM-as-Judge」改為「LockCore (fork 自 nanobot) + Agent Skills 標準 + LiteLLM 統一供應商 + per-user memory (移植自 Hermes)」。

此重寫使下列三 ADR 的核心立場全面失效：

| ADR | 原立場 | 失效原因 |
|---|---|---|
| **ADR-0008** product-info-architecture-canonical | `product_info/{Brand}/{Model}.md` mega-doc 為 canonical；§4.1 模組路徑禁區；§4.4 quality_check baseline | mega-doc 結構整批刪除（45 個 `.md`）；改為 `lockcore/skills/locksmith-product-knowledge/references/{Brand}/{Model}.md`（Agent Skills 標準）；quality_check LLM-as-Judge 全刪 |
| **ADR-0010** belief-augmented-react | Belief / Hypothesize / Calibrate / Turn Cycle 狀態機 | `belief*.py` / `calibrate.py` / `hypothesize.py` / `turn_cycle.py` 全刪；改為 nanobot loop |
| **ADR-0101** product-info-extension-final-spec | 補 ADR-0008 的 §2.1-§2.4 dynamic lookup tool / multi-tenant scope / custom SKU fallback / partner portal 場景 | 所有補強建議的「擴展 product_info mega-doc 結構」前提失效 — references 採 Agent Skills 標準扁平結構，無 mega-doc 容器 |

CLAUDE.md `Architecture Lock` 表格已標記三 ADR 為「失效 ❌」（2026-06-04 重寫表格內），CHANGELOG `[Unreleased]` Decisions 段 `feat/agent-update` entry 第 24 行明確列為「後續 ADR 工作待補」。本 ADR 是該後續工作。

## Decision

**ADR-0008、ADR-0010、ADR-0101 三者 superseded by ADR-0107。**

新架構唯一正典：
- **Agent 核心**：`agent/lockcore/`（fork 自 `HKUDS/nanobot`，VENDOR.md 記載 fork 來源）
- **知識 & SOP**：`lockcore/skills/{locksmith-product-knowledge,locksmith-cs-sop}/`，採 Agent Skills 標準（agentskills.io / Claude Skills）frontmatter (`name / description / version / metadata`)，不綁框架專屬欄位 — 可攜性可複製到 Claude Code / Cursor / nanobot / hermes
- **LLM 供應商**：單一 `LiteLLMProvider`，多家用 model 字串路由（`gemini/` / `vertex_ai/` / `ollama_chat/` / `claude-*` / `gpt-4o`）
- **Per-user 記憶**：`lockcore/agent/user_memory/`，移植自 Hermes，`tenant + user_id` 為 key，BUILD/SAVE 接 turn 狀態機，SQLite memory.db
- **工具白名單**：`lockcore/app_config.py:CS_TOOL_ALLOWLIST = {read_file, list_dir, find_files, grep, web_search, transfer_to_human}`，客服 only，砍 write/exec/shell/spawn/cron/message/web_fetch/image
- **Bronze-only sourcing rule 仍適用**：references 內容嚴格源自 `data/storage/bronze/`（YouTube 字幕 / website / video transcript）；PDF (GDrive) 不可信，references 只引 URL 不抄內容

## Consequences

### Positive

1. **可攜性**：skill bundle 可獨立移轉至其他 agent runtime（claude code / cursor / hermes）
2. **多供應商靈活性**：LiteLLM 隻字串切換成本接近 0
3. **工具最小化**：CS_TOOL_ALLOWLIST 縮減暴露面 / 提升安全性
4. **vendor 隔離**：lockcore fork 自 nanobot，未來 nanobot 演化可選擇性 rebase

### Negative

1. **LINE Flex push 整段刪除** — Flow 3 最後 10% / Flow 11 最後 20% / Flow 14 補救流卡住（待 CR-0017 裁決重建路徑）
2. **舊 Hermes Belief-Augmented ReAct 研究成果失效** — Turn Cycle / calibrate / hypothesize 不再可重用
3. **post-hoc CIA gap acknowledgment** — 業主已 BUILD code，違反 change-governance Hard Gate；本 ADR 是治理層 catch-up

### Neutral

- product_info mega-doc 內容**鎖定**（per memory `feedback_product_info_locked.md`），位置改 `lockcore/skills/locksmith-product-knowledge/references/{Brand}/{Model}.md` — 內容不變、結構保持 Brand/Model 雙層
- Bronze-only 來源規則仍是 hard constraint

## Compliance migration

| ADR-0008 段落 | 在新架構處置 |
|---|---|
| §1 mega-doc canonical | references/{Brand}/{Model}.md 取代，內容鎖定不動 |
| §3 反 revert 立場 | **不適用** — lockcore 架構即是新 source of truth |
| §4.1 模組路徑禁區 | **重定義**：禁區改為 lockcore 之外不可另寫 agent 核心 |
| §4.4 quality_check baseline | **完全失效** — 改 pytest 13 個 unit/integration |

| ADR-0010 段落 | 處置 |
|---|---|
| Turn Cycle 狀態機 | **全失效** |
| Belief / Hypothesize 機制 | **全失效** |
| Calibrate 信心評估 | **全失效** |

| ADR-0101 段落 | 處置 |
|---|---|
| §2.1 backend M14 scope governance | 由 backend `api/services/*` 既有 tenant_id 隔離承接，不在 agent 層 |
| §2.2 dynamic lookup tool | **未實作** — lockcore CS_TOOL_ALLOWLIST 不含；若未來需要，要在 `lockcore/agent/tools/` 新增 + 走 CIA |
| §2.3 multi-tenant scope filter | 同 §2.1 |
| §2.4 custom SKU fallback | **未實作** — 若需要，補 backend service |

## Future migration（不在本 ADR scope）

- ADR-0007（agent-skill-loader-canonical，如存在）— 若引用 product_info trio 也需更新
- 引用 ADR-0008/0010/0101 的其他 ADR 應補 cross-reference 至 ADR-0107
- lockcore 內部工具白名單演化 / 新工具加入 — 各自獨立走 CIA

## Open items

- [x] ADR-0008 frontmatter 補 `status: superseded` + `superseded_by: ADR-0107`（本 commit 同步）
- [x] ADR-0010 frontmatter 補 `superseded_by: ADR-0107`（本 commit 同步）
- [x] ADR-0101 frontmatter 補 `superseded_by: ADR-0107`（本 commit 同步）
- [ ] CLAUDE.md `Architecture Lock` 表格末尾的「待補 superseded 標記」備註於後續 commit 移除（OOSCope 本 ADR）
- [ ] INDEX.md 補 ADR-0107 entry（OOSCope 本 ADR）

## References

- 主要 commit: `0f037f45` (feat/agent-update branch)
- agent/README.md
- agent/lockcore/VENDOR.md
- CHANGELOG.md `[Unreleased]` 段 `feat/agent-update` Decisions entry
- 後遺症 audit: `docs/_audit/flow-11-agent-rewrite-impact.md` + `docs/_audit/CR-0017-line-flex-push-rebuild-cia.md`
