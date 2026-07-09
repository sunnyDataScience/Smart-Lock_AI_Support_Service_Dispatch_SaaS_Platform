# CR-0129: 急件事後補審引擎（WBS 1.2.2）

- **日期**: 2026-07-09
- **狀態**: done（2026-07-09 實作完成）
- **觸發面向**: Business flow（急件補審鏈）、報價/工單狀態機、DB schema（audit_due_at）、SLA 告警契約
- **上游正典**: 15_SDS §4.5（本引擎設計）、FR-API-19、TC-DISPATCH-08、BR-WO-04、ADR-015①②；前置 1.2.1（CR-0128 已鋪佔位報價與 audit_complete 轉移）

## §1 設計對映（SDS §4.5 六步 → 實作）

| SDS 步驟 | 實作 |
|---|---|
| 1 開單記 `emergency_bypass` audit | `create_from_problem_card` 急件路徑補 `audit_log_service.log_event`（1.2.1 漏此筆）|
| 3 補審 timer（onsite 結束 + 4h）| 佔位報價加 `quote.audit_due_at`；急件單**完工回報**（complete_order）時寫入 `NOW()+PT4H`（窗長讀 M18 config `emergency_audit_policy.audit_window_hours`，fallback 4）——不建獨立 task 表，佔位報價本身即任務（與 §4.3 scan 型 SLA timer 同型）|
| 4 補審佇列 | 報價工作台（admin/quotes）加「急件補審佇列」區塊：列 audit pending 報價（剩餘時間/逾時紅標）→ 補明細（含急件加價 URG-01）→ **LIFF 事後確認**（`send` 轉移放行 `retrospective_audit_only` 起點，沿用既有送客戶/LINE 推播/accept 鏈）或**紙本簽認**（`audit_complete` 轉移＋佐證註記，1.2.1 已鋪）|
| 5 逾時升級 | sla_monitor 新增 `audit_overdue` 掃描（`audit_due_at < NOW()` 且 state 未達 accepted）→ WS 告警升主管＋audit log；**同租戶最近 3 件急件補審全數逾時 → 自動開 `saas.change_request`**（type_code `emergency_audit_breach`，進主管佇列，BR-WO-04）|
| 6 結案 gate | 依 §8 D2 裁決落點（見下）|

**加價額**：補審明細帶「急件加價」目錄項 URG-01（`service_catalog` seed），金額依 §8 D1；
同步入 M18 config `emergency_audit_policy.surcharge_amount` 供調整（目錄 seed 為初值）。

## §4 契約影響

- `quote.audit_due_at`（additive migration 092）；`send` 轉移放行補審起點；`audit_complete`
  服務層限定急件單（audit_due_at 非空）並記 `quote_approval`。
- sla_monitor 告警型別新增第 5 類 `audit_overdue`（WS `/realtime/sla-alerts` payload 同構）。
- 新端點：報價補審佇列列表（`listAuditQueueV2`）。
- 完工/結案 gate 依 D2 調整（1.2.1 的完工閘急件分支需搬移或放寬）。

## §8 Human Decisions Required 🛑

| # | 決策 | 選項 | 待裁決 |
|---|---|---|---|
| D1 | 急件加價額 | ✅ **a. NTD 1500 初值（seed URG-01）＋M18 config `emergency_audit_policy.surcharge_amount` 可調**（業主 2026-07-09）| ✅ |
| D2 | 補審完成閘門落點 | ✅ **a. 擋結案（completed→confirmed）**——技師可完工回報、完工起算 4h 補審窗、未補審不可結案；BRD §5.7 字面同步勘誤（業主 2026-07-09）| ✅ |

## §9 Suggested Implementation Order（裁決後執行）

1. migration 092（`audit_due_at`＋URG-01 seed＋`change_request_type_dim` 補 type）
2. 完工/結案 gate 調整（D2）＋急件完工時寫 `audit_due_at`＋開單 `emergency_bypass` audit log
3. quote 狀態機：`send` 放行補審起點；`audit_complete` 限急件＋記 approval
4. sla_monitor `audit_overdue` 掃描＋連 3 逾時開 ChangeRequest
5. 補審佇列端點＋前端（admin/quotes 區塊：佇列/倒數/LIFF 補送/紙本簽認）
6. 測試（timer 寫入/逾時告警/連3 CR/兩路徑補審/gate）＋設計稿同步＋治理四件套

### 進度

- ✅ S1 done：migration 092（`audit_due_at`＋partial index＋URG-01 seed 1500＋
  `emergency_audit_breach` type）＋REGISTRY 補登
- ✅ S2 done：D2a 落地——完工閘放行急件補審中（佔位/已送），**結案閘**（confirm_order）
  補 `QUOTE_NOT_CONFIRMED_FOR_CLOSE`；完工回報起算 4h 窗（`_start_retrospective_audit_timer`，
  窗長讀 M18 config，fail-soft）；急件開單記 `emergency_bypass` audit（1.2.1 漏項補上）
- ✅ S3 done：`send` 放行補審起點（LIFF 事後確認沿用送客戶/推播/accept 全鏈）；
  `audit_complete` 允許 sent 起點＋服務層限定急件單（防一般報價繞過）＋記 quote_approval
- ✅ S4 done：sla_monitor 第 5 類 `audit_overdue`（WS 告警升主管＋audit log）；
  同租戶最近 3 件補審全數逾時 → 自動開 `saas.change_request`（pending_approval，防重複開）
- ✅ S5 done：`GET /quotes/audit-queue`（宣告先於 `/quotes/{id}` 防路徑吃掉）＋
  `POST /quotes/{id}:audit-complete`；admin/quotes 前端「急件補審佇列」區塊
  （倒數/逾時紅標/急件類別徽章/補明細送 LIFF/紙本簽認）；URG-01 金額 config 覆蓋（D1a）
- ✅ 正典同步：BRD §5.7 依 D2a 勘誤（補審完成擋結案非完工）；設計稿補審語意收斂
  （逾時不擋補審＝告警+連3 CR）
- ✅ 驗證：api unit 331＋component **878 passed**（隔離 scratch @5447；新增 0129 測試 7 項；
  0128 完工閘測試改寫 D2a 語意、0034 目錄測試放行業主已定案項）；四站 tsc 0；
  brand-portal build 綠；spectral 0 errors；types `--check` 冪等

### 遺留

- 逾時「410 AUDIT_WINDOW_EXPIRED」舊設計稿語意未採（逾時不擋補審，擋了更糟）——已同步設計稿。
- PC 階段 accept 延後開票的自動補開（CR-0128 遺留）仍留人工 from-quote；急件補審 accept
  時已有 WO 綁定，開票走既有 accept 鏈 ✅。
- 佇列頁面為 admin/quotes 區塊；若日後派工佇列頁要合流（15_SDS「派工小編工作台」），另 CR。
