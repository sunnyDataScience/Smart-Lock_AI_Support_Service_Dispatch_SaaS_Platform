# TC-SEC-RBAC-02

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務；另以本機 Docker 測試庫實跑既有測試） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/services/role_service.py`、`api/core/deps.py`、`api/tests/test_rbac_role_isolation.py`、`test_cr_0111_has_permission_shadow.py`、`test_rbac_dynamic.py`、`test_cr_0130_rbac_enforce.py` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

TC 判定基準兩條。「未列組合 deny-by-default」在矩陣判定函式中有對應實作：`api/services/role_service.py:376-377` 對未知 resource／action 直接回 `False`，`api/services/role_service.py:242`、`:246` 對矩陣無此角色列時回 `_perm(False, False, False, locked=True)`。「僅矩陣允許之組合通過」在程式碼中對不上——矩陣不是端點放行的判定來源，端點放行由 `role_required(*roles)` 的寫死角色元組決定（`api/core/deps.py:320`），矩陣只被 log-only 的 `permission_shadow` 讀取（`api/core/deps.py:339-378`）。TC 步驟所述的「矩陣掃描（自動生成案例）」在 `api/tests/` 中無對應實作：既有角色矩陣測試為手寫的 4 端點 × 5 角色（`api/tests/test_rbac_role_isolation.py:11-18`），非由矩陣自動生成的全端點案例。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 8. 權限與 RBAC 案例（TC-SEC-RBAC） |
| 前置 | 各角色 token × 全端點矩陣 |
| 步驟 | 矩陣掃描（自動生成案例） |
| 預期結果（判定基準） | 僅矩陣允許之組合通過；未列組合 deny-by-default |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-PLT-02、NFR-Sec-003 |
| 屬於哪條旅程腳本 | — |

出處：`smartlock-docs/enterprise/20_Test_Cases.md:331`。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 存在「全端點 × 全角色」矩陣掃描（自動生成案例） | `api/tests/test_rbac_role_isolation.py:11-18`（手寫 4 端點 × 5 角色）；`api/tests/test_cr_0092_rbac_hardening.py:23-31`（手寫 5 端點 × 2 角色） | 不一致（無自動生成案例） |
| 僅矩陣允許之組合通過 | 矩陣 `has_permission` 不接端點；`api/services/role_service.py:371` docstring 自述「純判斷、不擋」 | 不一致 |
| 未列組合 deny-by-default（未知 resource／action） | `api/services/role_service.py:376-377` | 一致 |
| 未列組合 deny-by-default（矩陣無此角色列） | `api/services/role_service.py:242`、`:246`、`:265` | 一致 |
| 未列組合 deny-by-default（端點層未列角色） | `api/core/deps.py:320-325`：`user.role not in roles` → 403 | 一致 |
| 死角色 token 不被任何守衛放行 | `api/core/deps.py:293` 註解；`api/tests/test_cr_0130_rbac_enforce.py:62-73` | 一致 |
| 端點層未掛 `role_required` 之組合 | 517 端點中 47 個僅 `require_tenant`、4 個僅 `get_current_user`、29 個無認證依賴 | 部分實作 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 測試框架 | 對「全端點 × 全角色」生成案例 | `MatrixScanExecuted` | 自動生成 | — | **找不到**：`api/tests/` 無矩陣驅動的案例產生器 |
| 任一角色 | 打 `role_required` 端點且角色不在元組內 | `RequestRejected(403)` | deny-by-default | `api/core/deps.py:320-325` | `FORBIDDEN`，403 |
| 未知角色（legacy／typo） | 查矩陣 | `PermissionDenied` | 矩陣查無行 | `api/services/role_service.py:265`（`_MATRIX.get(role_id, {})` → 空 dict → 無 granted） | 回空集合＝全拒 |
| 呼叫端 | `has_permission(resource=未知)` | `PermissionDenied` | fail-closed | `api/services/role_service.py:376-377` | 直接 `return False` |
| admin | `PUT rbac/roles/{role}/permissions` 改 locked 權限 | `RequestRejected` | locked 不可覆寫 | `api/services/role_service.py:455-457`、`:347` | locked 項不套 override |
| 系統 | 矩陣拒但端點放行 | `RbacShadowDeny` | log-only | `api/core/deps.py:361-369` | `logger.warning`，不改變結果 |

---

## 逐層走查

### 步驟 1 — 矩陣的維度與 deny-by-default 語意

`api/services/role_service.py:376-379`：

```python
    if action not in _ACTIONS or resource not in _RESOURCES:
        return False
    granted = await get_flat_permissions(tenant_id=tenant_id, role_name=role)
    return f"{resource}.{action}" in granted
