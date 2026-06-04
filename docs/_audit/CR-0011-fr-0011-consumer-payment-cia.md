---
id: CR-0011
title: "FR-0011 消費者付款 — 解 Q7 provider 選型 blocker + draft → active 路徑"
status: open-awaiting-decisions
decided: null
tier: 4-exploration
owner: HYBRID
created: 2026-06-04
target-release: 北極星條件 (1) draft FRs 4 → 3
product-version: null
supersedes: null
superseded-by: null
related:
  - docs/analysis/fr/FR-0011-consumer-payment.md
  - docs/architecture/adr/ADR-0019-pm-alignment-q7.md
  - docs/architecture/adr/ADR-VCH-001-platform-as-voucher-keeper.md
  - docs/architecture/adr/ADR-VCH-002-voucher-retention-7y.md
  - docs/_audit/CR-0010-fr-0019-promote-to-active.md
---

# CR-0011 — FR-0011 消費者付款 CIA

> **Tier**: 4-exploration → Change Impact Analysis
> **Mandated by**: `.claude/rules/change-governance.md` + CR-0010 HD-03=a「同步開 CR-0011~0014 審查其他 4 draft FR」
> **Triggered by**: MISSION 北極星 (1) draft FR = 0；FR-0011 為 4 剩餘 draft FR 之首（Q7=B provider 選型 blocker，最大金流風險）

---

## 1. Change Statement

**As-is**：
- `FR-0011` `status: draft`，`blocked_by: Q7=B  # provider 選型`
- D5 殼結構已寫齊（§1 Use Case + §1.1/§1.2 Main/Alt Flow + §2 G/W/T 6 AC + §3 Reference Map）
- ADR-0019（V1.0 金流範圍 / legacy_id PM-Q7）status: accepted（2026-05-07）；本 CR 解 Q7=B blocker 之延續
- code 端：M11 settlement 流（FR-0012 月結）已落地；**消費者直接付款（cash / Apple Pay / Line Pay）尚無 endpoint / service**
- 對應 BR-M11-NN 群組仍標 NN（未編號），表示細則未確認
- Workflow 觸發點：WO `completed` → invoice → 客戶選付款 → provider call → `paid` + emit `PaymentReceived` + `VoucherIssued`，**全鏈路缺實作**

**To-be**：
- `status: draft → active`（FR-0011 frontmatter）
- 對應 ADR 寫入：`ADR-0107`（暫定）— 消費者付款 provider 選型 + 三軌 fallback + dispute 介面
- BR-M11-NN 全群組落實際編號（`BR-M11-001~006`）
- M11 payment service + endpoint 建立（OOSCope of本 CR：只設計 contract + 留 stub，實作另開 BUILD CR）

**Driver**：
- 北極星條件 (1) 5 → 4 已由 CR-0010 達成（FR-0019 promote），FR-0011 是下一個可推進單位
- FR-0011 屬 V1.0 金流主流，未 active → MVP 流程缺最後一哩（WO 完成後付款）
- Phase 8 UAT 上線前必須補齊（否則客戶無法完成端到端體驗）

---

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| `BF-PAY-001`（V1.0 消費者付款主流）| **New** | WO completed → invoice → 客戶付款 → paid + voucher |
| `BF-PAY-002`（Line Pay → cash fallback）| **New** | Alt Flow A1 |
| `BF-PAY-003`（webhook idempotency）| **New** | Alt Flow A2 |
| `BF-PAY-004`（現金 dispute）| **New** | Alt Flow A3 |
| `BF-PAY-005`（< 1000 拒分期）| **New** | Alt Flow A4 |
| `SF-PAY-001`（高額 ≥ 50000 簽章）| **New** | §1.1 step 3 |

