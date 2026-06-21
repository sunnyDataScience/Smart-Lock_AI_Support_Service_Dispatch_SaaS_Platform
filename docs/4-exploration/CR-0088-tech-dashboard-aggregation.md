---
id: CR-0088
title: "技師端儀表板 P1 聚合端點（即時收入 / 月度快照 KPI）"
status: draft
tier: 4-exploration
owner: HYBRID
created: 2026-06-21
target-release: dev_new_arch / next sprint
product-version: null
supersedes: null
superseded-by: null
---

# CR-0088: 技師端儀表板 P1 聚合端點（即時收入 / 月度快照 KPI）

> **Tier**: 4-exploration → Change Impact Analysis
> **Mandated by**: `.claude/rules/change-governance.md`（觸發面向：API contract / Domain model / Test plan）
> **背景**: 接續 `feat(web): 技師端響應式版型 + 登入後儀表板決策屏`（已實作 P0，分支 `feat/tech-portal-dashboard`）。P0 儀表板的收入膠囊與案量區僅用現成端點，部分數字為「本月已結淨額」近似；本 CR 規劃 P1 即時/聚合數字所需的後端。

---

## 1. Change Statement

**As-is**: 技師端 `/home` 決策屏 P0 已上線，收入膠囊顯示「本月已結淨額」（`tech-statements` 當月 approved/paid 之 `net_amount`）；案量熱力圖用 `workload-heatmap`；無「今日/本週即時收入」「本月毛額（含未結預估）」「完成率」「租戶內排名」等即時聚合數字。

**To-be**: 新增技師自助聚合端點，讓決策屏顯示即時收入累計（今日/本週）與月度快照 KPI（毛額含未結預估、完成率、租戶內排名），提升「現在值不值得開工」的決策資訊密度。

**Driver**: 業主於逐頁測試時要求「登入後先看儀表板資訊」；研究（DoorDash/Uber/ServiceTitan）顯示即時收入與目標進度是接單者上線決策的核心訊號。P0 已交付決策屏骨架，P1 補足即時數字。

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| `UF-技師-home` | Modified | 決策屏收入膠囊由「本月已結淨額」升級為「今日/本週即時累計」；新增月度快照 KPI 區（漸進揭露） |
| `SF-技師-earnings-agg` | New | 技師即時收入/績效聚合規則（今日/本週完工預估報酬加總、完成率、排名） |

> 註：本 CR 不改變主流程（登入→/home 已於 P0 定案），僅豐富 /home 顯示資料。

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| `FR-技師-dashboard-summary` | New | 技師儀表板聚合：今日/本週收入、本月毛額（含未結）、完成率、租戶內排名、今日新單數 |
| `NFR-perf` | New | 聚合端點需 p95 < 300ms（單技師查詢，加索引或快取）；避免每次全表掃描 |

## 4. Affected API

| API ID | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| `API-tech-dashboard` | `GET /api/v1/technicians/me/dashboard-summary` | **New** | No | 單一聚合端點，回 `{today_earnings, week_earnings, month_gross_est, completion_rate_pct, rank_in_tenant, today_new_orders, computed_at}`；`_technician_only` 守衛、self-scoped |
| `API-workload-self` | `GET /api/v1/technicians/{id}/workload-heatmap` | Harden | No | 既有端點目前 `require_tenant` 未鎖 self（任何同租戶人可查他人 workload，IDOR）；建議加 self-guard 或新增 `/me/workload-heatmap`（見 §8-6） |

> 口徑說明：`today_earnings/week_earnings` 預設取「該期間內 `status=completed` 工單之 `estimated_reward` 加總」（預估，非實收）；是否改採實收淨額見 §8-2。

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `work_orders` | 讀取既有 `estimated_reward / status / created_at / updated_at` 聚合 | **無需 migration**（核心 KPI 用現有欄位可算） |
| `work_orders`（選用） | 若要「平均到場時間」「SLA 倒數」需新增 `en_route_at / arrived_at / sla_deadline` 時間戳 | 需 online migration（見 §8-5，預設不做） |
| `work_orders`（選用） | 若要「近期客戶評價」需 `customer_feedback / customer_rating` | 需 migration（預設不做，另開 CR） |
| 索引 | 建議 `idx_work_orders_tech_status_time (technician_id, status, updated_at)` 支援聚合 | online，CONCURRENTLY |

State machine impact: 無（純讀取聚合）。

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| `TC-dashboard-summary-happy` | New | 技師有今日完工單 → today_earnings 正確加總 |
| `TC-dashboard-summary-empty` | New | 新技師無工單 → 全回 0 / null，不 500 |
| `TC-dashboard-summary-rank` | New | 多技師同租戶 → rank_in_tenant 排序正確 |
| `TC-dashboard-summary-authz` | New | 技師 A 無法取得技師 B 的 summary（self-scoped） |
| `TC-workload-self-guard` | New | workload-heatmap self-guard（若採 §8-6 方案 a/b） |