```

`api/services/role_service.py:263-271` 的攤平只收 `granted=True` 的組合：

```python
def _flatten_matrix(role_id: str) -> set[str]:
    """把 _MATRIX[role_id] 攤平成 {`resource.action`} 集合（granted=True 的）。"""
    perms = _MATRIX.get(role_id, {})
    out: set[str] = set()
    for resource, p in perms.items():
        for action in _ACTIONS:
            if p.get(action):
                out.add(f"{resource}.{action}")
    return out
```

`_MATRIX.get(role_id, {})` 對矩陣未列的角色回空 dict，攤平後為空集合，任何 `resource.action` 皆不在其中。`api/services/role_service.py:171-174` 註解記載此即 legacy 角色的處理方式：「矩陣查無行＝deny-by-default」。

`api/services/role_service.py:240-249` 的呈現層同樣以全 False 補齊未列資源：

```python
def _role_to_dict(role_id: str, user_count: int) -> dict:
    meta = _ROLE_META[role_id]
    perms = _MATRIX.get(role_id, {})
    permissions = [
        {
            "resource": resource,
            **perms.get(resource, _perm(False, False, False, locked=True)),
        }
        for resource in _RESOURCES
    ]
```

### 步驟 2 — 動態覆寫（overrides）的邊界

`api/services/role_service.py:274-291` 的 `_parse_permission_code` 對未知 action／resource 回 422：

```python
    if action not in _ACTIONS:
        raise ApiError(
            "VALIDATION_ERROR",
            f"unknown action `{action}` in `{code}` (must be read/write/delete/approve)",
            422,
        )
    if resource not in _RESOURCES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"unknown resource `{resource}` in `{code}`",
            422,
        )
```

覆寫的授權者限制在 `api/services/role_service.py:49-58`：

```python
def can_grant(actor_role: str, target_role: str) -> bool:
    """actor 是否能修改 target_role 的權限（階層必須嚴格 >）。"""
    return ROLE_HIERARCHY.get(actor_role, 0) > ROLE_HIERARCHY.get(target_role, 0)


# 允許執行 updateRolePermissions 的角色白名單（SA-01：死角色移除，僅租戶 admin）
RBAC_ADMIN_ROLES = frozenset({"admin"})

