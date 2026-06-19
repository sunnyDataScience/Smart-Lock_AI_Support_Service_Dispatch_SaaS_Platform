---
title: 分階段測試計畫 Alpha/Beta/RC/GA（2026-06-19 更新版，會議 Action #2）
status: active
tier: 3-process
created: 2026-06-19
method: 9-agent workflow（8 測試領域盤點 + 綜整），對真實 api/tests + web/tests/e2e 查覆蓋
baseline: 20260617資料/02-phased-test-plan-alpha-beta-rc-ga（194 項，2026-06-17）
target: Lite 版目標測到 Beta（會議定調）；Alpha 內部自動、Beta 由 Irene+Johnson 點測
---

## 規模

| 指標 | 值 |
|---|---|
| 測試案例總數 | **275**（Alpha 157 / Beta 85 / RC 28 / GA 5）|
| ready（可跑且綠）/ gap（缺實作或測）/ blocked（依賴未建）| 165 / 85 / 25 |
| Alpha P0 ready | 84/89（≈94%）|

> 對齊 §4 覆蓋 Dashboard（agent 以唯一 TC 去重後 ready≈88/gap≈45/blocked≈17）；本表為原始 275 案例分佈。

---

# 分階段測試計畫 — Alpha / Beta / RC / GA（2026-06-19 更新版）

> 基準：`02-phased-test-plan-alpha-beta-rc-ga-20260617.txt`（194 項）。本版以 CR-0038 缺口盤點 + 本 session 新增（CR-0039/0040/0041 + 階段0 CI 修復 + AuthGuard/角色 landing）**重查覆蓋狀態**。spec 來源：`01-workorder-erp-final-spec-20260520.txt`（M01–M20、BR 編碼）。

---

## 1. 總覽

baseline 02（2026-06-17，194 項）盤點後，本 session 又落地三個硬閘 CR + 階段0 CI/migration 修復，使下列項目**由 BROKEN/缺測轉為可信綠燈**：

- **CR-0039 完工硬閘**（照片≥3 / 簽名真存在性 / install serial gate / 主管 override+reason）— `test_cr_0039_completion_gate.py` 8 案 component 真綠，serial gate 已串入 complete_order。
- **CR-0040 Evidence 治理**（品牌/會計角色 media 可見性 + 保存期軟刪 cron）— `test_cr_0040_evidence_governance.py` 6 案綠。
- **CR-0041 M15 異常框架**（exception_case 10×9 enum + high_risk_hold 串 assign/complete 422）— `test_cr_0041_exception_framework.py` 6 案綠。
- **階段0**：`test-suite.yml` unit job 改 `cd api && uv run pytest -m unit`，**實測 226 unit 收集真綠（965 component deselected）**；migration 046 建 `schema_migrations` 追蹤表 + redeploy-local 9 項 smoke；035/046 補套 dev DB 使 **password_reset 8 案 BROKEN→ready**。
- **AuthGuard 公開白名單修復 + 角色 landing**：7 公開頁未登入可達，dispatcher/cs/ops/admin 禁區重導 dashboard（`role-ui-isolation.spec.ts`）。

**Alpha/Beta 可達性一句話**：Alpha（內部自動冒煙）對「報價狀態機、完工硬閘、Evidence 治理、異常框架、退款/取消費 SoD、RBAC/Config/Auth、KPI/報表、AI 治理 trace」皆有可重複跑綠的 pytest；Beta（Irene+Johnson 多角色點測）可串到「進線→AI 草擬卡→確認→報價→工單→派工→完工硬閘→Evidence 可見性→異常 hold」，但**整鏈在「付款 gate 控派工」與「接單 SLA/逾時改派」兩個 P0 缺口處斷點**（依賴 payments 金流 + SLA 引擎，本期會議定調 Beta 綠燈後才動 P2）。

---

## 2. 四階段定義（沿用 02 §1，Exit 對齊現況）★ Lite 版目標到 Beta

| 階段 | 誰測 | 環境 | 目的 | Entry | Exit（對齊 2026-06-19 現況） |
|---|---|---|---|---|---|
| **Alpha** | 內部 / CI 自動 | 本機 docker compose（api+postgres+seeds）/ CI unit job | 邏輯正確性、契約、紅線守線自動冒煙 | code merge 至分支 | 226 unit 真綠 + 各 CR component（39/40/41/refund/rbac/config）在套 migration 的 DB 全綠；無 collection ERROR；Alpha 阻塞清單（§5）P0 gap 清空或業主豁免 |
| **Beta** | Irene（會計/客服主管）+ Johnson（營運/派工） | 對齊 HEAD 的 staging stack（redeploy-local smoke 9 項過）+ mock LINE | 真實多角色操作、UX、可見性、權限邊界 | Alpha Exit 達成 + redeploy-local smoke 全過 | §6 點測 checklist 全勾；可見性/權限/硬閘無洩漏；金流端到端標 blocked 可手動跳過 |
| **RC** | QA + 紅線 gate | 類正式 + k6/eval pipeline | 紅線量化 gate（leakage 0、AI eval ≥95%、SLA、hash-chain） | Beta 通過 | **本期非重點，僅標出**：100-mutation 0 leakage、K8≥95%、K3≥90%、月結 cron 實測、audit hash-chain 篡改偵測 |
| **GA** | 上線冒煙 | production | 上線健康、監控、初始匯入 | RC gate 全綠 | **本期非重點**：RMA case 編號/責任矩陣、初始建置匯入、prod drift 告警 |

