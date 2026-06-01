---
title: Spec ↔ Code 差異化分析報告（frozen V1.1 single source of truth vs 現行 api/ + web/）
date: 2026-06-01
status: active
author: Claude (Opus 4.8)
scope: 全 38 模組（ERP 20 + Chatbot 12 + Sync 6）+ 95 spec endpoint vs 139 code endpoint
authority: docs/ 為單一事實（業主 2026-06-01 裁決「spec 全贏 → 遷移 code」）
source_of_truth:
  - docs/architecture/api/openapi.yaml (v2.3.0, 30 paths)
  - docs/architecture/api/openapi-smart-lock-saas.yaml (1.0.0-phase1, 57 paths)
  - docs/analysis/fr/ (53 FR)
  - docs/analysis/br/ (122 BR)
  - docs/architecture/adr/ (75 ADR)
  - docs/architecture/data/ddl-migration-001-init.sql (53 tables)
  - specs/smart-lock-saas/handoff.md (V1.1)
related:
  - 第一個 vertical slice 實作見本報告 §7 波次 P1-A + 計畫檔
---

# Spec ↔ Code 差異化分析報告

> 對照基準：`specs/smart-lock-saas/handoff.md` V1.1（2026-05-28 frozen）。
> 本報告同時扮演 `.claude/rules/change-governance.md` 要求的 CIA（Change Impact Analysis）角色：§7 = impact/波次，§8 = 衝突裁決。

---

## §0 Executive Summary

### 核心事實（必讀）

**現行 `api/` 後端與 `web/` 前端，是針對一份「已被刪除的舊合約」建出來的。**

- 現行 `api/main.py:89` 仍宣告 `Contract SSOT: docs/02-design/specs/openapi.yaml`。
- 該檔已於 commit `8dca1db "chore(docs): cliff #4 — delete legacy docs/"` **整批刪除**。
- `api/models/generated.py`（datamodel-codegen, 2026-05-06）與 `web/types/api.generated.ts`（openapi-typescript）皆由該**已不存在的 spec** 生成。
- frozen V1.1 single-source-of-truth 已遷移到 `docs/architecture/api/`，內容是一份**實質演進過**的合約（tenant-scoped path、SoD headers、6 階段取消、5-mode 保固、三維退款 SoD、M18 config governance、sync/acl ACL 層……）。

結論：這不是「修幾個 bug」，而是**程式碼整體落後 frozen 合約一個世代**。需分波次遷移。

### 嚴重度分佈（endpoint 層）

| 狀態 | 數量 | 說明 |
|---|---:|---|
| ✅ 對齊（僅 path prefix 差 `/api/v1` vs `/tenants/{tid}`） | ~14 | 概念與欄位大致符合，差在 path scheme + SoD header |
| ⚠️ 部分（路徑/動詞/形狀不同，需改造） | ~16 | 如 cancel 無費用、close vs complete、quotes 缺 lifecycle |
| ❌ 缺（spec 有、code 完全沒有 REST 合約） | ~50 | quote lifecycle / dgs / change-requests / m18 / sync / acl / chatbot REST / sites / devices / brands / payments / exceptions |
| ➕ 多餘（code 有、spec 沒有的 legacy endpoint） | ~40 | dashboard/stats、notifications、sentiment、data-corrections、reschedule 家族、inventory、resolution… |

### 業務規則紅線缺口（14 條最高優先 constraint，詳見 §1）

- ❌ 取消費 6 階段（ADR-0102 / FR-0052）— **完全未實作**，只有 `status='cancelled'`
- ❌ 退款三維 SoD + 5-tier（ADR-0040 v2 / BR-REFUND-006）— 現為 legacy 2-step 雙簽@NT$100k
- ❌ 保固 5-mode（ADR-0044 v2）— 現為寫死 `purchase_date+90d`
- ❌ M18 staged rollout（ADR-0067）— 現為泛用 deep-merge config
- ⚠️ chatbot token cap = 1024（spec 要 1500，BR-A01-02）
- ❌ 報價有效期 14d/3d（BR-M04-05）— 未實作
- ❌ SoD headers（X-Initiator/X-Approver/X-Executor）— 未實作（用 approval_chain 替代）
- ⚠️ tenant 隔離靠 WHERE-clause + JWT，**無 RLS**（ADR-0030 要求 RLS policy）
- ⚠️ append-only / hash chain — approval_chain 是 JSONB append，**無 cryptographic hash chain**（ADR-VCH-002 / ADR-0064）