# 允許被修改的目標角色白名單（避免誤打 typo 角色名稱寫進 DB）
ALLOWED_TARGET_ROLES = frozenset(ROLE_HIERARCHY.keys())
```

未知角色在 `ROLE_HIERARCHY.get(actor_role, 0)` 取 0，`can_grant` 天然為 False。

### 步驟 3 — 矩陣與端點放行的關係

`api/services/role_service.py:9-11` 模組 docstring：

```
權限維度為 4 動作 read / write / delete / approve（CR-0111，approve 依 BR-M17-01
「can-view / can-edit / can-approve」補上）。approve 目前僅供矩陣配置與呈現、可持久化，
端點強制授權（改讀 approve）屬 CR-0092 rbac-hardening 脈絡、另 CR。
```

`api/services/role_service.py:66-68`：

```python
# approve 維度（CR-0111，權威來源 final-spec sheet 36 BR-M17-01「can-view / can-edit /
# can-approve」）：目前僅供 RBAC 矩陣「配置與呈現」，端點強制授權（改讀 approve 權限）
# 屬 CR-0092 rbac-hardening 脈絡、另 CR，故此處 approve 落地為「可配置 + 可持久化」但
# 尚未接端點守衛（前端 matrixHint 已標「僅配置」）。
```

TC 判定基準寫「僅矩陣允許之組合通過」（出處 `smartlock-docs/enterprise/20_Test_Cases.md:331`）／程式碼中端點放行的判定來源為 `api/core/deps.py:320` 的 `user.role not in roles`，矩陣 `has_permission` 於 `api/services/role_service.py:371` 自述「純判斷、不擋」。此處僅並陳，不裁定。

### 步驟 4 — 既有「矩陣掃描」測試的實際形態

`api/tests/test_rbac_role_isolation.py:1-18`：

```python
"""5 角色 RBAC 權限隔離矩陣（A3，會議 2026-06-10 Action #7 / 決議 #9）。

驗證授權層強制：
  - forbidden 角色 → 403（role guard 在處理 body 前就擋下）
  - authorized 角色 → 非 403（穿過 RBAC guard；後續可能因 body/資料 200/404/422，
    但「不是 403」即證明授權層放行）

測 5 個操作角色（conftest fixture）：
  admin / operations_manager / dispatcher / customer_service / technician

代表性守衛端點：
  - POST /api/v1/auth/admin-reset-password   → role_required("admin")
  - GET  /api/v1/technicians/me              → role_required("technician")
  - POST /tenants/{tid}/customers            → role_required("admin","operations_manager")
  - GET  /api/v1/admin/schedule-requests     → role_required("admin","operations_manager")
```

其斷言核心在 `api/tests/test_rbac_role_isolation.py:47-58`：

```python
async def _assert_matrix(client, *, method, path, json, allowed, role_headers):
    """allowed = 可穿過授權層的角色集合；其餘角色應 403。"""
    for role, headers in role_headers.items():
        res = await client.request(method, path, headers=headers, json=json)
        if role in allowed:
            assert res.status_code != 403, ...
        else:
            assert res.status_code == 403, ...
```

`allowed` 集合是各測試手寫傳入的字面值，不是由 `role_service._MATRIX` 推導。

### 步驟 5 — 端點層未被矩陣涵蓋的部分

以與 `scripts/ci/endpoint-guard-audit.py:26-28` 相同的裝飾器切分規則普查 `api/routers/*.py`（探針腳本寫於 scratchpad，**不在 repo 內**）：517 個 route handler 中 383 個掛 `role_required`、47 個僅 `require_tenant`、45 個 `require_platform_admin`、29 個無認證依賴（login／refresh／register／webhook／consumer token 類）、8 個 S2S credential、4 個僅 `get_current_user`、1 個 keeper。

---

## 既有測試證據

```
cd api && POSTGRES_URI=<本機測試庫> PYTHONPATH=<scratchpad> uv run pytest \
  tests/test_cr_0092_rbac_hardening.py tests/test_cr_0130_rbac_enforce.py \
  tests/test_rbac_role_isolation.py tests/test_rbac_dynamic.py \
  tests/test_rbac_v2_endpoint.py tests/test_sec_legacy_endpoint_guards.py \
  tests/test_cr_0111_rbac_approve_roles.py tests/test_cr_0111_has_permission_shadow.py \
  -p winloop_plugin -q
1 failed, 78 passed in 6.04s
```

唯一失敗項 `test_sec_legacy_endpoint_guards.py::test_endpoint_guard_audit_clean` 的失敗原因是子行程以 `python3` 呼叫（`api/tests/test_sec_legacy_endpoint_guards.py:175-183`），Windows 本機無此執行檔，回傳碼 9009；同腳本以 `python` 直接執行為 exit 0。

`api/tests/test_cr_0111_has_permission_shadow.py` 覆蓋 `has_permission` 的判定行為，`api/tests/test_rbac_dynamic.py` 覆蓋 overrides 持久化，兩者皆全數通過。

---

## 事實結論

1. 矩陣對未知 resource／action 回 `False`（`api/services/role_service.py:376-377`）；對矩陣未列角色回空 granted 集合（`api/services/role_service.py:265`）。
2. 端點層對未列角色回 403 `FORBIDDEN`（`api/core/deps.py:320-325`）。
3. 矩陣不是端點放行的判定來源，`has_permission` docstring 自述「純判斷、不擋」（`api/services/role_service.py:371`），`permission_shadow` 自述「絕不 raise、絕不改變請求結果」（`api/core/deps.py:347`）。
4. `approve` 動作在矩陣中可配置可持久化，但未接端點守衛（`api/services/role_service.py:66-68`）。
5. `api/tests/` 中無由矩陣自動生成的全端點案例；既有矩陣測試為手寫 4 端點 × 5 角色（`api/tests/test_rbac_role_isolation.py`）與 5 端點 × 2 角色（`api/tests/test_cr_0092_rbac_hardening.py`）。
6. 覆寫 API 的授權者限 `admin`（`api/services/role_service.py:55`），且階層必須嚴格大於目標角色（`api/services/role_service.py:51`）。