---

## 3. 測試矩陣

### 3.1 ALPHA（內部自動 / 冒煙）— P0 先排

| id | title | spec_ref | pri | coverage | status |
|---|---|---|---|---|---|
| TC-M01-01 | 全渠道進線建 Conversation + SLA clock 起點 | BR-M01-01/Q006 | P0 | pytest:test_create_conversation.py | ready |
| TC-M01-02 | session_id 冪等不重建 | A06 | P0 | pytest:test_create_conversation.py | ready |
| TC-M01-03 | LINE webhook HMAC 簽章 401/400 | M16/A01 | P0 | pytest:test_cr_0017_line_webhook.py | ready |
| TC-M01-05 | ingest_turn internal token fail-closed + 落庫 | ADR-0112/CR-0022 | P0 | pytest:test_internal_ingest.py | ready |
| TC-M02-01 | 客戶主檔 CRUD + 360 聚合 + display_name fallback | Q008/BR-M02-01 | P0 | pytest:test_customer_crud.py | ready |
| TC-M02-02 | line_user_id 唯一去重回 422 非 500 | BR-M02-01 | P0 | pytest:test_customer_crud.py | ready |
| TC-M02-03 | 客戶主檔跨租戶 403/404 隔離 | M17 | P0 | pytest:test_customers_v2_endpoint.py | ready |
| TC-M03-01 | ProblemCard 必填 + enum 校驗 422 | Q015 | P0 | pytest:test_problem_cards_v2_endpoint.py | ready |
| TC-M03-02 | PC 狀態機 incomplete→confirmed→resolved 非法 409 | BR-M03-01 | P0 | pytest:test_problem_cards_v2_endpoint.py | ready |
| TC-M03-03 | PC 1:1 Conversation 約束 409 | A06/Q014 | P0 | pytest:test_problem_cards_v2_endpoint.py | ready |
| TC-M03-04 | PC→WO 轉換 gate（缺址422/1:1冪等/跨租404） | Sync-M04/ADR-0032 | P0 | pytest:test_pc_convert_to_wo.py | ready |
| TC-M03-05 | AI escalation→草擬 PC（source=ai_line, 永不 confirm） | BR-M03-02/ADR-0028 | P0 | pytest:test_escalation_to_draft_pc.py | ready |
| TC-M03-06 | AI 分診紅線 CS_TOOL_ALLOWLIST 6 工具 | BR-M03-03/A03 | P0 | pytest:agent test_tool_allowlist.py | ready |
| TC-M04-01 | 報價狀態機 draft→submit→approve→send→accept | BR-M04-03/Q033 | P0 | pytest:test_cr_0032_quote_engine.py | ready |
| TC-M04-02 | 報價非法轉換 409 | BR-M04-03 | P0 | pytest:test_cr_0032_quote_engine.py | ready |
| TC-M04-03 | 核准門檻超額 draft 不可直送 | BR-M04-03/Q031 | P0 | pytest:test_cr_0032_quote_engine.py | ready |
| TC-M04-05 | 內外部報價成本遮蔽 RBAC | BR-M04-01 | P0 | pytest:test_cr_0032_quote_engine.py | ready |
| TC-M04-08 | 客戶端報價查看 public token 不洩成本 | CR-0032 PhaseC | P0 | pytest:test_cr_0032_phasec_consumer.py | ready |
| TC-M05-01 | 工單狀態機 happy created→…→closed | BR-M05-01 | P0 | pytest:test_work_orders_v2_endpoint.py | ready |
| TC-M05-03 | 取消工單強制 reason gate 422 | BR-M05-01/Q011 | P0 | pytest:test_cancellation_6stage.py | ready |
| TC-M05-05 | 單號編碼 + Idempotency + 跨租 404 | BR-M05/FR-0038 | P0 | pytest:test_wo_numbering.py | ready |
| TC-M05-08 | 派工前必填 gate 缺 problem_type 422 | BR-M05-03/CR-0026 | P0 | pytest:test_cr_0026_wo_fields.py | ready |
| TC-M06-01 | 自動派工 5 因子 top-1 + 候選擴大 | Q041/BR-M06-01 | P0 | pytest:test_dispatch_v2_endpoint.py | ready |
| TC-M06-03 | 手動派工 + audit + 非授權 403 | BR-M17-01/Q038 | P0 | pytest:test_manual_dispatch.py | ready |
| **TC-CR0039-01** | 完工照片<3→422 INSUFFICIENT_PHOTOS | BR-M08-03/CR-0039 HD-1 | P0 | pytest:test_cr_0039_completion_gate.py | ready |
| **TC-CR0039-02** | 3 照片足量通過 happy | CR-0039 HD-1 | P0 | pytest:test_cr_0039_completion_gate.py | ready |
| **TC-CR0039-03** | 無簽名紀錄→422 SIGNATURE_REQUIRED（真存在性） | Q060/CR-0039 HD-4 | P0 | pytest:test_cr_0039_completion_gate.py | ready |
| **TC-CR0039-05** | install 無 serial→422 SERIAL_REQUIRED | BR-M10-03/CR-0039 HD-3 | P0 | pytest:test_cr_0039_completion_gate.py | ready |
| **TC-CR0039-06** | install 有 serial 通過 / repair 無 serial 放行 | CR-0039 HD-3 | P0 | pytest:test_cr_0039_completion_gate.py | ready |
| **TC-CR0039-08** | 主管 override+reason 跳過證據+稽核註記 | CR-0039 HD-2 | P0 | pytest:test_cr_0039_completion_gate.py | ready |
| **TC-CR0040-01** | 品牌角色 media 排除客戶環境照 | BR-M09-02/CR-0040 HD-2 | P0 | pytest:test_cr_0040_evidence_governance.py | ready |
| **TC-CR0040-02** | 品牌 get 隱藏 purpose 回 404 不洩存在性 | BR-M09-02 | P0 | pytest:test_cr_0040_evidence_governance.py | ready |
| **TC-CR0040-04** | 保存期 cron 軟刪過期 media，list 排除 | BR-M09-03/CR-0040 HD-3 | P0 | pytest:test_cr_0040_evidence_governance.py | ready |
| TC-M09-03 | media_v2 跨租戶 403 + 無 token 401 | M09 | P0 | pytest:test_media_v2.py | ready |
| **TC-CR0041-01** | 開異常非法 exception_type 422 | CR-0041/BR-M15-01 | P0 | pytest:test_cr_0041_exception_framework.py | ready |
| **TC-CR0041-02** | medium 異常不設 high_risk_hold | BR-M15-03 | P0 | pytest:test_cr_0041_exception_framework.py | ready |
| **TC-CR0041-03** | high 異常設 hold 並擋派工/完工 422 | BR-M15-03 | P0 | pytest:test_cr_0041_exception_framework.py | ready |
| **TC-CR0041-04** | resolve 帶 return_path 清 hold + 記錄 | BR-M15-01/G026 | P0 | pytest:test_cr_0041_exception_framework.py | ready |
| TC-M13-DISP-01 | 開爭議合法 dispute_type→filed / 非法 422 | BR-M13 dual-sign | P0 | pytest:test_disputes_v2.py | ready |
| TC-M13-DISP-02 | 爭議雙簽 SoD review→cosign 不同人 resolved | BR-M13 SoD | P0 | pytest:test_disputes_v2.py | ready |
| TC-M13-WAR-01 | 保固 5-mode 起算 + 缺 anchor 422 | Q107/ADR-0044-v2 | P0 | pytest:test_warranty_5mode.py | ready |
| TC-M13-WAR-05 | 建保固索賠（有/無WO/冪等/跨租） | BR-M13-01/Q054 | P0 | pytest:test_create_warranty_claim.py | ready |
| TC-M11-01 | 退款單建立 happy + AR 連動 | BR-M11-01/P2-12 | P0 | pytest:test_create_refund_request.py | ready |
| TC-M11-03 | 退款 5-tier 門檻邊界解析 | BR-M11-02/ADR-0040 | P0 | pytest:test_refund_sod_5tier.py | ready |
| TC-M11-04 | 退款雙簽同 user 不可重簽（SoD 三維） | BR-M11-02 | P0 | pytest:test_refund_dual_sign.py | ready |
| TC-M11-05 | 不同 user 完成 + 高額自動雙簽 | BR-M11-02/ADR-009 | P0 | pytest:test_refund_dual_sign.py | ready |
| TC-M11-06 | 退款 SoD 端點層回歸 v2 | BR-M11-02 | P0 | pytest:test_refund_sod_endpoint.py | ready |
| TC-M11-07 | 取消費 6 階段 matrix S1~S5 | P2-06/ADR-0102 | P0 | pytest:test_cancellation_6stage.py | ready |
| TC-M11-10 | 報價 accepted→應收發票（不洩成本） | BR-M11-03/CR-0035 | P0 | pytest:test_cr_0035_invoice_billing.py | ready |
| TC-M12-05 | 師傅拆帳規則查詢 + RBAC 成本遮罩 | P2-14/CR-0037 | P0 | pytest:test_cr_0037_payout_rules.py | ready |
| TC-CR0025-01 | 忘記密碼 request 存在帳號建 token | CR-0025/ADR-0114 | P0 | pytest:test_password_reset.py | ready |
| TC-CR0025-02 | 忘記密碼 不存在帳號仍 200（枚舉防護） | CR-0025 | P0 | pytest:test_password_reset.py | ready |
| TC-CR0025-04 | 忘記密碼 confirm 改密碼標 used | CR-0025 | P0 | pytest:test_password_reset.py | ready |
| TC-CR0025-05 | confirm 過期 token 拒絕 | CR-0025 TTL30min | P0 | pytest:test_password_reset.py | ready |
| TC-CR0025-06 | confirm 已用/不存在 token + 單次用 | CR-0025 | P0 | pytest:test_password_reset.py | ready |
| TC-RBAC-01 | admin-reset-password 僅 admin（5角色矩陣） | BR-M17-01/Q110 | P0 | pytest:test_rbac_role_isolation.py | ready |
| TC-RBAC-02 | /technicians/me 僅 technician | BR-M17-01/Q112 | P0 | pytest:test_rbac_role_isolation.py | ready |
| TC-RBAC-03 | 建客戶/排程審批僅 admin+ops | BR-M17-01/Q113 | P0 | pytest:test_rbac_role_isolation.py | ready |
| TC-AUTH-01 | 認證 guard 缺/壞 token 401 / tenant 403 | BR-M17-01 | P0 | pytest:test_auth_guards.py | ready |
| TC-CONFIG-01 | M18 config draft + schema 驗證 + audit | BR-M18-01/G039 | P0 | pytest:test_config_m18.py | ready |
| TC-CONFIG-02 | M18 SoD initiator=approver 403 | BR-M17-02/G013 | P0 | pytest:test_config_m18.py | ready |
| TC-CONFIG-05 | M18 跨租戶 draft/讀取 403 | BR-M17-01 | P0 | pytest:test_config_m18.py | ready |
| TC-AUDIT-01 | audit_events v2 查詢/匯出 + 跨租 403 | Q055/Q114 | P0 | pytest:test_audit_v2_endpoint.py | ready |
| TC-M19-01 | Operational KPI 公式 happy + 無除零 | BR-M19-03/Q116 | P0 | pytest:test_operational_kpi.py | ready |
| TC-M19-03 | Reports v2 KPI/Revenue 200 + 跨租 403 | BR-M19-02/FR-0033 | P0 | pytest:test_reports_v2_endpoint.py | ready |
| TC-M19-04 | 報表匯出角色 gate（admin可/reviewer403/401） | BR-M19-02/G017 | P0 | pytest:test_export_report.py | ready |
| TC-M20-01 | AI 工具白名單強制 | BR-M20-02/A03 | P0 | pytest:agent test_tool_allowlist.py | ready |
| TC-M20-02 | AI 禁自動 convert_to_work_order（HITL） | BR-M03-02/ADR-0028 | P0 | pytest:test_pc_convert_to_wo.py | ready |
| TC-M20-03 | AI escalation→草擬 PC + dedup + flip | BR-M03-02 | P0 | pytest:test_escalation_to_draft_pc.py | ready |
| TC-M20-12 | SOP 改版 double-sign + family review gate | BR-M20-01/合約4.4(d) | P0 | pytest:test_sops_v2_endpoint.py | ready |
| TC-M20-15 | 情感警報建立/列出/升級 happy | M20/K3/合約4.4(a) | P0 | pytest:test_sentiment_alerts_v2_endpoint.py | ready |
| TC-XCUT-CI-01 | CI unit job 跑 226 unit 真綠（階段0 驗收） | CR-0038 §6 | P0 | pytest:test-suite.yml -m unit | ready |
| TC-XCUT-MIG-01 | schema_migrations 追蹤表 + drift smoke | CR-0038 §6/046 | P0 | manual | ready |
| TC-XCUT-GDPR-01 | createForgetRequest 兩階段生命週期 happy | GDPR/橫切#3 | P0 | pytest:test_gdpr_forget.py | ready |
| TC-XCUT-AUDIT-02 | 審批/狀態轉換 audit happy 斷言 | 橫切#2/Q011 | P0 | pytest:audit_log_service.py | ready |
| TC-XCUT-LINE-01 | LINE webhook 簽章驗證 4 情境 | M16/CR-0017 | P0 | pytest:test_cr_0017_line_webhook.py | ready |

