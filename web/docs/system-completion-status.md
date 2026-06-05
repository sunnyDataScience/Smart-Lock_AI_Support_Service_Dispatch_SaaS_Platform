# Smart Lock 工單系統完成度總覽

> 跨前端 / 後端 / Realtime / Workflow / 架構遷移的整體進度盤點。
> 每次開發完成後更新本文件，保持與 CR-0004 §8 進度區、CHANGELOG `[Unreleased]` 同步。

**最後更新：** 2026-06-05（Flow 4 admin 補料管理彙整 endpoint 落地 — 新 `GET /tenants/{tid}/material-requests` 跨工單列活躍缺料事件，urgency 排序；Flow 4 80% → 85%，剩前端彙整頁待下輪）
**對應分支：** `feat/admin-material-requests-list-endpoint`
**對應 reports：** v1.0.0 → v1.36.0（產品 MVP）+ CR-0003 P0-P3.5 ✅ + CR-0004 Track B S1-S7

---

## 總體：**約 89%**

```
██████████████████████████████  89%
```

> 6/04 微幅上修（88% → 89%）— P3.5 經取證收尾，CR-0003 階段往前推進一格；其餘維度持平。產品 MVP 本身沒有退步。

| 維度 | 完成度 | 變化（vs 2026-05-06）|
|:---|:---:|:---:|
| **Phase 5-7 產品 MVP**（V2.0 派工 + 會計）| **~95%** | 持平（無新增 MVP 功能）|
| **Phase 8 UAT 上線** | **0%** | 持平 |
| **架構遷移**（CR-0003 P0-P3.5 + CR-0004 Track B）| **~88%** | **新增**（Track B 7/7 done，**P3.5 ✅ 100%**，P4 未啟動）|
| **Phase II SaaS 模組**（9 個 placeholder FR）| **0%** | **新增** |

| Phase | 04-29 | 05-06 | **06-02** | 變化 |
|:---|:---:|:---:|:---:|:---:|
| Phase 5 V2.0 設計（W18-W19）| 85% | 97% | **97%** | — |
| Phase 6 派工 MVP（W20-W24）| 50% | 97% | **97%** | — |
| Phase 7 會計+整合（W25-W29）| 70% | 93% | **93%** | — |
| Phase 8 UAT 上線（W30-W31）| 0% | 0% | **0%** | — |
| **Phase 9 架構遷移**（CR-0003 + CR-0004）| — | — | **~85%** | **新維度** |

---

## 1. 前端覆蓋（spec 對照）

| 區域 | 完成度 | 說明 |
|:---|:---:|:---|
| **管理員後台**（A0-A37）| **~98%** | 61 admin/web 頁面（自 41 增至 61，新增 v2 對應視圖）；候選詳情 drawer / SOP 績效真實化次要項仍缺 |
| **技師端 PWA**（T0-T11）| **100%** | 12 頁全完成 + 6 個 subflow + 改期日曆 + 排班 |
| **通知中心**（G1）| **100%** | 全頁面 + Drawer + Bell + BroadcastChannel 跨 tab 同步 |
| **A32 AI 推理**（SSE）| **100%** | 對話頁逐 token 串流面板 |
| **PWA / 桌面 guard** | **100%** | manifest + 4 SVG icon + 桌面顯示 QR Code |
| **Caller 遷移 v1 → v2** | **~93%** | P3 track-A 完成 + P3.5 Track-B ✅ 100%；**P3 收尾 wave-1（2026-06-04）**：admin/schedule-requests reject 遷 v2、customers docstring 同步。**CR-0005 step 3/3 export caller（2026-06-04）**：knowledge-base/cases :export 從 v1 async-job 遷 v2 同步 CSV stream，scope dropdown 簡化為單 button。剩 41 個真實 v1 caller，分類：(a) BUILD_V2 前置依賴（KB manuals upload/sop-drafts、technicians/me self-service、accounting settlements、public scope-change） (b) agent-coupled 待 P4-T1（refunds/warranty/problem-cards） (c) 雜項（settings auth/change-password、api-status debug 頁、accounting recon dual-sign UX backlog）|

