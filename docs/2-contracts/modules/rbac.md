# Dynamic RBAC 規格書

> GAP #16 + #6 -- 動態角色權限控制  
> 狀態: Draft  
> 最後更新: 2026-04-04

---

## 1. 概述

目前平台採用靜態 4-role 系統 (admin, technician, line_user, reviewer)，角色與權限硬編碼於程式中，無法因應不同品牌商 (brand_oem) 與經銷商 (distributor) 的權限需求。本規格將靜態角色擴展為動態 RBAC (Role-Based Access Control)，支援 6 種以上可設定角色，並提供 resource + action 的細粒度權限矩陣。

---

## 2. Role Hierarchy (角色階層)

> **本節為全系統角色的權威來源。** 其他文件中的角色定義應引用本表：
> - 工單流程角色（6 個業務角色）：`E5x--workflow-work-order.md §2`
> - 治理流程角色（7 個治理角色）：`E5x--workflow-admin-governance.md §1`
> - 多租戶平台角色（5 個平台角色）：`platform-multi-tenant/E5x--flows-multi-tenant.md §1`

### 2.1 角色總覽（全版本）

| 角色 name | 顯示名稱 | 版本 | 說明 | 系統內建 | 對應業務角色 |
|---|---|---|---|---|---|
| `super_admin` | 超級管理員 | V3.0 | 完整系統存取權，平台擁有者 | 是 | — |
| `admin` | 管理員 | V1.0 | 管理使用者、工單、財務 | 是 | Admin（工單）、operations_manager（治理） |
| `reviewer` | 審查員 | V1.0 | SOP 審查、品質稽核 | 是 | — |
| `technician` | 技師 | V1.0 | 操作自身工單、提交報告 | 是 | Technician（工單） |
| `brand_oem` | 品牌商 | V2.0 | 檢視保固統計、上傳資料；平台資料僅限唯讀 | 是 | — |
| `distributor` | 經銷商 | V2.0 | 檢視區域報表、管理子帳號 | 是 | — |
| `line_user` | LINE 使用者 | V1.0 | 自身對話、個人資料 (預設角色) | 是 | Customer（工單） |
| `finance` | 財務人員 | V2.0 | 帳務結算、退款執行、月結對帳 | 是 | Finance（工單） |
| `tenant_admin` | 租戶管理員 | V3.0 | 管理該租戶的品牌設定、使用者、資料 | 是 | — |

- `super_admin` 擁有所有權限，不受 permission matrix 限制。
- 系統內建角色 (`is_system=true`) 不可刪除，但可調整其 permissions。
- 管理員可新增自訂角色 (`is_system=false`)。

---

## 3. Permission Model (權限模型)

### 3.1 Resources (資源)

| Resource | 說明 |
|---|---|
| `users` | 使用者帳號管理 |
| `conversations` | 對話紀錄 |
| `work_orders` | 服務工單 |
| `invoices` | 發票 / 帳單 |
| `refunds` | 退款申請 |
| `complaints` | 客訴紀錄 |
| `reports` | 統計報表 |
| `settings` | 系統設定 |

### 3.2 Actions (操作)

| Action | 說明 |
|---|---|
| `create` | 新增 |
| `read` | 讀取 / 查詢 |
| `update` | 修改 |
| `delete` | 刪除 |
| `export` | 匯出資料 |
| `approve` | 審核 / 核准 |

### 3.3 Permission Matrix (預設配置)

以下為系統內建角色的預設權限配置。`*` 代表所有 actions。

| Resource | super_admin | admin | reviewer | technician | brand_oem | distributor | line_user |
|---|---|---|---|---|---|---|---|
| users | * | create, read, update | read | read (self) | -- | read (sub) | read (self) |
| conversations | * | read, export | read | read (own) | -- | -- | read (own) |
| work_orders | * | * | read, approve | read (own), update (own) | read | read (region) | read (own) |
| invoices | * | create, read, update, export | read | read (own) | read | read (region) | read (own) |
| refunds | * | create, read, approve | read, approve | -- | -- | -- | create, read (own) |
| complaints | * | read, update | read, approve | read (own) | read | read (region) | create, read (own) |
| reports | * | read, export | read | -- | read | read (region) | -- |
| settings | * | read, update | -- | -- | -- | -- | -- |

註: `(self)` / `(own)` / `(region)` / `(sub)` 為 row-level filtering，在 service layer 實作。

---

## 4. Database Design

### 4.1 roles 表