---

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| `FR-0011` | Status flip | draft → active |
| `BR-M11-001`（三軌 cash/ApplePay/LinePay）| **New 編號** | 取代 BR-M11-NN |
| `BR-M11-002`（< 1000 不可分期）| **New 編號** | 同上 |
| `BR-M11-003`（≥ 50000 強制簽章）| **New 編號** | 同上 |
| `BR-M11-004`（Line Pay webhook idempotency）| **New 編號** | 同上 |
| `BR-M11-005`（fallback 兩次嘗試 audit）| **New 編號** | 同上 |
| `BR-M11-006`（現金 dispute → disputes 表）| **New 編號** | 同上 |
| `NFR-PAY-001`（webhook p95 < 500ms）| **New** | 配合 provider SLA |
| `ADR-0019` | Referenced | V1.0 金流範圍 / PM-Q7 accepted；本 CR ADR-0107 為其 implementation-level 補完，不 supersede |

---

## 4. Affected API

| API ID | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| `API-PAY-V2-INTENT` | `POST /tenants/{tid}/work-orders/{id}/payment:intent` | **New** | — | 客戶選付款方式 → 建立 payment_intent（HD-01 決定支援哪些 method）|
| `API-PAY-V2-CONFIRM` | `POST /tenants/{tid}/work-orders/{id}/payment:confirm` | **New** | — | 技師確認收款（cash 路徑）或 provider callback（電子支付）|
| `API-PAY-V2-DISPUTE` | `POST /tenants/{tid}/work-orders/{id}/payment:dispute` | **New** | — | 24h 內回報金額不符；HD-04 決定觸發者（技師 / 客戶 / 雙）|
| `API-PAY-WEBHOOK-LINEPAY` | `POST /webhook/payments/line-pay` | **New** | — | Line Pay async confirm；idempotency_key 設計見 HD-06 |
| `API-PAY-WEBHOOK-APPLEPAY` | `POST /webhook/payments/apple-pay` | **New** | — | 視 HD-01 是否選 Apple Pay |
| `API-VOUCHER-V2-ISSUE` | （續用既有 `/tenants/{tid}/vouchers`）| Touched | — | 觸發點移到 payment:confirm；不改 contract |

---

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `payments`（**新表**）| New | `(id, tenant_id, work_order_id, method, amount, currency, status, provider_ref, idempotency_key, created_at, paid_at, dispute_id)`；status enum: pending/processing/paid/failed/disputed |
| `payment_attempts`（**新表**）| New | fallback audit 用：`(payment_id, attempt_no, method, status, provider_error, attempted_at)` — 對應 BR-M11-005 |
| `disputes` | Modified | 新增 `source` 枚舉值 `'payment'`（既有 'service' / 'quality' 沿用）|
| `vouchers` | Touched | `payment_id` FK（追溯付款）|
| `work_orders.payment_status` | Touched | enum 擴充 `disputed`（已有 pending/paid，缺 disputed） |

---

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| `TC-PAY-001`（happy Line Pay）| **New** | AC-01 |
| `TC-PAY-002`（≥ 50000 簽章）| **New** | AC-02 |
| `TC-PAY-003`（fallback cash）| **New** | AC-03 |
| `TC-PAY-004`（webhook idempotency）| **New** | AC-04 |
| `TC-PAY-005`（< 1000 拒分期）| **New** | AC-05 |
| `TC-PAY-006`（現金 dispute）| **New** | AC-06 |
| `TC-PAY-XT-001`（cross-tenant guard）| **New** | 跨 tenant payment:confirm 403 |
| `TC-PAY-WEBHOOK-AUTH-001`（webhook signature verify）| **New** | provider 簽章驗證（HD-07）|

**Coverage delta**：+8 新 TC；M11 payment 覆蓋率 0% → ~85%

