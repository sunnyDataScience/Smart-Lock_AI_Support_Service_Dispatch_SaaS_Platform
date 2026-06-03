---
id: CR-0007
title: "Door-check + Reschedule v2 contract 重設計（解 P3 收尾 2 caller，FR-0006/FR-0009 對齊）"
status: awaiting-owner-decision
tier: 4-exploration
owner: HYBRID
created: 2026-06-04
target-release: P3 track-A 收尾 wave-4
product-version: null
supersedes: null
superseded-by: null
related:
  - docs/_audit/CR-0003-full-cutover-wbs.md
  - docs/_audit/CR-0005-kb-v2-expand-and-shape.md
  - api/routers/work_orders_v2.py
  - api/routers/work_orders_ops_v2.py
---

# CR-0007 — Door-check + Reschedule v2 contract redesign

> **Tier**: 4-exploration → CIA  
> **Mandated by**: `.claude/rules/change-governance.md`  
> **Triggered by**: P3 收尾 wave-1（a7a06133）取證 2 個 caller 因 v1/v2 contract 不一致無 drop-in 遷

---

## 1. Change Statement

**As-is**：
- **Door-check**：v1 `POST /api/v1/work-orders/{id}/door-check` 收 `{checklist, photos_before[], photos_after[], notes}`（門面完整檢核提交）；v2 `POST /tenants/{tid}/work-orders/{id}/onsite/arrival` 只收 `{arrived_at, gps}`（到場事件）。**語意不同**：v1 是門檢提交、v2 是 GPS 簽到。
- **Reschedule**：v1 `POST /api/v1/work-orders/{id}/reschedule` 收 `{proposed_slots[], message_to_customer, send_via}`（多時段提案給客戶選）；v2 `POST /tenants/{tid}/work-orders/{id}/reschedule-request` 收 `{new_scheduled_at, reason}`（單方直接改約）。**語意不同**：v1 是多時段提案流、v2 是單方變更。

**To-be**：
- Door-check：v2 補 `POST /tenants/{tid}/work-orders/{id}/door-check`（完整門檢提交）+ 保留現有 `/onsite/arrival`（GPS 簽到）為獨立 sub-action
- Reschedule：v2 補 `POST /tenants/{tid}/work-orders/{id}/reschedule:propose`（多時段提案，對應 FR-0009 客戶不在場 + RSVP）+ 保留 `/reschedule-request`（單方變更）

**Driver**：
- MISSION.md 北極星 (3) v1 caller 清零 — door-check + reschedule 2 caller 阻塞
- FR-0006「技師到場 + 門面檢核 evidence」與 FR-0009「客戶不在場改約」spec 要求並未被 v2 完整覆蓋
- 「P3-KEEP: legacy /reschedule（proposed_slots 多時段提案流）無 drop-in v2」(`work-orders/[id]/page.tsx:1072`) 是已知缺口

---

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| `BF-WO-006`（技師到場 + 門檢）| Modified | 拆解為兩 sub-action：到場簽到（GPS）+ 門檢提交（checklist + photos）|
| `BF-WO-008`（多時段改約提案）| New | reschedule:propose 對應 Flow 11 客戶不在場 RSVP 流（與既有 customer-confirm/reject 端點銜接）|
| `BF-WO-009`（單方改約）| Unchanged | 既有 reschedule-request 保留 |
| `SF-WO-010`（門檢 photos 媒體上傳）| Unchanged | 走 `media_v2` 既有 endpoint，本 CR 不動 |

---

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| `FR-0006`（技師到場 evidence）| Clarified | 拆分「到場簽到」與「門檢提交」為兩個離散 action（spec 原本綁在一起含糊）|
| `FR-0009`（完工送簽）| Referenced | door-check photos 對齊 spec 既有 ArrivalEvent + CompletionSubmit |
| `FR-0011-RSVP`（客戶不在場改約 RSVP）| Modified | reschedule:propose 是後端對應 endpoint |
| `NFR-WO-001`（door-check p95 < 500ms）| Unchanged | 既有效能預算 |