**Alpha P1/P2 ready 補充（同跑於 component suite）**：TC-M01-04, TC-M03-07/08/09, TC-M04-04/06/07, TC-M05-09, TC-M06-04/05/08, TC-CR0039-04/07, TC-CR0040-03, TC-CR0041-05/06, TC-M07-01/02/04/05/07, TC-M10-04, TC-M11-02/08/09/11/12, TC-M12-02/07, TC-M13-DISP-03/04/WAR-02/03/04/06/RMA-01, TC-EXV2-01, TC-RBAC-04/05, TC-AUTH-03, TC-CONFIG-03/04/06/07/08, TC-NOTIF-01, TC-LINE-01/02/03, TC-CONV-01, TC-M19-02/07/09/10, TC-M20-10/13, TC-XCUT-GDPR-02/OPS-01/LINE-02。

#### Alpha gap（spec-but-not-implemented，須先補實作再測 — 詳見 §5）
TC-M01-06（Case 8 渠道實體）, TC-M01-07（1.5s debounce）, TC-M03-12（completeness_score≥0.85 gate）, TC-M03-13（PC 語意狀態層）, TC-M05-07（reschedule/reassign reason gate）, TC-M05-02（狀態機非法轉換窮舉 unit）, TC-CR0039-10（技師走 override 路徑 403 router guard）, TC-CR0039-11（grandfather 抽樣）。