### 建議遷移順序（詳見 §7）

1. **P1-A（本 session 切片）**：Cancellation 6-stage — 跨 API/DB/audit/SoD/test 五維，作為**目標架構範式模板**。
2. **P1-B**：Refund 三維 SoD + 5-tier；Warranty 5-mode。
3. **P1-C**：報價有效期 14d/3d；chatbot token cap 1500。
4. **P2**：path scheme 全面遷移 tenant-scoped + SoD header 中介層 + RLS。
5. **P3**：補缺合約（quote lifecycle / m18 / sync / acl / dgs / change-requests / master data sites&devices&brands / chatbot REST）。

---

## §1 合約紅線 + value-decisions 對照（handoff §1 的 14 條）

| # | Constraint | Source | 現況 | 狀態 |
|--:|---|---|---|:--:|
| 1 | 負面情緒識別 ≥ 90% | 合約 4.4(a) / AC-CONTRACT-01 | agent sentiment 有，未見 90% gate/monitor | ⚠️ |
| 2 | 家族覆核員 100% + append-only ledger | 合約 4.4(d) / AC-CONTRACT-02 | `family_reviews` 有 CRUD；**無 hash chain ledger** | ⚠️ |
| 3 | PC 完整率 ≥ 85% | 合約 9.3 / AC-CONTRACT-03 | problem_cards 有；未見完整率 metric/alert | ⚠️ |
| 4 | AI 影像辨識禁用 violation = 0 | SOW 2.1(4) / AC-CONTRACT-04 | agent 多模態占位、無 vision API（符合）；未見 Forbidden Eval gate | ⚠️ |
| 5 | AI Forbidden Eval ≥ 95% block-deploy | AC-CONTRACT-05 | `/eval/forbidden/run`、`/chatbot/eval/runs` **未實作** | ❌ |
| 6 | Cross-tenant isolation ZERO leak | ADR-0030 / AC-CONTRACT-06 | WHERE-clause + JWT 隔離；**無 RLS policy** | ⚠️ |
| 7 | GDPR forget ≤ 7d | BR-PII-001b / FR-0053 / AC-CONTRACT-07 | `/dgs/forget`、`/dgs/evidence/*` **未實作** | ❌ |
| 8 | Cancellation 6-stage | ADR-0102 / FR-0052 / AC-V11-08 | 只有 `status='cancelled'`，**無費用/階段/師傅分支** | ❌ |
| 9 | Refund SoD 三維 (initiator≠approver≠executor) | BR-REFUND-006 / AC-V11-09 | legacy 2-step 雙簽@NT$100k，**無三維/X-headers/5-tier/refund_class** | ❌ |
| 10 | Warranty 5-mode + RMA 90d + B2B override | ADR-0044 v2 / AC-V11-10 | 寫死 `purchase_date+90d`，**無 warranty_mode enum** | ❌ |
| 11 | Chatbot reply token ≤ 1500 + truncate | BR-A01-02 / AC-V11-11 | config `max_tokens=1024`，無 truncate fallback | ⚠️ |
| 12 | 報價有效期 14d/3d | BR-M04-05 / AC-V11-12 | **未實作**（無 quote 有效期/狀態機） | ❌ |
| 13 | M18 staged rollout 5/50/100 + rollback ≤1min | BR-M18 / ADR-0067 / AC-V11-13 | 泛用 deep-merge config，**無 staged/rollback** | ❌ |
| 14 | 三層 rollback 各層獨立 SLA | rollback-plan / AC-V11-14 | ops 層，超出 code 範圍（部署腳本） | n/a |

---

## §2 Endpoint Traceability（95 spec paths）

> Code 全部掛 `/api/v1` 前綴（`api/main.py:106-144`）。spec companion 全部 tenant-scoped `/tenants/{tenantId}/...`。下表「Code」欄省略 `/api/v1` 前綴。

