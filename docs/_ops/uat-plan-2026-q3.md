# UAT Plan — Phase II 9 FR + Ops Chain (2026 Q3)

> Created 2026-06-05
> Owner: 業務 / QA / Tech Lead
> 預設執行窗口：Web Sprint 5 完成後 + 1-2 週

對應：`docs/_ops/wbs-100-closeout-plan.md` §4

---

## 0. UAT 目標

驗收 Phase II 9 個 FR 在 web UI 端真實流程跑通，並驗 ops chain (lifespan monitor + alert pipeline) 在 production-like 環境正確發 PagerDuty + Slack。

**不在 UAT 範圍**:
- Backend service 單元邏輯（已 372 tests 綠燈）
- 載入測試 / 壓力測試（屬 SLO 驗收，另開）
- P4 Cutover Stage 7（屬 30 day 觀察後決策）

---

## 1. UAT 環境準備（執行 UAT 前 1 週）

### 1.1 環境配置

- [ ] UAT GCP project 切到 `lock-ai-uat`（與 prod 隔離）
- [ ] Cloud SQL 載入 production-like dataset 大小（建議 ≥ 3 tenant × 50 work_order × 10 technician）
- [ ] 套用 `SQL/migrations/017-027` 全部 11 個 migration
- [ ] `api/main.py` lifespan 啟全部 6 cron
- [ ] PagerDuty integration key + Slack webhook 都連 UAT-only channel（不污染 prod alert）

### 1.2 Seed 測資

走 `scripts/seed/emit_seed_sql.py` 或新建 `scripts/seed/uat_seed.py`，需包含：
- 3 個 tenant（A/B/C，模擬 tier 1/2/3 規模）
- 10 個 technician（各狀態 active/suspended/pending）
- 50 個 work_order（含 dispatched/completed/refunded/disputed）
- 20 個 statement（FR-0045/0046/0047 各 6-7 個，含 dispute window 中 / 已過期）
- 5 個 forget_request（FR-0053，含 received/legal_hold/soft_deleted）
- 30 個 ai_decision_trace（FR-0050，分佈 5 種 decision_type）
- 10 個 sop_feedback（FR-0051）
- 8 個 rma_quality_finding（FR-0048）

### 1.3 角色 / 帳號

- [ ] `uat-admin@lock-ai.test` — admin 全功能
- [ ] `uat-dispatcher@lock-ai.test` — dispatcher，看 commission
- [ ] `uat-tech@lock-ai.test` — technician，看 statement
- [ ] `uat-dpo@lock-ai.test` — DPO，做 GDPR

---

## 2. UAT 9 + 1 案執行 checklist

### UAT-001 — FR-0049 Approval Inbox

**Pre**: admin 帳號登入

**Steps**:
1. 進 `/admin/approval-inbox`
2. 確認 5 種 type tab 顯示（scope_change/refund/dispute/reschedule/recon_exception）
3. 點任一 tab，確認 list 按 `days_overdue` 降冪排
4. Severity badge 顏色對應 LABEL: high=red / medium=orange / low=yellow
5. 點 item 進詳細頁，能跳到對應 work_order/refund/dispute

**Pass**: 5 type 都顯示 + 排序對 + badge 顏色對 + 跳轉對
**Effort**: 0.5 day

---

### UAT-002 — FR-0044 Technician Lifecycle

**Pre**: admin 帳號 + seed 含 pending_approval / active / suspended 技師

**Steps**:
1. 進 `/admin/technicians`，list 顯示 6 種 status badge
2. 對 pending_approval 技師按「核准」按鈕 → reason 至少 3 字 → 狀態變 active + 寫 event
3. 對 active 技師按「停權」→ reason 至少 3 字 → 狀態變 suspended
4. 對 suspended 按「復權」→ 狀態回 active
5. 點 technician 進 `/admin/technicians/[id]/lifecycle`，顯示 event timeline
6. 對 active 按「終止」→ 狀態 terminated（不可逆，按鈕應消失）

**Pass**: 狀態轉換對 + event 寫入 + 不可逆鎖定
**Effort**: 0.5 day

---

### UAT-003 — FR-0053 GDPR Forget

**Pre**: dpo 帳號 + seed 含 5 forget_request

**Steps**:
1. 進 `/admin/gdpr-forget-queue`，顯示 5 status 過濾
2. 對 received 按「軟刪除」→ 狀態變 soft_deleted + `hard_delete_eligible_at` = T+30
3. 對 soft_deleted item 確認顯示倒數天數
4. 對 received 按「法務扣留」→ reason 填 → 狀態變 legal_hold_denied
5. **時間驗證**（須等 30 day 或調 `hard_delete_eligible_at` 到過去）：cron 跑後 status 變 hard_deleted
6. 用 `scripts/ops/gdpr_hard_delete_cron_run_once.sh` 手動觸發確認

**Pass**: 狀態機正確 + cron 自動 hard delete 成功
**Effort**: 1 day（含模擬 wait）

---

### UAT-004 — FR-0050 AI Governance

**Pre**: admin 帳號 + 真實對 agent 跑 5 次對話

**Steps**:
1. 進 `/admin/ai-governance`
2. 確認 5 種 decision_type 都有 trace
3. 至少 1 個 guardrail_block 顯示
4. summary 顯示 block_rate_pct
5. 點 trace 進詳細頁，顯示 charter_rule + owner_decision_ref