---

### 3.2 BETA（真實多角色點測 — Irene + Johnson）

| id | title | spec_ref | pri | coverage | status |
|---|---|---|---|---|---|
| **TC-CR0039-09** | 技師 onsite 完工走正規硬閘（is_override=False） | CR-0039 §10 | P0 | pytest:test_work_orders_onsite_v2_endpoint.py | ready |
| **TC-CR0040-06** | media_v2 router 端到端套角色可見性 | BR-M09-02/CR-0040 §4 | P0 | manual | ready |
| **TC-CR0041-08** | 高風險異常→工單暫停→派工被擋（端到端） | BR-M15-03 | P0 | manual | ready |
| **TC-CR0041-07** | exception_cases_v2 RBAC：resolve 限管理角色 | CR-0041 §10 | P1 | manual | ready |
| TC-M03-17 | 後台 PC 列表 + 客戶 360 視圖 | M03/TI-M03-08 | P1 | playwright:problem-cards.spec.ts | ready |
| TC-M04-09 | 客戶端報價 accept/reject（真 LINE 連結） | CR-0032 PhaseC/Q033 | P0 | pytest:test_cr_0032_phasec_consumer.py | ready |
| TC-M05-04 | 取消 6 階段費用 S5 比例+材料精算 | 前期-P0-09 | P0 | pytest:test_cancellation_6stage.py | ready |
| TC-M11-13 | 真實退款雙簽流（NT$30k+，Irene+Johnson） | BR-M11-02/P2-28 | P0 | manual | ready |
| TC-M11-14 | 取消費 matrix 真實點測各階段 | P2-06/P2-28 | P0 | manual | ready |
| TC-M13-DISP-05 | 爭議雙簽全流程（後台 UI） | BR-M13 dual-sign | P1 | playwright:dispute-cosign.spec.ts | ready |
| TC-M13-WAR-07 | 保固索賠建立 + 後台保固頁 | Q054 | P1 | playwright:p0-create-warranty.spec.ts | ready |
| TC-AUTH-02 | AuthGuard 7 公開頁未登入可達冒煙 | CR-0038 §7.2 | P0 | manual | ready |
| TC-AUTH-04 | 角色 landing + route gating 禁區重導 | CR-0021 | P0 | playwright:role-ui-isolation.spec.ts | ready |
| TC-XCUT-TENANT-02 | 前端角色 landing/禁區導向 4 角色 | BR-M17-01 | P0 | playwright:role-ui-isolation.spec.ts | ready |
| TC-XCUT-GDPR-03 | GDPR forget queue 後台頁 | 橫切#3 | P1 | playwright:gdpr-forget-queue.spec.ts | ready |
| TC-XCUT-AUDIT-03 | audit-events 後台頁 tenant-scoped v2 | 橫切#2 | P1 | playwright:audit-events.spec.ts | ready |
| TC-XCUT-TENANT-03 | SOP 詳情頁不洩漏內部 UUID | Q026 | P1 | playwright:sop-internal-id-leak.spec.ts | ready |
| TC-CR0025-07 | 忘記密碼前端端到端可達 | CR-0025/§7.2 | P0 | manual | ready |
| TC-M20-04 | AI Forbidden 紅線（不報價/退款/保固轉真人） | BR-M20-02/K8 | P0 | manual:redline_gate.py | gap |
| TC-M02-04 | phone+LINE 去重（同人不誤建雙主檔） | BR-M02-01/G001 | P0 | none | gap |
| TC-M02-05 | 保固 Device record（serial mandatory 422） | BR-M02-02/ADR-0053 | P0 | none | gap |
| TC-M03-16 | 進線→AI→PC→WO→結案 端到端 E2E | e2e-main-flow | P0 | playwright:cr-0022-hitl.spec.ts(各段) | gap |
| TC-M03-14 | PC 照片完整度 gate + line_gateway 收圖 | Q022-024 | P1 | none | gap |
| TC-M07-03 | 師傅 onboarding 必填（bank/skill/brand/user_id） | BR-M07-01/G004 | P0 | pytest:test_technicians_onboard_v2 | gap |
| TC-M08-01 | GPS 到場事件 + geofence | BR-M08-01/Q056 | P0 | manual | gap |
| TC-M12-08 | 師傅看自己月結單 + 提爭議 | Q097/P2-28 | P0 | manual | gap |
| TC-CONV-02 | 對話可見性分流（品牌/會計/客戶頻道隔離） | BR-M16-01/Q076 | P0 | none | gap |
| TC-M05-10 | 付款/報價確認 gate 控派工 | BR-M05-03/前期-P0-04 | P0 | none | **blocked** |
| TC-M06-06 | 接單 SLA 計時 + 逾時自動改派 | BR-M06-03/前期-P0-05 | P0 | none | **blocked** |
| TC-M05-13 | E2E 主流程冒煙（含付款 gate+SLA） | Q009 | P0 | manual | **blocked** |
| TC-M11-16 | payments 表 + 三軌支付收款核心 | Flow12/Q088 | P0 | none | **blocked** |
| TC-M11-19 | payment 核銷到 WO/訂金/尾款/退款 | BR-M11-01/P2-01 | P0 | none | **blocked** |
| TC-XCUT-LINE-03 | LINE 進線→Customer/PC 建案鏈路 | BR-M01-02/Q008 | P0 | none | gap |

