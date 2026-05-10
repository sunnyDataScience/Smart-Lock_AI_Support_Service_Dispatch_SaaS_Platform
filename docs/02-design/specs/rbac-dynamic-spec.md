---
status: superseded
superseded_by: docs_v2/2-contracts/modules/rbac.md
superseded_at: 2026-05-10
supersede_cr: CR-0007
supersede_notice: |
  This file is part of the legacy docs/ 5D structure, superseded by docs_v2/ 6-tier (CR-0001).
  90-day observation period: 2026-05-10 → 2026-08-10. After 2026-08-10 this file will be deleted (CR-0008).
  AI: prefer the new path; do not treat this content as authoritative.
---

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
