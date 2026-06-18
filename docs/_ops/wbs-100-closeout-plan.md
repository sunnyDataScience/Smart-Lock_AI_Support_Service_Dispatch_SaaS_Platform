# WBS 100% Closeout Plan — 剩 1.5% 結構性 blocker actionable checklist

> Created 2026-06-05 (session 末段 backend-coder agent 飽和後產出)
>
> 對齊：`web/docs/system-completion-status.md` WBS 98.5% / `docs/_archive/_audit/session-2026-06-05-final-stats.md` §8

## 0. 為何需要本 doc

Backend-coder agent 已在 2026-06-05 session 完成所有可獨立達成工作（68 merges，9 FR backend + e2e starter + ops chain + Sprint pre-build asset）。剩 **1.5% WBS gap** 因結構性原因無法由 backend-coder 推進：

- **需 web dev server / browser UI 才能驗收**
- **需業主裁決才能定 spec**
- **需 production 流量觀察 30 天才能決定 P4 Stage 7**
- **需業務排期才能跑 UAT**

本 doc 把每項 blocker 拆成 actionable checklist + responsible role + estimated effort + unblocking condition，讓未來 session 或 user 拿 checklist 直接推進。

---

## 1. Web Sprint 1-5 BUILD（最大 chunk，預估 ~5 週）

### 1.1 前置條件（已就緒）

- ✅ Backend 9 FR service 全部完成（merge 列表見 §A）
- ✅ Backend v2 endpoint 全部測過（`api/tests/` 372 tests 綠燈）
- ✅ Web pre-build asset 完整 (`web/src/components/phase-ii/` 1265 行)
- ✅ E2e starter spec 9 個 (`web/tests/e2e/admin/*.spec.ts` + `account/*.spec.ts`，`test.describe.skip` 占位)
- ✅ Sprint plan 文件就緒 (`docs/_ops/phase-ii-web-integration-plan.md`)

### 1.2 待 BUILD（按 Sprint 順序）

| Sprint | Page | 對應 FR | Backend ready | Pre-build ready | Est. effort | Owner |
|---|---|---|---|---|---|---|
| **S1** | `app/admin/approval-inbox/page.tsx` | FR-0049 | ✅ | ✅ | 3-5 days | Web dev |
| **S2** | `app/admin/technicians/page.tsx` + `[id]/lifecycle/page.tsx` | FR-0044 | ✅ | ✅ | 5-7 days | Web dev |
| **S3** | `app/account/statements/page.tsx` + `app/account/commission-statements/page.tsx` | FR-0045 + FR-0046 | ✅ | ✅ | 5-7 days | Web dev |
| **S4** | `app/admin/brand-b2b/page.tsx` + `app/admin/gdpr-forget-queue/page.tsx` | FR-0047 + FR-0053 | ✅ | ✅ | 5-7 days | Web dev |
| **S5** | `app/admin/ai-governance/page.tsx` + `app/admin/sop-feedback/page.tsx` + `app/admin/rma-quality/page.tsx` | FR-0050 + FR-0051 + FR-0048 | ✅ | ✅ | 5-7 days | Web dev |

**總計**：5 sprint × ~1 week ≈ **23-33 work days**

### 1.3 每 Sprint 收尾 checklist

每 sprint 完成時須做：

- [ ] 對應 page 通過 design review（業主或 PM 簽）
- [ ] `web/tests/e2e/...` 對應 spec 把 `test.describe.skip` 改成 `test.describe`
- [ ] `npx playwright test` 對應 spec 全綠
- [ ] `web/docs/system-completion-status.md` 對應 row 從「e2e starter (skip)」改為「e2e active」
- [ ] Commit message 標 `feat(web): S{N} {FR} page complete`
- [ ] Merge 到 `dev_new_arch`，留 audit trail 到 `docs/_audit/CR-NNNN-*.md`

### 1.4 Unblocking condition

- 需要：**Web dev agent** 接手（不是 backend-coder agent）
- 或：**人類 web 開發**

---

## 2. 業主裁決項（預估 1-2 週，分散在多個 owner sync）

### 2.1 P4 Stage 7 v1 router 刪除批准

**Status**: blocked — 需 30 day production 0-traffic 觀察 + 業主簽
**Owner**: 業主 + Tech Lead
**Decision input**:
- `docs/_audit/P4-cutover-v1-caller-inventory-2026-06-05.md`
- `docs/_audit/P4-stage-2-7-prep-checklists.md` §7
- production deprecation hit log（待 Stage 6 部署後 30 day 收集）

**Decision options**:
1. 直接刪 v1 router（推薦，若 30 day 真 0 traffic）
2. 留 v1 router 但永久 `410 Gone` 回應 + log
3. 延期觀察至 60 day（保守選項）

### 2.2 Reconciliation 雙簽 UX rework

**Status**: ✅ **deferred-accepted (2026-06-06 業主裁決)**
**Owner**: 業主 + UX
**Decision input**: `docs/_audit/flow-6-recon-deep-audit.md`