**Beta P1 gap/blocked 補充**：TC-M02-07, TC-M03-10/11/15, TC-M04-10/11, TC-M06-09, TC-M08-05, TC-M09-04, TC-M10-01/02, TC-M11-15/17/18, TC-M12-09/10/11/12, TC-CR0041-09/10, TC-NOTIF-02, TC-CONV-03, TC-M19-05/06/11/12, TC-M20-05/06/07/08/09/11/20, TC-XCUT-CI-03, TC-XCUT-MIG-02/03, TC-XCUT-DEPLOY-01/02, TC-XCUT-TENANT-01, TC-XCUT-AUDIT-01, TC-XCUT-LINE-04/05。

---

### 3.3 RC（本期非重點，僅標出）
TC-M02-06（Site Group）, TC-CR0039-12（用料/教學完工套件）, TC-M05-11（完工六段細狀態）, TC-M06-07（搶單池 grab-order）, TC-M07-08（多維績效排序）, TC-M08-02/03/04（geofence/不在場/scope tier）, TC-M09-05（影片 gate）, TC-M10-03/05/06（庫存 gate/序號保固反查/瑕疵料）, TC-M11-20（LINE Pay）, TC-M12-13（月結 cutoff cron）, TC-FIN-RC-01（金流 SoD 全回歸）, TC-FIN-RC-02（k6 效能）, TC-M13-RMA-02（RMA 回寫師傅評分）, TC-M17-IT-01（IT 臨時授權）, TC-M17-ROLE-01（角色矩陣正規化）, TC-M18-EFFDATE-01, TC-WEB-MW-01（server-side middleware）, TC-M20-16（K3 ≥90%）, TC-M20-17（eval pipeline 100%）, TC-M20-18（影像辨識禁用）, TC-M20-19（AI 金流護欄）, **TC-XCUT-TENANT-04（100-mutation 0 leakage + RLS）**, TC-XCUT-AUDIT-04（hash-chain 篡改偵測）, TC-XCUT-GDPR-04（7d SLA）。