Coverage delta: +4~5 TCs（agent/api 後端 pytest）。

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| Module boundary | Unchanged | 留在 technicians 服務內（新增 service 函式 + router） |
| New ADR? | 否（除非排名/口徑成為產品政策） | 若排名對技師開放成為長期政策，建議補一則 ADR |
| 快取 | 評估 | 即時收入可短 TTL 快取（如 30~60s）平衡即時性與負載 |
| External integration | 無 | 純內部聚合 |

## 8. Human Decisions Required

🛑 **CIA 在每列有決策前，阻擋 P1 後端實作。**

| # | 問題 | 選項 | 負責 | 狀態 | 決策 |
|---|---|---|---|---|---|
| 1 | 這輪要做哪些 P1？ | (a) 只做即時收入(今日/本週) (b) 即時收入 + 月度快照KPI(毛額/完成率/排名)〔推薦〕 (c) 全做含 SLA/評價(需 work_orders migration) | 業主 | open | — |
| 2 | 收入口徑 | (a) 完工工單 `estimated_reward` 加總（預估，立即可算）〔推薦先用〕 (b) 實收淨額（需對齊金流/結算，較重） | 業主/財務 | open | — |
| 3 | 「租戶內排名」是否對技師開放？ | (a) 開放（激勵） (b) 不開放（避免考核壓力，研究指部分系統隱藏）〔保守推薦〕 (c) 由後台開關控制 | 業主 | open | — |
| 4 | 端點形狀 | (a) 單一 `/me/dashboard-summary` 一次回所有數字〔推薦〕 (b) 拆多個小端點 | 架構 | open | — |
| 5 | 是否納入「平均到場時間 / SLA 倒數」？（需 work_orders 新增時間戳欄位 + migration） | (a) 本 CR 納入 (b) 不做，另開 CR〔推薦〕 | 業主 | open | — |
| 6 | workload-heatmap IDOR（`require_tenant` 未鎖 self，任何同租戶人可查他人 workload） | (a) 加 self-guard 到既有端點 (b) 新增 `/me/workload-heatmap` self-scoped (c) 暫不處理（記安全債）〔建議 a 或 b〕 | 架構/安全 | open | — |

## 9. Suggested Implementation Order

§8 解決後，依序：

1. **Decisions** → 若排名/口徑成政策，補 ADR
2. **Schema**（僅若 §8-1=c 或 §8-5=a）→ work_orders 加時間戳/評價欄位 + 索引 migration
3. **Service** → `technician_service.get_my_dashboard_summary(tenant_id, user_id→technician_id)` 聚合查詢
4. **API** → `GET /api/v1/technicians/me/dashboard-summary`（`_technician_only`）+ openapi schema
5. **API harden** → 依 §8-6 處理 workload-heatmap 授權
6. **Tests** → 加 §6 的 TC（pytest）
7. **前端** → 升級 `StatusEarningsPill`（今日/本週）+ 新增 `MonthlySnapshot` widget；重生 `web/src/types/api.generated.ts`
8. **Traceability** → 更新 traceability matrix + CHANGELOG

## 10. Risks & Rollback

| Risk | 可能性 | 影響 | 緩解 |
|---|---|---|---|
| 聚合查詢全表掃描拖慢 | 中 | 中 | 加 `(technician_id, status, updated_at)` 索引 + 短 TTL 快取 |
| 預估報酬 ≠ 實收，技師誤解收入 | 中 | 中 | UI 明確標「預估」口徑；§8-2 決定是否切實收 |
| 排名造成技師壓力/客訴 | 低~中 | 中 | §8-3 預設保守不開放 / 後台可關 |
| workload IDOR 未修持續暴露 | 中 | 中（隱私） | §8-6 一併處理 |

**Rollback**: 新端點為純新增、前端 widget 可 feature-flag 或直接回退；無 schema 變更時（§8-1=a/b）零 migration、純加法、可即時 revert。

## 11. Out of Scope

- 任務/獎金（Quest）規則引擎與 `/me/quests`（P2，另開 CR）
- 待派熱區地圖 `/pool/hotspots` 聚合（P2，另開 CR）
- 客戶評價明細頁與通知模板（另開 CR）
- 金流實收對帳重構（依 §8-2 若選實收，另評估）

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product / 業主 | | | |
| Architect | | | |
| Engineering Lead | | | |
| QA Lead | | | |