### §2.1 Spec A — `openapi.yaml`（v2.3.0, M01/M03/M07/M11/M15/M17/M20/A09 core）

| Spec path | operationId | Code 對應 | 狀態 |
|---|---|---|:--:|
| POST /webhook/line | lineWebhook | agent/app.py `POST /webhook` | ⚠️ 在 agent，path 不同 |
| POST/GET /problem-cards | createProblemCard | POST/GET /problem-cards | ✅ prefix 差 |
| GET/PATCH /problem-cards/{id} | — | GET/PATCH /problem-cards/{id} | ✅ |
| POST /work-orders | — | POST /work-orders | ✅ |
| POST /work-orders/{id}/close | — | /work-orders/{id}/complete | ⚠️ 名稱 close→complete |
| POST /work-orders/{id}/onsite/scope-change | — | /work-orders/{id}/scope-change | ⚠️ 缺 /onsite |
| POST /pricing/calculate | pricingCalculate | /pricing/calculate | ✅ |
| POST /quotes | createQuote | — | ❌ 無 quotes 模組 |
| POST /quotes/{id}:approve | approveQuote | — | ❌ |
| POST /quotes/{id}:send-to-customer | sendQuoteToCustomer | — | ❌ |
| POST /quotes/{id}/customer-confirm | customerConfirmQuote | — | ❌ |
| POST /quotes/{id}/reject | rejectQuote | — | ❌ |
| POST /quotes/{id}:supersede | supersedeQuote | — | ❌ |
| POST /quotes/{id}/retrospective-audit | retrospectiveQuoteAudit | — | ❌ |
| POST/GET/GET/PATCH/DELETE /contract-templates(/{id}) | — | — | ❌ M15 contract template 缺 |
| POST /dgs/evidence/{id}/purge | — | — | ❌ |
| POST /dgs/evidence/{id}/legal-hold | — | — | ❌ |
| POST /dgs/forget | — | — | ❌ GDPR forget 缺 |
| GET /dgs/policy/version | — | — | ❌ |
| POST /change-requests(+/{id}/approve) | — | — | ❌ M15 ChangeRequest 缺 |
| POST /sops/{id}/review/dual | — | sop-drafts PATCH /review | ⚠️ 形狀不同 |
| POST /sops/{id}/review/family | — | /family-reviews (POST/GET) | ⚠️ 形狀不同 |
| POST /eval/forbidden/run | — | — | ❌ Forbidden Eval gate 缺 |
| GET /vouchers/{id} | — | — | ⚠️ 只有 list + export |
| GET /vouchers | — | /accounting/vouchers | ✅ |
| POST /vouchers/{id}/void | — | — | ❌ 紅字沖銷缺 |
| GET /vouchers/export | — | /accounting/vouchers/{id}/export | ⚠️ 形狀不同 |
| GET /exports/{job_id} | — | — | ❌ async export job 缺 |

### §2.2 Spec B — `openapi-smart-lock-saas.yaml`（companion, M01-M18 / A01-A12 / S-M01-M06 / ACL）

