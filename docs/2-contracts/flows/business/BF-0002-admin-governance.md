---
id: BF-0002
title: Admin Governance (Business Flow)
tier: 2
status: accepted
last-synced-with: 4e9658e90324cbceb26f5e5445f481fc5678df1f
sync-source: doc
synced-at: 2026-05-15
trace_to_fr:
  - "FR-0019-rbac-dynamic"
  - "FR-0020-audit-log-export"
  - "FR-0007-material-request"
  - "FR-0013-dual-sign-dispute"
related:
  - "../sub/SF-G1-rbac-lifecycle.md"
  - "../sub/SF-G2-audit-log-query-export.md"
  - "../sub/SF-G3-inventory-low-alert-replenish.md"
  - "../sub/SF-G4-dispute-arbitration.md"
  - "../../modules/{rbac, audit-logger, inventory, refund-service}.md"
  - "../../../1-decisions/ADR-0014-pm-alignment-q2.md (雙簽)"
legacy_id: E5x--workflow-admin-governance
---

# BF-0002 — Admin Governance

> 管理後台治理 BF。4 個子 flow (G1-G4) 已抽到 `flows/sub/`。
> 本檔保留 §共通定義（角色、權限碼、SLA）+ 跨 flow 關聯 + 附錄。

## §A. 共通定義（line 1-87 from source）

# E5x — 管理員治理流程規格書 (Admin Governance Flows)

> **文件版本**：v0.1（draft，待人工校對業務細節）
> **建立日期**：2026-04-23
> **狀態**：Claude 起草，待使用者逐節校對
> **適用範圍**：V2.0 管理員治理流程（非技師旁支）
> **觸發原因**：Pre-Week-2 驗證閘（plan §S）— 補齊 Flow 層完整度缺口
>
> **參考文件**：
> - `docs/02-design/specs/rbac-dynamic-spec.md` — RBAC 資料模型與 API
> - `docs/02-design/specs/audit-log-spec.md` — 稽核事件分類與保留政策
> - `docs/02-design/specs/inventory-management-spec.md` — 庫存資料模型
> - `docs/02-design/specs/warranty-dispute-spec.md` — 保固爭議狀態機
> - `docs/_flows-bdd-test/v-model-left/E5x--workflow-work-order.md` — 13 個工單 Flow
> - `docs/02-design/E5x--frontend-architecture.md §8.3` — 動態 RBAC 契約
>
> **與其他 Flow 文件的關係**：
> - `work-order-interaction-flows.md`：工單生命週期（技師為中心）
> - **本檔**：後台治理（管理員為中心）
> - `platform-multi-tenant/E5x--flows-multi-tenant.md`：V3.0 多租戶（待建）

---

## 目錄

