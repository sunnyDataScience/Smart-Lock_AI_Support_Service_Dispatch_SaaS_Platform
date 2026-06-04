---
id: ADR-0105
title: Door-check + Reschedule v2 contract 設計（CR-0007 §8 業主裁決紀錄）
status: Accepted
date: 2026-06-04
deciders: [sunny@funngo.ai (2026-06-04 value decision)]
related:
  - docs/_audit/CR-0007-door-check-reschedule-contract.md
  - docs/_audit/CR-0003-full-cutover-wbs.md
  - SQL/migrations/014-reschedule-proposals.sql
  - api/routers/work_orders_v2.py
  - api/routers/work_orders_ops_v2.py
source_trade_off: CR-0007 §1 As-is/To-be + §10 風險回退表
eternal_transient: Eternal (door-check 強制 arrival 前置原則) / Transient (slot 上限 1-3、SLA 24h、proposed_slots 表結構 — Phase II 可配置)
---

# ADR-0105 — Door-check + Reschedule v2 contract 設計

## Context

CR-0007 取證：v1/v2 在 work-orders subflow 兩條路徑語意不一致：
- v1 `POST /api/v1/work-orders/{id}/door-check` 收完整門檢提交 vs v2 `/onsite/arrival` 只收 GPS 簽到
- v1 `POST /api/v1/work-orders/{id}/reschedule` 收多時段提案 vs v2 `/reschedule-request` 只收單方變更

兩者無 drop-in，需業主裁設計方向才能補 v2 endpoint 並遷 caller。

## Decisions（2026-06-04 業主拍）

| HD | Question | Decision |
|---|---|---|
| HD-01 | door-check 是否強制 arrival 前置 | **(a) 強制**。無 arrived_at 記錄 → 409 STATE_CONFLICT |
| HD-02 | reschedule proposed_slots 數量上限 | **(a) 1-3**。避免客戶選擇疲勞 + LINE Flex 簡潔 |
| HD-03 | 客戶 RSVP SLA | **(a) 24h**。與 v1 一致；cron 偵測 `sla_deadline < NOW()` 標 expired |
| HD-04 | reschedule_proposals DB 結構 | **(a) 獨立表 saas.reschedule_proposal**。清楚 lineage + 未來統計快 |
| HD-05 | door-check checklist 結構 | **(a) freeform jsonb**。BE 不驗證內部結構，frontend 決定樣貌 |

## Consequences

### Eternal（永久原則，不可逆）
- door-check action 必須在 arrival 之後（狀態機硬性）
- reschedule_proposals 有獨立 lineage 表
- checklist payload 不在 BE 層做 schema 驗證

### Transient（可配置 / Phase II 可調）
- slot 上限 1-3 → 未來如客戶研究顯示需要 5 個，調整 CHECK constraint
- SLA 24h → Phase II M18 config 可 per-tenant 覆寫
- freeform jsonb → 未來如要 audit 嚴格化，可加 schema validator middleware

## Implementation

1. SQL/migrations/014-reschedule-proposals.sql — saas.reschedule_proposal 表 + index
2. api/services/work_order_service.py:
   - `submit_door_check_v2(...)`: 查 work_order_events WHERE event_type='arrival'，不存在 raise 409
   - `propose_reschedule(...)`: INSERT saas.reschedule_proposal + 推 LINE Flex（既有 line_push_service）
3. api/routers/work_orders_v2.py: 補 `POST /tenants/{tid}/work-orders/{id}/door-check`
4. api/routers/work_orders_ops_v2.py: 補 `POST /tenants/{tid}/work-orders/{id}/reschedule:propose`
5. web:
   - my-orders/[id]/door-check/page.tsx 改 v2 path
   - work-orders/[id]/page.tsx reschedule handler 改打 :propose

## Risks Acknowledged

- 強制 arrival 前置可能增加 UX 摩擦（技師趕時可能跳過 GPS）→ UI 必須清楚提示「先簽到」
- slot 上限 1-3 比 v1 嚴格 → 既有訓練文件 / SOP 需更新「最多提 3 個時段」
- 24h SLA cron 需獨立 job（本 CR 不含；列入 Phase 5-7 收尾 backlog）

## References

- CR-0007 §1-§12（取證 + HD 來源 + 實作順序）
- SQL/migrations/011 schema 細節
- FR-0006 / FR-0009 / FR-0011-RSVP（spec 對齊）
