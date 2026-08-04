# TC-SEC-RBAC-03

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務；另以本機 Docker 測試庫實跑既有測試） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/routers/config_m18.py`、`api/services/config_m18_service.py`、`SQL/migrations/103-config-namespace-owner-protected.sql`、`SQL/migrations/004-config-m18.sql`、`api/tests/test_cr_0166_config_governance.py`、`api/tests/test_config_m18.py` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

TC 判定基準「僅 namespace 之 owner 角色可改；其餘 403」在程式碼中有完整兩層對應：router 層靜態 gate `role_required(*OPS_ROLES)`（`api/routers/config_m18.py:169`、`:216`）先擋掉 OPS 以外的登入者（403 `FORBIDDEN`），service 層 `_assert_namespace_writable`（`api/services/config_m18_service.py:149-189`）再依 `saas.config_namespace.owner_role_codes` 動態縮權（403 `CONFIG_OWNER_ROLE_REQUIRED`），另有受保護層擋租戶覆寫（403 `CONFIG_PROTECTED_OVERRIDE`）。TC 步驟指名的兩個 namespace 均在程式碼／migration 中命中：`payment_gate` 於 `SQL/migrations/103-config-namespace-owner-protected.sql:37-39` 被設為 `is_protected=true` 且 `owner_role_codes` 保持空集合（＝admin-only fallback）；`discount_policy` 於同檔 `:24-34` 被回填為 `ARRAY['operations_manager']`。三種身分（非 owner／owner／admin）各有既有測試釘住。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 8. 權限與 RBAC 案例（TC-SEC-RBAC） |
| 前置 | 任意登入者 |
| 步驟 | 修改 config namespace（payment_gate / discount_policy 等） |
| 預期結果（判定基準） | 僅 namespace 之 owner 角色可改；其餘 403 |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-PLT-02、NFR-Sec-003 |
| 屬於哪條旅程腳本 | SC-18 |

出處：`smartlock-docs/enterprise/20_Test_Cases.md:332`。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 存在 config namespace 修改端點 | `api/routers/config_m18.py:157-172`（PUT draft）、`:203-219`（start-rollout） | 一致 |
| 任意登入者（非 OPS）修改 → 403 | `api/routers/config_m18.py:169` `role_required(*OPS_ROLES)` → `api/core/deps.py:320-325` | 一致 |
| owner 角色可改 | `api/services/config_m18_service.py:184-189`：`role in allowed` 時不 raise | 一致 |
| 非 owner（但在 OPS 內）→ 403 | `api/services/config_m18_service.py:184-189` `CONFIG_OWNER_ROLE_REQUIRED` 403 | 一致 |
| `payment_gate` 有 owner 治理設定 | `SQL/migrations/103-config-namespace-owner-protected.sql:37-39`（`is_protected=true`，owner 空集合＝admin-only） | 一致 |
| `discount_policy` 有 owner 治理設定 | `SQL/migrations/103-config-namespace-owner-protected.sql:24-34`（`ARRAY['operations_manager']`） | 一致 |
| owner 未回填的 namespace 之行為 | `api/services/config_m18_service.py:177-183`：admin-only fallback，其餘 403 | 一致 |
| 不存在的 namespace | `api/services/config_m18_service.py:163-164` → 404 `CONFIG_NOT_FOUND` | 一致 |
| SoD 併行要求（draft 需 X-Initiator；rollout 需雙簽） | `api/routers/config_m18.py:83-105` | 一致 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| dispatcher / customer_service / technician | `PUT .../m18/configs/{ns}/{key}` | `RequestRejected(403)` | router 靜態 gate | `api/routers/config_m18.py:169`、`api/core/deps.py:320-325` | `FORBIDDEN`，403 |
| operations_manager | `PUT .../m18/configs/discount_policy/*` | `ConfigDraftCreated` | owner 允許 | `api/services/config_m18_service.py:184-189`（不 raise）→ `:353` | 201 建 draft |
| operations_manager | `PUT .../m18/configs/payment_gate/*` | `RequestRejected(403)` | owner 空集合＝admin-only | `api/services/config_m18_service.py:177-183` | `CONFIG_OWNER_ROLE_REQUIRED`，403 |
| 任一角色（含 admin） | 對 `is_protected` namespace 做租戶層 override | `RequestRejected(403)` | 受保護層 | `api/services/config_m18_service.py:168-173` | `CONFIG_PROTECTED_OVERRIDE`，403 |
| admin | `PUT` owner 受限 namespace | `ConfigDraftCreated` | admin bypass | `api/services/config_m18_service.py:146`、`:174-175` | 通過 |
| 任一角色 | `PUT` 不存在的 namespace | `RequestRejected(404)` | 存在性 | `api/services/config_m18_service.py:163-164` | `CONFIG_NOT_FOUND`，404 |
| operations_manager | `:start-rollout` 且 initiator=approver | `RequestRejected(403)` | 二維 SoD | `api/routers/config_m18.py:99-104` | `SOD_VIOLATION`，403 |

---

## 逐層走查

### 步驟 1 — 前端呼叫端

品牌後台的 config 治理頁在 `web/brand-portal/src/lib/rolePolicy.ts:63`：

```ts
  { prefix: "/admin/config-governance", roles: ["admin"] }, // CR-0036 M18 config 治理
```

### 步驟 2 — API 路由與靜態角色 gate

`api/routers/config_m18.py:157-172`：

```python
@router.put(
    "/tenants/{tenantId}/m18/configs/{namespace}/{key}",
    operation_id="createConfigDraft",
    summary="建 config draft（schema 驗證 + audit）(M18)",
    status_code=201,
    response_model=dict,
)
async def create_config_draft(
    body: ConfigDraft,
    tenantId: str = Path(...),
    namespace: str = Path(...),
    key: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
    initiator: str = Depends(_require_initiator),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
```

其 docstring（`api/routers/config_m18.py:173-178`）自述兩層設計：

```
    """建 config_version(state='draft')。

    header X-Initiator required（draft 只需發起人，不強制雙簽）。
    proposed_value 先經 namespace.json_schema 驗證（422 CONFIG_SCHEMA_INVALID on fail）。
    CR-0166 R1：靜態 gate 放寬 OPS_ROLES，service 依 namespace owner_role_codes 動態縮權。
    """
```

`OPS_ROLES` 展開為 `("admin", "operations_manager")`（`api/core/deps.py:293-295`）。

同一模式亦套用於 `:start-rollout`（`api/routers/config_m18.py:216`）；`rollbackConfig`（`:265`）、`slo-check`（`:310`）、`listConfigNamespaces`（`:121`）、`listConfigAudit`（`:347`）則為 `FULL_ACCESS_ROLES`（＝僅 `admin`）。

### 步驟 3 — service 層 owner 縮權

`api/services/config_m18_service.py:142-189`：

```python
# CR-0166 R1-6/R1-7：admin 永遠可寫（全權治理角色；owner_role_codes 語意＝
# 「除 admin 外的授權 owner」）。
_ADMIN_BYPASS_ROLES = frozenset({"admin"})


async def _assert_namespace_writable(
    namespace: str, *, actor_role: str | None, tenant_id: str | None
) -> None:
    """CR-0166 R1-6（受保護層）＋R1-7（owner 治理）統一寫入 gate。

    - is_protected 且租戶層 override（tenant_id 非 NULL）→ 403 CONFIG_PROTECTED_OVERRIDE。
    - owner_role_codes 非空 → actor_role 須 ∈ 其中或 admin；否則 403 CONFIG_OWNER_ROLE_REQUIRED。
    - owner_role_codes 空 → admin-only fallback（未回填的 namespace 零行為變化）。
    """
    cur = await db_module._conn.execute(
        "SELECT is_protected, owner_role_codes FROM saas.config_namespace WHERE code = %s",
        (namespace,),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("CONFIG_NOT_FOUND", f"namespace '{namespace}' 不存在", 404)
    is_protected, owner_roles = bool(row[0]), list(row[1] or [])
    role = (actor_role or "").lower()

    if is_protected and tenant_id is not None:
        raise ApiError(
            "CONFIG_PROTECTED_OVERRIDE",
            f"namespace '{namespace}' 為受保護配置，租戶層不可覆寫（僅平台級可改）",
            403,
        )
    if role in _ADMIN_BYPASS_ROLES:
        return
    allowed = set(owner_roles) if owner_roles else set()
    if not allowed:
        # 未回填：admin-only fallback（admin 已於上方 return）
        raise ApiError(
            "CONFIG_OWNER_ROLE_REQUIRED",
            f"namespace '{namespace}' 僅管理員可修改",
            403,
        )
    if role not in allowed:
        raise ApiError(
            "CONFIG_OWNER_ROLE_REQUIRED",
            f"namespace '{namespace}' 僅 {', '.join(sorted(allowed))} 或管理員可修改",
            403,
        )
```

呼叫點兩處：`api/services/config_m18_service.py:353`（`create_draft`）與 `:419`（`start_rollout`）。

### 步驟 4 — DB schema 與 TC 指名的兩個 namespace

`SQL/migrations/004-config-m18.sql:58`：

```sql
  owner_role_codes text[] NOT NULL DEFAULT '{}'
```

`SQL/migrations/103-config-namespace-owner-protected.sql:20-39`：

```sql
ALTER TABLE saas.config_namespace
    ADD COLUMN IF NOT EXISTS is_protected boolean NOT NULL DEFAULT false;

-- 財務金額 / 政策 / 字典 / 文案類：operations_manager 可改（admin 隱含 bypass）
UPDATE saas.config_namespace
SET owner_role_codes = ARRAY['operations_manager']
WHERE code IN (
    'cancellation_fee_tiers', 'refund_tier_thresholds', 'travel_fee_distance_tiers',
    'deposit_policy', 'dispatch_commission', 'monthly_close_schedule', 'tax_policy',
    'discount_policy', 'quote_policy', 'quote_validity_policy',
    'completion_policy', 'problemcard_policy', 'scope_change_policy',
    'auto_confirm_policy', 'sla_dispatch', 'sla_policy',
    'cancellation_reason_codes', 'technician_suspension_reasons', 'company_profile'
)
AND owner_role_codes = '{}';

-- 平台閘門：payment_gate 鎖 admin-only（owner 空集合）＋受保護（租戶不可 override）
UPDATE saas.config_namespace
SET is_protected = true
WHERE code = 'payment_gate';
```

TC 步驟指名的 `discount_policy` 在第 29 行的清單內；`payment_gate` 在第 37-39 行單獨處理。

`SQL/migrations/MIGRATION_REGISTRY.md:156` 登記此支 migration：「saas.config_namespace 加 is_protected 欄＋回填 owner_role_codes（19 namespace=operations_manager，payment_gate=admin-only＋protected）」。

### 步驟 5 — config 值的消費端

`payment_gate` 的讀取端在 `api/services/payment_service.py:198-213`：

```python
async def assert_payment_gate(*, tenant_id: str, work_order_id: str) -> dict:
    """PAY-01：派工/建 WO 前 payment gate。config payment_gate.require_payment_for_dispatch
    ...
    cfg = await config_m18_service.read_global_value(namespace="payment_gate")
```

`discount_policy` 的讀取端在 `api/services/quote_engine_service.py:67-70`：

```python
    """CR-0046：報價核准門檻讀 M18 config discount_policy（fallback 10000，不寫死）。"""
    cfg = await config_m18_service.read_global_value(namespace="discount_policy")
```

### 步驟 6 — SoD 併行條件

`api/routers/config_m18.py:83-105` 定義兩個 M18 專屬 header 依賴（二維，無 executor）：

```python
async def _require_initiator(
    x_initiator: str | None = Header(default=None, alias="X-Initiator"),
) -> str:
    if not x_initiator:
        raise ApiError("VALIDATION_ERROR", "Missing required header X-Initiator", 422)
    return _validate_uuid(x_initiator, "X-Initiator")


async def _require_sod_two(
    x_initiator: str | None = Header(default=None, alias="X-Initiator"),
    x_approver: str | None = Header(default=None, alias="X-Approver"),
) -> tuple[str, str]:
    ...
    if x_initiator == x_approver:
        raise ApiError(
            "SOD_VIOLATION",
            "Separation of Duties violated: X-Initiator 與 X-Approver 必須不同",
            403,
        )
```

---

## 既有測試證據

```
cd api && POSTGRES_URI=<本機測試庫> PYTHONPATH=<scratchpad> uv run pytest \
  tests/test_account_security_phase1.py tests/test_cr_0166_config_governance.py \
  tests/test_config_m18.py tests/test_cr_0182_portal_guard.py \
  tests/test_cr_0183_intra_portal_guards.py tests/test_cross_tenant_error_code_class.py \
  tests/test_work_order_read_ownership.py tests/test_auth_guards.py \
  tests/test_cr_0131_surface_failclosed.py -p winloop_plugin -q
82 passed in 12.22s
```

對到 TC 步驟的三支測試：

`api/tests/test_cr_0166_config_governance.py:50-58`（受保護 namespace，TC 指名的 `payment_gate`）：

```python
async def test_protected_namespace_tenant_override_blocked(client, admin_headers):
    """payment_gate 為受保護 namespace → 租戶層 draft 被擋 403 CONFIG_PROTECTED_OVERRIDE。"""
    res = await client.put(
        f"/tenants/{TENANT_ID}/m18/configs/payment_gate/enabled",
        ...
    assert res.json()["error_code"] == "CONFIG_PROTECTED_OVERRIDE"
```

`api/tests/test_cr_0166_config_governance.py:62-74`（非 owner → 403）：

```python
async def test_owner_role_dispatcher_blocked(client, dispatcher_headers):
    """tax_policy owner=operations_manager；dispatcher（在 OPS_ROLES 外）→ 403。

    注意：dispatcher 不在 OPS_ROLES，會先被 router 靜態 gate 擋（403），
    這正是「無權者進不來」的期望行為。"""
    ...
    assert res.status_code == 403
```

`api/tests/test_cr_0166_config_governance.py:77-97`（owner 放行、admin bypass）：

```python
async def test_owner_role_ops_manager_allowed(client, secondary_admin_headers):
    """tax_policy owner=operations_manager；ops manager 可建 draft（動態縮權放行）。"""
    ...
    assert res.status_code == 201, res.text


async def test_admin_bypasses_owner_role(client, admin_headers):
    """admin 永遠可寫 owner 受限 namespace（全權治理角色 bypass）。"""
    ...
    assert res.status_code == 201, res.text
```

既有測試以 `tax_policy` 為 owner 縮權的代表 namespace；`discount_policy` 與 `tax_policy` 在 `SQL/migrations/103-config-namespace-owner-protected.sql:26-33` 屬同一批 `UPDATE`，owner 值相同。

---

## 事實結論

1. config namespace 修改走兩層授權：router 靜態 `role_required(*OPS_ROLES)`（`api/routers/config_m18.py:169`、`:216`）＋ service `_assert_namespace_writable`（`api/services/config_m18_service.py:149-189`）。
2. 非 owner 角色的拒絕碼為 `CONFIG_OWNER_ROLE_REQUIRED` 403（`api/services/config_m18_service.py:179-189`）；OPS 以外角色更早被 router gate 擋為 `FORBIDDEN` 403。
3. `admin` 在 service 層永遠 bypass owner 檢查（`api/services/config_m18_service.py:146`、`:174-175`），但仍受 `is_protected` 的租戶層 override 限制（`:168-173`）。
4. TC 指名的 `payment_gate` 在 `SQL/migrations/103-config-namespace-owner-protected.sql:37-39` 設 `is_protected=true`、owner 保持空集合；`discount_policy` 在同檔 `:29` 設 owner 為 `operations_manager`。
5. owner 未回填的 namespace 走 admin-only fallback（`api/services/config_m18_service.py:177-183`）。
6. 不存在的 namespace 回 404 `CONFIG_NOT_FOUND`（`api/services/config_m18_service.py:163-164`）。
7. 既有測試以 `payment_gate`（受保護）與 `tax_policy`（owner=operations_manager）覆蓋三種身分的結果，本次全數通過。
