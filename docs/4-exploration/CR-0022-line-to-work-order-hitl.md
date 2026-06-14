---
id: CR-0022
title: "LINE 對話 → 工單：HITL 轉換鏈（escalation → draft 問題卡 → 1-click 轉工單）"
status: draft
tier: 4-exploration
owner: HYBRID
created: 2026-06-14
target-release: dev_new_arch
product-version: null
supersedes: null
superseded-by: null
related:
  - docs/architecture/adr/ADR-0031-ai-auto-convert-to-work-order.md
  - docs/architecture/adr/ADR-0028-ai-employee-charter.md
  - CHANGELOG.md（方案 A：feat/agent-conversation-bridge + feat/wo-conversation-thread）
---

# CR-0022: LINE 對話 → 工單 HITL 轉換鏈

> **Tier**: 4-exploration → Change Impact Analysis（per-change，實作後歸檔）
> **Mandated by**: `.claude/rules/change-governance.md`（觸發面向：User flow / API contract / Domain model / DB schema / Architecture boundary — 命中 5 項）
> **前置已完成**：方案 A 已打通「LINE 對話 → DB → 工單後台可見」（對話旁路持久化 + 工單頁逐字稿渲染）。本 CR 處理**反向缺口**：讓 LINE 對話能（經人審）變成一張工單。

---

## 1. Change Statement

**As-is**：LINE 客人對話進 agent → agent 回覆 + 轉真人時只把 escalation 寫進 agent 自己的
SQLite（`agent/lockcore/agent/user_memory/escalation.py`），與 API 的 PostgreSQL **零連線**。
客服後台看不到 agent 轉了誰，更無從把對話變成工單。工單只能由「有認證的人類」從**既有**
問題卡手動開立。

**To-be**：agent 轉真人 / 判定需派工時，經內部通道在 API 建立一張 **AI 草擬的 draft 問題卡**
（帶對話連結 + 信心/缺漏提示），出現在客服「待處理佇列」；客服 1-click 補全 → confirm →
convert-to-work-order。**AI 全程不可自行轉工單**（ADR-0028 charter / ADR-0031 鎖死）。

**Driver**：2026-06-10 lock-AI 會議「工單系統能否與 LINE 串接」工項；ADR-0031 已裁定走
「AI 草擬 + 客服 1-click 人審」但**從未實作**（無 escalation→API 同步、無待轉佇列 UI）。

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| `F-001`（LINE 報修首訊建 ServiceTicket/conversation） | Unchanged | 對話建立沿用方案 A ingest |
| `F-002`（客服審 PC → 開 WO） | Modified | 入口新增「AI 草擬 draft PC」來源；confirm→convert 流程不變 |
| `SF-line-escalation-to-pc`（新） | New | escalation/需派工 → draft 問題卡的轉換規則（含去重、缺漏處理） |
| `UF-cs-pending-queue`（新或擴充） | New/Modified | 客服「待轉 WO 佇列」：列出 AI 草擬 PC + 信心分數 + 缺漏 hint + 1-click |

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| `FR-0003 / FR-0004`（auto/manual dispatch） | Unchanged | 派工本身不變，只多一個工單來源 |
| `FR-ai-draft-pc`（新） | New | AI 草擬問題卡規則：何時觸發、必填/可空欄位、信心分數定義 |
| `ADR-0031` | 落地 | 本 CR 是 ADR-0031「推薦方案」的實作；不改決策，補實作 |
| `ADR-0028`（AI charter Forbidden 清單） | Honor | 「AI 不可直接 convert_to_work_order」必須在實作中保證 |
| `NFR`（轉真人延遲） | Check | 草擬 PC 不可阻斷對客人的回覆（沿用 fail-soft 旁路） |

## 4. Affected API