| Spec path | Module | Code 對應 | 狀態 |
|---|:--:|---|:--:|
| GET /tenants/{tid}/channels(+/status) | M01 | — | ❌ |
| GET /tenants/{tid}/brands | M02 | — | ❌ brand master 缺 |
| POST/GET /brands/{bid}/models | M02 | — | ❌ model master 缺 |
| GET/POST /tenants/{tid}/customers | M04 | GET/POST /customers | ✅ prefix+tenant 差 |
| GET/POST /customers/{cid}/sites | M04 | — | ❌ site master 缺 |
| POST /sites/{sid}/devices | M04 | — | ❌ device master 缺 |
| GET/PATCH /devices/{did}/warranty | M13 | — | ❌ device-warranty 缺（只有 claims） |
| GET/POST /tenants/{tid}/technicians | M05 | GET /technicians；POST register(auth) | ⚠️ onboard 形狀不同 |
| POST /technicians/{tid}:suspend | M05 | — | ❌ 停權缺 |
| POST /tenants/{tid}/dispatch:plan | M06 | /dispatch/candidates + /auto-match | ⚠️ 近似 |
| POST /work-orders/{woId}:assign | M06 | /work-orders/{id}/assign | ✅ verb/path 差 |
| POST /work-orders/{woId}:accept | M06 | /work-orders/{id}/accept | ✅ |
| POST /work-orders/{woId}/onsite/arrival | M07 | — | ❌ 到場回報缺（有 door-check） |
| POST /work-orders/{woId}/onsite/completion | M07 | /complete + /signature | ⚠️ 拆成兩支 |
| **POST /work-orders/{woId}/cancel** | **M11** | **/work-orders/{id}/cancel** | **⚠️ 存在但無 6-stage → §7 P1-A 切片** |
| POST /tenants/{tid}/refunds | M11 | POST /refunds | ⚠️ 無 tenant/SoD/tier/class |
| GET /refunds/{rid} | M11 | GET /refunds/{id} | ✅ |
| POST /tenants/{tid}/payments | M11 | — | ❌ 消費者付款缺 |
| POST /tenants/{tid}/warranty-claims | M13 | POST /warranty-claims | ✅（但保固判定邏輯差，見 §4） |
| GET /partners/{pid}/dashboard | M14 | — | ❌ partner portal 缺 |
| GET /exceptions:inbox | M15 | — | ❌ 異常核准箱缺 |
| POST /exceptions/{eid}:approve | M15 | — | ❌ |
| GET /consumer/work-orders/{token} | M16 | /public/work-orders/{token}/status | ⚠️ path 不同 |
| GET/PUT /rbac/roles | M17 | GET /roles + PATCH /roles/{name}/permissions | ⚠️ 形狀不同 |
| GET /audit/events | M17 | GET /audit-logs | ✅ |
| POST /audit/exports | M17 | POST /audit-logs/export | ✅ |
| GET /m18/configs | M18 | GET /config | ⚠️ 泛用、非 namespace/version |
| GET/PUT /m18/configs/{ns}/{key} | M18 | — | ❌ |
| POST .../versions/{vid}:start-rollout | M18 | — | ❌ staged rollout 缺 |
| POST /m18/rollouts/{rid}:rollback | M18 | — | ❌ rollback 缺 |
| GET .../{ns}/{key}/audit | M18 | — | ❌ |
| GET /m18/config-read/{ns}/{key} | M18 | — | ❌ ACL config read 缺 |
| POST /chatbot/intake:debounce-check | A01 | (agent harness 內部) | ❌ 無 REST 合約 |
| POST /chatbot/agent:respond | A03 | (agent ReAct 內部) | ❌ 無 REST |
| POST /chatbot/rag:search | A04 | — | ❌ |
| POST /chatbot/guardrails:check | A05 | — | ❌ |
| POST /chatbot/problem-cards:draft | A06 | — | ❌ |
| POST /chatbot/handoff:request | A07 | — | ❌ |
| POST /chatbot/multimodal:image | A08 | — | ❌ |
| POST /chatbot/eval/runs(+/{id}) | A09 | — | ❌ |
| GET /chatbot/health | A11 | agent/app.py GET /health | ⚠️ path 不同 |
| GET/POST /kb/documents(+/{id}) | KB | /knowledge-base/cases + /manuals | ⚠️ 模型不同 |
| GET /kb/dynamic-lookup/serial-warranty | KB | — | ❌ |
| GET /kb/dynamic-lookup/project-unit-model | KB | — | ❌ |
| POST /sync/intake-capture | S-M01 | — | ❌ |
| POST /sync/facts-master | S-M02 | — | ❌ |
| POST /sync/pc-convert | S-M03 | — | ❌（code 有 /problem-cards/{id}/convert-to-work-order，非 sync 合約） |
| POST /sync/convert-to-wo | S-M04 | /problem-cards/{id}/convert-to-work-order | ⚠️ 近似、缺 human gate 合約 |
| POST /sync/dispatch | S-M05 | — | ❌ |
| POST /sync/evidence-writeback | S-M06 | — | ❌ |
| POST /acl/serial-control/lookup | ACL | — | ❌ |
| POST /acl/brand-warranty/inquire | ACL | — | ❌ |
| POST /acl/rma-partner/submit | ACL | — | ❌ |
| POST /tenants/{tid}/settlements/monthly | M12 | GET /settlements (list) | ⚠️ Phase II（spec 期望 501） |