---

## 4. Affected API

| API ID | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| `API-WO-V2-DOOR-CHECK` | `POST /tenants/{tid}/work-orders/{id}/door-check` | **New** | — | 收 `{checklist, photos_before[], photos_after[], notes}`，呼叫既有 `record_door_check` service（v2 只是補 endpoint，service 已存在）|
| `API-WO-V2-ARRIVAL` | `POST /tenants/{tid}/work-orders/{id}/onsite/arrival` | Unchanged | No | 保留現狀，仍為 GPS 簽到 |
| `API-WO-V2-RESCHEDULE-PROPOSE` | `POST /tenants/{tid}/work-orders/{id}/reschedule:propose` | **New** | — | 收 `{proposed_slots[], message_to_customer, send_via}`，呼叫 `propose_reschedule_to_customer` service |
| `API-WO-V2-RESCHEDULE-REQUEST` | `POST /tenants/{tid}/work-orders/{id}/reschedule-request` | Unchanged | No | 既有單方變更保留 |
| `API-WO-V2-RESCHEDULE-APPROVE` | `POST /tenants/{tid}/work-orders/{id}/reschedule:approve` | Unchanged | No | 既有核准單方變更保留 |
| `API-WO-V1-DOOR-CHECK / RESCHEDULE`（legacy）| 廢棄 | **Yes（P4 統一刪）** | — | 不在本 CR scope |

---

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `work_order_events` | 既有 `door_check` event_type 沿用 | 無 migration |
| `work_order_events` | 既有 `reschedule_proposed` event_type 沿用 | 無 migration |
| `scope_change_proposals`（可能複用為 reschedule_proposals）| 評估是否新增 `reschedule_proposals` 表 | §8 HD-04 決策 |

**State machine impact**：work_order 狀態機不變（door-check 仍進 `in_progress`，reschedule:propose 仍進 `awaiting_customer_response` 子狀態）。

---

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| `TC-WO-DC-001`（v2 door-check happy path）| **New** | checklist + photos + notes 完整提交 |
| `TC-WO-DC-002`（v2 door-check 與 arrival 順序）| **New** | arrival → door-check 順序檢查；door-check 不需 arrival 前置（待 HD-01）|
| `TC-WO-RS-001`（v2 reschedule:propose 多時段）| **New** | 1-5 個 proposed_slots + LINE Flex RSVP 推送 |
| `TC-WO-RS-002`（客戶選時段後 happy path）| **New** | 與既有 customer-confirm 端點銜接 |
| `TC-WO-XT-001`（cross-tenant guard）| **New** | 跨 tenant 觸發 403 |

**Coverage delta**：+5 TC，`work_orders_v2.py` 從 ~60% → ~80%

---

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| Module boundary | Unchanged | work-orders bounded context 內部 |
| New ADR? | **Maybe** | 若 HD-01 拍「door-check 強制要 arrival 前置」需新 ADR 記狀態機限制 |
| External integration | LINE Flex | reschedule:propose 推 RSVP Flex Message，沿用既有 `line_push_service.push_to_work_order_customer` |
| WS publish | 既有 `_publish_state_change` | door-check 已有 `work_order.door_check_recorded` 事件；reschedule:propose 已有 `work_order.reschedule_proposed`；無新增 |

---

## 8. Human Decisions Required

🛑 **CIA blocks code changes until every row here has a recorded decision.**

