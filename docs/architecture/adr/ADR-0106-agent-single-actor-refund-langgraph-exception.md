---
id: ADR-0106
title: Agent 自動退款 single-actor 路徑 — LangGraph 特例（CR-0009 HD-02=a 業主裁決）
status: Accepted
date: 2026-06-04
deciders: [sunny@funngo.ai (2026-06-04 value decision)]
related:
  - docs/_audit/CR-0009-agent-caller-migration-p4-t1.md
  - docs/architecture/adr/ADR-0040-refund-approval-tiers.md
  - api/routers/refunds_v2.py
  - api/services/refund_service.py
source_trade_off: CR-0009 §8 HD-02 三選一 + §10 風險表
eternal_transient: Eternal (agent 服務帳號可單簽退款) / Transient (具體 amount 上限可配置；後置 review 流程可演進)
---

# ADR-0106 — Agent 自動退款 single-actor LangGraph 特例

## Context

ADR-0040 / `createRefundSod` 強制三維 SoD（X-Initiator / X-Approver / X-Executor）。但 LINE bot agent 自動退款流程（F-014 dual-trigger）由 LangGraph 決策樹自動發起，無法在 ms 級內取得三個人類 actor 簽核。

CR-0009 HD-02 給三選一：
- (a) 新增 v2 single-actor `refunds:agent-initiate`（保留 agent 自動退款）
- (b) 重構走人工 dual-sign（安全但慢）
- (c) 保留 v1 至 Phase II 重設計

業主裁 **(a)**。

## Decision

新增 `POST /tenants/{tid}/refunds:agent-initiate` v2 endpoint：
- 接受 single actor（agent 服務帳號 JWT）
- Server-side enforcement：`user.role` 必為 `'agent'` 或 `'system'`，人類用戶禁用
- 寫入 refunds 表時 `requires_dual_sign=False`、`requested_by_role='agent'`
- 視為「LangGraph 特例」，**不違背全面 SoD 原則** — 因 agent 自動化受 LLM 反應時間限制，無法等人類 dual-sign

## Consequences

### Eternal
- agent 服務帳號保有單簽建退款能力
- agent / system role enforcement 在 BE 層（不可繞過）
- LangGraph 特例設計記入 ADR，不可隨意擴張到其他 service-account

### Transient
- amount 上限：service 層既有 `_DUAL_SIGN_THRESHOLD = NT$100,000`；超過自動轉 dual-sign 模式（即便 agent 也擋）
- 後置 review：ops dashboard 可篩 `requested_by_role='agent'` 退款做人類後置 review/reject

## Safety Guards

1. **Role enforcement**: BE endpoint check `user.role IN ('agent', 'system')`
2. **Amount cap**: 超過 100k 走 dual-sign（DB schema CHECK）
3. **Audit log**: 寫 refund row + actor='agent'，可追溯任何 agent 行為
4. **Rate limit**: agent JWT 受 API gateway rate limit（如 100 req/min）
5. **PagerDuty alert**: 若 24h 內 agent-initiate refund 數量超過 baseline 2x → 警告（HD-05 LINE bot 監控延伸）

## Open Questions（Phase II 治理）

- agent 自動退款的「金額上限」（除既有 SoD threshold 外）是否要 per-tenant configurable？→ FR-0050 AI Governance 收斂
- 「後置 review SLA」（人類多久內必須 review agent 退款）→ FR-0049 Exception Approval Inbox

## References

- ADR-0040 refund-approval-tiers（被本 ADR 部分例外，但原則仍適用人類路徑）
- CR-0009 §8 HD-02 + §11 Out of Scope
- refunds_v2.py:agentInitiateRefundV2 實作