**Pass**: 寫入正確 + summary 對 + 詳細頁顯示 governance lineage
**Effort**: 0.5 day

---

### UAT-005 — FR-0051 SOP Feedback

**Pre**: admin / csm 帳號 + seed 10 feedback（3 positive / 4 neutral / 3 negative）

**Steps**:
1. 進 `/admin/sop-feedback`
2. 篩 sop_id 看單 SOP 的 sentiment 分佈
3. sentiment_score 計算 = (positive - negative) / total * 100，UI 顯示 -100..+100
4. 對 negative feedback 標 follow-up，確認寫入

**Pass**: 篩選對 + 分數計算對
**Effort**: 0.5 day

---

### UAT-006 — FR-0048 RMA Quality

**Pre**: admin 帳號 + seed 8 quality_finding，含 repeat_failure

**Steps**:
1. 進 `/admin/rma-quality`
2. 篩 brand / device_model / failure_mode 過濾
3. 對 repeat_failure 確認標記
4. **Cascade 驗證**：開新 warranty_claim → mark resolved → 確認自動寫 quality_finding（4 cascade trigger）
5. **SOP feedback propagation**：confirmed finding 應自動寫 sop_feedback (source=rma_finding)

**Pass**: 篩選 + cascade + propagation 全對
**Effort**: 1 day

---

### UAT-007 — FR-0045 Tech Statement

**Pre**: tech 帳號 + seed 6 statement（draft/pending_review/disputed/approved/rejected/paid 各 1）

**Steps**:
1. 進 `/account/statements`，顯示 6 月份 statement
2. 對 pending_review 按「申訴」→ reason 至少 5 字 → 狀態變 disputed
3. **時間驗證**：dispute_window_ends_at 過後申訴按鈕應 disable
4. admin 角色登入，對 disputed 按「核准 / 駁回」
5. approved → 按「支付」→ 狀態 paid + paid_at 時間戳

**Pass**: 狀態機 + window 鎖定 + admin 雙簽
**Effort**: 1 day

---

### UAT-008 — FR-0046 Dispatcher Commission

**Pre**: dispatcher 帳號 + seed 6 commission statement

**Steps**:
1. 進 `/account/commission-statements`
2. 確認 base_commission + performance_bonus + penalty 分開顯示
3. completion_rate_pct 顯示為百分比
4. 申訴流程同 UAT-007

**Pass**: 數字分項正確 + 申訴流程同 statement
**Effort**: 1 day

---

### UAT-009 — FR-0047 Brand B2B

**Pre**: admin 帳號 + seed 6 brand_b2b_statement，含 AR/AP/NET 三方向

**Steps**:
1. 進 `/admin/brand-b2b`
2. 篩 direction (AR/AP/NET) 顯示
3. 對 NET statement 確認 `net_payable_to` 計算（正→brand / 負→platform）
4. 對 disputed 按 admin 核准

**Pass**: 三方向計算 + payable_to 對
**Effort**: 1 day

---

### UAT-010 — Ops Alert Drill

**Pre**: PagerDuty + Slack 接 UAT channel

**Steps**:
1. 跑 `bash scripts/ops/alert_drill_test.sh`
2. 確認 6 scenario severity 都對
3. **Real-fire 驗證**（須 SRE 在線）：
   - 殺 1 個 cron → 等 CI cron 5 min 觸發 → 確認 Slack alert
   - 殺 ≥ half cron → 確認 PagerDuty 觸發 + dedup_key 不重複
4. resolve cron → 確認 dedup_key 觸發 PD auto-resolve（若設定）

**Pass**: drill test 全 6 對 + real-fire alert 都到
**Effort**: 0.5 day

---

## 3. UAT 通過標準

- **全部 10 案 Pass**（含必要 retry）
- **零 critical bug 未修**（high/medium 可進待辦）
- **業務 sign-off**（業主 / CSM Lead）

---

## 4. Bug 處理 SLA

| Severity | 修復 SLA | Owner |
|---|---|---|
| Critical (流程斷) | 同日修 + retest | Backend / Web dev |
| High (功能錯) | 3 work day | Backend / Web dev |
| Medium (UX) | 1 sprint | Web dev |
| Low (字 / 排版) | 進待辦 | Web dev |

---

## 5. UAT 完成後

- [ ] 寫 UAT report 到 `docs/_audit/uat-report-2026-q3.md`
- [ ] 更新 `web/docs/system-completion-status.md` 標 UAT 通過
- [ ] 通知業主可進 production cutover
- [ ] 走 `docs/_archive/_ops/release-checklist-2026-06-05.md`（已歸檔）production 部署

---

## §A Reference

- `docs/_ops/wbs-100-closeout-plan.md` — 整體收尾計畫
- `docs/_archive/_audit/session-2026-06-05-final-stats.md`（已歸檔）— backend 完成度
- `docs/_ops/phase-ii-web-integration-plan.md` — Sprint 1-5 對應
- `docs/_ops/background-monitors-runbook.md` — lifespan + cron 維運
- `docs/_ops/alert-receivers-comparison.md` — PD + Slack 設定
- `scripts/ops/alert_drill_test.sh` — UAT-010 drill