| API ID | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| `internal/escalations:ingest`（新） | `POST /api/v1/internal/escalations/ingest` | New | No | service-to-service，`require_internal_token`（沿用方案 A 機制）；body 帶 tenant/line_user/session/reason/facts_snapshot |
| `createProblemCardV2` | `POST /tenants/{tid}/problem-cards` | Reuse | No | 既存；但需 AI-draft 來源 → 見 §5 是否放寬必填 |
| `confirmProblemCardV2` | `POST .../problem-cards/{id}/confirm` | Unchanged | No | 既存 incomplete→confirmed |
| `convertProblemCardToWorkOrderV2` | `POST .../problem-cards/{id}/convert-to-work-order` | Unchanged | No | **既存且可用**；客服人審後呼叫 |
| `listProblemCardsV2` | `GET .../problem-cards?status=&source=` | Modified | No | 佇列需可篩 status=incomplete + source=ai_line |

> 關鍵：**轉工單端點已存在且可用**。本 CR 的新 code 集中在「escalation→draft PC 同步」與
> 「佇列 UI」，不是重造轉換邏輯。

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `problem_cards` | 新欄位 `source TEXT`（'human' / 'ai_line'）+ `ai_confidence NUMERIC NULL` + `ai_missing_fields JSONB NULL` | online migration，預設 'human' / null（反相容） |
| `problem_cards.conversation_id` | Unchanged（UNIQUE 已存在） | UNIQUE 天然保證「一對話最多一 PC」去重 |
| `conversations.last_problem_card_id` | Reuse | 已存在（CR-0001 雙向 FK），草擬後回填 |
| `problem_cards.status` | **決策點** | create_card 現要求 brand/model/symptom 必填；AI 草擬常缺 → 見 §8 #2 |
| escalation（agent SQLite） | Unchanged | 仍為 agent 端稽核；本 CR 不搬遷，只在發生時旁路同步到 API |

狀態機影響：problem_card 既有 `incomplete → confirmed → converted` 不變；AI 草擬一律進
`incomplete`，由客服補全推進，符合既有狀態機。

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| `TC-escalation-ingest-auth` | New | internal token 503/401 邊界（沿用方案 A 測試模式） |
| `TC-escalation-to-draft-pc` | New | escalation → draft PC 建立（source=ai_line，conversation 連結正確） |
| `TC-draft-pc-dedup` | New | 同 conversation 重複 escalation → 不重建 PC（UNIQUE/upsert） |
| `TC-draft-pc-missing-fields` | New | 缺 brand/model → 依 §8 #2 裁決行為（建空殼 or 不建 + 記 alert） |
| `TC-queue-list-filter` | New | listProblemCards 篩 status=incomplete+source=ai_line |
| `TC-hitl-no-ai-convert` | New | 確認 AI 路徑無法觸發 convert（charter lock 回歸測試） |
| `TC-e2e-line-to-wo`（Playwright） | New | 佇列點 PC → 補全 → confirm → convert → 工單出現 |

覆蓋率：估 +6~7 TC，集中於 problem_card_service / internal router。

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| Agent 架構鎖 | Honor | `CS_TOOL_ALLOWLIST` **不變**；同步發生在「通道旁路」層（沿用方案 A），agent 核心零變更 |
| AI charter（ADR-0028） | Honor | AI 最多建 draft PC；confirm + convert 一律人類。需回歸測試守線 |
| Module boundary | Unchanged | 留在 conversation/problem-card/work-order 既有 bounded context |
| New ADR? | **Yes（選配）** | 若 §8 決議放寬 problem_card 必填或新增 AI-draft 狀態 → 開 ADR 記錄；否則沿用 ADR-0031 |
| 外部整合 | None | 不接新 vendor |

## 8. Human Decisions Required

🛑 **CIA 未對每列記錄決策前，不動 code。**