---

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| Module boundary | New sub-module | `api/services/payment_service.py`（新）+ `api/providers/{line_pay,apple_pay}.py`（新介面層）|
| New ADR? | **Yes** | `ADR-0107` 記錄 §8 HD-01~07 outcomes（provider 選型 / fallback / dispute UX / 簽章機制 / webhook 設計）|
| External integration | Line Pay / Apple Pay | 新 vendor；HD-01 決定範圍 |
| Secrets | New | `LINE_PAY_CHANNEL_ID` / `LINE_PAY_CHANNEL_SECRET` / `APPLE_PAY_MERCHANT_ID` 等進 GCP Secret Manager |
| Realtime | Touched | `/realtime/payments/{wo_id}` 新頻道（payment_intent / paid / disputed 推送），HD 暫不開（CR-0011 OOSCope，移 BUILD CR）|
| ADR-0019 link | Referenced | ADR-0107 frontmatter `related: ADR-0019`；不 supersede（ADR-0019 為 PM 級決策，ADR-0107 為 implementation 級）|

---

## 8. Human Decisions Required

🛑 **CIA blocks code changes until every row here has a recorded decision.**

| # | Question | Options | Owner | Status | Decision |
|---|---|---|---|---|---|
| **HD-01** | Payment provider 選型範圍 | (a) Line Pay only（V1 簡化）<br>(b) Line Pay + Apple Pay（雙軌）<br>(c) Line Pay + Apple Pay + cash 三軌（per FR-0011 §1.1 原規劃）<br>(d) 加 街口 / Apple Pay / Google Pay 多軌 | Product + Finance | **pending** | — |
| **HD-02** | ≥ 50000 強制簽章機制 | (a) 紙本簽收照片 upload（媒體 v2 既有）<br>(b) 電子簽章 OTP（簡訊驗證碼）<br>(c) 電子簽章面板手繪簽名（canvas image）<br>(d) (a)+(b) 雙路 | Finance + Legal | **pending** | — |
| **HD-03** | Line Pay fallback 觸發 | (a) 自動 retry 1 次後 prompt 改現金<br>(b) 失敗立即 prompt 改現金<br>(c) 失敗讓技師手動切換<br>(d) 不做 fallback，純失敗回 invoice 重選 | Product | **pending** | — |
| **HD-04** | 現金 dispute 觸發介面 | (a) 技師端按鈕（24h 內）<br>(b) 客戶端 LINE Flex（回報金額不符）<br>(c) 雙端都可<br>(d) 僅 backend admin 介面 | Product | **pending** | — |
| **HD-05** | 7y voucher retention 實作（per ADR-VCH-002）| (a) postgres partitioning（年 partition + 老分區轉 cold tablespace）<br>(b) postgres + 7y 後遷 GCS Archive（外掛 service）<br>(c) 全程 postgres hot 表 + 索引 prune<br>(d) Phase II 再決 | Compliance + Infra | **pending** | — |
| **HD-06** | webhook idempotency_key 設計 | (a) 用 provider transaction_id 作為 key<br>(b) 自建 `{wo_id}:{attempt_no}` 格式 key<br>(c) provider key + 內部 key 雙鎖 | Backend | **pending** | — |
| **HD-07** | provider webhook 簽章驗證 | (a) provider SDK 內建驗證（依賴）<br>(b) 自建 HMAC + secret 驗證<br>(c) SDK + 自建雙保險 | Security | **pending** | — |
| **HD-08** | M12 月結 vs M11 即時付款的金流關係 | (a) FR-0011 = 客戶直付（即時），FR-0012 = 平台月結技師（延遲），各走獨立帳<br>(b) FR-0011 收進中介帳，FR-0012 月結對帳支付技師<br>(c) 由 platform 暫收 → 技師 settle 走 vouchers | Finance | **pending** | — |

---

## 9. Suggested Implementation Order

§8 業主裁決後，依以下順序實作（**本 CR 僅含 step 1-2，code 實作另開 BUILD CR**）：