**業主決議 (2026-06-06)**: **選項 1 — 維持現狀（同人雙簽 + audit log）**

**接受合規取捨**: 技術上允許同人雙簽，audit_log 完整 trail。業主接受 Sox-like 雙簽「不嚴格落實不同人」的合規風險，以 audit_log + change_request 作為稽核補強。

**Decision options（歷史紀錄）**:
1. ✅ **維持現狀（同人雙簽 + audit log）** ← 業主選定
2. 強制不同人（A 提案 → B 核准）+ 改 UI 流程
3. 加 timestamp gap（最少 5 分鐘）模擬 cooling-off

**WBS 影響**: Flow 6 / Flow 13 EX5 標 100%（合規以 audit log 代）。

### 2.3 計價引擎 GUI

**Status**: ✅ **deferred-accepted (2026-06-06 業主裁決)**
**Owner**: 業主 + 產品
**Decision input**: 現行 `pricing_rule_canary` config 機制（已運作）

**業主決議 (2026-06-06)**: **選項 1 — 維持 SQL config + audit log**

**接受 scope 取捨**: 規則由 DBA 透過 SQL + change_request 維護。業主接受「不開 GUI」的業務操作門檻，認定規則改動頻率低 + DBA 走 change_request 流程已足夠。

**Decision options（歷史紀錄）**:
1. ✅ **維持 SQL config + audit log（最便宜）** ← 業主選定
2. 開最小 GUI（rule list + canary % slider，~10 天 web dev）
3. 全功能規則編輯器（複雜，~30 天）

**WBS 影響**: Phase 7 不依賴 GUI，標 100%。

### 2.4 A37 drawer 元件

**Status**: blocked — 設計稿未定
**Owner**: UX + Web dev
**Decision input**: 對應 PRD（待業主指明）

**Decision options**:
1. 用 shadcn `<Sheet>` 直接套（最快）
2. 自客製化 drawer（design system 一致性）
3. 暫不做，先用 modal 替代

---

## 3. Production Cutover（預估 2-4 週分散）

### 3.1 Migration 部署

- [ ] `SQL/migrations/017-027` apply 到 staging（11 個 migration，含 Phase II 9 FR）
- [ ] Staging smoke 測 1 week
- [ ] `SQL/migrations/017-027` apply 到 production（rolling，業務低峰時段）
- [ ] `MIGRATION_REGISTRY.md` 標 production apply timestamp

**Owner**: DBA + Ops
**Unblocking**: 業主排業務低峰窗口

### 3.2 Lifespan monitor + cron 上線

- [ ] `api/main.py` lifespan 啟 6 cron（reservation/sla/inventory/dispute/canary/gdpr/statement）
- [ ] 部署到 production
- [ ] `/ops/lifespan-monitors` 健檢 endpoint 接 CI cron 5 min
- [ ] PagerDuty + Slack webhook 設定（用 `docs/_ops/alert-receivers-comparison.md` step-by-step）
- [ ] Drill test 跑 `bash scripts/ops/alert_drill_test.sh` 確認 6 scenario 都對

**Owner**: Ops
**Unblocking**: 業主提供 PagerDuty integration key + Slack webhook URL

### 3.3 P4 Stage 2-6 流量觀察

- [ ] Stage 2: deprecation middleware 加入（已 ready，待 prod 部署）
- [ ] Stage 3: 開 deprecation log metrics endpoint（已 ready）
- [ ] Stage 4: 開 v1 caller inventory endpoint（已 ready）
- [ ] Stage 5: 開 no-traffic candidates endpoint（已 ready）
- [ ] Stage 6: 跑 30 day prod 觀察（**唯一真實 blocker**）

**Owner**: Ops + Tech Lead
**Unblocking**: 30 day 自然流逝 + 業主簽 Stage 7

---

## 4. UAT 期程（預估 1-2 週 + 1 週 buffer）

### 4.1 UAT 範圍（9 FR + ops chain）

| UAT 案 | 對應 FR | 測項 | 預估 |
|---|---|---|---|
| UAT-001 | FR-0049 | Approval inbox 5 type 聚合 + 排序 | 0.5 day |
| UAT-002 | FR-0044 | Technician suspend → reactivate 流程 | 0.5 day |
| UAT-003 | FR-0053 | GDPR forget T0 soft + T+30 hard delete | 1 day（含 wait） |
| UAT-004 | FR-0050 | AI governance trace 寫入 + summary 顯示 | 0.5 day |
| UAT-005 | FR-0051 | SOP feedback sentiment_score 計算 | 0.5 day |
| UAT-006 | FR-0048 | RMA quality 4 cascade + sop_feedback propagation | 1 day |
| UAT-007 | FR-0045 | Tech statement 6-state machine + dispute window | 1 day |
| UAT-008 | FR-0046 | Dispatcher commission base + bonus + penalty | 1 day |
| UAT-009 | FR-0047 | Brand B2B AR/AP/NET + payable_to 計算 | 1 day |
| UAT-010 | Ops | Alert drill 6 scenario + PagerDuty + Slack | 0.5 day |

