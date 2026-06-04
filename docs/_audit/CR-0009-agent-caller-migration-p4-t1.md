---
id: CR-0009
title: "Agent caller migration P4-T1（4 callers + LINE bot 404 風險，agent-coupled legacy 刪除前置）"
status: awaiting-owner-decision
tier: 4-exploration
owner: HYBRID
created: 2026-06-04
target-release: P4-T1（P4 cutover 前置硬依賴）
product-version: null
supersedes: null
superseded-by: null
related:
  - docs/_audit/CR-0003-full-cutover-wbs.md
  - docs/_audit/CR-0006-sop-v2-list-expand.md
  - agent/app.py
  - agent/integrations/admin_api.py
  - api/routers/consumer_v2.py
  - api/routers/refunds_v2.py
---

# CR-0009 — Agent caller migration P4-T1

> **Tier**: 4-exploration → CIA  
> **Mandated by**: `.claude/rules/change-governance.md` + CR-0003 §3「agent 404 風險：P4-T1 設為刪 agent-coupled legacy 的硬 depends_on」  
> **CRITICAL**: 任何 agent caller 漏遷或 v1 router 提早刪 → LINE bot prod 404 連環炸

---

## 1. Change Statement

**As-is**：agent 服務有 4 個 v1 caller，全帶 P3-KEEP 註解（缺 v2 對應）：

| 檔案 | line | endpoint | P3-KEEP 原因 |
|---|---|---|---|
| `agent/app.py` | 387 | `POST /api/v1/work-orders/{wo_id}/reschedule/customer-confirm` | Flow 11 RSVP，consumer_v2 未涵蓋 |
| `agent/app.py` | 407 | `POST /api/v1/work-orders/{wo_id}/reschedule/customer-reject` | 同上 |
| `agent/integrations/admin_api.py` | 282 | `POST /api/v1/refunds` | refunds_v2 createRefundSod 強制三維 SoD（agent 自動退款不適用）|
| `agent/integrations/admin_api.py` | 356 | `POST /api/v1/sop-drafts` | sops_v2 僅 review action（無 create）|

**To-be**：
- agent app.py 2 caller → 走 consumer_v2 新增 customer-confirm/reject endpoint
- agent admin_api.py refunds → 走 refunds_v2 新增「agent 自動退款 single-actor 路徑」（或保留 v1 至 Phase II 改設計）
- agent admin_api.py sop-drafts → 走 CR-0006 補的 sops/drafts POST endpoint

**Driver**：
- **CR-0003 §3 硬 depends_on**：P4 cutover 刪 legacy router 前，agent caller 必須清零
- MISSION.md 北極星 (3) v1=0 不可達成（agent 還在打 v1）
- prod LINE bot 已上線（v1.36.0），任一漏遷 → 客戶 RSVP / 自動退款 / SOP 寫入全 404

---

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| `BF-WO-RSVP`（客戶不在場 RSVP）| Modified | agent 改打 consumer_v2 新 endpoint |
| `BF-RF-AGENT`（agent 自動退款）| Modified | 看 HD-02 決策走 v2 single-actor 路徑或保留 v1 |
| `BF-SOP-AGENT`（agent 寫 SOP 草稿）| Modified | 依賴 CR-0006 補的 sops/drafts POST |

---

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| `FR-0011-RSVP`（客戶不在場 RSVP）| Modified | consumer_v2 新增 confirm/reject |
| `FR-RF-AGENT`（agent 自動退款）| Modified | 看 HD-02 是否要重寫 service 層 |
| `FR-SOP-001`（SOP 草稿生命週期）| Modified | 透過 CR-0006 解決 |
| `NFR-AG-001`（LINE bot 404 zero-tolerance）| **Critical** | P4-T1 期間需 0% 404 |

---

## 4. Affected API

