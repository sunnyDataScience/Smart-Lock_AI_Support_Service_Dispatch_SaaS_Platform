# TC-WO-07 — 主管 override 結案與技師走 override 路徑的 403

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試，override 兩項通過（見步驟 5） |
| 走查時間 | 2026-08-03 19:48（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/services/work_order_service.py:1541-1549`、`:1893-1905`、`api/routers/work_orders_v2.py:564-601`、`api/routers/work_orders.py:222-254`、`api/core/deps.py:293-304`、`api/tests/test_cr_0039_completion_gate.py:135-157` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 三項判定條件中，「override 通過（跳過證據閘）」與「技師走 override 路徑 → 403」皆有對應實作；「audit 記 COMPLETE_OVERRIDE + 角色 + reason」則分散在兩個載體：`COMPLETE_OVERRIDE` 字串前綴寫進 `work_orders.service_report`，角色與 reason 另存 `work_order_events` payload（`actor_role` / `override_reason` / `is_override`），而 `audit_events` 稽核表在完工路徑上零寫入。另可觀測到 override 端點的角色白名單為 `BACKOFFICE_ROLES`（admin / operations_manager / dispatcher / customer_service），非僅主管角色。 |

**TC 原文**｜前置：主管角色 + override 理由｜步驟：override 結案｜判定基準：通過；audit 記 COMPLETE_OVERRIDE + 角色 + reason；技師角色走 override 路徑 → 403｜⚠ 未標註｜P0｜FR-API-08、FR-API-09｜SC-06

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 主管 | POST `.../work-orders/{id}:complete` | `WorkOrderCompletedByOverride` | 跳過照片/簽名/序號閘 | `work_order_service.py:1541-1549` | `if is_override:` 直接 return 加註記的 summary |
| 主管 | 未填理由 | `OverrideRejected(422)` | reason 必填 | `work_order_service.py:1544-1545` | 422 `VALIDATION_ERROR` |
| 技師 | POST `:complete` | `Forbidden(403)` | 技師須走現場硬閘 | `routers/work_orders_v2.py:581-586` | 403 `FORBIDDEN` |
| 系統 | 留痕 | `AuditTrailWritten` | 記 COMPLETE_OVERRIDE + 角色 + reason | `work_order_service.py:1546-1549`、`:1893-1905` | summary 前綴 + `work_order_events` payload |
| 系統 | 寫 `audit_events` | `AuditEventLogged` | — | — | **完工路徑無 `log_event` 呼叫** |

---

## 走查紀錄

### 步驟 1 — override 通過與 reason 必填

- **動作**：讀硬閘的 override 分支
- **預期**：帶 reason 通過、跳過證據閘
- **實際**：一致

`api/services/work_order_service.py:1541-1549`

```python
    if is_override:
        if not policy.get("allow_supervisor_override", True):
            raise ApiError("OVERRIDE_NOT_ALLOWED", "完工 override 已停用", 403)
        if not (override_reason and override_reason.strip()):
            raise ApiError("VALIDATION_ERROR", "主管 override 完工必須填寫原因", 422)
        return (
            f"[COMPLETE_OVERRIDE by {actor_role or 'supervisor'}: "
            f"{override_reason.strip()[:300]}] {summary}"
        )
```

此 `return` 位於照片閘（`:1552`）之前，故 override 路徑完全不執行照片 / 簽名 / 序號 / 三段同意 / pending scope / 地址 / 報價七道閘。

### 步驟 2 — `COMPLETE_OVERRIDE` 字串的落點

- **動作**：全 repo 搜此識別碼
- **預期**：寫入稽核紀錄
- **實際**：僅兩處命中，其一為產生處、其一為測試斷言

```
git grep -n "COMPLETE_OVERRIDE" -- api web SQL
api/services/work_order_service.py:1547:            f"[COMPLETE_OVERRIDE by {actor_role or 'supervisor'}: "
api/tests/test_cr_0039_completion_gate.py:155:    assert "COMPLETE_OVERRIDE" in out
```

該字串作為 summary 前綴回傳後，被寫入 `work_orders.service_report`：

`api/services/work_order_service.py:1791-1797`（節錄）

```python
    _cur = await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  status = 'completed', "
        "  completed_at = NOW(), "
        "  started_at = COALESCE(started_at, NOW()), "
        "  service_report = %s, "