### §2.3 Code 多餘 endpoint（spec 沒有的 legacy 表面，~40 條）

`dashboard/stats`、`notifications/*`(5)、`sentiment/alerts`(2)、`data-corrections/*`(4)、`dispatch-logs`、`reports/kpi|revenue|export`、`inventory/items`、`roles`、`media/*`(4)、`resolution/resolve`、`pricing/rules` CRUD(3, spec 只有 calculate)、`work-orders/{id}/reschedule*` 家族(6)、`work-orders/{id}/material-request|delay|door-check`、`technicians/me/*` schedule 家族、`disputes/*`(3)、`reconciliations`(2)、`invoices`(2)。

> 處置：spec 全贏不代表立刻刪這些 — 多數是 admin dashboard 實用功能。建議在 P3 對 spec 提 backlog（補進 companion 或標 out-of-scope），**不要靜默刪除可運作功能**（Never break userspace）。

---

## §3 FR Traceability（53 FR，摘要）

| FR | 標題 | 實作位置 | 狀態 |
|---|---|---|:--:|
| FR-0001 | LINE 報修受理 | agent/app.py webhook | ⚠️ 在 agent |
| FR-0002 | PC 智能分診 | problem_card_service | ⚠️ 部分 |
| FR-0003 | 自動派工演算法 | dispatch_service auto-match | ✅ |
| FR-0004 | 手動派工 + audit | dispatch assign | ✅ |
| FR-0005 | 技師接單出發 | work_orders accept | ✅ |
| FR-0006 | 到場拍照存證 | (door-check 近似) | ⚠️ 無 arrival |
| FR-0007 | 材料申請扣庫存 | /material-request + inventory | ⚠️ |
| FR-0008 | Scope Change | /scope-change + public respond | ⚠️ 缺三件套合約 |
| FR-0009 | 完工簽名雙方確認 | /complete + /signature + /confirm | ✅ |
| FR-0010 | 改約/延遲/取消 | reschedule/delay/cancel | ⚠️ cancel 無 6-stage |
| FR-0011 | 消費者付款 | — | ❌ /payments 缺 |
| FR-0012 | 技師月結撥款 | settlements (list) | ⚠️ Phase II |
| FR-0013 | 對帳爭議雙簽 | reconciliations approve | ⚠️ 無三維 |
| FR-0014 | 退款流程 | refunds | ❌ 缺三維/tier/class |
| FR-0015 | 保固申訴 | warranty-claims | ❌ 缺 5-mode |
| FR-0016 | SLA 2hr | sla_monitor | ⚠️ SUPERSEDED |
| FR-0017 | SOP 草稿審核 | sop-drafts | ✅ |
| FR-0018 | 客服接管三層 | conversations + resolution | ⚠️ |
| FR-0019 | 動態 RBAC | roles + WS rbac | ⚠️ 形狀不同 |
| FR-0020 | 稽核日誌匯出 | audit-logs + export | ✅ |
| FR-0021 | Dashboard/報表 | dashboard/reports | ✅ |
| FR-0022 | 消費者工單追蹤 | public/work-orders | ⚠️ path 不同 |
| FR-0023 | 錯誤頁/離線 | web 前端 | ✅ |
| FR-0024 | LINE Webhook HA | agent | ⚠️ SUPERSEDED |
| FR-0025 | 多模態理解 | agent multimodal | ⚠️ 占位 |
| FR-0026 | Debounce 合併 | agent harness debounce | ✅ 在 agent |
| FR-0027 | 品牌型號 Resolver | agent brand_match | ✅ 在 agent |
| FR-0028 | Skill-Gated ReAct | agent ReAct | ✅ 在 agent |
| FR-0029 | SKILL 知識庫 | agent product_info | ✅ 在 agent |
| FR-0030 | Guardrails | agent output_validator | ✅ 在 agent |
| FR-0031 | ProblemCard Bridge | agent → api PC | ⚠️ |
| FR-0032 | AI Eval/觀測 | quality_check | ⚠️ 無 REST eval gate |
| FR-0033 | 部署健康檢查 | /health | ✅ |
| FR-0034 | AI Charter (II) | — | n/a Phase II |
| FR-0035-0040 | Sync 6 模組 | — | ❌ 無 sync REST 合約 |
| FR-0041 | Customer/Site/Device Master | customers only | ⚠️ 缺 site/device |
| FR-0042 | Quote 內外部視圖 | — | ❌ |
| FR-0043 | M18 Admin Config | /config (泛用) | ❌ 缺 governance |
| FR-0044-0048 | Technician onboarding/AP/commission/RMA (placeholder) | 部分 | ⚠️ Phase II |
| FR-0049 | Exception Approval Inbox | — | ❌ |
| FR-0050-0051 | AI Governance/SOP Spiral (placeholder) | — | n/a Phase II |
| FR-0052 | **Cancellation Fee 6-Tier** | cancel (status only) | ❌ → §7 P1-A |
| FR-0053 | DPO Forget/GDPR | — | ❌ |

