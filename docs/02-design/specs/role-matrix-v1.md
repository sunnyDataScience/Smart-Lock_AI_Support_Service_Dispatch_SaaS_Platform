---
title: Role Matrix v1.0 — V1.0 角色與權限矩陣
phase: DESIGN
gate: TR4
status: Active
owners:
  - PM
  - Tech Lead
  - Ops Manager
related:
  - "[[_flows-bdd-test/v-model-left/E5x--workflow-admin-governance]]"
  - "[[_flows-bdd-test/v-model-left/E5x--workflow-work-order]]"
  - "[[decision-log/E7x--pm-alignment-Q1-Q10]]"
  - "[[02-design/specs/dispatch-weights]]"
  - "[[02-design/specs/sla-policy]]"
last_reviewed: 2026-05-07
---

# V1.0 角色與權限矩陣（Role Matrix v1.0）

## 0. Purpose

本文件為 V1.0 GA 階段之 **唯一角色與權限真相來源（SSOT）**，提供：
1. RBAC 後端實作的角色清單（含 `dispatch_officer` 新角色）
2. BDD scenarios `Given a user with role X` 的角色枚舉
3. 前端 sidebar / route guard 的權限判斷依據

**對應 PM 拍板**：
- [[decision-log/E7x--pm-alignment-Q1-Q10|Q1=A]]：派工員為 V1.0 獨立角色 `dispatch_officer`
- [[decision-log/E7x--pm-alignment-Q1-Q10|Q2=A]]：Director > Manager 階層（`operations_director` 為 `operations_manager` 之上級覆核）
- [[decision-log/E7x--pm-alignment-Q1-Q10|Q6=A]]：客服可繞過自動派工但需稽核

## 1. 角色清單（V1.0 共 7 個 system role）

引用 [[_flows-bdd-test/v-model-left/E5x--workflow-admin-governance|admin-governance]] §1.1 + [[_flows-bdd-test/v-model-left/E5x--workflow-work-order|work-order]] §2.1 角色映射。

| Role Key | 中文名 | 階層 | 對應 work-order §2.1 6 角色映射 | 備註 |
|---|---|---|---|---|
| `super_admin` | 平台超管 | L0（跨租戶） | Admin（超集合） | 不可刪除 / 改名 |
| `tenant_admin` | 租戶管理員 | L1 | Admin | 同租戶內所有治理權限 |
| `operations_director` | 營運總監 | L2（高於 Manager） | Admin（特化）| **Q2=A 新增**；Manager 之上級覆核 |
| `operations_manager` | 營運主管 | L3 | Admin（特化）| 工單覆核、爭議一級審核 |
| `dispatch_officer` | 派工員 | L4 | Dispatch_Engine（人工介入）| **Q1=A 新增**；人工指派 / 重派 / 候選排序 |
| `support_agent` | 客服人員 | L4 | Admin（客服面向）| 對話、問題卡、客訴；Q6=A 可繞過自動派工 |
| `auditor` | 稽核員 | L5（read-only） | （新角色） | 唯讀；不可寫 / 不可匯出原始資料 |

> **未列入 V1.0 system role**：`technician`、`customer`、`finance`（V1.0 後者由 `tenant_admin` 兼任，V1.5 拆分）

## 2. 8 維權限矩陣

| 權限維度 \ Role | super_admin | tenant_admin | ops_director | ops_manager | dispatch_officer | support_agent | auditor |
|---|---|---|---|---|---|---|---|
| **Work Order CRUD** | ✅ all | ✅ all | ✅ all | ✅ all | 🟡 read + reassign | 🟡 read + create from PC | 👁 read-only |
| **Dispatch（手動派 / 重派）** | ✅ | ✅ | ✅ | ✅ | ✅ | 🟡 Q6=A 可繞過 + 稽核 | ❌ |
| **Refund Approval** | ✅ all | ✅ ≤ NT$10k auto / > NT$10k 二級 | ✅ 終裁 | 🟡 一級 ≤ NT$10k | ❌ | ❌ | 👁 |
| **RBAC（角色管理）** | ✅ all tenants | ✅ own tenant | ❌ | ❌ | ❌ | ❌ | 👁 |
| **Audit Events** | ✅ read + export | ✅ read + export | ✅ read | ✅ read | 👁 own actions | 👁 own actions | ✅ read + export（**Q2 受限：不可 export 原始 PII**） |
| **Inventory** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | 👁 |
| **Reports（KPI / 營收 / 排行）** | ✅ all | ✅ own tenant | ✅ | ✅ | 👁 dispatch KPI | ❌ | 👁 |
| **System Settings（含 SLA / weights）** | ✅ | ✅ | 🟡 SLA only | ❌ | ❌ | ❌ | 👁 |

**圖示說明**：✅ 完整權限 / 🟡 受限權限（見備註）/ 👁 唯讀 / ❌ 無權限

## 3. 階層關係（Q2=A）

```
super_admin
    ↓
tenant_admin
    ↓
operations_director  ←─ Q2=A 新增層級；爭議 / 退款終裁
    ↓
operations_manager   ←─ 一級覆核
    ↓
dispatch_officer / support_agent  ←─ 第一線執行
    ↓
auditor（read-only，獨立於階層之外）
```

**升級路徑**：
- 工單覆核：`dispatch_officer` → `operations_manager` → `operations_director`
- 退款：`tenant_admin` ≤ NT$10k 自動 / > NT$10k 升 `operations_director`（Q2=A）
- 爭議終裁：`operations_director`（取代舊版 `tenant_admin`）

## 4. 影響範圍

- **後端**：`api/services/rbac_service.py` 須新增 `dispatch_officer` / `operations_director` 兩個 role + 對應 permission set
- **前端**：`web/src/lib/auth.ts` route guard 須擴充；sidebar `NavItem` 對應 7 個角色
- **DB**：`roles` table seed data（PR #40 已含 `dispatch_officer` seed）
- **BDD**：`Given a user with role "dispatch_officer"` / `"operations_director"` 步驟需在 step definitions 新增

## 5. Verification

- [ ] `roles` table 含 7 筆 system role
- [ ] BDD `Given a user with role X` 涵蓋 7 個 role（grep `step_defs/`）
- [ ] OpenAPI security scheme `bearerAuth` 配套 RBAC matrix（見 [[02-design/specs/rbac-dynamic-spec]]）
- [ ] Frontend route guard 對 `auditor` 阻擋所有 `*.write.*` endpoints

## 6. Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-07 | Claude (assisted) | 初版：7 role × 8 權限維度 + Q1=A / Q2=A / Q6=A 拍板整合 |
