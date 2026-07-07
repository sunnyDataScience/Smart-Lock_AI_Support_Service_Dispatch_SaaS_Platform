---
title: "ADR-008: Agent 核心採 LockCore（fork 自 nanobot 的最小核心）"
version: 1.0
status: active
owner: agent 系統 tech lead
last-updated: 2026-07-07
upstream:
  - smartlock-docs/agent/P2/04_adr/ADR-001_LockCore_fork_nanobot_取代_ReAct.md
---

# ADR-008: Agent 核心採 LockCore（fork 自 nanobot 的最小核心）

| 欄位 | 內容 |
|---|---|
| 狀態 | Accepted |
| 層級 | 系統級（agent）|
| 關聯 ADR | [ADR-009](./ADR-009_Model_Orchestration_Layer.md) · [ADR-010](./ADR-010_知識分層_Skill行為驅動_RAG-via-MCP.md) · [ADR-011](./ADR-011_Agent整合風格三分類.md) · [ADR-025](./ADR-025_AI話術邊界與永不自轉工單憲章.md) |

## Context（背景與問題）

LINE Bot 智慧鎖 AI 客服 agent 的核心迴圈（tool-using loop、context 治理、重試恢復）若完全自建，每個 edge case（工具重試、上下文壓縮、空回覆恢復）都要自己踩坑，且無上游社群紅利。同時客服場景有深度客製需求：per-user 記憶注入、工具白名單、供應商層瘦身、多用戶隔離——這些需要改核心內部，套件依賴方式做不到。

## Decision（決策）

**Agent 核心 = LockCore：fork 自 `HKUDS/nanobot` 的最小核心**（來源 commit `ac8bef76`，MIT 授權，`lockcore/LICENSE`；出處與範圍記於 `agent/lockcore/VENDOR.md`）：

- 只複製 `AgentLoop` 的**遞移 import closure**（~77 模組 + templates + tools 全目錄），涵蓋 `agent / utils / providers / config / command / session / bus`；不含上游 channels / api / heartbeat / webui。
- 套件更名 `nanobot` → `lockcore`（import 與執行期字串一併改），persona 模板為「鎖市 LockSmart 客服助理」（`templates/SOUL.md`）。
- **深改點**：`ContextBuilder` 可注入 per-user `MemoryManager`（BUILD 注入 Customer Memory）；`AgentLoop._state_save` 接 `record_turn`（SAVE 寫回記憶）；`Dream` 不掛 WriteFileTool（防多用戶客服污染共用 skill）。
- **工具白名單**：`lockcore/app_config.py:CS_TOOL_ALLOWLIST` 統一控管，客服僅開 6 個唯讀 / 轉接工具：`read_file / list_dir / find_files / grep / web_search / transfer_to_human`。新增工具屬 architecture change，須走 CIA。
- 推理迴圈採 nanobot 原生 Turn 狀態機（RESTORE→…→DONE），刻意保持最小核心、不疊多段自製推理階段。

## Alternatives（考量的選項）

- **A：LockCore（fork 最小核心，採用）** — 成熟迴圈 + context governance + 有界重試；fork 保留深改自由；代價是上游更新需手動 cherry-pick。
- **B：以套件依賴引入 nanobot（不 fork）** — 上游自動跟隨，但記憶注入、工具剝離、供應商瘦身等深改撞上上游 API 邊界，做不到。
- **C：自建 agent 核心（LangGraph ReAct 等框架自組 + 多段推理階段）** — 完全可控，但 edge case 全自踩、長期維護負擔最重、複雜度與 token 成本高、社群紅利為零。

## Consequences（後果）

**正面**：核心穩定度來自成熟上游；知識走 Agent Skills 標準可攜（[ADR-010](./ADR-010_知識分層_Skill行為驅動_RAG-via-MCP.md)）；per-user 記憶、白名單、供應商瘦身皆落地；迴圈簡單、token 成本低。
**風險**：fork 維護成本——上游 bug fix / 安全 patch 需手動 cherry-pick；closure 帶進部分客服未用模組（cron / pairing / webui closure，擴大維護面與攻擊面）；`bus/queue.py` 存在但 LINE 路徑走同步 `_process_message`，mid-turn 注入 / auto-compact 不在此路徑生效。
**影響範圍**：`agent/lockcore/` 整包；進入點 `scripts/line_gateway.py`（`POST /callback`）；測試 `agent/tests/`（e2e mock turn / skill loaded / tool allowlist / 記憶隔離等 ~13 測試）。
**重評觸發**：上游 nanobot 停止維護或授權變更；cherry-pick 衝突成本超過自建預期；客服需求超出核心能力邊界導致 fork 徹底分岔。

## Status 附註

- 供應商層見 [ADR-009](./ADR-009_Model_Orchestration_Layer.md)；知識格式見 [ADR-010](./ADR-010_知識分層_Skill行為驅動_RAG-via-MCP.md)。
- 硬性約束（Architecture Lock）：不准在 lockcore 之外另寫 agent 核心；skill 必須留在 `lockcore/skills/`。