---

## §4 業務規則深差（6 大項）

### §4.1 Cancellation 6-stage（ADR-0102 / FR-0052 / BR-CANCEL-001..008）— ❌ 完全未實作
- **Spec**：伺服器端依 WO/quote 狀態機推算 6 階段（S1=0 / S1_5=0 / S2=300 / S3=車馬500-1200+取消費 / S4=+檢測300 / S5=partial 公式）；師傅 initiated 三段政策（首次免責 / 同月≥2 扣 weight / 不可抗力豁免）；reason code dictionary（13 codes，走 M18 config）；goodwill_waiver override（delta>50% 或歸零需主管）；SoD 三維 audit。
- **Code**（`api/services/work_order_service.py:418` `cancel_order`）：只 `UPDATE work_orders SET status='cancelled'`。無費用、無階段、無 reason_code、無師傅分支、無 audit 欄位。
- **修正**：見計畫 Part B（本 session 切片）。建 `cancellation` 表 + `cancellation_service.py` + tenant-scoped route + SoD headers + config reason_codes + audit。

### §4.2 Refund 三維 SoD + 5-tier（ADR-0040 v2 / BR-REFUND-006 / FR-0014）— ❌
- **Spec**：`initiator ≠ approver ≠ executor`（DB CHECK + X-* headers）；5-tier（L1≤1k/L2≤5k/L3≤20k/L4≤100k/L5>100k，L5=ops_director）；`refund_class` enum（product/labor/material/travel/inspection）必填；amount>0。
- **Code**（`api/services/refund_service.py`）：legacy ADR-009 2-step 雙簽，閾值寫死 `_DUAL_SIGN_THRESHOLD=100000`；只檢查「同人不可簽兩次」（二維，非三維）；無 tier、無 refund_class、無 X-headers。註解明言「本 phase 不實作多步雙簽流程」。
- **修正（P1-B）**：refund 表加 `tier`/`refund_class`/三維 user id + CHECK；SoD header dep；tier 自動分級。

### §4.3 Warranty 5-mode（ADR-0044 v2 / AC-V11-10）— ❌
- **Spec**：`warranty_mode` enum {purchase, handover, activation, contract, manual_override}，各 mode 不同起算錨點；RMA 延長換新零件 90 天獨立重算；B2B 覆寫上限 5 年走 ChangeRequest + audit。
- **Code**（`api/services/warranty_service.py:217`）：寫死 `purchase_date + INTERVAL '90 days'`，缺 purchase_date 用 `today+90d`。無 warranty_mode 概念。
- **修正（P1-B）**：device_warranty 表加 `warranty_mode`；mode-specific 起算；RMA 重算邏輯。

### §4.4 Chatbot token cap 1500（BR-A01-02 / AC-V11-11）— ⚠️
- **Spec**：reply ≤ 1500 tokens + 截斷 fallback（補「（詳情請洽客服）」），不送空回覆。
- **Code**：`agent/config.toml` / config_service `max_tokens=1024`，無 truncate fallback。
- **修正（P1-C）**：config 改 1500 + guardrails 層加截斷 fallback。

