# TC-SETTLE-02 — L1 退款三維 SoD 與 audit 事件鏈

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；正式機金流環境不可用，本批不做執行期驗證。後續以本機 Docker 測試庫實跑既有測試，退款 5 檔 66 項全數通過（見步驟 6） |
| 走查時間 | 2026-08-03（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/routers/refunds_v2.py:36-78`、`api/core/deps.py:246-301`、`api/services/refund_service.py:442-673`、`:296-424`、`api/services/cancellation_service.py:203-211`、`api/services/audit_log_service.py:74-92`、`:527-580`、`api/services/config_service.py:133-155`、`SQL/migrations/002-refund-sod-5tier.sql:15-95`、`api/tests/test_refund_sod_endpoint.py:90-195` |
| 優先級 / 路徑類型 | P0 / happy |
| 事實結論 | `POST /tenants/{tenantId}/refunds` 未設 `status_code`，成功走 FastAPI 預設 200；NTD 500 由 `resolve_tier` 推得 L1（門檻 `[1000,5000,30000,100000]`，`amount <= t0`）；三個行為人由 `X-Initiator/X-Approver/X-Executor` 解析並落 `initiator_user_id / approver_user_ids / executor_user_id` 三欄。audit 只在**建立**這一步寫入一筆 `financial_action` / `refund.created`（含 hash chain），後續 `submit_decision`（核准）**不寫 `audit_events`**，只 append `approval_chain` JSONB；repo 中**找不到**任何把退款推進到 `executed`（executor 執行）的程式碼路徑。此外該端點的角色守衛為 `REVIEW_ROLES`（admin / operations_manager / reviewer），不含 `customer_service`。 |

**TC 原文**｜前置：退款申請 NTD 500（L1）｜步驟：initiator=客服 → approver=會計 → executor=system｜判定基準：200 + 完整 audit 事件鏈｜需求：FR-API-11｜旅程：SC-06、SC-08、SC-09

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客服 | 建立退款 NTD 500 | `RefundRequested(tier=L1)` | 三維 SoD + 5-tier | `routers/refunds_v2.py:42-78` | 回 200；tier 由伺服器端推算 |
| 客服 | 帶 SoD headers | `SodActorsResolved` | 任二相同 403 | `core/deps.py:255-276` | 解析三 header，重複即 403 |
| 系統 | 寫稽核 | `AuditLogged(refund.created)` | hash chain | `services/refund_service.py:614-638` | 一筆 `financial_action`，回傳 `audit_event_id` |
| 會計 | 核准 | `AuditLogged(refund.approved)` | 事件鏈延續 | `services/refund_service.py:395-400` | 只 UPDATE `status` + `approval_chain`；**找不到** audit 寫入 |
| system | 執行出款 | `RefundExecuted` | 執行者留痕 | — | **找不到**任何寫 `status='executed'` 的程式碼 |

---

## 走查紀錄

### 步驟 1 — 端點與回應狀態碼

- **動作**：讀 `createRefundSod` 端點簽章
- **預期**：成功回 200
- **實際**：未設 `status_code`，走 FastAPI 預設 200

`api/routers/refunds_v2.py:36-48`

```python
@router.post(
    "/tenants/{tenantId}/refunds",
    operation_id="createRefundSod",
    summary="Create Refund — 三維 SoD + 5-tier (ADR-0040 v2)",
    response_model=RefundSodEnvelope,
)
async def create_refund_sod(
    body: RefundSodRequest,
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*REVIEW_ROLES)),
    sod: SodActors = Depends(require_sod_actors),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
```

對照同檔 `:156-162` 的 `:agent-initiate` 顯式標 `status_code=201`，本端點無此參數。

角色守衛為 `REVIEW_ROLES`：`api/core/deps.py:293-301`

```python
FULL_ACCESS_ROLES: tuple[str, ...] = ("admin",)
OPS_ROLES: tuple[str, ...] = FULL_ACCESS_ROLES + ("operations_manager",)
...
REVIEW_ROLES: tuple[str, ...] = OPS_ROLES + ("reviewer",)
```

- TC 步驟：`initiator=客服`
- 程式碼：`customer_service` 不在 `REVIEW_ROLES`（`core/deps.py:301`）；`X-Initiator` 是行為人 header，與呼叫者 JWT 角色是兩個獨立值（`routers/refunds_v2.py:45-46`）

此處僅並陳，不裁定。

### 步驟 2 — NTD 500 的 tier 推算

- **動作**：讀 tier 規則
- **預期**：500 → L1
- **實際**：`amount <= thresholds[0]`（1000）即 L1

`api/services/refund_service.py:473-491`

```python
def resolve_tier(amount: float, refund_config: dict) -> str:
    """伺服器端從金額推算 5-tier（ADR-0040 §97-104）。

    門檻來自 config（預設 1000/5000/30000/100000），邊界含於較低 tier：
      amount <= t0 → L1 ; t0 < amount <= t1 → L2 ; ... ; amount > t3 → L5。
    """
    thresholds = refund_config.get("tiers", {}).get("thresholds")
    if not thresholds or len(thresholds) != 4:
        raise ApiError("INTERNAL_ERROR", "refund tier thresholds misconfigured", 500)
    amt = float(amount)
    if amt <= thresholds[0]:
        return "L1"