| API ID | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| `API-CONS-V2-CONFIRM` | `POST /consumer/work-orders/{token}/reschedule:confirm` | **New** | — | 沿用既有 token-based public auth；body `{slot_index}` |
| `API-CONS-V2-REJECT` | `POST /consumer/work-orders/{token}/reschedule:reject` | **New** | — | body `{reason?}` |
| `API-RF-V2-AGENT` | `POST /tenants/{tid}/refunds:agent-initiate` | **New** | — | single-actor，agent 身分驗證；無 SoD（HD-02 a/b 決定）|
| `API-SOP-V2-DRAFTS-POST`（cross-ref CR-0006 API-SOP-V2-CREATE）| 沿用 CR-0006 | — | — | 同 endpoint 不重複建 |

---

## 5. Affected Data

無新表（既有 `refunds` / `sop_drafts` / `reschedule_proposals` 沿用）。

---

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| `TC-AG-001`（agent app.py confirm 走 v2 happy path）| **New** | LINE postback → agent → consumer_v2 confirm |
| `TC-AG-002`（agent app.py reject 走 v2）| **New** | 同上 reject |
| `TC-AG-003`（agent admin_api refunds 走 v2 single-actor）| **New** | 依 HD-02 決策 |
| `TC-AG-004`（agent admin_api sop-drafts POST 走 v2）| **New** | 沿用 CR-0006 |
| `TC-AG-PROD-001`（prod canary：v1 caller=0 確認）| **New** | grep agent/ `api/v1/` = 0；E2E LINE bot 流 happy path |

---

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| Module boundary | Unchanged | agent 仍透過 admin_api / app 呼叫 api |
| New ADR? | **Yes** | `ADR-0106`（暫定）— agent 退款 single-actor vs 三維 SoD 決策（HD-02 重大架構分歧）|
| External integration | LINE bot | prod 已上線 v1.36.0，**zero-tolerance 404** |
| Monitoring | 新增 alert | Sentry / Datadog 監控 agent → api v1 404 比例（HD-05）|

---

## 8. Human Decisions Required

🛑 **CIA blocks code changes until every row here has a recorded decision.**

| # | Question | Options | Owner | Status | Decision |
|---|---|---|---|---|---|
| **HD-01** | consumer_v2 confirm/reject endpoint 位置 | (a) `/consumer/work-orders/{token}/reschedule:{confirm\|reject}`（與 /track 對齊）<br>(b) `/consumer/reschedule-proposals/{token}:respond` body decision 區分<br>(c) 與 CR-0007 reschedule:propose 共用 webhook 設計 | Architect | open | — |
| **HD-02** | agent 自動退款路徑 | (a) **新增** v2 single-actor `refunds:agent-initiate`（保持 agent 自動退款功能）<br>(b) **重構** agent 走人工 dual-sign（人介入流程，安全但慢）<br>(c) **保留** v1 至 Phase II 重設計（P4 cutover 對 refunds 法外開恩）| Security/Finance | **decided 2026-06-04** | **(a) 新增 v2 single-actor agent-initiate**（保留 agent 自動退款功能；需 ADR-0106 記 LangGraph 特例不違背全面 SoD 原則）|
| **HD-03** | CR-0009 與 CR-0006 sop-drafts POST 整合時機 | (a) CR-0006 拍板再做 CR-0009（依序）<br>(b) CR-0006/0009 平行起 + 同時 merge<br>(c) CR-0009 sop-drafts 部分等 CR-0006 落地後補 | Eng Lead | open | — |
| **HD-04** | P4-T1 → P4 cutover 之間是否要 canary 期 | (a) 改完 agent 即 P4 cutover（dev-phase 簡化）<br>(b) Canary 48h 觀察 agent caller 404 = 0<br>(c) Canary 7d（謹慎，但延後 P4）| Ops | open | — |
| **HD-05** | LINE bot 404 監控告警閾值 | (a) 任何 v1 404 即 PagerDuty<br>(b) 5min 內 ≥ 3 次 → 告警<br>(c) Sentry log only（無主動告警）| Ops | open | — |

---

## 9. Suggested Implementation Order