```

- TC 判定基準寫「audit 記 COMPLETE_OVERRIDE + 角色 + reason」
- 程式碼把該字串寫入 `work_orders.service_report`（`work_order_service.py:1546-1549` 產生、`:1796` 落庫），並另在 `work_order_events` payload 記角色與 reason（見步驟 3）；`audit_events` 表在完工路徑無寫入（見步驟 4）

此處僅並陳，不裁定。

### 步驟 3 — `work_order_events` 的 override 欄位

- **動作**：讀完工的事件寫入
- **預期**：留有角色與理由
- **實際**：payload 有 `actor_role` / `is_override` / `override_reason` 三欄，`event_type` 為 `completed`

`api/services/work_order_service.py:1893-1905`

```python
    # CR-0193：生命週期事件（原本 complete 不落事件流 → timeline 看不到「完工」，
    # 而 evidence_package_service 正是拿事件流當爭議舉證來源）
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="completed",
        payload={
            "from_status": current,
            "actor_role": actor_role,
            "is_override": is_override,       # True = 後台代為結案，非技師現場送簽
            "override_reason": override_reason,
            "actual_amount": actual_amount,
        },
    )
```

事件流本身不含 `COMPLETE_OVERRIDE` 字面值；`event_type` 受 migration 122 的 CHECK 清單約束（`SQL/migrations/122-wo-events-seq-and-lifecycle.sql:72-88`，含 `completed` 但無 override 專屬值）。

### 步驟 4 — `audit_events` 在完工路徑的寫入情形

- **動作**：搜 `complete_order` 內的 audit 呼叫
- **預期**：寫一筆稽核事件
- **實際**：`complete_order`（`:1727-1908`）全函式無 `audit_log_service.log_event` 呼叫

同檔其他路徑則有：急件 bypass（`:700-712`）、拒單（`:1402-1409`）、`_audit_action` 覆蓋的 reschedule / delay 三動作（`:3713-3735`、`:3837`、`:3968`、`:4059`）。`complete_order` 的註解亦自述此範圍：

`api/services/work_order_service.py:1742-1744`

```python
    # CR-0193：生命週期事件要記「誰做的」。此前 complete/cancel/escalate/confirm
    # 的 actor 沒有任何結構化留痕（_audit_action 只覆蓋 reschedule/delay 三個動作）。
    actor_user_id: str | None = None,
