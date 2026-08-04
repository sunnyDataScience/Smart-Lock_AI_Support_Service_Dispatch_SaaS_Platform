# TC-DISPATCH-02 — 手動派工、override 稽核與角色授權

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 6） |
| 走查時間 | 2026-08-03 17:22（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/routers/work_orders_v2.py`、`api/routers/dispatch_v2.py`、`api/routers/dispatch.py`、`api/core/deps.py`、`api/core/auth.py`、`api/services/work_order_service.py`、`api/services/dispatch_service.py` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 手動派工三個入口皆存在且掛 `role_required(..., fail_closed=True)`；override 稽核只在兩個條件下寫入 `audit_log_service`（帶 `override_reason` query，或呼叫者角色為 `customer_service`），且僅 `assignWorkOrderV2` 兩者兼備。TC 判定基準「非 dispatcher 角色 → 403」與程式碼的四角色白名單（admin / operations_manager / dispatcher / customer_service）不一致。另查得 `dispatch:plan` / `/dispatch/assign` 路徑不把 `actor_role` 與 `override_reason` 傳進 `assign_order`，該路徑上的 gate override 不成立。 |

**TC 原文**｜前置：dispatcher 角色｜步驟：手動派工 + override｜判定基準：成功且 audit 記 override；非 dispatcher 角色 → 403｜⚠ 未標註｜P0｜FR-API-06｜SC-05

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| dispatcher | 手動派工 | `WorkOrderAssigned` | 指定技師覆寫自動建議 | `routers/work_orders_v2.py:498-530` | `assign_order(...)`，狀態 → `assigned` |
| 系統 | 記錄 override | `OverrideAudited` | 覆寫必留 audit（who/why） | `routers/work_orders_v2.py:531-541` | 僅在 `override_reason` 非空時 `log_event(action="quote_gate_override")` |
| 系統 | 記錄客服繞過 | `BypassAudited` | PM Q6=A | `routers/work_orders_v2.py:542-557` | 僅 `user.role in {"customer_service"}` 時記 `manual_dispatch_bypass` |
| 非授權角色 | 手動派工 | `Forbidden` | 403 | `core/deps.py:320-325` | 白名單外角色 → 403 `FORBIDDEN` |
| 系統 | 安全狀態不可驗 | — | fail-closed | `core/deps.py:326-334` | 503 `SECURITY_STATE_UNAVAILABLE` |

---

## 走查紀錄

### 步驟 1 — 手動派工的入口與角色白名單

- **動作**：列出手動指派端點與其守衛
- **預期**：dispatcher 可派工
- **實際**：三個入口，白名單皆為 `admin / operations_manager / dispatcher / customer_service`

`api/routers/work_orders_v2.py:498-514`

```python
@router.post(
    "/tenants/{tenantId}/work-orders/{id}:assign",
    operation_id="assignWorkOrderV2",
    ...
    override_reason: str | None = Query(
        default=None,
        description="CR-0095：主管強制派工原因（繞過『須有已同意報價』gate；僅 admin/ops 生效，audited）",
    ),
    user: CurrentUser = Depends(role_required(*_DISPATCH_ALLOWED_ROLES, fail_closed=True)),
```

`api/routers/dispatch_v2.py:37-45`

```python
# POST /tenants/{tenantId}/dispatch:plan — FR-0003/ADR-0045
# 與 legacy POST /dispatch/assign 相同角色白名單
_PLAN_ALLOWED_ROLES = (
    "admin",
    "operations_manager",
    "dispatcher",
    "customer_service",
)
_BYPASS_ROLES = {"customer_service"}
```

`api/routers/dispatch.py:26-34` 為 legacy `/dispatch/assign` 的同名常數 `_DISPATCH_ALLOWED_ROLES`，內容相同。

TC 判定基準寫「非 dispatcher 角色 → 403」；程式碼對 `admin`、`operations_manager`、`customer_service` 三個非 dispatcher 角色亦放行。此處僅並陳，不裁定。

### 步驟 2 — 403 的實際產生點

- **動作**：讀 `role_required`
- **預期**：白名單外角色 403
- **實際**：`FORBIDDEN` 403；另有 `fail_closed=True` 的 503 分支

`api/core/deps.py:314-335`

```python
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
        if fail_closed:
            from core.auth import security_state_verifiable

            if not await security_state_verifiable(user.role):
                raise ApiError(
                    error_code="SECURITY_STATE_UNAVAILABLE",
                    message="安全狀態不可驗（撤銷/停權查核離線）——關鍵金流/派工寫入拒絕執行（SA-05 fail-closed）",
                    status_code=503,
                )
        return user
```

`api/core/deps.py:293-299` 為角色集合定義：

```python
FULL_ACCESS_ROLES: tuple[str, ...] = ("admin",)
#: 營運後台寫入（accounting / billing / pricing / vendor-mgmt / warranty / 結算）
OPS_ROLES: tuple[str, ...] = FULL_ACCESS_ROLES + ("operations_manager",)
#: 派工寫入（dispatch / 自動媒合 / 技師生命週期管理）
DISPATCH_ROLES: tuple[str, ...] = OPS_ROLES + ("dispatcher",)
#: 後台唯讀／一般後台操作（含客服）
BACKOFFICE_ROLES: tuple[str, ...] = DISPATCH_ROLES + ("customer_service",)
```

`GET dispatch:candidates` / `POST dispatch:auto-match` 用的是 `DISPATCH_ROLES`（不含 `customer_service`，`routers/dispatch_v2.py:65`、`:122`），與指派端點的四角色白名單不同集合。

### 步驟 3 — override 稽核的寫入條件

- **動作**：定位 audit 寫入分支
- **預期**：override 一律留 audit（who/why）
- **實際**：兩個獨立條件，且三個入口覆蓋不一致

`api/routers/work_orders_v2.py:531-557`

```python
    # CR-0095：主管 override 報價同意 gate → 留稽核軌跡
    if override_reason and override_reason.strip():
        await audit_log_service.log_event(
            event_type="dispatch_decision",
            actor_id=user.user_id,
            actor_role=user.role,
            action="quote_gate_override",
            target_type="work_order",
            target_id=id,
            payload={"endpoint": "assignWorkOrderV2", "override_reason": override_reason.strip()},
        )
    # PM Q6=A — 客服繞過自動派工必須留稽核軌跡
    if user.role in _BYPASS_ROLES:
```

`api/routers/dispatch_v2.py:181-195`（`dispatch:plan`）只有 `_BYPASS_ROLES`（= `{"customer_service"}`）分支：

```python
    # 客服繞過自動派工 → 稽核軌跡（ADR-0045 §4 / PM Q6=A）
    if user.role in _BYPASS_ROLES:
        await audit_log_service.log_event(
            event_type="dispatch_decision",
            actor_id=user.user_id,
            actor_role=user.role,
            action="manual_dispatch_bypass",
            target_type="work_order",
            target_id=str(body.work_order_id),
            payload={
                "endpoint": "planDispatchV2",
                "technician_id": str(body.technician_id),
                "override_reason": body.override_reason or "未提供理由",
            },
        )
```

`api/routers/dispatch.py:121-135`（legacy `/dispatch/assign`）同樣只有 `_BYPASS_ROLES` 分支。

即：`dispatcher` 角色帶 `override_reason` 走 `dispatch:plan`／`/dispatch/assign` 時，不會落 `audit_log_service` 記錄；走 `assignWorkOrderV2` 帶 `override_reason` query 才會。

### 步驟 4 — 非 audit_log 的 override 軌跡

- **動作**：確認是否另有結構化軌跡
- **預期**：可查 who/why
- **實際**：`dispatch_logs` 與 `work_order_events` 各寫一筆，內容為 `reason_code` / `reason_text`

`api/services/work_order_service.py:2275-2293`

```python
    await db_module._conn.execute(
        "INSERT INTO dispatch_logs "
        "  (work_order_id, action, technician_id, notes) "
        "VALUES (%s::uuid, 'assign', %s::uuid, %s)",
        (wo_id, technician_id, note),
    )
    # 也寫一筆 work_order_events 對齊 reassign 的 timeline 觀感
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="assign",
        payload={
            "technician_id": str(technician_id),
            "reason_code": reason_code,
            "reason_text": reason_text,
            "from_status": current,
        },
    )