| # | 問題 | 選項 | Owner | Status | Decision |
|---|---|---|---|---|---|
| 1 | **何時**建草擬 PC？ | (a) 每次 escalation（轉真人即建）(b) 僅「明確要真人 / 需派工」才建（is_explicit 或 intent=repair）(c) AI 主動判定「資訊足夠開單」才建 | Product/CS 主管 | open | — |
| 2 | **缺必填欄位**怎麼辦？create_card 現要 brand/model/symptom | (a) 新增寬鬆 'draft' 狀態允許 null（schema+ADR）(b) 缺欄位就**不建 PC**，只建「待跟進 alert」(c) AI 用 placeholder 佔位、客服補 | Architect/CS | open | — |
| 3 | **同步機制** | (a) gateway 旁路即時 POST（沿用方案 A，推薦）(b) 背景 job 輪詢 escalation.db (c) escalation store 直寫 PG | Architect | open | — |
| 4 | **佇列 UI** | (a) 新獨立頁 `/admin/pending-work-orders`（b) 擴充既有 `/admin/problem-cards` 加 source/status filter（推薦，省一頁）| UX/CS | open | — |
| 5 | **AI 信心分數 + 缺漏 hint** | (a) 本 CR 一起做（ADR-0031 原意）(b) 先只做來源標記，信心分數延後 | Product | open | — |
| 6 | **去重粒度** | 一對話一 PC（UNIQUE 已保證）夠嗎？同對話多次 escalation 是否更新既有 PC 的 reason/facts？ | Architect | open | — |
| 7 | **客服身分**：旁路同步無 JWT，建出的 PC `created_by` 記誰？ | (a) 系統帳號 'ai-agent'（b) null + source 標記 | Architect/CS | open | — |

## 9. Suggested Implementation Order

§8 全部裁決後，依相依順序：

1. **Decisions** → 若 #2/#5 決議改 schema/狀態，先寫 ADR-NNNN 記錄
2. **Schema** → migration：`problem_cards.source` + `ai_confidence` + `ai_missing_fields`（依 #5）
3. **API** → 新 `POST /internal/escalations/ingest`（沿用 `require_internal_token`）+ `escalation_to_draft_pc` service（含去重、缺漏處理依 #2/#6）
4. **API** → `listProblemCardsV2` 加 source/status filter（#4）
5. **Agent gateway** → transfer/需派工時旁路 POST escalation（沿用方案 A fail-soft；依 #1 觸發條件）
6. **Tests** → §6 的 6~7 個 TC（charter lock 回歸測試必做）
7. **UI** → 佇列頁（#4）：列 AI 草擬 PC + 信心/缺漏 + 1-click「補全→confirm→convert」
8. **Traceability** → 更新 TM matrix；CHANGELOG + system-completion-status 同步
9. **Docs sync** → 確認 ADR-0031 由「decided 未實作」更新為「implemented」

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| AI 草擬品質差 → 客服佇列被垃圾 PC 淹沒 | Medium | Medium | #1 收緊觸發條件（僅 explicit/需派工）+ #5 信心分數排序 |
| charter 邊界漂移：未來有人讓 AI 直接 convert | Low | **High** | `TC-hitl-no-ai-convert` 回歸測試 + code review 守 ADR-0028 |
| 缺地址/品牌的空殼 PC（ADR-0032 缺地址 hard stop） | Medium | Medium | #2 裁決；convert 端點本就會擋缺地址 |
| 旁路同步失敗 → escalation 沒進 API | Medium | Low | fail-soft + agent SQLite 仍留底；可加重試/對帳 job |

**Rollback**：同步為旁路、schema 欄位皆 nullable/有預設 → 反相容。停用 = gateway 不再 POST
escalation（或拔 `INTERNAL_API_TOKEN`），既有手動開單流程不受影響。

## 11. Out of Scope

- 低風險場景**全自動**轉工單（ADR-0031 Option A）— 需 6 個月人審通過率 + 法務 sign-off，另案。
- escalation.db 整體搬遷到 PostgreSQL（本 CR 只旁路同步，不搬家）。
- AI 信心分數的模型訓練/校準（若 #5 選 a，先用啟發式：缺欄位數 → 信心）。
- 多租戶官方帳號 → tenant 反推（gateway 目前單一 tenant）。

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product / CS 主管 | | | |
| Architect | | | |
| Engineering Lead | | | |
| QA Lead | | | |