```sql
CREATE TABLE roles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(64) UNIQUE NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    description TEXT DEFAULT '',
    is_system   BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 4.2 permissions 表

```sql
CREATE TABLE permissions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource    VARCHAR(64) NOT NULL,
    action      VARCHAR(32) NOT NULL,
    description TEXT DEFAULT '',
    UNIQUE (resource, action)
);
```

### 4.3 role_permissions 表

```sql
CREATE TABLE role_permissions (
    role_id       UUID REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);
```

### 4.4 users 表異動

```sql
-- users.role 欄位維持 VARCHAR，值對應 roles.name
-- 新增 foreign key 約束 (deferred，確保 seed 順序不影響)
ALTER TABLE users
    ADD CONSTRAINT fk_users_role
    FOREIGN KEY (role) REFERENCES roles(name)
    DEFERRABLE INITIALLY DEFERRED;
```

---

## 5. Migration Path (遷移路徑)

### 目標: 零停機遷移

1. **Phase 1 -- Schema migration**: 建立 `roles`、`permissions`、`role_permissions` 表。不修改 `users` 表結構。
2. **Phase 2 -- Data seeding**: 執行 `seed_default_roles()` 寫入 7 個預設角色及其 permissions。此操作為 idempotent，可重複執行。
3. **Phase 3 -- Constraint activation**: 在 `users.role` 上新增 deferred FK 約束，確保所有現有 role 值都已存在於 `roles.name`。
4. **Phase 4 -- Code rollout**: 部署新版 RBAC service，API layer 開始使用 `check_permission()` 取代硬編碼角色判斷。

### Rollback 策略

- Phase 1-2 為 additive (僅新增表)，不影響現有功能。
- Phase 3 的 FK 約束可透過 `ALTER TABLE users DROP CONSTRAINT fk_users_role` 回退。
- Phase 4 的 code rollout 透過 feature flag 控制。

---

## 6. API Endpoints

### 6.1 列出所有角色

```
GET /api/v1/roles
```

**Response (200 OK):**

```json
[
  {
    "name": "admin",
    "display_name": "管理員",
    "description": "管理使用者、工單、財務",
    "is_system": true,
    "permissions": [
      {"resource": "users", "action": "create"},
      {"resource": "users", "action": "read"},
      {"resource": "users", "action": "update"}
    ]
  }
]
```

### 6.2 建立自訂角色

```
POST /api/v1/roles
```

**Request Body:**

```json
{
  "name": "regional_manager",
  "display_name": "區域經理",
  "description": "管理特定區域的工單與技師",
  "permissions": [
    {"resource": "work_orders", "action": "read"},
    {"resource": "work_orders", "action": "update"},
    {"resource": "reports", "action": "read"}
  ]
}
```

### 6.3 更新角色權限

```
PUT /api/v1/roles/{id}/permissions
```

**Request Body:**

```json
{
  "permissions": [
    {"resource": "work_orders", "action": "read"},
    {"resource": "work_orders", "action": "update"},
    {"resource": "work_orders", "action": "approve"}
  ]
}
```

### 6.4 查詢使用者有效權限

```
GET /api/v1/users/{id}/permissions
```

**Response (200 OK):**

```json
{
  "user_id": "usr_abc123",
  "role": "technician",
  "permissions": [
    {"resource": "work_orders", "action": "read"},
    {"resource": "work_orders", "action": "update"},
    {"resource": "invoices", "action": "read"}
  ]
}
```

---

## 7. 技術實作要點

- `super_admin` 的權限檢查直接短路回傳 `true`，不查 permission matrix。
- Permission 查詢結果應以 TTL cache (60 秒) 暫存，避免每次 request 都查資料庫。
- `require_permission(resource, action)` decorator 套用於 FastAPI endpoint，自動從 JWT 取得 `user_id` 並呼叫 `check_permission()`。
- 系統內建角色以 `seed_default_roles()` 寫入，此函式為 idempotent -- 已存在的角色僅更新 permissions，不重複建立。

---

## 8. 相關文件

- GAP #16: Dynamic RBAC
- GAP #6: Role/Permission 擴展
- `agent/services/auth/rbac.py`: 實作模組
- `docs/02-design/specs/data-export-spec.md`: 匯出功能的授權規則依賴本 RBAC

---

## §B. Role Matrix v1.0 (merged from former _pending-merge_role-matrix.md)


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
| 2026-05-11 | Claude (assisted) | 新增 §7 測試情境（6 cases，IT-0045 ~ IT-0050）|

## §7 測試情境與案例 (RBAC)

<!-- TC-ID: IT-0045 -->
#### 情境 1: 正常路徑 — admin 對 work_orders 有完整 CRUD 權限

*   **描述**: User 角色為 `admin`，呼叫 `work_orders` 各 endpoint 應全部通過。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - Seed user `u-admin-001` 帶 role `admin`，登入取得 bearer token。
        - DB 已有 work_order `wo-001`。
    2.  **Act**: 依序呼叫 POST /work-orders（create）、GET /work-orders/wo-001（read）、PATCH /work-orders/wo-001（update）、DELETE /work-orders/wo-001（delete）。
    3.  **Assert**:
        - 4 個 endpoint 全部回 2xx。
        - `audit_logs` 含 4 筆 `rbac.allowed` 事件，標 `actor=u-admin-001, role=admin`。

<!-- TC-ID: IT-0046 -->
#### 情境 2: 正常路徑 — technician 僅能讀寫自己的 work_orders

*   **描述**: technician 對自己的 work_order 可 read/update，對他人的應 403。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - User `u-tech-001` 角色 `technician`，其 work_order `wo-mine` (assigned_technician_id=u-tech-001)、`wo-others` (assigned_technician_id=u-tech-002)。
    2.  **Act**:
        - GET /work-orders/wo-mine 與 PATCH /work-orders/wo-mine
        - GET /work-orders/wo-others 與 PATCH /work-orders/wo-others
    3.  **Assert**:
        - 前兩個回 200。
        - 後兩個回 403 `Forbidden`，body 含 `error_code="rbac.forbidden.scope_own"`。
        - `audit_logs` 含 1 筆 `rbac.allowed` + 1 筆 `rbac.denied`。

<!-- TC-ID: IT-0047 -->
#### 情境 3: 邊界情況 — line_user 角色降級檢查（預設角色）

*   **描述**: 新註冊 LINE user 預設 role=`line_user`，僅能 read self conversations，對 reports 應 403。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - User `u-line-001` 角色 `line_user`（預設）。
    2.  **Act**:
        - GET /conversations/own → 200
        - GET /conversations/u-line-002（他人）→ 403
        - GET /reports → 403
    3.  **Assert**:
        - 三個結果符合預期。
        - 後兩個 audit_logs `rbac.denied` 帶 `denied_resource` 標籤。

<!-- TC-ID: IT-0048 -->
#### 情境 4: 邊界情況 — dispatch_officer 繞過自動派工 audit 強制

*   **描述**: per ADR-0018，`support_agent` 角色繞過自動派工時必須寫 audit log（不可靜默繞過）。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - User `u-sa-001` 角色 `support_agent`。
        - ProblemCard `pc-001` 已存在。
    2.  **Act**: 呼叫 POST /work-orders/manual-assign，body=`{"problem_card_id":"pc-001","technician_id":"t-99","reason":"customer requested specific tech"}`。
    3.  **Assert**:
        - 回 201，WorkOrder 建立。
        - `audit_logs` 必須含 `dispatch.bypass.manual` 事件，含 `actor`, `reason`, `original_recommendation` 三欄位。
        - 若 audit 寫入失敗，整個 transaction rollback（assert：強制故意讓 audit DB down 時，WorkOrder 不應建立）。

<!-- TC-ID: IT-0049 -->
#### 情境 5: 異常處理 — 已撤銷 token 嘗試呼叫 API

*   **描述**: User token 已 revoke 後仍嘗試呼叫，應 401 不可洩漏角色資訊。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - User `u-admin-001` 登入取得 token，然後管理員呼叫 POST /auth/revoke。
    2.  **Act**: 用舊 token GET /work-orders。
    3.  **Assert**:
        - 回 401 `Unauthorized`，body 僅 `{"error":"invalid_token"}`，**不可**洩漏 `role` 或 `user_id`。
        - `audit_logs` 含 `auth.revoked_token_attempt` 事件。

<!-- TC-ID: IT-0050 -->
#### 情境 6: 業務規則 — 角色階層升級需更高權限角色簽核

*   **描述**: 把 user 從 `technician` 升為 `admin` 需要 `super_admin` 或現有 `admin` 簽核（per Q2=A 拍板）。
*   **測試步驟 (Arrange-Act-Assert)**:
    1.  **Arrange**:
        - Actor `u-admin-001` 角色 `admin`。
        - Target user `u-tech-005` 目前角色 `technician`。
    2.  **Act**:
        - 情境 A: actor=admin 呼叫 PATCH /users/u-tech-005/role，body=`{"new_role":"admin"}` → 應 200。
        - 情境 B: actor=reviewer 同呼叫 → 應 403。
        - 情境 C: actor=admin 嘗試升為 `super_admin` → 應 403。
    3.  **Assert**:
        - 三個 case 回應符合預期。
        - 情境 A audit_logs 含 `rbac.role_change`，old_role/new_role/approver_id 完整。