```

`note` 由 `api/services/work_order_service.py:2253-2255` 組成（`[ASSIGNED:{reason_code}] {reason_text}`）。`dispatch_logs` 無 `actor_user_id` 欄位寫入（該 INSERT 只有 4 欄）。

### 步驟 5 — `dispatch:plan` 路徑的 override 語意

- **動作**：追 `override_reason` 從 router 到 service 的傳遞
- **預期**：override 生效
- **實際**：`dispatch_service.assign_dispatch` 未傳 `actor_role` 與 `override_reason`，只把它塞進 `reason_text`

`api/services/dispatch_service.py:632-651`

```python
async def assign_dispatch(
    *,
    tenant_id: str,
    work_order_id: str,
    technician_id: str,
    override_reason: str | None = None,
) -> dict:
    """assignDispatch — body 版本的指派；複用 work_order_service.assign_order。
    ...
    """
    from services.work_order_service import assign_order

    return await assign_order(
        tenant_id=tenant_id,
        wo_id=work_order_id,
        technician_id=technician_id,
        reason_code="other",
        reason_text=override_reason,
    )
```

`assign_order` 的 override 判斷條件（`api/services/work_order_service.py:2079-2080` 定義角色集，`:2131-2137` 使用）：

```python
_QUOTE_GATE_OVERRIDE_ROLES = {"admin", "operations_manager"}  # SA-01：死角色移除
```

```python
    if (
        actor_role in _QUOTE_GATE_OVERRIDE_ROLES
        and override_reason
        and override_reason.strip()
    ):
        logger.info("assign brand-auth overridden by %s for wo=%s", actor_role, wo_id[:8])
        return
