---
id: CR-0013
title: "FR-0022 消費者端工單追蹤 — LINE rich menu 缺口 + spec/code 衝突裁決 + draft → active 路徑"
status: open-awaiting-decisions
decided: null
tier: 4-exploration
owner: HYBRID
created: 2026-06-04
target-release: 北極星條件 (1) draft FRs 4 → 3（與 CR-0011/0012 並列）
product-version: null
supersedes: null
superseded-by: null
related:
  - docs/analysis/fr/FR-0022-consumer-tracking.md
  - docs/architecture/adr/ADR-0015-pm-alignment-q3.md
  - docs/_audit/CR-0010-fr-0019-promote-to-active.md
  - api/routers/consumer_v2.py
  - api/services/public_token.py
  - web/src/app/track/[token]/page.tsx
  - agent/app.py
---

# CR-0013 — FR-0022 消費者端工單追蹤 CIA

> **Tier**: 4-exploration → Change Impact Analysis
> **Mandated by**: `.claude/rules/change-governance.md` + CR-0010 HD-03=a 「同步開 CR-0011~0014 審查其他 4 draft FR」
> **Triggered by**: MISSION 北極星 (1) draft FR = 0；FR-0022 為 4 剩餘 draft FR 第 3 件，**Web 路徑已實作但 LINE rich menu 路徑未動 + 1 個 spec/code 衝突**

---

## 1. Change Statement

**As-is**：
- `FR-0022` `status: draft`，`blocked_by: Q3=C  # Web token spec`
- **Q3 已經有 ADR**：`ADR-0015` (PM-Q3 消費者端追蹤入口) `status: accepted` — blocked_by 為 stale
- **Web 路徑已實作**：
  * `api/routers/consumer_v2.py:80 GET /consumer/work-orders/{trackingToken}` ✅
  * `web/src/app/track/[token]/page.tsx` ✅（per code comment「已切換至 /consumer/work-orders/{token}（spec M16 對齊）」）
  * `api/services/public_token.py` 提供 token 解析（HMAC 或 JWT 機制）
- **LINE 路徑未實作**：
  * 無 rich menu 設定（grep `LINE_RICHMENU` / `richmenu` 全空）
  * 無「查進度」專屬 postback handler（agent/app.py 只有 F2 改期 RSVP `_handle_reschedule_postback`）
  * 客戶在 LINE 發訊息「查進度」會走 ReAct agent 自然語言流，但**沒有 dedicated quick-action UX**
- **1 個 spec/code 衝突**：
  * FR-0022 §1.2 A1: 「Web token mismatch → 401 unauthorized」
  * `consumer_v2.py:63` 註解: 「驗證 consumer tracking token；**失敗一律 404，不洩露原因**」
  * Spec 401 vs code 404 不一致，下游 UX/log/alert 策略可能受影響
- BR-M16-NN 3 條未編號

**To-be**：
- `status: draft → active`（FR-0022 frontmatter）+ 移除 stale `blocked_by: Q3=C`
- 補對應 ADR：`ADR-0109`（暫定）— Consumer Tracking LINE rich menu 入口決策 + 多單顯示策略 + binding 機制 + Web token 401 vs 404 統一
- BR-M16-NN 群組落實際編號（`BR-M16-001~003`）
- 依 HD-01 決定是否補 LINE rich menu 實作（另開 BUILD CR）
- spec FR-0022 §1.2 A1 與 code consumer_v2 對齊（依 HD-05 裁決）

**Driver**：
- 北極星條件 (1) 4 → 3 第 3 路徑（與 CR-0011/0012 並列）
- FR-0022 可能是「準完工 status flip」候選（類似 FR-0019 經 CR-0010 promote 模式），Web 已 100%，LINE 端視 HD-01 裁決而定
- 解 spec/code 衝突（401 vs 404）— 違 governance rule 不允許「腦補合理版本」

