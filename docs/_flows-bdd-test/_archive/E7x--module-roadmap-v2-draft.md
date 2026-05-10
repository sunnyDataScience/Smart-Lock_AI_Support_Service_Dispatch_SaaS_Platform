---
title: V2.0 Business Module Roadmap (DRAFT — 已封存)
phase: V-MODEL LEFT (placeholder, awaiting active development)
gate: TR4 (deferred)
status: ARCHIVED (33 days untouched as of 2026-05-07; resurrect when V2.0 architecture finalizes)
last_updated: 2026-04-04
owners: [Tech Lead]
status: superseded
superseded_by: docs_v2/4-exploration/archive/module-roadmap-v2-draft.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
---

> **§0 Note**：本檔自 `E7x--module-specification-and-tests.md` 拆出 V2.0 部分。各模組僅有名稱 / 路徑 / 職責簡述，無 DbC 規格。待 V2.0 架構鎖定後復活。

## V2.0 業務服務模組規格 (agent/services/)

以下 16 個業務服務模組於 GAP 補齊階段建立，提供完整的派工、帳務、品質管理業務邏輯。
所有模組使用 async psycopg 連接 PostgreSQL，遵循統一的 Service 模式。

### 模組 6: RefundService (agent/services/finance/refund.py)

- **GAP**: #11 退款審批/大額雙簽
- **職責**: 退款申請建立、多層簽核狀態機、執行退款
- **關鍵方法**: `create_refund_request()`, `approve()`, `reject()`, `execute_refund()`
- **業務規則**: BR-REFUND-001~005 (單簽/雙簽閾值 100,000 TWD)

### 模組 7: TechnicianMatcher (agent/services/dispatch/matcher.py)

- **GAP**: #24 師傅網路壁壘
- **職責**: 四維加權匹配 (技能40%/距離25%/評分20%/時段15%)
- **關鍵方法**: `find_best_match()`, `handle_rejection()`, `handle_timeout()`
- **業務規則**: BR-005 (二次派工強制 S 級), BR-008 (15 分鐘超時重派), BR-012 (月拒單率>50% 停權)

### 模組 8: PricingEngine (agent/services/pricing/engine.py)

- **GAP**: #9/#23 報價確認/標準化定價
- **職責**: 價格規則查詢、報價單生成、加價項計算
- **關鍵方法**: `generate_quote()`, `check_warranty_override()`
- **業務規則**: BR-WARRANTY-002 (保固案件禁止 AI 自動報價)

### 模組 9: ComplaintLifecycleService (agent/services/complaint/lifecycle.py)

- **GAP**: #1 CRM 客訴流程
- **職責**: 客訴生命週期 (filed -> assigned -> investigating -> proposed -> accepted/rejected -> resolved -> closed)
- **關鍵方法**: `file_complaint()`, `propose_resolution()`, `check_sla_breaches()`
- **SLA**: critical=4h, high=24h, medium=72h, low=168h

### 模組 10: TechnicianRatingService (agent/services/technician/rating.py)

- **GAP**: #10 師傅多維度評分
- **職責**: 四維評分 (技術品質40%/服務態度25%/時間紀律20%/環保規範15%)
- **關鍵方法**: `calculate_rating()`, `determine_grade()`, `run_monthly_evaluation()`
- **等級**: S(>=4.5) / A+(>=4.0) / A(>=3.5) / Apprentice(<20 orders) / Delisted(<3.0)

### 模組 11: WorkOrderExceptionService (agent/services/work_order/exception.py)

- **GAP**: #2 工單異常流程
- **職責**: 5 種異常處理 (拒單/範圍變更/缺料/延遲/取消)
- **關鍵方法**: `handle_rejection()`, `handle_scope_change()`, `handle_material_shortage()`, `handle_delay()`, `handle_cancellation()`

### 模組 12: WarrantyClaimService (agent/services/warranty/claims.py)

- **GAP**: #12 保固爭議處理
- **職責**: 保固索賠生命週期 (filed -> verified -> approved/rejected -> disputed)
- **關鍵方法**: `file_claim()`, `verify_claim()`, `calculate_discount()`
- **業務規則**: 保固以交屋日為準 (非購買日)

### 模組 13: AuditLogger (agent/services/audit/logger.py)

- **GAP**: #13 稽核日誌完整性
- **職責**: 7 種事件類型結構化日誌 + PII 遮罩 + 差異化保留期
- **事件類型**: conversation(90d), tool_invocation(90d), safety_gate(1y), escalation(1y), dispatch_decision(2y), financial_action(7y), admin_action(7y)

### 模組 14: RBACService (agent/services/auth/rbac.py)

- **GAP**: #16/#6 動態 RBAC + 角色擴展
- **職責**: 動態角色權限管理 (7 角色, resource x action 矩陣)
- **角色**: super_admin, admin, reviewer, technician, brand_oem, distributor, line_user

### 模組 15-21: 其他業務服務

| 模組 | 路徑 | GAP | 職責 |
|---|---|---|---|
| **InventoryManager** | `agent/services/inventory/manager.py` | #17 庫存管理 | 師傅車載庫存追蹤、缺料預警、補貨建議 |
| **AppearanceConsentService** | `agent/services/consent/appearance.py` | #18 門外觀同意書 | 門外觀變更同意書生成、LINE 推播確認、數位簽名 |
| **ESignatureService** | `agent/services/consent/signature.py` | #19 電子簽收 | OTP 驗證、簽名影像存儲、法規合規 |
| **EvidencePackageService** | `agent/services/dispute/evidence.py` | #20 舉證包 | 多表聯合查詢組裝爭議舉證包 (problem_cards + conversations + invoices) |
| **BrandDataUploadService** | `agent/services/brand/data_upload.py` | #21 品牌資料上傳 | PDF/Excel 上傳、格式驗證、RAG pipeline 觸發 |
| **CompletionEvidenceService** | `agent/services/completion/evidence.py` | #25 完工證據 | 完工照片上傳驗證、16 項拍攝規範檢查、客戶簽收流程 |
| **DataExporter** | `agent/services/export/exporter.py` | #14 資料匯出 | CSV/Excel 匯出、欄位權限過濾、PII 遮罩 |