---

## 2. 後端 API（73 routers — v1 + v2 雙軌共存）

| 模組 | 完成度 | 備註 |
|:---|:---:|:---|
| 工單狀態機（accept/complete/cancel/assign/escalate/confirm/reschedule）| **100%** | v2 endpoints 已落地（`work_orders_v2`, `work_orders_ops_v2`）|
| 4 個 subflow endpoints（T5-T8）| **100%** | scope-change/material-request/delay/door-check |
| 5 個排班 endpoints（T10）+ admin 審核 3 個 | **100%** | — |
| Dispute decision | **100%** | **+ v2 dual-sign 狀態機**（Track B S2，FR-0013）|
| Refund decision + 雙簽流程 | **100%** | v1.29.0；**2026-06-04 deep audit 確認**：dual-sign 狀態機 (pending → csm_approved → approved) + 同 user 不可雙簽 (DUAL_SIGN_SAME_USER 409) + approval_chain JSONB audit + WS publish /realtime/refunds + admin/refunds/page.tsx v2 tenantPath；**agent 自動退款已於 CR-0009 ADR-0106 遷 v2**（refunds_v2:150 `:agent-initiate` single-actor，原「暫續用 v1」stale claim 移除）|
| 認證（JWT、tenant、RBAC）| **100%** | P4 規劃 auth 扁平化 |
| WebSocket server + ACL（JWT/tenant/RBAC）| **100%** | — |
| 媒體上傳 endpoint | **100%** | v1.25.0；含 `media_v2`（P2-W6） |
| Inventory low-stock 背景偵測 job | **100%** | v1.28.0 |
| SLA 引擎（quote/dispatch/response）| **100%** | v1.33.0 |
| **M18 Runtime Config Governance** | **100%** ✅ | Track B S1，saas.config_* 4 表 + 7 endpoints + SoD/ACL/rollback |
| **Reconciliations v2** | **100%** ✅ | Track B S2 上半，dual-sign（CSM → ops_manager co-sign）+ settlement dual-write |
| **Disputes v2** | **100%** ✅ | Track B S2 下半，FR-0013 狀態機 + dual-sign close + reopen lineage |
| **Inventory v2**（row-lock 扣庫存）| **100%** ✅ | Track B S3，FR-0007 + ADR-0052/0053；FOR UPDATE 交易 |
| **Pricing-rules v2** | **100%** ✅ | Track B S4，路徑 C + change_request 審計 |
| **Data-corrections v2** | **100%** ✅ | Track B S5，方案 B 就地補 tenant_id + 4 態 |
| **Resolution v2 suggest** | **100%** ✅ | Track B S6，sub-resource C4 |
| **Vouchers-void v2** | **100%** ✅ | Track B S7，紅字沖銷 append-only + hash chain（ADR-VCH-001/002）|

---

## 3. 即時通訊（10 個頻道前端整合 + 9 個 WS server）

| 頻道 | 前端訂閱 | 後端 server | 後端 publish |
|:---|:---:|:---:|:---:|
| `/realtime/notifications/{user_id}` | ✅ | ✅ | ✅（schedule resolve）|
| `/realtime/pool/{tech_id}` | ✅ | ✅ | ⏳（無觸發 service）|
| `/realtime/dispatch-queue` | ✅ | ✅ | ✅（8 個 wo events）|
| `/realtime/work-orders/{id}` | ✅ | ✅ | ✅（同上）|
| `/realtime/diagnostics/{conv_id}`（SSE）| ✅ | ⏳ | ⏳ |
| `/realtime/sla-alerts` | ✅ | ✅ | ✅（v1.33.0 SLAMonitor 背景偵測）|
| `/realtime/refunds` | ✅ | ✅ | ✅ |
| `/realtime/disputes` | ✅ | ✅ | ✅ |
| `/realtime/inventory/low-stock` | ✅ | ✅ | ✅（v1.28.0 背景偵測 job）|
| `/realtime/rbac` | ✅ | ✅ | ✅（role_service.update_role_permissions:457 已 publish；2026-06-04 補 mount RbacChangedBanner 至 AuthGuard）|