### §4.5 報價有效期 14d/3d（BR-M04-05 / FR-0042 / AC-V11-12）— ❌
- **Spec**：一般報價 TTL=14d，急件=3d；過期 `state=expired` 需重報，無靜默延長；走 M18 config。
- **Code**：無 quote 模組（§2 quote lifecycle 全缺），自然無有效期。
- **修正（P3，依賴 quote lifecycle）**。

### §4.6 M18 staged rollout（ADR-0067 / BR-M18 / AC-V11-13）— ❌
- **Spec**：config namespace + version + staged canary 5→50→100%（每段 30min 觀察）+ rollback ≤1min；每 transaction snapshot `config_version`；ACL read API（`/m18/config-read`）P99≤50ms。
- **Code**（`api/services/config_service.py`）：per-tenant JSONB，PATCH deep-merge，version++。無 namespace 隔離、無 staged rollout、無 rollback、無 ACL read。
- **修正（P3）**：重建 config governance（config_namespace/version/rollout/audit 四表）。

---

## §5 DB Schema 差異

### §5.1 Schema 命名
- **Spec**：`saas` schema（避免 public），`ddl-migration-001-init.sql` 53 表 + 41 index + 14 trigger。
- **Code**：`SQL/Schema.sql` 等，public schema（無 `saas.` 前綴）。

### §5.2 表名映射（spec → code）
| Spec 表 | Code 表 | 差異 |
|---|---|---|
| `work_order` | `work_orders` | 複數；無 monthly partition |
| `refund` | `refund_requests` | 名稱 + 缺 tier/refund_class 欄 |
| `cancellation` | （無） | **整表缺** → P1-A 新建 |
| `quote_version` | （無） | quote lifecycle 缺 |
| `device_warranty` | （warranty_claims 近似） | 缺 warranty_mode |
| `customer`/`site`/`device`/`brand`/`model` | `customers` only | site/device/brand/model master 缺 |
| `config_namespace`/`config_version`/`config_rollout`/`config_audit` | 單一 config JSONB | M18 四表缺 |
| `journal_entry`(append-only+hash) | （vouchers/journal 近似） | 無 hash chain trigger |
| `audit_event`(monthly partition) | `audit_logs` | 無 partition |

### §5.3 結構性缺口
- **RLS**：spec 要求每表 `tenant_id` RLS policy（ADR-0030）；code 無 RLS，靠 app 層 WHERE。
- **Append-only trigger**：spec `tg_block_mutation()` 攔 quote_version/journal_entry 的 UPDATE/DELETE；code 無。
- **Hash chain**：spec quote_version/journal_entry `hash_prev`+`hash_self`；code 無 cryptographic chain（refund approval_chain 只是 JSONB append）。
- **Partition**：spec work_order/journal/audit monthly、message weekly、evidence LIST by retention_class；code 無 partition。
- **PII `*_enc bytea`**：spec PII 全加密欄位不出現於 API schema；code 待查（customer service 有 PII redaction 提及，加密程度待 P1-B 確認）。

---

## §6 橫切關注點

| 面向 | Spec | Code | 狀態 |
|---|---|---|:--:|
| Tenant 路由 | path `/tenants/{tid}/...` | JWT claim + `X-Tenant-ID` header | ⚠️ 機制不同 |
| SoD headers | `X-Initiator/X-Approver/X-Executor` → 403 SOD_VIOLATION | approval_chain JSONB | ❌ |
| Config 快照 | `X-Config-Version` per transaction | 無 | ❌ |
| Error model | RFC 7807 problem+json + trace_id | 自訂 `{error_code,message,request_id,...}` | ⚠️ 近似非標準 |
| Pagination | cursor `?cursor=&limit=` | cursor base64 | ✅ |
| Idempotency | 強制 Idempotency-Key | `idempotency_guard` 24h TTL | ✅ |
| Auth | OAuth2 client_credentials + JWT | JWT HS256 + JTI revoke | ⚠️ 無 OAuth2 cc |
| Versioning | URL + header + x-phase II → 501 | `/api/v1` 固定 | ⚠️ |

---

## §7 嚴重度分級 + 建議遷移波次（= CIA impact）