§8 + CR-0006 § 8 業主裁決後實作：

1. **Decisions** → `ADR-0106`（暫定）記錄 HD-02 退款設計重大決策
2. **Schema** → 不動（既有表沿用）
3. **API layer（並行）**：
   - consumer_v2 補 confirm/reject endpoints（依 HD-01 路徑）
   - refunds_v2 補 agent-initiate（依 HD-02）或 SKIP
   - sop_v2 補 drafts POST（依賴 CR-0006）
4. **Agent migration**（依序，**每改 1 個跑 1 輪 staging E2E LINE bot 測試**）：
   - app.py customer-confirm → v2
   - app.py customer-reject → v2
   - admin_api.py refunds → v2 single-actor（HD-02=a）
   - admin_api.py sop-drafts → v2
5. **Tests** → TC-AG-001~005
6. **Monitoring** → HD-05 告警上線（在 deploy 前）
7. **Canary** → 依 HD-04 觀察期
8. **驗證 `grep agent/ "api/v1/" = 0`** → 解開 P4 cutover gate
9. **CR-0003 §5** → P4-T1 ✅，P4 解 gate

---

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **LINE bot prod 404 連環炸**（任何漏遷 + legacy 提早刪）| Certain if rushed | **Critical** | 每改 1 caller 跑 staging E2E；HD-04 選 (b)/(c) canary；HD-05 告警上線 |
| agent 自動退款 → 人工流程切換破壞客戶體驗（HD-02=b）| Medium | High | 強烈建議 HD-02 選 (a)（保留 agent 自動退款功能）|
| consumer_v2 path 結構衝突（HD-01 三選一影響型別重生）| Low | Medium | 與 spec 合併 P1-T1 對齊；prefer (a) 與既有 /track 一致 |
| ADR-0106 退款 single-actor 違反「全 dual-sign」原則 | Medium | Medium | ADR-0106 明確區分「agent 自動退款」是受 LangGraph 限制的特例，非全面開放 |

**Rollback plan**：
- staging 出 404 → revert agent commit，legacy v1 router 仍存（雙軌期間 agent 可隨時切回 v1）
- prod 出 404 → 即時 rollback agent image + LINE bot 暫停（HD-05 告警觸發）
- legacy v1 router 刪除（P4）前 agent 必須 100% v2，否則 **P4 cutover 不可執行**

---

## 11. Out of Scope

- **agent_v2 搬遷**（M18 ACL Phase II）→ 獨立 CR
- **agent 自動退款全面重設計**（風險評估 / 上限 / 監控）→ Phase II FR-0050 AI Governance
- **LINE bot v2 SDK 升級** → 獨立 CR

---

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product | | | |
| Architect | | | |
| Engineering Lead | | | |
| Security/Finance（HD-02）| | | |
| Ops（HD-04/05）| | | |

---

## §A 取證附錄

```bash
# agent v1 caller 全列：
$ grep -n "api/v1/" agent/app.py agent/integrations/admin_api.py
# →
# agent/app.py:387: customer-confirm
# agent/app.py:407: customer-reject
# agent/integrations/admin_api.py:282: /api/v1/refunds
# agent/integrations/admin_api.py:356: /api/v1/sop-drafts

# v2 缺口：
$ grep "@router" api/routers/consumer_v2.py
# → 1 個（/track GET），缺 confirm/reject

$ grep "@router" api/routers/refunds_v2.py | head
# → createRefundSod（強制三維 SoD），缺 agent single-actor 路徑

# CR-0003 §3 引用：
# "agent 404 風險：P4-T1（遷 agent /api/v1 caller）設為刪 agent-coupled legacy 的硬 depends_on"
```

---

> 🛑 **§8 業主裁決前不動 code。** 預計裁決後工時 3-5 天（含 canary 觀察期）。  
> ⚠️ **本 CR 解 4 caller 但保 LINE bot 不掛**，是 P4 cutover 的唯一硬 gate。