### 3.4 GA（本期非重點）
TC-FIN-GA-01（上線冒煙會計 dashboard）, TC-M13-RMA-03（RMA case 編號）, TC-M13-RMA-04（7 分類責任矩陣）, TC-M13-RMA-05（RMA 結果連帳務）, TC-M18-IMPORT-01（初始建置匯入）。

---

## 4. 覆蓋 Dashboard

### 4.1 status 統計（全 8 領域，~150 唯一 TC）

| status | 計數 | 意義 |
|---|---|---|
| **ready** | ~88 | 可跑且綠（Alpha 自動 + Beta 已有 spec/pytest） |
| **gap** | ~45 | 缺實作或缺測試（spec 在、code 不在 或 測試未補） |
| **blocked** | ~17 | 依賴未建（payments 金流 / SLA 引擎 / nightly CI / RLS / 真 LINE channel） |

### 4.2 各 stage P0 happy-path 覆蓋率

| stage | P0 總數 | ready | gap | blocked | P0 自動覆蓋率 |
|---|---|---|---|---|---|
| **Alpha** | ~58 | 50 | 8 | 0 | **86%**（8 gap 為 spec 缺口，§5） |
| **Beta** | ~22 | 11 | 6 | 5 | **50%**（多角色 manual + 5 金流/SLA blocked） |
| RC | ~10 | 0 | 5 | 5 | 0%（本期非重點） |
| GA | ~5 | 0 | 4 | 1 | 0%（本期非重點） |

### 4.3 可信綠燈（本 session 新增，實測確認）

- **226 unit 真綠**：`cd api && uv run pytest -m unit --collect-only -q` → **226/1191 collected（965 deselected），無 `No module named harness` ERROR**（階段0 修復驗收）。
- **CR-0039** 8 案、**CR-0040** 6 案、**CR-0041** 6 案 component（live DB）真綠 — 完工硬閘 / Evidence 治理 / 異常 hold 是 Beta 最強驗收面。
- **password_reset 8 案** 由 BROKEN→ready（035/046 補套 dev DB）。
- **退款/取消費 SoD**（refund 雙簽+5-tier+三維 + cancellation 6 階段）+ **保固 5-mode**（32 案）+ **dispute v2**（33 案）皆 ready。
- **e2e specs 確認存在**：role-ui-isolation / dispute-cosign / gdpr-forget-queue / audit-events / p0-create-warranty / warranty-claims-v2 / sop-internal-id-leak。

---

## 5. Alpha Exit 阻塞清單（擋退出的 P0 spec 缺口）

這些是 **spec 要求但 code 未實作**，無法靠跑既有 pytest 變綠，須先補實作（多數要先跑 CIA）再測。會議定調 Lite 到 Beta，下列除金流/SLA 外建議優先補：

| # | 缺口 | TC | grep 實證 | 阻塞性 | 建議 |
|---|---|---|---|---|---|
| 1 | **completeness_score ≥0.85 轉 WO gate 完全未實作** | TC-M03-12 | `grep completeness_score=0`；convert-to-WO 無 gate | **Alpha exit 阻塞** | 三層欄位定義+計分函式+阻擋 gate+測試（先 CIA） |
| 2 | **付款/報價確認 gate 控派工** | TC-M05-10 | `grep payment.gate=0`；assign 無 quote.accepted 檢查 | Beta 整鏈斷點 | **blocked 依賴 payments 表**；會議定調 Beta 綠燈後動 P2 |
| 3 | **接單 SLA 計時 + 逾時自動改派** | TC-M06-06 | `grep acceptance_sla/auto_reassign=0` | Beta 整鏈斷點 | **blocked**；須建 accept_deadline + 逾時 reassign |
| 4 | **PC 照片完整度 gate + line_gateway 收圖** | TC-M03-14 | line_gateway 只收 TextMessage，圖片丟棄 | Beta 點測前置 | line_gateway 接 Image/Video + media gate（前置條件） |
| 5 | **Case 8 渠道 source_channel 實體** | TC-M01-06 | ConversationChannel 僅 3 值，無 Case 級實體 | spec 缺口 | 建 Case 實體（先 CIA），非 Lite 必需可標 RC |
| 6 | **phone+LINE 去重** | TC-M02-04 | customer_service 只查 line_user_id | P0 誤建風險 | 補 phone+line match/merge（Beta 點測誤建率） |
| 7 | **師傅 onboarding 必填 + 寫 user_id** | TC-M07-03 | create 不寫 user_id、無 bank/skill/brand 欄 | FR-0044 BROKEN | 補必填欄 + 寫 user_id（否則真表 JOIN 404） |
| 8 | **對話可見性分流** | TC-CONV-02 | `grep visibility/audience=0` | P0 阻擋（品牌洩內部成本） | 補 visibility scope 欄 + 過濾（先 CIA） |