| 波次 | 範圍 | 規模 | 風險 | 依賴 |
|:--:|---|:--:|---|---|
| **P1-A** | Cancellation 6-stage（本 session）| M | 中（前端同步遷移路徑）| cancellation 表、config reason_codes、SoD dep |
| **P1-B** | Refund 三維+5-tier、Warranty 5-mode | M | 中（改既有運作中 refund/warranty）| SoD dep（P1-A 共用）、DB 加欄 |
| **P1-C** | Chatbot token 1500、報價有效期占位 | S | 低 | agent config |
| **P2** | Path scheme 全面遷移 tenant-scoped + SoD 中介層 + RLS | **L** | **高（打爆全前端合約 + 全 DB RLS）** | P1 範式驗證後 |
| **P3** | 補缺合約：quote lifecycle / m18 governance / sync / acl / dgs / change-requests / master(site/device/brand/model) / payments / exceptions / chatbot REST | **XL** | 高 | 逐模組 CIA |

> **Linus 式提醒**：P2 是「Never break userspace」最危險的一步——現行前端 92 條 typed client 全打 `/api/v1`。建議 P2 採**雙掛**過渡（新 tenant-scoped 路徑上線、舊路徑 thin 轉呼 + deprecation header），前端逐頁遷移後再撤舊路徑，而非一次切換。

---

## §8 衝突清單（spec ↔ code 真正衝突，spec 全贏下的 reconcile 動作）

| # | 衝突點 | Spec（贏） | Code（現況） | Reconcile 動作 |
|--:|---|---|---|---|
| C-01 | Contract SSOT 指向 | `docs/architecture/api/` | `api/main.py:89` 指向已刪 `docs/02-design/specs/openapi.yaml` | 修註記 + 重生 generated.py/api.generated.ts（P1-A 先修註記，型別整體重生排 P2）|
| C-02 | Cancel 語意 | 6 階段費用 + 師傅分支 | 只改 status | P1-A 重寫 |
| C-03 | Refund SoD 維度 | 三維 initiator≠approver≠executor | 二維（同人不可簽兩次）| P1-B 加第三維 + X-headers |
| C-04 | Refund 分級 | 5-tier 金額分級 | 單一 NT$100k 閾值 | P1-B 改 tier 表 |
| C-05 | Warranty 起算 | 5-mode 錨點 | 寫死 purchase+90d | P1-B 加 warranty_mode |
| C-06 | Token cap | 1500 | 1024 | P1-C 改值 + truncate |
| C-07 | Tenant 路由 | path-based | header/JWT-based | P2 遷移（雙掛過渡）|
| C-08 | SoD 機制 | X-* headers | approval_chain | P2 中介層；P1-A 先在 cancel 落地 |
| C-09 | Error model | RFC 7807 | 自訂 envelope | P2 對齊 problem+json |
| C-10 | DB schema 名 | `saas.` + spec 表名 | public + 複數 legacy 名 | P2/P3 整批遷移（風險高，需 migration plan）|
| C-11 | Code 多餘 endpoint | spec 未涵蓋 | ~40 條 admin 功能 | P3 對 spec 補 backlog，**不靜默刪**（先確認業主是否要保留）|

> ⚠️ **C-10 / C-11 待業主二次裁決**：schema 全改名 + 多餘 endpoint 處置屬「會打爆現有資料/功能」的破壞性決定。本報告標記為衝突，**P2/P3 動手前需各自跑 CIA**。本 session 切片（P1-A）刻意**不**碰 schema 改名與舊路徑刪除，只新增 spec-compliant 表面，以零破壞示範範式。

---

## §9 本 session 動作

依業主裁決「報告 + 修第一個 vertical slice」+「spec 全贏」+「全 38 模組覆蓋」：

- ✅ 本報告（§0-§8）完成全覆蓋差異化分析。
- ⏳ 實作 **P1-A Cancellation 6-stage** 垂直切片（見計畫檔 Part B）：DB `cancellation` 表 + `cancellation_service.py` + tenant-scoped route + SoD headers + config reason_codes + audit + TDD + 前端遷移。作為 P1-B/P2/P3 的**架構範式模板**。

---

**End of Gap Audit 2026-06-01**