---

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| `BF-CT-001`（Web token 查工單）| Existing | 已實作；本 CR 補正典化（spec 401 vs code 404 裁決後寫入 FR）|
| `BF-CT-002`（LINE rich menu tap 查進度）| **New** | 視 HD-01 = (a)/(c) 決定是否實作 |
| `BF-CT-003`（LINE 自然語言查詢）| Existing | ReAct agent 既有；HD-01=(b)/(c) 認列為 FR-0022 LINE 路徑實作 |
| `SF-CT-001`（多單顯示策略）| **New** | HD-02 決定 |
| `SF-CT-002`（LINE binding 自動 vs 主動）| **New** | HD-03 決定 |

---

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| `FR-0022` | Status flip + 衝突解 | draft → active；§1.2 A1 401 ↔ code 404 對齊（per HD-05）|
| `BR-M16-001`（Web token TTL）| **New 編號** | 24h vs 7day vs infinite per HD-04 |
| `BR-M16-002`（LINE 入口策略）| **New 編號** | rich menu / ReAct / 雙路 per HD-01 |
| `BR-M16-003`（多單顯示策略）| **New 編號** | per HD-02 |
| `NFR-CT-001`（Web token 查詢 p95 < 200ms）| **New** | 簡單 GET，現有 endpoint 已達 |
| `ADR-0015` | Referenced | PM-Q3 入口 accepted；本 CR ADR-0109 為 implementation 級補完，不 supersede |

---

## 4. Affected API

| API ID | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| `API-CT-V2-WO-BY-TOKEN` | `GET /consumer/work-orders/{trackingToken}` | Existing | No | 已實作；本 CR 補 401 vs 404 裁決後若需改 401 則為 breaking |
| `API-CT-V2-LIST-BY-LINE` | `GET /consumer/work-orders?line_user_id=...` | **New (conditional)** | — | 視 HD-02 多單顯示策略；rich menu 需要時新增 |
| `API-CT-WEBHOOK-LINE-POSTBACK` | （agent/app.py 內部 handler）| **New (conditional)** | — | HD-01=(a)/(c) 時新增「查進度」postback 解析；走既有 LINE webhook 結構 |
| `API-CT-V2-BIND-LINE` | `POST /consumer/bindings:create-line` | **New (conditional)** | — | HD-03=(b)/(c) 時新增主動綁定流程 |

---

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| 既有 `consumer_tracking_tokens`（若存在）| Touched | 視 HD-04 TTL 調整；若改 7day 需 backfill 評估 |
| `line_bindings`（**新表，依 HD-03**）| New (conditional) | `(id, tenant_id, customer_id, line_user_id, bound_at, bind_method enum 'auto'/'manual')` — HD-03=(a) auto only 則沿用既有 customer.line_user_id 不新增表 |
| `consumer_tracking_events` (audit)（**新表 optional**）| New (conditional) | 對應 `emits_events: ConsumerTrackingOpened` 之 audit 紀錄；若 M17 audit 既有支援可沿用 |
| `customers.line_user_id` | Existing | 已存在於 schema |

---

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| `TC-CT-001`（happy Web token）| Existing | 既有 e2e 已覆蓋 |
| `TC-CT-002`（token expired）| **New** | AC-03，HD-04 TTL 決定後寫死 |
| `TC-CT-003`（token tampered）| Update | AC-04，依 HD-05 裁決 401 or 404 |
| `TC-CT-004`（LINE rich menu tap）| **New (conditional)** | HD-01=(a)/(c) 時新增 e2e |
| `TC-CT-005`（LINE 自然語言查詢經 ReAct）| **New** | HD-01=(b)/(c) 時新增 agent integration test |
| `TC-CT-006`（多單顯示）| **New (conditional)** | HD-02 決定後寫對應 case |
| `TC-CT-007`（LINE binding 流）| **New (conditional)** | HD-03=(b)/(c) 時新增 |
| `TC-CT-XT-001`（cross-tenant token isolation）| **New** | 跨 tenant 用 trackingToken 必 fail |

**Coverage delta**：+5~7 新 TC（依 HD-01/02/03 conditional 而定）

---

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| Module boundary | Unchanged | M16 Comms 既有；agent 端維持 LINE webhook 統一入口 |
| New ADR? | **Yes** | `ADR-0109` 暫定 — HD-01~05 outcomes |
| External integration | LINE Messaging API rich menu config | HD-01=(a)/(c) 時新增 ops 任務（LINE Developer Console + setRichMenu API call） |
| Realtime | Touched (low) | `/realtime/consumer/{token}` 暫不必（pull 即可，wo status 更新頻率低）|
| Security | Touched | HD-05 401 vs 404 影響滲透測試與 audit 行為 |