> **判定**：嚴格 Alpha exit 唯一硬阻塞 = #1（completeness gate，零外部依賴可立即補）。#2/#3 依賴金流/SLA，會議已定調延後 → Alpha exit 對這兩項採**業主豁免**，Beta 整鏈在派工段標手動跳過。#7 建議補（否則師傅真表測試 404）。

---

## 6. Beta 點測腳本（給 Irene + Johnson）

> 環境前置：先跑 `./scripts/dev/redeploy-local.sh`（rebuild→up→migrate→smoke 9 項全過）+ 載入 seeds + mock LINE channel。**勾不過的項目對照 §5 阻塞清單**。

### A. 主流程（進線→完工硬閘）— Johnson 派工側 / Irene 客服側
- [ ] **A1 進線建案**：客戶用 LINE 傳症狀（不報品牌）→ AI 追問品牌/型號（TC-M03-11）。⚠️ 若 webhook 不建 Customer/PC（TC-XCUT-LINE-03 gap），改由客服後台手動建 PC。
- [ ] **A2 AI 草擬卡**：確認後台「待轉 WO 佇列」出現 source=ai_line 草擬卡，帶「AI 草擬」badge + 待補欄位 hint（TC-M03-17）。
- [ ] **A3 客服確認轉 WO**：補齊地址 → 轉 WO；**缺地址應被擋 422**（TC-M03-04）。
- [ ] **A4 報價**：建報價 → 超門檻需 submit→approve→send；客戶端 LINE 連結點開 **看不到 unit_price/成本**，只見實收（TC-M04-08）。
- [ ] **A5 客戶 accept/reject**：客戶點 accept → 報價 accepted；點 reject → decline（TC-M04-09）。⚠️ 條款/同意勾選文案可能裸金額（esales-Q12 MISSING）。
- [ ] **A6 派工**：Johnson 手動/自動派工，audit 記 override（TC-M06-03）。⚠️ 付款 gate（TC-M05-10）與接單 SLA（TC-M06-06）blocked → 此段不驗逾時改派。
- [ ] **A7 完工硬閘**（CR-0039 重點）：師傅 onsite 完工提交——
  - [ ] 只傳 2 張照片 → **擋下 INSUFFICIENT_PHOTOS**（TC-CR0039-09）
  - [ ] 無客戶簽名 → **擋下 SIGNATURE_REQUIRED**
  - [ ] 安裝案無 serial → **擋下 SERIAL_REQUIRED**；維修案無 serial 放行
  - [ ] 3 照片+簽名+（install 時 serial）齊 → 完工通過
- [ ] **A8 主管 override**：Irene/主管角色用 override+reason 強制結案 → 通過且稽核串含 COMPLETE_OVERRIDE+角色（TC-CR0039-09）；**技師角色走 override 路徑應 403**（TC-CR0039-10，建議先補 router guard）。

### B. Evidence 角色可見性（CR-0040）— Irene 多角色交叉
- [ ] **B1 品牌帳號**登入 Evidence 面板：完工工單 media 清單**看不到客戶家中環境照**（door_check_before/completion_before），只見成品照（completion_after）與爭議照（TC-CR0040-01）。
- [ ] **B2 品牌點開/下載**隱藏照 → 回 **404**（不洩漏存在性，TC-CR0040-02）。
- [ ] **B3 admin 帳號**同工單 → 看到全部 4 張。
- [ ] **B4 會計帳號** → 看不到 door_check_before，看得到 completion_after（TC-CR0040-03）。

### C. 異常框架（CR-0041）— Johnson 派工側 / Irene 核准側
- [ ] **C1 開高風險異常**：對進行中工單 open `appearance_refused`/safety（high severity）→ 工單 high_risk_hold=TRUE（TC-CR0041-08）。
- [ ] **C2 hold 擋派工/完工**：嘗試 assign 或 complete 該工單 → 回 **422 HIGH_RISK_HOLD**。
- [ ] **C3 resolve 清 hold**：選 return_path（reschedule/reassign/cancel…）resolve → hold 解除可繼續（TC-CR0041-04）。
- [ ] **C4 RBAC 邊界**：Irene 以 supervisor resolve 成功；以 technician 角色 resolve → **403**（TC-CR0041-07）。
  - ⚠️ 前端異常 inbox 頁未建（TC-CR0041-10 gap）→ 本輪走 API/Postman，approval_inbox 尚未聚合 exception_case。

