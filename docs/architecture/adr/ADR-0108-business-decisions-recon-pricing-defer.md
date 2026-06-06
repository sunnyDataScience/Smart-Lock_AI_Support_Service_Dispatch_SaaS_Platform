---
adr_id: ADR-0108
title: Reconciliation 雙簽 UX + 計價引擎 GUI — 業主裁決維持現狀 (deferred-accepted)
status: accepted
date: 2026-06-06
deciders: 業主
related: [ADR-0046, ADR-0102]
tags: [governance, business-decision, recon, pricing, deferred-accepted]
---

# ADR-0108 — Reconciliation 雙簽 UX + 計價引擎 GUI 業主裁決

## Context

`docs/_ops/wbs-100-closeout-plan.md` §2 列出 backend-coder agent 飽和後剩
4 項業主待裁決事項。其中事項 2 + 3 屬「合規 / 業務 scope 取捨」，AI 不能
建議，只能由業主親自決定。

兩項皆已在 `pending-business-decisions-2026-06-06.html` 整理選項 + 影響範圍。

## Decision

業主於 **2026-06-06** 對兩項裁決均選擇 **維持現狀 (deferred-accepted)**：

### 事項 2 — Reconciliation 雙簽 UX rework

- **決議**：選項 1 — 維持現狀（同人雙簽 + audit log）
- **理由**：技術上允許同人雙簽，audit_log 完整 trail。業主接受 Sox-like
  雙簽「不嚴格落實不同人」的合規風險，以 audit_log + change_request 作
  為稽核補強。
- **拒絕選項**：
  - 選項 2（強制不同人）— web dev 成本高 + 業務流程變繁
  - 選項 3（timestamp gap cooling-off）— 合規效果弱

### 事項 3 — 計價引擎 GUI

- **決議**：選項 1 — 維持 SQL config + audit log
- **理由**：規則由 DBA 透過 SQL + change_request 維護。業主認定規則改動
  頻率低 + DBA 走 change_request 流程已足夠，不開 GUI 接受業務操作門檻。
- **拒絕選項**：
  - 選項 2（最小 GUI ~10 天）— 投資回報不足
  - 選項 3（全功能編輯器 ~30 天）— scope creep 風險高

## Consequences

### Positive

- WBS 推進 98.5% → **98.7%**（Flow 6 / Flow 13 EX5 + Phase 7 收 100%）
- 不需 web dev 投入 ~10-30 天於計價 GUI
- 不需 backend / web 重做 recon 雙簽 UX
- 既有 audit_log + change_request 機制延續為合規補強

### Negative

- **合規風險（事項 2）**：未來若內審或客戶要求嚴格 Sox-like 雙簽，需開新 CR
  重啟決議
- **業務門檻（事項 3）**：計價規則變動仍需 DBA + change_request 工單，
  業務無法即時自助調整

### Neutral

- 兩項皆標 `status: deferred-accepted` — 不是 reject，是「現階段不做但
  保留未來重啟空間」
- 未來若條件變化（規模 / 合規要求 / 業務動因）可開新 ADR superseded 本決議

## Compliance Audit Trail

- 對應文件：`docs/_ops/wbs-100-closeout-plan.md` §2.2 + §2.3 已標
  deferred-accepted + 業主決議日期
- HTML 視覺化：`pending-business-decisions-2026-06-06.html` 已標 ✅ 業主已決
- WBS 反映：`web/docs/system-completion-status.md` 從 98.5% → 98.7%
- 既有 audit trail 持續運作：
  - `saas.config_audit` table — pricing rule change_request audit
  - `approval_chain` JSONB — recon dual-sign actor + timestamp

## See also

- ADR-0046 — Pricing rules CRUD + change_request 審計（現行機制依據）
- ADR-0102 — Cancellation audit_event_id 必填（audit_log 合規範式）
- `docs/_ops/wbs-100-closeout-plan.md` §2 — 業主裁決區段
- `pending-business-decisions-2026-06-06.html` — 業主一頁 review HTML
