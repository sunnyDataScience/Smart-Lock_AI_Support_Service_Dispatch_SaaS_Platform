# TC-SEC-RBAC-01

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務；另以本機 Docker 測試庫實跑既有測試） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/core/deps.py`、`api/routers/*.py`（517 個 route handler）、`api/services/role_service.py`、`api/tests/test_cr_0092_rbac_hardening.py`、`test_cr_0130_rbac_enforce.py`、`test_sec_legacy_endpoint_guards.py`、`scripts/ci/endpoint-guard-audit.py` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

TC 判定基準有三條。第一條「technician / vendor token 打敏感寫入端點一律 403」在程式碼中有對應實作並有既有測試釘住（`api/tests/test_cr_0130_rbac_enforce.py:53-59`，8 條金流／派工／設定寫入樣本 × 2 角色斷言 403 `FORBIDDEN`）。第二條「授權矩陣（12 角色 × 12 資源 × 4 動作）與端點守衛一致」在程式碼中對不上兩件事：矩陣為 **7 個角色**（`api/services/role_service.py:103-205`，`test_cr_0130_rbac_enforce.py:87-95` 明文釘住 7 角色正典），且矩陣**不是端點授權的來源**——端點授權由 `role_required(*ROLES)` 的寫死角色元組決定（`api/core/deps.py:307-336`），矩陣只在 `permission_shadow` 的 log-only 稽核中被讀取（`api/core/deps.py:339-378`）。第三條「deny log 清零」的觀測對象 `RBAC_SHADOW_DENY` 存在於 `api/core/deps.py:362-369`，但其計數需執行期日誌，靜態走查不可得。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 8. 權限與 RBAC 案例（TC-SEC-RBAC） |
| 前置 | technician / vendor token |
| 步驟 | 打金流、派工、設定等敏感寫入端點（約 80 個） |
| 預期結果（判定基準） | 一律 403；授權矩陣（12 角色 × 12 資源 × 4 動作）與端點守衛一致，deny log 清零 |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-PLT-02、NFR-Sec-003 |
| 屬於哪條旅程腳本 | SC-11、SC-16 |

出處：`smartlock-docs/enterprise/20_Test_Cases.md:330`。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| technician token 打敏感寫入 → 403 | `api/core/deps.py:320-325`；樣本清單與斷言 `api/tests/test_cr_0130_rbac_enforce.py:31-59` | 一致 |
| vendor token 打敏感寫入 → 403 | 同上（`vendor` 不在任何 `deps.py:293-304` 角色集合內） | 一致 |
| 敏感寫入端點「約 80 個」 | `api/core/deps.py:283-285` 註解記載稽核當時「407 端點中 80 個敏感寫入只用 require_tenant」；現況普查見「逐層走查／步驟 2」 | 部分實作（現況寫入端點 302 個，其中 234 個掛 `role_required`，8 個僅 `require_tenant`） |
| 授權矩陣 12 角色 | `api/services/role_service.py:103-205` 共 7 個 role key | 不一致（7 ≠ 12） |
| 授權矩陣 12 資源 | `api/services/role_service.py:81-94` `_RESOURCES` 共 12 項 | 一致 |
| 授權矩陣 4 動作 | `api/services/role_service.py:260` `_ACTIONS = ("read","write","delete","approve")` | 一致 |
| 矩陣與端點守衛一致 | 矩陣不參與端點授權；`api/services/role_service.py:364-379` docstring 自述「純判斷、不擋」 | 部分實作 |
| deny log 清零 | `api/core/deps.py:362-369` 有 `RBAC_SHADOW_DENY` warning；計數需執行期日誌 | 無法靜態判定 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| technician | POST 庫存／定價／退款發起 | `RequestRejected(403)` | 角色白名單 | `api/core/deps.py:320-325` | `FORBIDDEN`，403 |
| vendor | 同上 | `RequestRejected(403)` | 角色白名單 | 同上 | `FORBIDDEN`，403（`vendor` 不在 `deps.py:293-304` 任一集合） |
| tenant_admin / super_admin（死角色） | POST 庫存／排程報表 | `RequestRejected(403)` | 死角色移除 | `api/core/deps.py:293`、`api/tests/test_cr_0130_rbac_enforce.py:62-73` | 403 |
| 任一角色 | 打端點 | `PermissionMatrixEvaluated` | 矩陣為授權來源 | — | **找不到**：矩陣只被 `permission_shadow` 讀，且該 dependency「絕不 raise」（`api/core/deps.py:347-348`） |
| 系統 | 矩陣拒但端點放行 | `RbacShadowDeny` | 落差蒐集 | `api/core/deps.py:362-369` | `logger.warning("RBAC_SHADOW_DENY ...")`，不改變請求結果 |

---

## 逐層走查

### 步驟 1 — 端點層守衛的實作

`api/core/deps.py:307-336`：

```python
def role_required(*roles: str, fail_closed: bool = False):
    """Dependency factory 限制角色。
    ...
    """
    async def _dep(
        request: Request,
        authorization: str | None = Header(default=None, alias="Authorization"),
        x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    ) -> CurrentUser:
        user = await require_tenant(request, authorization, x_tenant_id)
        if roles and user.role not in roles:
            raise ApiError(
                error_code="FORBIDDEN",
                message=f"Requires one of roles: {', '.join(roles)}",
                status_code=403,
            )
```

角色集合常數在 `api/core/deps.py:293-304`：

```python
FULL_ACCESS_ROLES: tuple[str, ...] = ("admin",)
OPS_ROLES: tuple[str, ...] = FULL_ACCESS_ROLES + ("operations_manager",)
DISPATCH_ROLES: tuple[str, ...] = OPS_ROLES + ("dispatcher",)
BACKOFFICE_ROLES: tuple[str, ...] = DISPATCH_ROLES + ("customer_service",)
REVIEW_ROLES: tuple[str, ...] = OPS_ROLES + ("reviewer",)
TECH_ACTION_ROLES: tuple[str, ...] = BACKOFFICE_ROLES + ("technician",)
```

`vendor` 不出現在任何一個集合中；`technician` 只出現在 `TECH_ACTION_ROLES`。

### 步驟 2 — 「約 80 個敏感寫入端點」的現況普查

`api/core/deps.py:283-285` 記載該數字的來源：

```python
# 為什麼集中在此：稽核發現 407 端點中 80 個敏感寫入只用 require_tenant（不檢查
# 角色），任何登入者含 technician/vendor 皆可寫金流/設定/派工。
```

以與 `scripts/ci/endpoint-guard-audit.py:26-28` 相同的裝飾器切分規則對 `api/routers/*.py` 全量普查（探針腳本寫於 scratchpad，**不在 repo 內**），本次基準 commit 結果：

```
== 全部端點守衛分佈 == 517
  role                 383
  tenant_only          47
  platform_admin       45
  no_dep               29
  s2s                  8
  authenticated_only   4
  keeper               1
== 寫入端點（POST/PUT/PATCH/DELETE）== 302
  role                 234
  platform_admin       28
  no_dep               21
  tenant_only          8
  s2s                  7
  authenticated_only   3
  keeper               1
```

寫入端點中未掛 `role_required` 的 32 條，逐條分類如下：

| 類別 | 端點 | 檔案 |
|---|---|---|
| 未認證公開（login / refresh / register / reset / webhook / consumer token） | `/auth/login`、`/auth/refresh`、`/auth/request-password-reset`、`/auth/confirm-password-reset`、`/technicians/login`、`/technicians/register`、`/technicians/registration-documents`、`/vendors/login`、`/platform/auth/login`、`/platform/auth/refresh`、`/platform/brand-applications`、`/platform/brand-applications:lookup`、`/line/webhook`、`/technicians/line-webhook`、`/consumer/*`(5)、`/public/scope-changes/{token}`、`/tenants/{tenantId}/staff-applications` | `auth.py`、`platform_auth.py`、`platform_brand_applications.py`、`line_webhook.py`、`technician_line.py`、`consumer_v2.py`、`public.py`、`staff_applications.py` |
| 僅需登入（`get_current_user`） | `/auth/logout`、`/auth/change-password`、`PATCH /auth/me` | `api/routers/auth.py:232-235`、`:255-257` |
| 僅 `require_tenant`（無角色收斂） | `PATCH /tenants/{tenantId}/devices/{deviceId}/warranty`、`PATCH /notifications/{id}`、`POST /notifications/bulk`、`POST /notifications/mark-all-read`、`PATCH /tenants/{tenantId}/notifications/{notificationId}`、`POST /tenants/{tenantId}/notifications:bulk`、`POST /tenants/{tenantId}/notifications:mark-all-read`、`POST /tenants/{tenantId}/work-orders:search` | `device_warranty.py:102-108`、`notifications.py`、`notifications_v2.py`、`work_orders_v2.py` |

其中 `api/routers/device_warranty.py:102-110` 的依賴為：

```python
async def patch_device_warranty(
    body: DeviceWarrantyPatch,
    response: Response,
    tenantId: str = Path(...),
    deviceId: str = Path(...),
    user: CurrentUser = Depends(require_tenant),
    sod: SodActors = Depends(require_sod_actors),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
```

`require_sod_actors` 的性質由 `api/tests/test_cancel_v2_role_guard.py:79-93` 明文釘住：「它只驗兩個 header 有值且相異，是 client 可控字串，不比對真實身分」。

### 步驟 3 — 授權矩陣的維度

`api/services/role_service.py:81-94`（12 資源）：

```python
_RESOURCES = [
    "work_orders", "technicians", "customers", "accounting",
    "invoices", "refunds", "inventory", "warranty",
    "disputes", "audit_logs", "roles", "system_settings",
]
```

`api/services/role_service.py:260`（4 動作）：

```python
_ACTIONS = ("read", "write", "delete", "approve")
```

`api/services/role_service.py:103-205` 的 `_MATRIX` key 為 `admin` / `operations_manager` / `reviewer` / `technician` / `line_user` / `dispatcher` / `customer_service`，共 7 個。`api/services/role_service.py:171-174` 註解記載 6 個 legacy 角色行已移除：

```python
    # ── SA-01（CR-0130）：CR-0111 的 legacy 6 行（accounting/supervisor/auditor/
    # family_reviewer/distributor/brand_oem）已依業主裁決移除——矩陣＝7 角色正典
    # ＋line_user 通道行。歷史帳號若持 legacy 角色：登入已擋（_ADMIN_WEB_ROLES）、
    # 矩陣查無行＝deny-by-default。──────────────────────────────────────────
```

`api/tests/test_cr_0130_rbac_enforce.py:87-95` 以測試釘住此 7 角色：

```python
def test_role_canon_consistency():
    """矩陣/階層/RBAC_ADMIN/角色組常數 收斂 7 角色正典（13_Security §3.1）。"""
    canon = {"admin", "operations_manager", "reviewer", "customer_service",
             "dispatcher", "technician", "line_user"}
    assert set(r._MATRIX) == canon
```

TC 判定基準寫「12 角色 × 12 資源 × 4 動作」（出處 `smartlock-docs/enterprise/20_Test_Cases.md:330`）／程式碼與其測試釘死為 7 角色 × 12 資源 × 4 動作（`api/services/role_service.py:103-205`、`api/tests/test_cr_0130_rbac_enforce.py:90-93`）。此處僅並陳，不裁定。

### 步驟 4 — 矩陣與端點守衛的關係

`api/services/role_service.py:364-379`：

```python
async def has_permission(
    *, tenant_id: str, role: str, resource: str, action: str
) -> bool:
    """矩陣授權判斷（CR-0111 後續）：role 對 (resource, action) 是否有權。
    ...
    **純判斷、不擋**——目前僅供 `core.deps.permission_shadow` shadow 稽核用（記錄
    「矩陣 vs 現行寫死 role_required」的落差），尚未成為端點強制授權來源；把授權收斂
    到矩陣屬 CR-0092 rbac-hardening / 另 CR（需先對帳 195 條 role_required）。
    未知 resource / action 一律回 False（fail-closed）。
    """
```

`api/core/deps.py:339-378` 的 `permission_shadow`：

```python
    """Shadow-mode RBAC 稽核 dependency（CR-0111 後續 · log-only · 永不擋）。
    ...
    **絕不 raise、絕不改變請求結果**（授權仍由既有守衛決定）。
    """
```

deny log 的產生點在 `api/core/deps.py:361-369`：

```python
            if not allowed:
                logger.warning(
                    "RBAC_SHADOW_DENY resource=%s action=%s role=%s tenant=%s "
                    "— 矩陣會拒但目前放行（接強制前需對帳）",
                    resource, action, user.role, user.tenant_id,
                )
```

### 步驟 5 — 等價路徑的守衛對稱性

`scripts/ci/endpoint-guard-audit.py:1-14` 掃「v2/legacy 孿生」與「list/detail 不對稱」。本次執行結果：

```
$ python scripts/ci/endpoint-guard-audit.py
✅ 端點守衛稽核：無 v2/legacy 或 list/detail 不對稱
EXIT=0
```

該腳本另有 4 條人工例外（`scripts/ci/endpoint-guard-audit.py:35-40`）：`problem_cards.py` 與 `problem_cards_v2.py` 的 `/problem-cards/{id}` 與 `/problem-cards/{id}/export`。

---

## 既有測試證據

本機 Docker 測試庫（`smartlock-test-db`，pg17，port 5433）。

```
cd api && POSTGRES_URI=<本機測試庫> PYTHONPATH=<scratchpad> uv run pytest \
  tests/test_cr_0092_rbac_hardening.py tests/test_cr_0130_rbac_enforce.py \
  tests/test_rbac_role_isolation.py tests/test_rbac_dynamic.py \
  tests/test_rbac_v2_endpoint.py tests/test_sec_legacy_endpoint_guards.py \
  tests/test_cr_0111_rbac_approve_roles.py tests/test_cr_0111_has_permission_shadow.py \
  -p winloop_plugin -q
1 failed, 78 passed in 6.04s
```

唯一失敗項為 `tests/test_sec_legacy_endpoint_guards.py::test_endpoint_guard_audit_clean`，失敗原因是該測試以 `python3` 呼叫子行程（`test_sec_legacy_endpoint_guards.py:175-183`），Windows 本機無 `python3` 可執行檔，回傳碼 9009（命令找不到）而非稽核不通過：

```
E       assert 9009 == 0
E        +  where 9009 = CompletedProcess(args=['python3', '...\\endpoint-guard-audit.py'], returncode=9009, stdout='', stderr='')
```

同一支腳本以 `python` 直接執行的結果為 exit 0（見步驟 5）。

對到 TC 步驟的測試：`api/tests/test_cr_0130_rbac_enforce.py:53-59`

```python
@pytest.mark.parametrize("role", ["technician", "vendor"])
async def test_protected_writes_forbidden_for_field_roles(client, role):
    """SA-01 驗收線：technician / vendor token 寫金流/派工/設定 → 一律 403。"""
    headers = _headers(role)
    for method, path, body in _PROTECTED_WRITES:
        res = await client.request(method, path, json=body, headers=headers)
        assert res.status_code == 403, f"{role} {method} {path} → {res.status_code}（應 403）"
        assert res.json().get("error_code") == "FORBIDDEN"
```

`_PROTECTED_WRITES`（`test_cr_0130_rbac_enforce.py:31-40`）為 8 條樣本，非 TC 所述的約 80 個端點全集。

---

## 事實結論

1. `role_required` 為端點授權的實際強制點，違反回 403 `FORBIDDEN`（`api/core/deps.py:320-325`）。
2. `vendor` 不存在於 `api/core/deps.py:293-304` 的任何角色集合；`technician` 僅存在於 `TECH_ACTION_ROLES`。
3. 517 個 route handler 中 383 個掛 `role_required`；302 個寫入端點中 234 個掛 `role_required`、8 個僅 `require_tenant`、3 個僅 `get_current_user`、21 個無認證依賴（皆為 login／refresh／register／webhook／consumer token／公開申請類）。
4. 授權矩陣為 7 角色 × 12 資源 × 4 動作（`api/services/role_service.py:103-205`、`:81-94`、`:260`），並由 `api/tests/test_cr_0130_rbac_enforce.py:87-95` 釘住。
5. 矩陣不參與端點授權判定；`has_permission` 的 docstring 自述「純判斷、不擋」（`api/services/role_service.py:371`），`permission_shadow` 自述「絕不 raise、絕不改變請求結果」（`api/core/deps.py:347`）。
6. `RBAC_SHADOW_DENY` 日誌行存在於 `api/core/deps.py:362`；其實際筆數為執行期資料，本次未取得。
7. 既有測試以 8 條樣本端點 × 2 個角色驗證 403，非全端點掃描。
8. 端點守衛對稱性稽核腳本本次執行為零不對稱（exit 0）。