1. [共通定義](#1-共通定義)
2. [Flow G1：RBAC 角色生命週期](#2-flow-g1rbac-角色生命週期)
3. [Flow G2：稽核日誌查詢與匯出](#3-flow-g2稽核日誌查詢與匯出)
4. [Flow G3：庫存低警報與補貨](#4-flow-g3庫存低警報與補貨)
5. [Flow G4：爭議仲裁獨立流程](#5-flow-g4爭議仲裁獨立流程)
6. [跨 Flow 關聯](#6-跨-flow-關聯)

---

## 1. 共通定義

### 1.1 角色（本檔登場）

> **權威角色清單：** 全系統角色定義與權限矩陣見 `specs/rbac-dynamic-spec.md §2`。
> 本節列出治理流程涉及的 8 個角色（含 Q2=A 新增 `operations_director`）。

| 角色 | 說明 | 關鍵權限 | 對應 work-order 角色 |
|:---|:---|:---|:---|
| `super_admin` | 平台最高權限，跨租戶 | 所有 `*.admin` 權限；唯一可授 `tenant_admin` | Admin（超集合） |
| `tenant_admin` | 租戶管理員 | 同租戶內所有治理權限 | Admin |
| `operations_director` | 營運總監（Q2=A 新增）| 工單覆核、雙簽核准、爭議三級裁決 | Admin（特化，Manager 之上）|
| `operations_manager` | 營運主管 | 工單指派/覆核、爭議二級審核 | Admin（特化） |
| `accountant` | 會計 | 退款/發票/對帳；**爭議金額裁決雙簽簽核人** | Finance |
| `support_agent` | 客服人員 | 對話、問題卡、客訴處理 | Admin（客服面向）|
| `dispatch_officer` | 派工員（✅ Q1=A 拍板獨立角色）| 工單派遣、人工介入、候選排序 | Admin（特化，新角色）|
| `auditor` | 稽核員（可外部審計） | **只讀**所有稽核事件 | （新角色，無對應） |

> **階層（Q2=A 拍板，PR #49 實作 ROLE_HIERARCHY）**：
> `super_admin` > `tenant_admin` ≅ `admin` > `operations_director` > `operations_manager` > `dispatch_officer` ≅ `support_agent` > `accountant` ≅ `auditor`
> （`can_grant` 採嚴格 > 比較，禁止平階授權；詳見 `api/services/role_service.py`）

> **角色映射說明**：[[E5x--workflow-work-order]] §2.1 用 6 角色（Customer / AI_System / Dispatch_Engine / Technician / Admin / Finance）；admin-governance 細化 Admin 為 5 子角色（tenant_admin / operations_director / operations_manager / support_agent / dispatch_officer）+ 額外 super_admin / auditor。dispatch_officer 獨立角色見 [[../decision-log/E7x--pm-alignment-Q1-Q10#2-q1-—-派工員是-v2-0-新角色還是客服子權限|PM Q1]] = ✅ A 拍板。

### 1.2 權限碼格式（對齊 `rbac-dynamic-spec.md`）

`<resource>.<action>.<scope>`，例：
- `refunds.approve.tenant` — 可核准本租戶所有退款
- `refunds.approve.own_team` — 僅可核准自己團隊的退款
- `audit.read.all` — 讀取所有稽核事件
- `inventory.write.warehouse_a` — 寫入 A 倉庫庫存

### 1.3 通用前置條件

所有治理操作必須：
1. 使用者已登入（Bearer JWT 有效）
2. `X-Tenant-ID` 與 JWT payload 一致
3. 對應權限碼驗證通過（後端 + 前端雙層檢查）
4. 寫操作附 `Idempotency-Key`（UUID v4，24h 窗）
5. 操作完成後產生稽核事件（見 Flow G2）

### 1.4 SLA（治理流程）

| 操作 | SLA | 超時處理 |
|:---|:---|:---|
| RBAC 角色變更生效 | < 5 秒（WS 即時推送） | 降級至下次登入生效 |
| 稽核查詢回應 | < 2 秒（含分頁） | 改非同步匯出 |
| 低庫存告警觸發 | 達閾值後 < 60 秒 | — |
| 爭議受理確認 | 提出後 < 24 小時 | 自動升級主管 |
| 爭議最終裁決 | 受理後 < 7 個工作日 | 自動升級至 `tenant_admin` |

---


## §B. 跨 Flow 關聯（line 575-end from source）

## 6. 跨 Flow 關聯

### 6.1 本檔與 work-order-interaction-flows 的分界

| 議題 | 歸屬 | 理由 |
|:---|:---|:---|
| 工單生命週期狀態機 | work-order-flows | 技師操作為中心 |
| 退款審批雙簽（Flow 6）| work-order-flows | 客戶觸發、工單衍生 |
| 爭議仲裁 | **本檔 G4** | 管理員裁決為中心、跨多工單 |
| 保固索賠流程（Flow 7）| work-order-flows | 技師回場修復為中心 |
| RBAC | **本檔 G1** | 治理操作 |
| 稽核事件**產出** | work-order-flows 各 Flow 附帶 | 各流程自然產出 |
| 稽核事件**查詢/匯出** | **本檔 G2** | 管理員主動操作 |
| 庫存消耗（完工回報）| work-order-flows Flow 1 | 技師動作 |
| 庫存告警與補貨 | **本檔 G3** | 管理員處理 |

### 6.2 本檔觸發的事件 → 下游消費者

```
G1 RBAC 變更 ──→ /realtime/rbac ──→ 所有登入 session 重繪 UI
                                  ──→ audit_events 表

G2 匯出完成 ──→ /realtime/notifications/{user_id} ──→ 原請求者下載

G3 低庫存觸發 ──→ /realtime/inventory/low-stock ──→ inventory UI 紅色 banner
                                                ──→ tenant_admin LINE Notify（escalated）

G4 爭議裁決 ──→ LINE Push（客戶）
            ──→ App Push（技師）
            ──→ 若需退款 ──→ Flow 6 退款審批流
```

### 6.3 與 multi-tenant 的關係（待 `platform-multi-tenant/E5x--flows-multi-tenant.md` 建立後對齊）

- `super_admin` 跨租戶稽核查詢 → 指向 `platform-multi-tenant/E5x--flows-multi-tenant.md` G_MT_3 超管查詢
- 租戶設定變更（角色預設、閾值）→ 指向 `platform-multi-tenant/E5x--flows-multi-tenant.md` G_MT_1 租戶設定

---

## 7. 校對檢核表（給使用者）

起草階段自知的模糊處，需使用者校對：

- [ ] §1.1 角色清單是否完整？`auditor` 是否為本專案既有或新增？
- [ ] §1.4 SLA 數字（5 秒 / 2 秒 / 60 秒 / 24 小時 / 7 工作日）是否符合業務承諾？
- [ ] §2.6 R7「`auditor` 不可被授予寫權限」是否需要放寬（讓 auditor 能匯出？）
- [ ] §3.4 保留期（180 天 / 3 年 / 5 年 / 7 年 / 10 年）是否符合台灣法規與公司政策？
- [ ] §3.5 大量匯出門檻（10,000 筆）是否合理？
- [ ] §3.6 PII 遮蔽規則細節（特別是超管層級的開放度）
- [ ] §4.6 R2 金額門檻（5 萬 / 20 萬）是否與 Flow 6 退款門檻一致？
- [ ] §5.6 R9 爭議雙簽門檻（5000）是否與 Flow 6 退款雙簽門檻（§9.1 可能的 10000/100000）統一？
- [ ] §5.6 R4 技師熔斷閾值（12 個月 3 次）是否為新規則？還是已在 `E5x--workflow-work-order.md §22` 有等價規則？
- [ ] §5.6 R7 保固爭議 vs 金額爭議的分界是否清楚？
- [ ] §5.7 新錯誤碼 `DISPUTE_EXTERNAL_PENDING` 的命名
- [ ] §6.1 議題分界是否準確？

---

## 8. 變更記錄

| 日期 | 版本 | 變更摘要 |
|:---|:---|:---|
| 2026-04-23 | v0.1 | 初稿（Claude 起草）：4 個 Flow + 共通定義 + 跨 Flow 關聯 |
