---
id: CR-0012
title: "FR-0012 技師月結撥款 — 解 Q7 bank provider 選型 + monthly settlement trigger 從 501 stub 落地路徑"
status: open-awaiting-decisions
decided: null
tier: 4-exploration
owner: HYBRID
created: 2026-06-04
target-release: 北極星條件 (1) draft FRs 4 → 3（與 CR-0011 並列）
product-version: null
supersedes: null
superseded-by: null
related:
  - docs/analysis/fr/FR-0012-monthly-settlement.md
  - docs/architecture/adr/ADR-0019-pm-alignment-q7.md
  - docs/architecture/adr/ADR-0041-travel-fee-split.md
  - docs/architecture/adr/ADR-VCH-002-voucher-retention-7y.md
  - docs/_audit/CR-0010-fr-0019-promote-to-active.md
  - docs/_audit/CR-0011-fr-0011-consumer-payment-cia.md
  - api/routers/settlements_v2.py
  - api/services/settlement_service.py
---

# CR-0012 — FR-0012 技師月結撥款 CIA

> **Tier**: 4-exploration → Change Impact Analysis
> **Mandated by**: `.claude/rules/change-governance.md` + CR-0010 HD-03=a「同步開 CR-0011~0014 審查其他 4 draft FR」
> **Triggered by**: MISSION 北極星 (1) draft FR = 0；FR-0012 為 4 剩餘 draft FR 第二件（與 CR-0011 共享 Q7=B blocker，但金流方向相反：CR-0011=客戶付平台，CR-0012=平台付技師）

---

## 1. Change Statement

**As-is**：
- `FR-0012` `status: draft`，`blocked_by: Q7=B`
- D5 殼結構已寫齊（§1 Use Case + §1.1/§1.2 Main/Alt Flow + §2 G/W/T 5 AC + §3 Reference Map）
- `api/routers/settlements_v2.py:39 trigger_monthly_settlement` 為 **501 stub**（comment：「Phase II → 回 501 stub。service 層尚無對應 monthly settlement 觸發實作。」）
- `api/services/settlement_service.py` 只有 `list_settlements`（CR-0008 補的），無 `trigger_monthly_settlement` / `compute_payouts` / `payout_via_bank`
- 對應 BR-M12-NN 群組仍標 NN（5 條未編號）
- ADR-0041 (travel fee 80/20) accepted，但 split 邏輯尚未進 settlement 計算公式
- 既有 `settlements` 表 schema 已建（CR-0008 list 用），但無 `period`, `wo_count`, `gross_amount`, `material_cost`, `net_amount`, `bank_payout_status`, `attempt_count` 等 monthly 特有欄位

**To-be**：
- `status: draft → active`（FR-0012 frontmatter）
- 對應 ADR 寫入：`ADR-0108`（暫定）— 月結 cron 觸發 + bank provider 選型 + retry/manual_payout 策略
- BR-M12-NN 全群組落實際編號（`BR-M12-001~005`）
- `settlement_service.trigger_monthly_settlement` 落地、`settlements_v2.trigger_monthly_settlement` 從 501 → 200/202
- Cron 排程接入（依 HD-04 決定 in-process scheduler / external GCP Cloud Scheduler / pgcron）

**Driver**：
- 北極星條件 (1) 4 → 3 路徑第二件（與 CR-0011 並列，但 HD 數較少、scope 較窄）
- FR-0011（消費者付平台）+ FR-0012（平台付技師）= V1.0 金流閉環，缺一不可
- Phase 8 UAT 前必須有月結機制（技師端期待固定週期撥款體驗）

---

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| `BF-PAY-006`（月結 cron happy path）| **New** | 每月 1 日 02:00 → 聚合 → calculate → bank payout |
| `BF-PAY-007`（negative settlement）| **New** | Alt A1：材料費 > 收款 |
| `BF-PAY-008`（manual_payout fallback）| **New** | Alt A2：Bank API 3 次失敗 |
| `BF-PAY-009`（unique constraint guard）| **New** | Alt A3：同 wo 雙重計算 DB 拒絕 |
| `BF-PAY-010`（dispute exclusion）| **New** | Alt A4：active dispute 排除當月，下月 retry |
| `SF-PAY-002`（travel fee 80/20 split）| **New** | per ADR-0041 計算公式並入 settlement |