---

## 8. Human Decisions Required

🛑 **CIA blocks code changes until every row here has a recorded decision.**

| # | Question | Options | Owner | Status | Decision |
|---|---|---|---|---|---|
| **HD-01** | LINE 端「查進度」入口策略 | (a) 強制 LINE rich menu + 專屬 postback handler（quick-action UX）<br>(b) 接受 ReAct 自然語言查詢即為 LINE 路徑「實作」（客戶說「查進度」走 agent → 內部 tool 查 wo）<br>(c) 雙路並存（rich menu 為主，ReAct 為輔）<br>(d) 只做 Web 路徑，FR-0022 §1.1 step 1 LINE 部分降為 optional / Phase II | Product | **pending** | — |
| **HD-02** | 多單顯示策略（一個 LINE 用戶綁多個活躍 wo）| (a) 顯示最新 1 筆<br>(b) list 全部活躍 wo 讓客戶點選<br>(c) 讓客戶輸入 wo_id 過濾 | Product | **pending** | — |
| **HD-03** | LINE binding 機制 | (a) 自動綁（wo 建立時若 customer 有 line_user_id 自動關聯，沿用 customers.line_user_id 欄位）<br>(b) 客戶主動綁（rich menu「綁定」流程 + 新表 line_bindings）<br>(c) 雙路：auto 為主，使用者可主動補綁 | Product + Backend | **pending** | — |
| **HD-04** | Web token TTL | (a) 24h（FR-0022 §1.2 A2 預設）<br>(b) 7 day（UX 較友善）<br>(c) 30 day<br>(d) infinite（風險高，需審慎） | Security + Product | **pending** | — |
| **HD-05** | Web token tampered / expired 行為（**spec/code 衝突解**）| (a) 401（FR-0022 §1.2 A1 spec 寫法；明確告知 token 問題）<br>(b) 404（code consumer_v2.py:63「不洩露原因」策略；防 enumeration 攻擊）<br>(c) 400（明確 client-side error 但不指明原因）<br>**注意：選 (a) 需修 code，選 (b) 需修 FR spec** | Security + Product | **pending** | — |

---

## 9. Suggested Implementation Order

§8 業主裁決後，依以下順序實作：

1. **Decisions** → 寫 `ADR-0109` 記錄 §8 HD-01~05 outcomes；frontmatter `related: ADR-0015`（PM 級 vs implementation 級分層，不 supersede）
2. **BR 編號** → FR-0022 內 BR-M16-NN 改 `BR-M16-001~003`
3. **Spec/Code 衝突解**：依 HD-05
   - 選 (a) 401 → 修 `consumer_v2.py:_verify_consumer_token` 回 401 + docstring 同步
   - 選 (b) 404 → 修 FR-0022 §1.2 A1 改為 404 + 補「防 enumeration」rationale
4. **FR-0022 status flip** → draft → active；移除 stale `blocked_by: Q3=C`；補 ADR-0109 至 `related_adrs`
5. **LINE 路徑實作**（視 HD-01 conditional）：
   - HD-01=(a)/(c) → 另開 BUILD CR：rich menu setRichMenu 部署腳本 + postback handler + 對應 ops
   - HD-01=(b) → 認列 ReAct 自然語言流，不需 code 變更，補測試 TC-CT-005
   - HD-01=(d) → 純 Web 路徑 active，FR §1.1 step 1 LINE 條目改 optional
6. **多單顯示 + binding**（視 HD-02/03 conditional）：
   - 多 endpoint / schema 變更時，本 step 移至 BUILD CR
7. **TM-0000 更新** → 補 FR-0022 ↔ ADR-0109 ↔ API-CT-V2-* ↔ TC-CT-* row
8. **CR-0013 status flip** → open-awaiting-decisions → decided
9. **system-completion-status.md** → draft FR 計數推進；Flow 5/F-022 行更新