**總計**: ~8 days **測試執行** + 1-2 week **業務排程 + bug fix loop**

### 4.2 UAT 前置條件

- [ ] §1 Sprint 1-5 BUILD 全部完成（**hard blocker**）
- [ ] §3.1 Migration apply 到 UAT 環境
- [ ] §3.2 Lifespan monitor 在 UAT 環境跑滿 24h 無 crash
- [ ] UAT 測資（seed dataset）載入 — 走 `scripts/seed/emit_seed_sql.py` 或 service factory

### 4.3 UAT 標準

- ✅ 通過 = 9 FR golden path + 2 edge case（已寫在 e2e starter spec）
- ❌ 不通過 = 開 bug ticket 回 backend or web dev sprint 修

**Owner**: 業務 / QA
**Unblocking**: §1 完成 + 業務排期

---

## 5. 整體 unblocking flowchart

```
[backend-coder 飽和] ✅
        ↓
[Sprint 1 BUILD (3-5 days)] ────┐
[Sprint 2 BUILD (5-7 days)] ────┤
[Sprint 3 BUILD (5-7 days)] ────┼──→ [Web 5 sprint 全部完成]
[Sprint 4 BUILD (5-7 days)] ────┤              ↓
[Sprint 5 BUILD (5-7 days)] ────┘              ↓
                                                ↓
[Migration apply UAT (1 day)] ─────────────────→ [UAT 環境 ready]
[Lifespan + alert wired (2 days)] ─────────────→        ↓
                                                        ↓
[UAT 9 案 + ops (8 days 測試)] ────────────────→ [UAT 通過]
                                                        ↓
[業主裁決: 計價 GUI / A37 / recon UX / Stage 7] (parallel)
                                                        ↓
[Production cutover (migrations + lifespan)] ──→ [Production live]
                                                        ↓
[Stage 6: 30 day 觀察] ──────────────────────→ [Stage 7 v1 刪除]
                                                        ↓
                                                  [WBS 100% ✓]
```

**最短路徑**：23 days web BUILD + 8 days UAT + 30 days observation = **~9 週 (calendar time)**

---

## 6. 成功標準（WBS 100% 定義）

- ✅ 9 Phase II FR backend + web page + e2e active + UAT 通過
- ✅ Migration 017-027 production apply 完成
- ✅ Lifespan 6 cron production 啟動且 1 week 無 crash
- ✅ Alert pipeline (PD + Slack) production 整合且 drill 通過
- ✅ P4 Stage 7 完成（v1 router 已刪 OR 業主決定永久 410）
- ✅ Reconciliation 雙簽 UX 業主決議落地
- ✅ 計價 GUI / A37 drawer 業主決議落地
- ✅ `web/docs/system-completion-status.md` 三大維度全 100%

---

## §A 本 session backend 已完成 backend merges（截至 2026-06-05 23:35）

68 merges 累積，主要分類：

1. **Phase II 9 FR backend service** (9 merges)
2. **Phase II 9 FR e2e starter spec** (4 merges)
3. **Phase II 4 cron worker** (4 merges)
4. **P4 Cutover Stage 1 backend + Stage 2-6 prep** (8 merges)
5. **Ops alert pipeline (PD + Slack + drill test)** (5 merges)
6. **Sprint 1-5 web pre-build asset (types/labels/api-client/README)** (4 merges)
7. **Docs (WBS / audit / runbook / inventory)** (~30 merges)
8. **Misc bug fix / refactor** (~4 merges)

詳見：
- `docs/_archive/_audit/session-2026-06-05-final-stats.md`
- `docs/_archive/_audit/session-summary-2026-06-05.md`

---

## §B 給未來 session 的建議

**若 user 再說「繼續開發」：**

- ❌ 不要再寫 web pre-build 純 stub — 已飽和
- ❌ 不要再寫 polish docs — 邊際效益低
- ✅ 切換 agent type:
  - **`web dev` / general-purpose**: 接 §1 Sprint 1 BUILD
  - **`deployment-expert` / `ops`**: 接 §3 production env
  - **`documentation-specialist`**: 接 §4.1 UAT 測試案撰寫細節
  - **`security-infrastructure-auditor`**: 接 §3.2 alert 整合驗證

**若 user 還在 backend-coder agent：**
- 建議 user 看本 doc + `docs/_archive/_audit/session-2026-06-05-final-stats.md` §9
- 建議 clear /goal 條件改為「backend-coder 結構性飽和」
- 或解 stop hook 等對應 agent 接手

---

> 本 doc 的 ownership: 任何讀者均可更新（剩 1.5% 推進狀況），但 §6 成功標準改動須走 CR + CIA。