1. **Decisions** → 寫 `ADR-0107` 記錄 §8 HD-01~08 outcomes；frontmatter `related: ADR-0019`（PM 級 vs implementation 級分層，不 supersede）
2. **BR 編號** → 把 FR-0011 內 BR-M11-NN 全群組改 `BR-M11-001~006`；補對應描述至 `docs/analysis/br/`（若尚無檔案目錄則用 inline）
3. **FR-0011 status flip** → draft → active；移除 `blocked_by: Q7=B`；補 ADR-0107 至 `related_adrs`
4. **TM-0000 更新** → 補 FR-0011 ↔ ADR-0107 ↔ API-PAY-V2-* ↔ TC-PAY-* row
5. **CR-0011 status flip** → open-awaiting-decisions → decided
6. **system-completion-status.md** → draft FR 4 → 3；新增「Phase II SaaS 金流」維度（或 Phase 5-7 內列 FR-0011 進度條）
7. **下一步另開 BUILD CR**（暫定 CR-0011-BUILD）→ payments / payment_attempts 表 migration + service 實作 + endpoints + webhooks + tests；前置 ClamAV 等外部整合 secret rotation 流程已就緒

---

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| HD-01 選多 provider → 工期暴增 | High | High | 階段化：V1 落 Line Pay only，Phase II 補 Apple Pay；本 CR §8 強烈建議 HD-01=(a) |
| Line Pay vendor 條款 review 拖延 | Medium | High | 提前送 Legal review；契約準備中可平行做 contract / mock |
| dispute 流量大時人力負擔 | Medium | Medium | 加自動分派規則 + alert SLA；Phase II AI 輔助 |
| voucher 7y 儲存成本（HD-05 估算）| Low | Medium | (a)/(b) 估算 → 預算 review；MVP 期較小 |
| webhook 重送風暴（provider 端 retry）| Medium | Medium | HD-06 idempotency_key 嚴格 + DB unique constraint |
| Phase II 改 provider 時 schema 不容 | Medium | High | `payments.method` 用 text + 應用層 enum（避免 PG enum migration 痛）|

**Rollback plan**：
- Schema migration 全為 additive（新表 payments / payment_attempts + columns）→ 可逆
- 上線後出問題 → kill switch（config flag `payments.enabled=false`）回退至「全交易 backend admin 手動 mark paid」
- ADR-0107 / FR-0011 status 改回 draft + 標 reverted 註解（不刪 ADR，append-only）

---

## 11. Out of Scope

- **payment_service / endpoints / webhooks 實作** → 另開 BUILD CR（CR-0011-BUILD 暫定）
- **退款流程**（FR-0014）→ 既有 refunds_v2 沿用
- **月結技師**（FR-0012）→ 另開 CR-0012（per CR-0010 HD-03=a 同步）
- **Phase II AP 流程**（FR-0012 月結延伸）→ CR-0012 範疇
- **發票 / 三聯式 / 電子發票串接** → 完全 OOSCope，待 Compliance 提
- **跨幣別 / 跨境付款** → V2 才議

---

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product | | | |
| Finance | | | |
| Legal | | | |
| Architect | | | |
| Backend Lead | | | |
| Security | | | |
| Compliance | | | |
| Infra | | | |

---

## §A 取證附錄（為何此 CR 是必要）

```bash
# 1. FR-0011 仍 draft + 有 blocker
$ grep -E "^status:|^blocked_by:" docs/analysis/fr/FR-0011-consumer-payment.md
status: draft
blocked_by:
  - Q7=B  # provider 選型

# 2. M11 payment endpoint 完全不存在（不在 v1 也不在 v2）
$ grep -rn "payment:intent\|payment:confirm\|payment:dispute" api/ 2>/dev/null
（空）

# 3. payments 表不存在
$ grep -rn "CREATE TABLE.*payments\b" SQL/ 2>/dev/null
（空；只有 voucher / refund / settlement / payment_status 欄位）

# 4. ADR-0019（PM-Q7 V1.0 金流範圍）accepted；本 CR 解 Q7=B blocker
$ grep "^status:" docs/architecture/adr/ADR-0019-pm-alignment-q7.md
status: accepted
```

**結論**：FR-0011 為 V1.0 金流主流 spec，draft + blocked + 0 實作；本 CR 解 Q7 blocker 並列 8 個 HD 等業主裁，是 MISSION 北極星 (1) 4 → 3 唯一可推進路徑。