```

因 `actor_role` 與 `override_reason` 皆未傳入，經 `dispatch:plan` / `/dispatch/assign` 呼叫時兩者恆為 `None`，報價 gate（`:2083`）、熔斷 gate（`:2240-2249`）、品牌授權 gate（`:2251`）的 override 分支在該路徑皆不成立。

### 步驟 6 — 執行既有測試

- **動作**：跑手動派工測試（由統籌者於本批次執行，數字沿用不重跑）
- **預期**：取得執行證據
- **實際**：第一輪無資料庫時單獨跑 `test_admin_assign_does_not_write_bypass_audit` 回 `fail_closed=True` 分支的 503；建立本機測試庫後重跑，`test_manual_dispatch.py` 10 項全數通過

第一輪（無資料庫）：

```
cd api && python -m pytest tests/test_manual_dispatch.py::test_admin_assign_does_not_write_bypass_audit -q --tb=line
1 failed in 3.02s

ERROR    api.db:db.py:48 環境變數 POSTGRES_URI 未設定
api/tests/test_manual_dispatch.py:350: AssertionError: {"type":"urn:smartlock:error:security_state_unavailable","status":503,
"error_code":"SECURITY_STATE_UNAVAILABLE","message":"安全狀態不可驗（撤銷/停權查核離線）——關鍵金流/派工寫入拒絕執行（SA-05 fail-closed）"}
```

該 503 的產生點為 `api/core/deps.py:326-334`（上引），判準函式為 `api/core/auth.py:202-215`：

```python
async def security_state_verifiable(role: str | None = None) -> bool:
    """安全狀態是否可驗（SA-05 / CR-0131）：能取得對應安全庫連線＝可查 revoked_jti
    與 users.is_active。DB 不可用 → False——關鍵金流/派工寫入端點（fail_closed=True
    白名單）此時拒絕請求（503），不退 claims-only；一般端點維持 fail-open（C-05 取捨）。
    ...
    """
    if role == "technician" and db_module.tech_db_enabled():
        try:
            await db_module.require_tech_conn()
        except Exception:  # noqa: BLE001 — RuntimeError(Tech DB unavailable) 等
            return False
    return (await _security_conn(role)) is not None
```

即在無資料庫的本機環境下，手動派工寫入被拒（503）而非放行。

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_manual_dispatch.py -q -p winloop_plugin --tb=no
10 passed in 2.99s
```

安全狀態可驗後不再落入 `SECURITY_STATE_UNAVAILABLE` 分支，`test_admin_assign_does_not_write_bypass_audit`（斷言 admin 手動指派**不**寫 `manual_dispatch_bypass` audit）通過。同批派工測試逐檔執行結果：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/<檔名> -q -p winloop_plugin --tb=no

test_cr_0051_dispatch_eligibility.py       8 passed in 0.38s
test_cr_0030_dispatch_mode.py              3 passed in 2.97s
test_manual_dispatch.py                   10 passed in 2.99s
test_dispatch_v2_endpoint.py               6 passed in 2.97s
test_dispatch_plan_v2_endpoint.py          8 passed in 2.96s
test_cr_0164_tech_mirror_projection.py     5 passed in 0.46s
test_cr_0172_tech_dispatch_outbox.py       5 passed in 0.40s
test_dispatch_fairness_load.py             7 passed in 0.40s
```

`test_manual_dispatch.py` 的 10 項含「technician 呼叫 assignWorkOrder → 403」（`:148-165`）、「brand_oem 呼叫 assignDispatch → 403」（`:391-415`）與 customer_service 繞過寫 `audit_log_service.log_event` 的四項（`:114-144`、`:201-233`、`:280-318` 等）；該檔以 mock `audit_log_service.log_event` 驗證呼叫契約（檔頭 `:19-20` 自述「不依賴真實 DB」），故驗的是 hook 是否被呼叫，非 audit 資料落庫。

---

## 觀測到的其他事實

- `smartlock-docs/enterprise/04_SRS.md:297`（FR-API-06）記載「小編指定技師覆寫自動建議｜覆寫必留 audit（who/why）」。
- `assignWorkOrderV2` 的 `override_reason` 是 query 參數（`routers/work_orders_v2.py:509-512`），`dispatch:plan` 的 `override_reason` 是 body 欄位（`DispatchAssignRequest`，`routers/dispatch_v2.py:178`）。
- 改派入口 `reassign_order`（`services/work_order_service.py:2348`）必填 `reason`（`:2374-2376`），並在 `:2427` 以該 `reason` 當作 override 傳入 `_assert_brand_authorized`。