| # | Question | Options | Owner | Status | Decision |
|---|---|---|---|---|---|
| **HD-01** | door-check 是否強制 arrival 前置？ | (a) 必須先 arrival 才能 door-check（狀態機限制）<br>(b) 不限定（任一可獨立呼叫）<br>(c) door-check 隱含 arrival（自動補寫 GPS=null）| Product | open | — |
| **HD-02** | reschedule:propose 的 proposed_slots 數量上限 | (a) 1-3（避免客戶選擇疲勞）<br>(b) 1-5（與 v1 相容）<br>(c) 1-10（最大彈性）| UX | open | — |
| **HD-03** | reschedule:propose 推 LINE 後 customer 回應 SLA | (a) 24h（與 v1 一致）<br>(b) 48h<br>(c) 客戶可設定 | Product | open | — |
| **HD-04** | reschedule_proposals 是否獨立 DB 表 | (a) 獨立表（清楚 lineage）<br>(b) 複用 scope_change_proposals 表（加 type 欄）<br>(c) 只存 work_order_events.payload（不另建表）| Architect | open | — |
| **HD-05** | door-check checklist 結構 | (a) freeform jsonb（彈性）<br>(b) 固定 schema（驗證強）<br>(c) tenant-configurable template（M18 config 整合）| Architect | open | — |

---

## 9. Suggested Implementation Order

§8 業主裁決後實作：

1. **Decisions** → `ADR-0105`（暫定）記錄 HD-01~05
2. **Schema migration**（若 HD-04 選 a/b）→ alembic：`reschedule_proposals` 表或 `scope_change_proposals.type` 欄
3. **Domain layer** → `work_order_service`：補 `submit_door_check_v2`、`propose_reschedule_v2`（包 LINE Flex）
4. **API layer** → `work_orders_v2.py` 補 2 endpoints + tenant-scoped + idempotency
5. **Tests** → TC-WO-DC-001/002 + TC-WO-RS-001/002 + TC-WO-XT-001
6. **UI 遷移** → `web/src/app/my-orders/[id]/door-check/page.tsx`（tech side）+ `web/src/app/work-orders/[id]/page.tsx`（admin reschedule propose）
7. **LINE Flex template** → reschedule RSVP Flex（slots radio 選擇器，banner 對齊 Flow 11）
8. **Traceability** → TM-0000 加 BF-WO-006~009 + API-WO-V2-* + TC-WO-* 對應 row
9. **CR-0003 §5 進度區** → wave-4 ✅ door-check + reschedule 2 caller 遷完

---

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| door-check + arrival 兩 sub-action UX 混淆 | Medium | Medium | HD-01 選 (a)（強制前置）+ 前端清楚標示「先簽到再門檢」|
| reschedule:propose LINE Flex template 跑不出來 | Low | High | 沿用 Flow 11 已驗證 customer-confirm Flex 模板，僅改 slot 渲染 |
| proposed_slots 衝突（與其他工單時段撞）| Medium | Low | 不在本 CR 處理；技師端 UI 提示，後端不強制驗 |
| HD-04 選獨立表後 v1 legacy 雙寫過渡期 | Low | Low | dev-phase 直接 cutover，無雙寫期 |

**Rollback plan**：API endpoints 為 new，無破壞性。Caller migration 逐檔 git revert。

---

## 11. Out of Scope

- **客戶端 RSVP UI 規格**（FR-0011 待 active）→ 獨立 CR
- **reschedule:propose 自動算可用時段**（與技師排班整合）→ 獨立 CR
- **legacy v1 door-check / reschedule router 刪除** → P4 cutover

---

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product | | | |
| Architect | | | |
| Engineering Lead | | | |
| UX | | | |
| QA Lead | | | |

---

## §A 取證附錄

```bash
# 2 個阻塞 caller：
$ grep -n "api/v1/work-orders.*door-check\|api/v1/work-orders.*reschedule" web/src \
    -r --include="*.tsx" 2>/dev/null
# →
# web/src/app/my-orders/[id]/door-check/page.tsx:161: `/api/v1/work-orders/.../door-check`
# web/src/app/work-orders/[id]/page.tsx:1076: `/api/v1/work-orders/.../reschedule`
```

```python
# v1 vs v2 semantic 不一致取證：
$ grep -A1 "record_door_check" api/services/work_order_service.py
# v1 door-check submit ≠ v2 onsite/arrival GPS sign-in
# v1 reschedule proposed_slots[] ≠ v2 reschedule-request single new_scheduled_at
```

---

> 🛑 **§8 業主裁決前不動 code / DB schema。** 預計裁決後工時 2-3 天。