---

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| HD-05 選 (a) 401 後增 enumeration 攻擊風險 | Medium | Medium | 加 rate limit + token 結構含 HMAC 即不可預測；現有 public_token.py 已具備 |
| LINE rich menu config / 部署人為錯 | Medium | Low | HD-01=(a)/(c) 時補 ops runbook + 設定 idempotent 腳本 |
| HD-02 多單策略選錯導致客戶體驗差 | Low | Medium | Phase 8 UAT 客戶實測再調整；A/B test optional |
| HD-04 TTL 過長導致 token 外洩風險上升 | Medium | High | 24h 為安全預設；若選 (b) 7day 須補審計 |
| 自動 LINE binding 隱私同意 | Low | High（合規）| HD-03=(a) 自動綁須評估 PDPA / GDPR 是否需明示同意；若要保守則 HD-03=(b) 主動綁 |

**Rollback plan**：
- Spec 衝突解 (HD-05) 為單向變更（spec or code），revert 為 1-line 修正
- LINE rich menu 部署有 Console 端 + code 端兩處，rollback 需 setRichMenu(default) + revert code
- HD-04 TTL 調整 → config 改即可，無 schema impact
- ADR-0109 / FR-0022 status 改回 draft + 標 reverted 註解（append-only）

---

## 11. Out of Scope

- **LINE rich menu 視覺設計圖** → UX team 提，不在本 CR
- **多語言 rich menu** → V2 議題
- **客戶在 LINE 內 inline 改期 / 取消**（已由 Flow 11 F2 postback handler 處理）→ 不重複
- **Scope change consumer 流**（已有 `/consumer/scope-changes/{token}` v2）→ 不重複
- **FR-0044 customer.line_user_id schema 擴充** → 既有 customers 表已含

---

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product | | | |
| Architect | | | |
| Backend Lead | | | |
| Frontend Lead | | | |
| Security | | | |
| Compliance / Legal | | | |
| QA Lead | | | |

---

## §A 取證附錄（為何此 CR 是必要）

```bash
# 1. FR-0022 仍 draft + Q3 blocker（但 ADR-0015 已 accepted → blocked_by stale）
$ grep -E "^status:|^blocked_by:" docs/analysis/fr/FR-0022-consumer-tracking.md
status: draft
blocked_by:
  - Q3=C  # Web token spec
$ grep "^status:" docs/architecture/adr/ADR-0015-pm-alignment-q3.md
status: accepted

# 2. Web 路徑已實作（v2 endpoint + web page 都對齊 spec M16）
$ grep -n "@router\.\|consumer.work-orders" api/routers/consumer_v2.py | head -3
80:    "/consumer/work-orders/{trackingToken}",
$ head -20 web/src/app/track/[token]/page.tsx | grep "consumer/work-orders"
# v2 spec-aligned path（CR-0002-α M16 Consumer）: /consumer/work-orders/{token}

# 3. LINE rich menu 未實作（grep richmenu/LINE_RICHMENU 全空）
$ grep -rn "LINE_RICHMENU\|richmenu\|RICH_MENU" agent/ api/ scripts/ 2>/dev/null
（空）

# 4. agent webhook 只有 F2 改期 postback，無「查進度」postback handler
$ grep -n "postback" agent/app.py | head -3
340:# ── F2 客戶改期 RSVP postback handler ──
343:async def _handle_reschedule_postback(event):
（無 _handle_tracking_postback 或類似）

# 5. spec/code 衝突取證
$ grep -A2 "A1. Web token mismatch" docs/analysis/fr/FR-0022-consumer-tracking.md
A1. Web token mismatch:
    A1.1 401 unauthorized
$ grep -n "404\|不洩露" api/routers/consumer_v2.py | head -3
63:    """驗證 consumer tracking token；失敗一律 404，不洩露原因。"""
```

**結論**：FR-0022 為「準完工 status flip 候選」（類似 FR-0019 經 CR-0010 promote 模式），Web 路徑 100% 已實作；LINE rich menu 為 0%（視 HD-01 是否強制）。本 CR 列 **5 HD**，HD-05 解 spec/code 401 vs 404 衝突為 critical 治理事項，必須裁決而非腦補。