### D. 金流多角色（退款/取消費）— Irene 會計 + Johnson 主管
- [ ] **D1 退款雙簽**：對 NT$30k+ 退款，A 角色發起+第一簽 → B 角色第二簽核准 → 執行；**同帳號連簽被擋 403**；audit 顯示兩簽人+時間+退款分類（TC-M11-13）。
- [ ] **D2 取消費 matrix**：對不同階段工單（未確認/已派未出發/已出發/已到場/已施工）執行取消 → 系統算 0/取消費/車馬費/檢測費/部分完成費，金額符 P2-06 matrix，主管可 override 留 reason（TC-M11-14）。
  - ⚠️ 退款 thresholds / 取消費值仍硬編（TC-M11-15 gap，建議仿 CR-0036 搬進 M18 config）。

### E. 權限與可達性 — 兩人各自登入驗
- [ ] **E1 角色 landing**：dispatcher/cs/ops/admin 各登入，進禁區被導 dashboard（TC-AUTH-04）。
- [ ] **E2 公開頁**：未登入逐一開 `/ /login /tech-login /vendor-login /register /forgot-password /reset-password` 皆不被踢回 login（TC-AUTH-02）。
- [ ] **E3 忘記密碼**：開 /forgot-password 提交 email（enumeration-safe 訊息）→ 點 email 連結 /reset-password?token= 設新密碼 → 可登入（TC-CR0025-07）。
- [ ] **E4 GDPR queue**：後台 forget queue 狀態篩選 + cooldown 倒數 + hard-delete 按鈕僅 cooldown 過才 enabled（TC-XCUT-GDPR-03）。

---

## 7. 建議執行順序 + 工具對接

### 7.1 Alpha 自動（按依賴順序）
1. **CI unit gate（零環境）**：`cd api && uv run pytest -m unit` → 確認 226 真綠（TC-XCUT-CI-01）。agent 紅線：`cd agent && pytest tests/test_tool_allowlist.py test_transfer_to_human.py`。
2. **起 component 環境**：`./scripts/dev/redeploy-local.sh`（rebuild→up→**套全 migration 含 035/045/046/047**→smoke 9 項）。⚠️ component 測試需 live DB，CI PR-gate **不跑**（965 留 nightly，nightly job 未建 = TC-XCUT-CI-03 gap）。
3. **跑 CR component**（須先套 migration，否則 UndefinedTable FAIL）：
   ```
   cd api && uv run pytest -m component \
     tests/test_cr_0039_completion_gate.py \
     tests/test_cr_0040_evidence_governance.py \
     tests/test_cr_0041_exception_framework.py \
     tests/test_cr_0037_payout_rules.py \
     tests/test_rbac_role_isolation.py \
     tests/test_config_m18.py \
     tests/test_disputes_v2.py tests/test_warranty_5mode.py \
     tests/test_refund_*.py tests/test_cancellation_6stage.py
   ```
4. **migration drift**：`./scripts/dev/redeploy-local.sh --smoke-only` 第 4f 項 `count(schema_migrations) ≥ 47`（TC-XCUT-MIG-01）。

### 7.2 Beta Playwright E2E（staging stack + mock LINE）
```
cd web && npx playwright test tests/e2e/admin/role-ui-isolation.spec.ts \
  dispute-cosign.spec.ts gdpr-forget-queue.spec.ts audit-events.spec.ts \
  sop-internal-id-leak.spec.ts p0-create-warranty.spec.ts warranty-claims-v2.spec.ts
```
+ 補建（gap）：進線→PC→WO→結案串接 spec（TC-M03-16）、reports.spec.ts（TC-M19-08）。

### 7.3 人工點測（§6 checklist）
- Irene：Evidence 角色可見性（B）、退款雙簽（D1）、異常核准（C4）、忘記密碼（E3）。
- Johnson：完工硬閘（A7/A8）、派工（A6）、異常 hold→派工被擋（C1-C3）、取消費（D2）。

### 7.4 blocked 前置（本期非重點，標出依賴）
- **payments core 表**（grep `CREATE TABLE payment=0`）→ 解鎖 TC-M05-10/M11-16~19/M12-12 + E2E 整鏈（TC-M05-13）。
- **SLA 引擎 accept_deadline + auto_reassign** → 解鎖 TC-M06-06/07。
- **nightly CI job**（postgres container + 全 migration + `-m component,contract`）→ 解鎖 Beta exit 客觀判定（TC-XCUT-CI-03）。
- **真 LINE channel token + per-tenant channel 主檔** → 解鎖 TC-LINE-04/XCUT-LINE-04。

**關鍵交付檔路徑**：
- 測試：`/Users/imding1211/project/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/api/tests/`（pytest）、`/Users/imding1211/project/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/web/tests/e2e/admin/`（Playwright）
- 缺口依據：`/Users/imding1211/project/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/docs/4-exploration/CR-0038-gap-inventory-20260617.md`
- 部署冒煙：`/Users/imding1211/project/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/scripts/dev/redeploy-local.sh`
- CI：`/Users/imding1211/project/Smart-Lock_AI_Support_Service_Dispatch_SaaS_Platform/.github/workflows/test-suite.yml`