```

### 步驟 5 — 技師走 override 路徑的 403

- **動作**：讀 v2 與 v1 兩個 `:complete` 端點
- **預期**：技師被擋 403
- **實際**：兩者皆有相同守衛

`api/routers/work_orders_v2.py:571-597`（節錄）

```python
async def complete_work_order_v2(
    body: CompletionReport,
    tenantId: str = Path(...),
    id: str = Path(...),
    user: CurrentUser = Depends(role_required(*TECH_ACTION_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    _cross_tenant_write(user, tenantId)
    # CR-0039：:complete 為後台 admin/dispatcher 完工 override 路徑（記 summary 為 reason、跳過證據閘）；
    # 技師必須走 /onsite/completion 正規硬閘，否則可繞過照片/簽名/序號驗證。
    if (user.role or "") == "technician":
        raise ApiError(
            "FORBIDDEN",
            "技師請走現場完工送簽端點 /onsite/completion（含照片/簽名硬閘）",
            403,
        )

    order = await work_order_service.complete_order(
        tenant_id=tenantId,
        wo_id=id,
        summary=body.summary,
        actual_amount=body.actual_amount,
        is_override=True,
        override_reason=body.summary,
        actor_role=user.role,
```

v1 flat 路徑同樣：`api/routers/work_orders.py:234-240`

```python
    # CR-0039：v1 :complete 同 v2，為後台 override 路徑；技師須走現場完工送簽硬閘端點
    if (user.role or "") == "technician":
        raise ApiError(
            "FORBIDDEN",
            "技師請走現場完工送簽端點（含照片/簽名硬閘）",
            403,
        )
```

守衛以 `user.role == "technician"` 字串比對達成；`role_required(*TECH_ACTION_ROLES)` 本身放行技師（`api/core/deps.py:304`），403 由端點內的顯式判斷產生。

### 步驟 6 — override 的角色白名單與 reason 來源

- **動作**：追誰能呼叫、reason 從哪來
- **預期**：主管角色 + 獨立 override 理由欄位
- **實際**：白名單為 `TECH_ACTION_ROLES` 扣除 technician（實效等同 `BACKOFFICE_ROLES`），reason 取自 `body.summary`

`api/core/deps.py:293-304`

```python
FULL_ACCESS_ROLES: tuple[str, ...] = ("admin",)
#: 營運後台寫入（accounting / billing / pricing / vendor-mgmt / warranty / 結算）
OPS_ROLES: tuple[str, ...] = FULL_ACCESS_ROLES + ("operations_manager",)
#: 派工寫入（dispatch / 自動媒合 / 技師生命週期管理）
DISPATCH_ROLES: tuple[str, ...] = OPS_ROLES + ("dispatcher",)
#: 後台唯讀／一般後台操作（含客服）
BACKOFFICE_ROLES: tuple[str, ...] = DISPATCH_ROLES + ("customer_service",)
#: 審核寫入（退款 / 保固 / 爭議）—— 對齊 role_service._MATRIX：reviewer 於此三域可寫（CR-0094）
REVIEW_ROLES: tuple[str, ...] = OPS_ROLES + ("reviewer",)
#: 技師現場動作（接單/完工/簽名/到場/門況/延誤/用料/現場修正）＋後台代操作（SA-01/CR-0130）
#: —— 對齊矩陣 technician.work_orders.write；vendor / line_user 一律 403
TECH_ACTION_ROLES: tuple[str, ...] = BACKOFFICE_ROLES + ("technician",)
```

- TC 前置寫「主管角色 + override 理由」
- 程式碼放行 admin / operations_manager / dispatcher / customer_service 四種角色（`routers/work_orders_v2.py:575` + `:581-586`），且 `override_reason=body.summary`（`:594`）——沒有獨立的 reason 欄位，完工摘要即理由，`CompletionReport.summary` 為必填字串（`api/models/generated.py:282-283`）

此處僅並陳，不裁定。

### 步驟 7 — 執行既有測試

- **動作**：跑 override 兩項（本機 Docker 測試庫）
- **預期**：取得執行證據
- **實際**：通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0039_completion_gate.py \
  tests/test_state_machine_optimistic_lock.py -q -p winloop_plugin --tb=line
20 passed in 1.67s
```

`api/tests/test_cr_0039_completion_gate.py:144-157`

```python
@pytest.mark.asyncio
async def test_override_with_reason_skips_evidence():
    """override + reason：0 照片、無簽名也通過，summary 加稽核註記。"""
    assert await db_module._ensure_conn()
    out = await _gate(
        is_override=True,
        override_reason="主管放行：客戶趕時間",
        actor_role="operations_manager",
        photo_evidence_ids=[],
        signature_evidence_id=None,
    )
    assert "COMPLETE_OVERRIDE" in out
    assert "主管放行" in out
    assert "operations_manager" in out
```

該斷言驗的是**函式回傳字串**，不是稽核表列。

---

## 觀測到的其他事實

- `allow_supervisor_override` 若由 M18 config 設為 false，override 路徑改回 403 `OVERRIDE_NOT_ALLOWED`（`work_order_service.py:1542-1543`）；前端字典有此鍵（`web/brand-portal/src/lib/apiError.ts:46`、`web/tech-portal/src/lib/apiError.ts:46`，文案「您沒有覆寫此設定的權限。」）。
- override 理由前綴會截斷至 300 字（`work_order_service.py:1548`：`override_reason.strip()[:300]`）。
- override 路徑仍受 `_assert_not_high_risk_hold` 約束（`work_order_service.py:1764-1765`，註解自述「含 override」），以及 `_COMPLETE_FROM` 狀態集合限制。
- `CR-0058` 的用料 / 付款證明檢查僅在 `if not is_override:` 分支（`work_order_service.py:1777-1783`），override 路徑不執行。
- `:complete` 端點掛有 `idempotency_guard` 並在成功後 `idem.save(200, payload)`（`routers/work_orders_v2.py:598-601`）。