---

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| `FR-0012` | Status flip | draft → active |
| `BR-M12-001`（cron 每月 1 日 02:00）| **New 編號** | 取代 BR-M12-NN |
| `BR-M12-002`（negative settlement = 技師應付公司）| **New 編號** | 同上 |
| `BR-M12-003`（dispute 未結排除當月）| **New 編號** | 同上 |
| `BR-M12-004`（Bank API 失敗 3 次 → manual_payout）| **New 編號** | 同上 |
| `BR-M12-005`（settlement unique constraint per (tenant, technician, period)）| **New 編號** | 同上 |
| `NFR-SETT-001`（月結 cron 全 tenant 在 30min 內跑完）| **New** | 配 cron schedule timing |
| `ADR-0041`（travel fee 80/20）| Referenced | 計算公式並入 |

---

## 4. Affected API

| API ID | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| `API-SETT-V2-TRIGGER` | `POST /tenants/{tid}/settlements/monthly` | **Replace** | No | 既有 501 stub → 真實實作；body `{period_start, period_end}` 觸發 |
| `API-SETT-V2-RETRY` | `POST /tenants/{tid}/settlements/{id}/payout:retry` | **New** | — | 對 manual_payout 狀態手動 retry |
| `API-SETT-V2-MANUAL-CLOSE` | `POST /tenants/{tid}/settlements/{id}/payout:manual-close` | **New** | — | 財務手動標記已撥（off-band 匯款）|
| `API-SETT-WEBHOOK-BANK` | `POST /webhook/bank-payout-status`（依 HD-01 bank API 提供）| **New** | — | bank async 回呼撥款結果 |
| `API-SETT-V2-LIST` | `GET /tenants/{tid}/settlements` | Touched | No | 既有 CR-0008 落地，新增 status filter `manual_payout` |

---

## 5. Affected Data

| Entity | Action | Migration |
|---|---|---|
| `settlements` | Extend | 新增欄位：`period_start TIMESTAMPTZ`, `period_end TIMESTAMPTZ`, `wo_count INT`, `gross_amount DECIMAL`, `material_cost DECIMAL`, `net_amount DECIMAL`, `bank_payout_status TEXT`, `bank_attempt_count INT DEFAULT 0`, `bank_payout_ref TEXT`, `manual_payout_reason TEXT` |
| `settlements` unique constraint | New | `UNIQUE (tenant_id, technician_id, period_start, period_end)` per BR-M12-005 |
| `settlement_payout_attempts`（**新表**）| New | `(settlement_id, attempt_no, status, bank_error, attempted_at)` per BR-M12-004 retry audit |
| `work_orders.settled_in_period_id` | New FK | 標記已納入哪期 settlement，配合 dispute exclusion 重 retry |

---

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| `TC-SETT-MNT-001`（happy cron）| **New** | AC-01：30 件 WO → SettlementCalculated × 30 |
| `TC-SETT-MNT-002`（negative）| **New** | AC-02：5000 收 - 6000 材料 = -1000 |
| `TC-SETT-MNT-003`（bank 3-retry → manual_payout）| **New** | AC-03 |
| `TC-SETT-MNT-004`（dispute exclude）| **New** | AC-04 |
| `TC-SETT-MNT-005`（unique constraint）| **New** | AC-05 |
| `TC-SETT-MNT-006`（travel fee 80/20 in net_amount）| **New** | ADR-0041 整合驗證 |
| `TC-SETT-XT-002`（cross-tenant trigger guard）| **New** | 已有 401/403 測試，加 monthly trigger 變體 |
| `TC-SETT-CRON-IDEMPOTENT-001`（重跑同 period 不重複建 settlement）| **New** | BR-M12-005 unique 確保 |

**Coverage delta**：+8 新 TC；M12 monthly settlement 覆蓋率（service 層）0% → ~85%