---

## 4. 使用者 Workflow 覆蓋（spec 14 個 Flow + Track B dual-sign）

| Flow | 完成度 | 缺口 |
|:---|:---:|:---|
| Flow 1 Happy Path | **100%** | — |
| Flow 2 拒單重派 | **100%** | — |
| Flow 3 範圍變更 | **85%** | proposal INSERT scope_changes + token mint 落地 (gap #1+#2 解)；剩 15% LINE Flex push 待 CR-0017 |
| Flow 4 缺料 | **100%** | e2e 完成：list endpoint + admin page + supply_arrived 收尾 + UI 標記按鈕 |
| Flow 5 延遲通知 | **100%** | **2026-06-04 deep audit 確認**（複用 Flow 3/6 方法論）：`work_order_service.notify_delay:1553` 全鏈路完整：(1) INSERT work_order_events `event_type='delay'` + delay_minutes payload（line 1611）/ (2) UPDATE work_orders.updated_at（line 1617）/ (3) `_audit_action('work_order.delay_notified')`（line 1622）/ (4) `line_push_service.push_to_work_order_customer` 真實 LINE push（line 1636，`push_message` AsyncMessagingApi 含 retry+backoff+audit）/ (5) `_publish_and_return(event_type='work_order.delay_notified')` WS publish（line 1643）/ (6) role guard（technician 只能 notify 自己單 line 1597）+ state machine guard（_SUBFLOW_FROM line 1590）。Web caller `my-orders/[id]/delay/page.tsx:74` 用 tenantPath v2 |
| Flow 6 退款雙簽 | **100%** | csm_approved 中介態 + 同 user 不可雙簽 + WS 推送 |
| Flow 7 爭議 | **100%** | 雙方證據上傳 + 縮圖瀏覽 + 仲裁決定全鏈路 |
| Flow 8 二次派工 | **100%** | reassign backend + frontend e2e 完成 (`_REASSIGN_FROM={assigned,accepted,in_progress}` + service + endpoint + 雙表 audit + WS publish + 前端分流) |
| Flow 9 客訴升級 | **100%** | escalate-to-work-order endpoint + 前端 EscalateAlertModal + i18n e2e 完成 |
| Flow 10 門面檢核 | **100%** | T8 + admin 縮圖瀏覽完成端到端 |
| Flow 11 客戶不在場 | **100%** | T11 提案 + LINE Flex RSVP + customer-confirm/reject endpoints + WS 推回技師 |
| Flow 12 金流支付 | **0%** | **2026-06-05 deep audit 校正**（推翻 60-80% 粗估）：payments 表 + endpoint + LINE Pay webhook + 客戶 LINE 支付頁全 0；對齊 [`CR-0011-fr-0011-consumer-payment-cia.md`](../../docs/_audit/CR-0011-fr-0011-consumer-payment-cia.md) 8 HD 待業主裁決。**Build blocked by CR-0011**。詳見 [`docs/_audit/flow-12-14-deep-audit.md`](../../docs/_audit/flow-12-14-deep-audit.md) |
| Flow 13 帳款異常 EX5 | **50%** | **2026-06-05 deep audit 校正**（推翻 60-80% 粗估）：reconciliation 正常流 (CSM→ops_manager dual-sign Track B S2) 100% ✅；disputes_v2 客訴流 100% ✅；但 EX5 例外流（帳款金額不符 / 缺單 / 雙簽超時）**無獨立 endpoint**，僅靠 admin 手動進 disputes 介面。待開 CIA — Domain model 變動 + Test plan 觸發。詳見 [`docs/_audit/flow-12-14-deep-audit.md`](../../docs/_audit/flow-12-14-deep-audit.md) |
| Flow 14 排班衝突 | **85%** | **2026-06-05 兩輪推進**：(1) deep audit 校正粗估 60-80%→70% / (2) **本輪 conflict → WS publish 鏈路落地**：新 service helper `_detect_schedule_conflict_and_publish(*, tenant_id, wo_id, technician_id, window_hours=2)` — 同技師 ±2hr 內 active wo（排除 completed/confirmed/cancelled + 排除自身）偵測 → INSERT `work_order_events event_type='schedule_conflict'` payload（含 conflicting_wo_ids / technician_id / window_hours / scheduled_at）→ WS publish `/realtime/dispatch-queue` type='schedule_conflict_detected'；接於 `assign_order` UPDATE 後 best-effort 呼叫（不阻擋 assign，DB/WS 失敗 swallow）；admin 已訂閱 dispatch-queue channel 無需新前端訂閱碼。**剩 15% 缺口**：補救流（建議時段 / 改派建議 / 升級）涉 LINE Flex push 與 Flow 11 同病 — 待 CR-0017 LINE Flex 重建一併處理；A37 衝突告警頁屬前端 admin UI follow-up。詳見 [`docs/_audit/flow-12-14-deep-audit.md`](../../docs/_audit/flow-12-14-deep-audit.md) |
| **🆕 Dual-sign Reconciliation**（Track B S2）| **100%** | CSM → ops_manager co-sign 跨兩 call SoD |
| **🆕 Dual-sign Dispute**（Track B S2）| **100%** | filed → in_review →(mediation)→ resolved\|escalated\|closed_withdrawn |
| **🆕 Voucher Void 紅字沖銷**（Track B S7）| **100%** | append-only + hash chain + require_keeper_role |

---

## 5. 架構遷移狀態（CR-0003 + CR-0004）

> 5/06 之後的最大工作量集中於此 — 把 `/api/v1/...` 全面遷至 `/api/v2/tenants/{tid}/...` 以支援 multi-tenant SaaS。

### CR-0003 全面 cutover

| 階段 | 內容 | 狀態 |
|:---|:---|:---:|
| **P0** | tenant-scoped v2 殼建立 + RFC7807 + RLS | ✅ 100% |
| **P1** | 8 大模組 spec 合併 | ✅ 100% |
| **P2** | tenant-scoped v2 router 落地（含 P2-W3 KB/SOPs、W4 work-orders ops、W5 invoices、W6 media + dispatch-logs）| ✅ 100% |
| **P3** | Caller 遷移 — track-A（agent + web 大部分）| ✅ 100% |
| **P3.5** | Track-B drop-in callers 補遺 | ✅ **100%**（取證：`grep "api/v1.*\{pricing\|recon\|inventor\|data.correction\}" web/src` 全 0；唯一例外 `accounting/page.tsx:189` 是 dual-sign UX 重設計，故意保留為產品 backlog）|
| **P4** | Cutover — 刪 legacy v1 + 型別重生 + auth 扁平化 + 刪 DeprecationMiddleware | ⏳ 0% |

### CR-0004 §8 Track B（8 業務模組建/遷 v2）

| Step | 模組 | 狀態 | Merge SHA |
|:---|:---|:---:|:---|
| S1 | config-m18 governance | ✅ | `2c4dbf1e` |
| S2 上 | reconciliations dual-sign | ✅ | `4c265155` |
| S2 下 | disputes dual-sign 狀態機 | ✅ | `b23edabf` |
| S3 | inventory row-lock | ✅ | `ba42c2ab` |
| S4 | pricing-rules 路徑 C | ✅ | `039f1038` |
| S5 | data-corrections 方案 B | ✅ | `2e47e904` |
| S6 | resolution engine v2 | ✅ | `f19d8485` |
| S7 | vouchers-void 紅字沖銷 | ✅ | `223f066e` |

**Track B 總成果**：7/7 done，**回歸測試 663+1 skip 全綠**，spec +33 path。

### 重大架構決策（5/06 → 6/02 新增）

| ADR | 標題 | 狀態 |
|:---|:---|:---:|
| ADR-0024 | Tier 1 戰術級重構 2026 Q2（hands-on 修正版）| accepted（supersedes ADR-0023）|
| ADR-0025 | Harness branching pipeline + module PHASE 常數 | accepted |
| ADR-0029 | Data-corrections review queue 治理 | accepted |
| ADR-0052/0053 | Inventory owner enum + serial_required 門檻 | accepted |
| ADR-0067 | M18 Runtime Config Governance | accepted（Phase 0）|
| ADR-0068 | M18 Anti-Corruption Layer | accepted |
| ADR-0101 | product_info extension final spec | accepted |
| ADR-0102 | Cancellation fee tiers v2 final spec | accepted |
| ADR-VCH-001/002 | Platform-as-voucher-keeper + 7y retention | accepted |
| ADR-PII-002 | Data minimization schema CI double defense | accepted |

---

## 6. 基礎設施與品質

| 項目 | 狀態 | 對應 Report |
|:---|:---|:---|
| DB 連線池統一（CloudSQL idle 修復）| ✅ | v1.22.1 / v1.23.0 |
| Output validator（品牌型號錯配 + 不重複追問）| ✅ | v1.24.1-v1.24.3 |
| Quick Reply 首訊推論 | ✅ | v1.24.2 |
| OpenAPI / TypeScript types 同步 CI | ✅ | — |
| BroadcastChannel 跨 tab | ✅ | v1.13.0 |
| WS 認證強化（JWT/tenant/RBAC）| ✅ | v1.22.0 |
| **architecture-lock.sh hook**（攔截 `from skills` import）| ✅ | ADR-0008 |
| **回歸測試套件**（pytest 663 cases）| ✅ | Track B S1-S7 全綠 |

---

## 7. Phase II SaaS 模組（9 個 placeholder FR — 全部未啟動）

> Phase II 是「完整 SaaS 平台」級別的功能，當前 V1.0 MVP 不含。

| FR | 標題 | 業務影響 |
|:---|:---|:---|
| FR-0044 | Technician Onboarding 與停權 | 技師生命週期（目前需手動加） |
| FR-0045 | Technician AP 月結 | 技師工資月結（會計手動算） |
| FR-0046 | 派工人 Commission 月結 | 派工員獎金 |
| FR-0047 | 品牌月結 + B2B Settlement | 跟品牌商對帳 |
| FR-0048 | RMA 品質回饋迴圈 | 退換貨資料回饋品牌商 |
| FR-0049 | Exception Approval Inbox（M15）| 主管核准收件匣 |
| FR-0050 | AI Governance & PRD Traceability | AI 行為治理 |
| FR-0051 | SOP Feedback Spiral 深化 | SOP 螺旋演進 |
| FR-0053 | DPO Forget / GDPR 遺忘權 | 法規合規（GDPR）|

### 仍處 draft 的 Phase I FR（4 個 — 細節未定）

| FR | 標題 | 卡在哪 |
|:---|:---|:---|
| FR-0011 | 消費者付款 V1.0 升級 | 金流方案 / 串接哪家 — **CR-0011 CIA opened 2026-06-04（8 HD 等業主裁；payments 表/endpoint 0 實作）** |
| FR-0012 | 技師月結撥款 V1.0 升級 | 同上 + AP 流程 — **CR-0012 CIA opened 2026-06-04（6 HD 等業主裁；`settlements_v2.trigger_monthly_settlement` 501 stub；HD-06 escrow 鏡像 CR-0011 HD-08）** |
| FR-0022 | 消費者端工單追蹤 | Web 版規格 — **CR-0013 CIA opened 2026-06-04（5 HD 等業主裁；Web 路徑已 100% 實作；ADR-0015 已 accepted → `blocked_by: Q3=C` stale；LINE rich menu 0%；HD-05 解 spec 401 vs code 404 衝突；準完工 status flip 候選）** |
| FR-0034 | AI Employee Charter / PRD 治理 | 整體 AI 治理框架 — **CR-0014 CIA opened 2026-06-04（4 HD 等業主裁；Phase II 骨架 + Q2=C 延後正當狀態；ADR-0028 accepted + safety_gate 已落地涵蓋 95% rule body；推薦維持 draft + acknowledged；Off-board Triggers 為 implementation gap，純 ops 流程）** |

> **2026-06-04**：FR-0019 動態 RBAC 角色管理 已 `draft → active`（CR-0010 取證 content-complete + ADR-0042 accepted + code 全部實作；業主拍 HD-01=a）。**CR-0010 HD-03=a batch 收尾**：CR-0011/0012/0013/0014 共 4 CIA 同日 opened，**共 23 HD 待業主裁**（CR-0011: 8 / CR-0012: 6 / CR-0013: 5 / CR-0014: 4）；其中 CR-0011 HD-08 ↔ CR-0012 HD-06 為同步裁決對（escrow 模型）；CR-0013 HD-05 為 critical spec/code 衝突解；CR-0014 推薦立場「維持 draft」。北極星 (1) 潛在推進空間：4 → 1（CR-0011/0012/0013 全 promote 成功時）或 4 → 0（含 FR-0034 強推）。

---

## 8. 主要尚未完成（剩 ~12%）

| 優先級 | 項目 | 工時 |
|:---:|:---|:---|
| **P0** | **P4 Cutover**（刪 legacy + 型別重生 + auth 扁平化 + 刪 DeprecationMiddleware；含全 web 殘留 30 個 v1 caller 收尾）| 3-5 天 |
| **P1** | **Reconciliation dual-sign UX rework**（v2 `:review` + `:co-sign` 兩步驟流；目前 `accounting/page.tsx` 仍打 v1 單簽）| 1-2 天 |
| **P0** | UAT（合約 1.2.8）| 計畫期程 |
| 🟡 P0 | 整合測試 / E2E Playwright | 持續 |
| P1 | A37 candidate detail drawer（排班熱力圖）| 半天 |
| ~~P1~~ | ~~RBAC 權限變更後端推送~~ ✅ | 2026-06-04 收工（取證後端 publish 已存在，補 mount banner）|
| P1 | Pool 即時推播觸發（前端訂閱已備）| 半天 |
| P1 | M18 Phase II — canary auto-advance / SLO halt（需 scheduler）| 數天 |
| P1 | 60d cron + 負值 DGS（reconciliations）| 數天 |
| P2 | 計價引擎 GUI / SOP 績效真實化 / 報表 metrics 擴充 | 數天 |
| P3 | Phase II 9 個 FR（commission/AP/B2B settlement/RMA/GDPR/...）| Roadmap |

---

## 結論

**5/06 → 6/02 一個月主要產出**：

1. ✅ **CR-0003 全面 cutover P0-P3** — tenant-scoped v2 architecture 全面落地
2. ✅ **CR-0004 §8 Track B S1-S7** — 8 個業務模組搬到 v2（含 dual-sign、row-lock、紅字沖銷等核心邏輯）
3. ✅ **新增 10+ ADR** 涵蓋治理、庫存、傳票、PII、M18 config
4. 🔄 **P3.5 補遺進行中**（4 個 web 模組 caller 待遷）
5. ⏳ **P4 cutover 待啟動**（清掉 v1 殘留 + auth 扁平化）

**接下來的關鍵路徑**：

1. **P3.5 補遺完成** → 解鎖 P4 cutover gate
2. **P4 cutover** → 真正完成 V2.0 multi-tenant SaaS
3. **Phase 8 UAT** → 上線
4. **Phase II 模組規劃** → Roadmap 決策（與業主對齊優先順序）

---

## 維護規則

- 每次合併 PR / 完成一個 milestone 後，**主 agent 必須更新本文件**
- 三大維度同步調整：完成度 % / 模組狀態表 / Workflow 覆蓋表
- 重大 milestone 時更新「最後更新」日期 + Phase 進度表
- 細粒度變更紀錄請查 `CHANGELOG.md [Unreleased]` + `docs/_audit/CR-NNNN-*.md` §8 進度區
- 新功能上線 / 架構決策 → 同步開 ADR（append-only）