```

門檻預設值：`api/services/refund_service.py:446-449`

```python
    "tiers": {
        # 升冪門檻：amount <= thresholds[0] → L1；> thresholds[3] → L5（ADR-0040 §97-104）
        "thresholds": [1000, 5000, 30000, 100000],
```

config 來源：`api/services/config_service.py:145-155`，tenant 無 `refund` namespace 時回 `DEFAULT_REFUND_CONFIG` + version `"default"`。

### 步驟 3 — 三維行為人的解析與落庫

- **動作**：讀 header 解析與 INSERT 欄位
- **預期**：initiator / approver / executor 三者分別留痕
- **實際**：三值皆入表；`approver_user_ids` 為陣列，本路徑只放一個

`api/core/deps.py:255-276`

```python
async def require_sod_actors(
    x_initiator: str | None = Header(default=None, alias="X-Initiator"),
    x_approver: str | None = Header(default=None, alias="X-Approver"),
    x_executor: str | None = Header(default=None, alias="X-Executor"),
) -> SodActors:
    """解析 X-Initiator / X-Approver / X-Executor headers。

    spec（openapi-smart-lock-saas.yaml）: X-Initiator + X-Approver required，
    X-Executor optional。任二相同 → 403 SOD_VIOLATION。
    """
```

`api/services/refund_service.py:641-656`

```python
    approver_arr = [sod_approver] if sod_approver else []
    cur = await db_module._conn.execute(
        "INSERT INTO refund_requests "
        "  (work_order_id, requested_by, amount, reason, status, "
        "   tier, refund_class, initiator_user_id, approver_user_ids, "
        "   executor_user_id, audit_event_id, config_version_used) "
        "VALUES (%s::uuid, %s::uuid, %s, %s, 'pending', "
        "        %s, %s, %s::uuid, %s::uuid[], "
        "        %s, %s::uuid, %s) "
```

DB 端另有 CHECK backstop：`SQL/migrations/002-refund-sod-5tier.sql:65-67`、`:74-77`

```sql
            ADD CONSTRAINT refund_requests_sod_initiator_chk
            CHECK (initiator_user_id IS NULL OR initiator_user_id <> ALL(approver_user_ids));
...
            ADD CONSTRAINT refund_requests_sod_executor_chk
            CHECK (executor_user_id IS NULL OR initiator_user_id IS NULL
                   OR executor_user_id <> initiator_user_id);
```

TC 步驟寫 `executor=system`；`X-Executor` 在 `require_sod_actors` 中為 optional（`core/deps.py:258`、`:269`），該欄以 `%s`（無 `::uuid` cast）寫入（`refund_service.py:649`）。

### 步驟 4 — audit 事件鏈

- **動作**：追退款全程的 `audit_events` 寫入點
- **預期**：建立→核准→執行的完整鏈
- **實際**：只有建立這一步寫入

`api/services/refund_service.py:614-638`

```python
    from services import audit_log_service

    audit_payload = {
        "operator_id": sod_initiator,
        "approver_id": sod_approver,
        "executor_id": sod_executor,
        "operator_role": actor_role,
        "amount": float(amount),
        "tier": tier,
        "refund_class": refund_class,
        "reason": reason,
        "evidence_ids": evidence_ids or [],
        "config_version_applied": config_version,
        "approver_role_required": approver_role_for_tier(tier, refund_config),
    }
    audit_event_id = await audit_log_service.log_event_returning_id(
        event_type="financial_action",
        actor_id=actor_id,
        actor_role=actor_role,
        action="refund.created",
```

該寫入帶 hash chain（`services/audit_log_service.py:88-92`）：

```python
    prev_hash = await _latest_entry_hash()
    content = _canonical_audit_content(
        event_type, actor_id, actor_role, action, target_type, target_id, payload_canon
    )
    return prev_hash, _compute_entry_hash(prev_hash, content), payload_json
```

核准步驟的寫入（`api/services/refund_service.py:383-400`）：

```python
    chain.append(
        {
            "user_id": decided_by_user_id,
            "decision": decision,
            "reason": reason.strip()[:500],
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "stage": "first_sign"
            if new_status == _FIRST_SIGN_STATUS
            else "final",
        },
    )

    await db_module._conn.execute(
        "UPDATE refund_requests "
        "SET status = %s, approval_chain = %s::jsonb, updated_at = NOW() "
        "WHERE id = %s::uuid",
        (new_status, json.dumps(chain), refund_id),
    )
```

`api/services/refund_service.py` 全檔搜 `audit_log_service`：只命中 `:615` 與 `:630` 兩處，皆在 `create_refund_sod` 內。`submit_decision` 之後的副作用為 WebSocket publish（`:404-422`，best-effort）。

執行端（executor）：全 repo 搜寫入 `status='executed'` 的 SQL —

```
git grep -n "'executed'" -- api | grep -v tests
api/models/generated.py:392:    executed = 'executed'
api/services/refund_service.py:61:    "executed",
api/services/refund_service.py:468:_VALID_TERMINAL_REFUND_STATES = {"rejected", "executed"}
```

三處皆為 enum／常數宣告，**找不到** UPDATE 或 INSERT 把該值寫進 `refund_requests.status`。

- TC 判定基準：「200 + 完整 audit 事件鏈」
- 程式碼：建立步驟寫一筆 `refund.created` 稽核；核准步驟寫 `approval_chain` JSONB 但不寫 `audit_events`；執行步驟無程式碼

此處僅並陳，不裁定。

### 步驟 5 — 稽核鏈的可驗證性

- **動作**：查稽核鏈是否可被驗證
- **預期**：可驗證完整性
- **實際**：有端點

`api/routers/audit_v2.py:82-103`

```python
    summary="稽核 hash-chain 完整性驗證（NFR-Aud-001；偵測竄改/斷鏈）",
...
    result = await audit_log_service.verify_audit_chain(limit=limit, use_checkpoint=use_checkpoint)
```

該端點驗的是 `audit_events` 表的 hash chain，與 `refund_requests.approval_chain` 為兩套獨立機制。

### 步驟 6 — 執行既有測試

- **動作**：跑退款測試
- **預期**：取得執行證據
- **實際**：5 檔 66 項全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_refund_sod_5tier.py \
  tests/test_refund_sod_endpoint.py tests/test_refund_dual_sign.py \
  tests/test_create_refund_request.py tests/test_refund_decision_v2_endpoint.py \
  -q -p winloop_plugin --tb=line

66 passed in 3.84s
```

`api/tests/test_refund_sod_endpoint.py:102-107` 斷言 200 與 `audit_event_id` 存在：

```python
    assert res.status_code == 200, res.text
...
    assert data["audit_event_id"]
```

該檔**未**斷言核准／執行階段的稽核事件。

---

## 觀測到的其他事實

- 同檔另有一條 service-層冪等：同 WO 同 `refund_class` 已有 active 退款 → 409 `DUPLICATE_REFUND`（`services/refund_service.py:600-612`）；註解 `:588-599` 記載 DB 端 `uniq_refund_wo_reason_active` 索引因 SoD 路徑不填 `reason_code` 而不生效。
- 舊 flat 路徑 `POST /api/v1/refunds`（`routers/refunds.py:64-105`）仍在，走 `create_refund_request`（雙簽 `approval_chain` 模型），該路徑**不寫** `audit_events`。
- `agent`／`system` 角色可經 `:agent-initiate`（`routers/refunds_v2.py:156-204`）單一行為人建立退款，不走 SoD；docstring `:169-176` 記載其為 ADR-0106 特例。
- `DEFAULT_REFUND_CONFIG["tiers"]["required_approvals"]`（`services/refund_service.py:458-464`）定義各 tier 需 1／1／2／2／3 簽，但 `create_refund_sod` 與 `submit_decision` 皆未讀取該值（全 repo 除測試外零引用）。
- 跨租戶防護：path tenantId ≠ JWT tenant → 403 `CROSS_TENANT_WRITE`（`routers/refunds_v2.py:50-55`）；工單不屬本租戶時偽裝 404（`services/refund_service.py:586`）。