---

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| Module boundary | Extend | `payment_service`（FR-0011）vs `settlement_service`（FR-0012）保持分離；settlement 不直接呼 payment provider |
| New ADR? | **Yes** | `ADR-0108` 記錄 §8 HD-01~06 outcomes |
| External integration | Bank API | 新 vendor；HD-01 決定（台銀 / 玉山 / 中信 / 街口商家撥款 / 第三方 AP 平台）|
| Scheduling | New | HD-04：in-process APScheduler / GCP Cloud Scheduler → POST endpoint / pg_cron |
| Realtime | Touched | `/realtime/settlements/{tech_id}` 推 `SettlementPayoutInitiated` 給技師（OOSCope，移 BUILD CR）|
| Secret | New | `BANK_API_KEY` / `BANK_MERCHANT_ID` 進 GCP Secret Manager |

---

## 8. Human Decisions Required

🛑 **CIA blocks code changes until every row here has a recorded decision.**

| # | Question | Options | Owner | Status | Decision |
|---|---|---|---|---|---|
| **HD-01** | Bank payout provider | (a) 直接串台銀 SFTP / API（自有銀行帳戶）<br>(b) 串第三方 AP / payout 平台（如綠界 / 街口商家 / Stripe Connect）<br>(c) 純 manual file export（財務每月匯出 CSV 上傳銀行 ATM 端，無 API）<br>(d) 階段化：V1=(c) manual → V2=(a)/(b) API | Finance + Backend | **pending** | — |
| **HD-02** | Cron 排程實作 | (a) in-process APScheduler（單機 in-memory，現有 SLA / inventory monitor pattern）<br>(b) GCP Cloud Scheduler → POST `/settlements/monthly` HTTP trigger<br>(c) pg_cron 直接資料庫排程<br>(d) external GitHub Actions cron / workflow | Infra + Backend | **pending** | — |
| **HD-03** | Bank API 3-retry 策略 | (a) 即時 inline retry（30 秒間隔，HTTP 同步等）<br>(b) 排程化 retry（每次失敗 enqueue 至 retry_queue，下次 cron tick 處理）<br>(c) 純 1 次嘗試 → manual_payout（不做 retry） | Backend | **pending** | — |
| **HD-04** | manual_payout 完結機制 | (a) 財務透過 admin UI 標記 `manual_paid` + 上傳水單<br>(b) 純 backend mark via SQL/admin script<br>(c) 等 bank webhook 自動 close | Finance + Product | **pending** | — |
| **HD-05** | Dispute 排除實作 | (a) 月結 cron 時即時查 disputes 表 filter（per FR-0012 §1.2 A4）<br>(b) WO completion 時即標 `settled_eligible=false` 若有 dispute 開啟，cron 直接 trust flag<br>(c) 雙保險：(b) flag + (a) 即時 re-check | Backend | **pending** | — |
| **HD-06** | M11 即時付款 vs M12 月結金流關係（與 CR-0011 HD-08 鏡像）| (a) 客戶付款進中介帳 → M12 月結對帳支付技師（platform-escrow）<br>(b) 客戶付款直入技師帳（platform 收手續費）→ M12 退化為對帳 only<br>(c) 客戶付平台 → 平台月結付技師（typical SaaS marketplace 流程）| Finance | **pending** | — |

---

## 9. Suggested Implementation Order

§8 業主裁決後，依以下順序實作（**本 CR 僅含 step 1-2，code 實作另開 BUILD CR**）：

1. **Decisions** → 寫 `ADR-0108` 記錄 §8 HD-01~06 outcomes；frontmatter `related: ADR-0019, ADR-0041`；CR-0011 ADR-0107 HD-08 與本 CR HD-06 須同步裁決（避免 escrow 模型矛盾）
2. **BR 編號** → FR-0012 內 BR-M12-NN 全群組改 `BR-M12-001~005`
3. **FR-0012 status flip** → draft → active；移除 `blocked_by: Q7=B`；補 ADR-0108
4. **TM-0000 更新** → 補 FR-0012 ↔ ADR-0108 ↔ API-SETT-V2-* ↔ TC-SETT-MNT-* row
5. **CR-0012 status flip** → open-awaiting-decisions → decided
6. **system-completion-status.md** → draft FR 3 → 2（若 CR-0011 已先落地則 2 → 1）；M12 settlement 行從 501 stub 更新進度
7. **下一步另開 BUILD CR**（暫定 CR-0012-BUILD）→ schema migration + settlement_service.trigger_monthly_settlement / compute_payouts / payout_via_bank + cron 接入 + retry policy + tests；前置 bank vendor 契約簽訂、secret 進 SM

---

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Bank API vendor 契約 review 拖延 | High | High | HD-01=(c) manual 階段化 → V1 直接出 CSV 給財務，BUILD CR 可立即啟動不卡 vendor |
| Cron 跑超時（HD-02=a 單機）| Medium | High | 大 tenant 場景下單機 APScheduler 易卡；HD-02=(b) Cloud Scheduler + 多 worker 較穩 |
| settlement 計算錯誤（travel fee 80/20 漏算）| Medium | Critical | TC-SETT-MNT-006 強制驗證 ADR-0041；上線前財務手動對 1 個月真實資料 |
| dispute 同步窗口問題（cron 跑時 dispute 剛開）| Low | High | HD-05=(c) 雙保險（flag + 即時 re-check）|
| Bank webhook 重送 / 順序錯亂 | Medium | High | idempotency_key + DB unique constraint + state machine（per status enum）|
| 技師對撥款金額不認可 | Medium | Medium | settlement 明細 web UI（OOSCope，移 BUILD CR）+ 技師回報入口 → 進 disputes 流 |
| Phase II 改 bank vendor 時 schema 不容 | Medium | High | `settlements.bank_payout_ref TEXT`（不綁特定 provider）+ `settlements.bank_provider TEXT` 標記廠商 |

**Rollback plan**：
- Schema migration 全為 additive（新欄位 + 新表 settlement_payout_attempts）→ 可逆
- Cron 上線後出問題 → config flag `monthly_settlement.enabled=false` kill switch
- 已建 settlement 不可逆 SQL，但因屬計算/匯款記錄，rollback 應走「沖銷紀錄」而非物理 delete（per ADR-VCH-001 append-only 精神）
- ADR-0108 / FR-0012 status 改回 draft + 標 reverted 註解（append-only）

---

## 11. Out of Scope

- **settlement_service.trigger_monthly_settlement 實作** → 另開 BUILD CR
- **bank vendor 串接 SDK / webhook handler** → BUILD CR
- **技師端 settlement 明細 UI** → BUILD CR / 後續 UI 任務
- **FR-0047 品牌月結 / B2B settlement** → 完全 OOSCope（Phase II 模組）
- **退款流程**（FR-0014）→ 既有 refunds_v2 沿用
- **發票 / 三聯式** → CR-0011 OOSCope 已標
- **跨幣別** → V2 才議

---

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product | | | |
| Finance | | | |
| Legal | | | |
| Architect | | | |
| Backend Lead | | | |
| Infra | | | |
| Security | | | |
| Compliance | | | |

---

## §A 取證附錄（為何此 CR 是必要）

```bash
# 1. FR-0012 仍 draft + Q7 blocker
$ grep -E "^status:|^blocked_by:" docs/analysis/fr/FR-0012-monthly-settlement.md
status: draft
blocked_by:
  - Q7=B

# 2. settlements_v2 trigger 為 501 stub
$ grep -n "501\|Phase II stub\|service 層尚無" api/routers/settlements_v2.py
（包含「Phase II → 回 501 stub。service 層尚無對應 monthly settlement 觸發實作。」）

# 3. settlement_service 無 monthly trigger
$ grep -n "def trigger_monthly\|def compute_payouts\|def payout_via_bank" api/services/settlement_service.py
（空）

# 4. ADR-0041（travel fee 80/20）accepted，可直接引用作為計算公式正典
$ grep "^status:\|^title:" docs/architecture/adr/ADR-0041-travel-fee-split.md
title: 車馬費歸屬 — 80% 師傅 / 20% 平台
status: accepted

# 5. CR-0008 已建 settlements 表 list endpoint，shape 沿用即可
$ git log --oneline -- api/routers/settlements_v2.py | head -3
（5f9479a2 落地 GET list；trigger_monthly_settlement 501 stub 維持）
```

**結論**：FR-0012 為 V1.0 金流閉環必要件（與 CR-0011 互補：消費者付平台 + 平台付技師），draft + Q7 blocked + service 501 stub + 0 cron；本 CR 列 6 HD 等業主裁，與 CR-0011 HD-08（escrow 模型）須同步裁決避免金流方向矛盾。
