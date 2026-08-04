# TC-SETTLE-08 — 佣金 statement 查詢的 scope 隔離與成本欄位遮蔽

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；以本機 Docker 測試庫實跑 `test_technician_statement.py` / `test_dispatcher_commission.py` 等五檔，50 項全數通過（見「既有測試證據」） |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（＋既有測試實跑） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/routers/dispatcher_commission_v2.py:1-200`、`api/routers/technician_statement_v2.py:65-210`、`api/routers/technicians.py:33`、`:137-149`、`api/services/technician_commission_service.py:160-200`、`api/routers/vendors_v2.py:1-54`、`api/routers/catalog_v2.py:20`、`:35`、`:52`、`api/routers/quote_v2.py:24`、`:34`、`api/routers/work_orders_v2.py:67-68`、`:1068`、`api/services/payout_rule_service.py:35-47`、`web/tech-portal/src/app/account/statements/page.tsx:44-60` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

「成本欄位對非授權角色遮蔽」有完整且一致的實作：三個 router 各自宣告同一份 `_COST_VISIBLE_ROLES = {"admin", "operations_manager"}`（`catalog_v2.py:20`、`quote_v2.py:24`、`work_orders_v2.py:68`），以 `include_cost` 旗標傳入 service，service 端在組 dict 時才決定是否放入成本欄（`payout_rule_service.py:44-46` 的 `base_payout`），即 server 端結構性不回傳而非前端隱藏。「技師僅見自己 scope」在技師自助端點成立：`GET /technicians/me/commission-statements` 限 `role_required("technician")`（`api/routers/technicians.py:33`、`:143`），且以 JWT 的 `user_id` 反查 `technicians.id`（`technician_commission_service.py:180-187`），無任何 client 可控的 id 參數。判為部分實作的落差在：①TC 前置指名的「派工小編佣金」對應的 `dispatcher-commissions` 全部 8 個端點（含 list / get）皆限 `OPS_ROLES`（`api/routers/dispatcher_commission_v2.py:63`、`:83`、`:101` 等），技師與 vendor 是 403 而非「見自己 scope」；②`vendor` 角色在 `api/routers` 中只有 `/vendors/me` 與品牌唯讀清單兩個端點（`api/routers/vendors_v2.py:34`、`:51`），無任何佣金／對帳單端點；③兩張 statement 的回傳結構無 `include_cost` 型遮蔽（`dispatcher_commission_service.py:165` 直接回 `net_commission`），其保護方式是整支端點的角色門檻。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 7. 結算與退款案例（TC-SETTLE） |
| 前置 | 派工小編佣金 |
| 步驟 | 佣金 statement 查詢 |
| 預期結果（判定基準） | 技師/vendor 僅見自己 scope；成本欄位對非授權角色遮蔽 |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 權限 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-API-12、FR-TEC-06 |
| 屬於哪條旅程腳本 | SC-13 |

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 派工小編佣金 statement 端點存在 | `api/routers/dispatcher_commission_v2.py:54-200`（8 個端點） | 有落點 |
| 該端點的角色門檻 | `dispatcher_commission_v2.py:63`、`:83`、`:101`、`:116`、`:133`、`:151`、`:170`、`:188` 皆 `role_required(*OPS_ROLES)` | 有落點（技師／vendor 403） |
| 技師見自己的佣金 | `api/routers/technicians.py:137-149` `GET /technicians/me/commission-statements`，`_technician_only`（`:33`） | 有落點 |
| 技師 scope 由 token 決定 | `api/services/technician_commission_service.py:180-187`：`user_id → technicians.id`，無 client 參數 | 有落點 |
| 技師見自己的月結對帳單 | `api/routers/technician_statement_v2.py:91-97` `role_required(*OPS_ROLES)`，技師不可讀 | 無對應 scope 落點 |
| vendor 僅見自己 scope | `api/routers/vendors_v2.py:34`（`/vendors/me`）；vendor 無任何 statement 端點 | 部分（無佣金端點可見） |
| 成本欄位遮蔽 — 角色集合 | `catalog_v2.py:20`、`quote_v2.py:24`、`work_orders_v2.py:68` 三處同值 `{"admin", "operations_manager"}` | 有落點 |
| 成本欄位遮蔽 — 報價主檔 | `catalog_v2.py:35`、`:52` → `quote_catalog_service` / `payout_rule_service` | 有落點 |
| 成本欄位遮蔽 — 拆帳規則 | `api/services/payout_rule_service.py:44-46`（`base_payout` 僅 `include_cost` 時放入） | 有落點 |
| 成本欄位遮蔽 — 工單報價明細 | `work_orders_v2.py:1068-1071` → `quote_service.list_line_items(include_cost=...)` | 有落點 |
| 成本欄位遮蔽 — 客戶端 | `api/routers/consumer_v2.py:279-291`：`include_cost=False` 固定值 | 有落點 |
| statement 回傳的成本欄遮蔽 | `dispatcher_commission_service.py:165` 直接回 `net_commission`；`technician_statement_service.py` 無 `include_cost` | 無遮蔽層（以端點角色門檻取代） |
| 跨租戶保護 | `dispatcher_commission_v2.py:27-30` `_guard_tenant`（`CROSS_TENANT_READ` / `WRITE` 403） | 有落點 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| ops_manager | `GET /tenants/{tid}/dispatcher-commissions` | `CommissionListReturned` | OPS 可讀全租戶 | `api/routers/dispatcher_commission_v2.py:78-91` | `role_required(*OPS_ROLES)` + `_guard_tenant` |
| technician | 同上 | `RequestRejected(403)` | 非 OPS | `api/core/deps.py:317-322` | `FORBIDDEN` 403（不是「見自己 scope」） |
| vendor | 同上 | `RequestRejected(403)` | 非 OPS | 同上 | `FORBIDDEN` 403 |
| technician | `GET /technicians/me/commission-statements` | `MyCommissionReturned` | 本人 scope | `api/routers/technicians.py:143`、`technician_commission_service.py:180-187` | 以 JWT `user_id` 反查 `technicians.id`；查無 → 空清單 |
| technician | 試圖帶他人 id | （無此參數） | 結構性阻斷 | `api/routers/technicians.py:138-145` | 端點只有 `limit` 一個參數 |
| vendor | 查自身佣金 | — | — | `api/routers/vendors_v2.py` | 無對應端點 |
| admin / ops | `GET /tenants/{tid}/quote-catalog` | `CatalogWithCost` | 成本可見 | `api/routers/catalog_v2.py:35` | `include_cost=True` |
| dispatcher / cs / reviewer | 同上 | `CatalogWithoutCost` | 成本遮蔽 | `api/routers/catalog_v2.py:20`、`:35` | `include_cost=False` |
| service 層 | 組回傳 dict | `CostFieldOmitted` | 結構性不回 | `api/services/payout_rule_service.py:44-46` | `if include_cost: out["base_payout"] = ...` |
| 客戶（token 視圖） | 查報價 | `CostFieldOmitted` | 固定不回 | `api/routers/consumer_v2.py:279-291` | `include_cost=False` 硬編 |

---

## 逐層走查

### 第 1 層 — 派工小編佣金 statement 端點的角色門檻

`api/routers/dispatcher_commission_v2.py:1-16`

```python
"""Dispatcher Commission v2 router — FR-0046 MVP 8 endpoints (對應 FR-0045)。"""
...
from core.deps import OPS_ROLES, CurrentUser, require_tenant, role_required
```

八個端點的守衛：

```
api/routers/dispatcher_commission_v2.py:63   generate      role_required(*OPS_ROLES)
api/routers/dispatcher_commission_v2.py:83   list_         role_required(*OPS_ROLES)
api/routers/dispatcher_commission_v2.py:101  get_          role_required(*OPS_ROLES)
api/routers/dispatcher_commission_v2.py:116  submit        role_required(*OPS_ROLES)
api/routers/dispatcher_commission_v2.py:133  dispute       role_required(*OPS_ROLES)
api/routers/dispatcher_commission_v2.py:151  approve       role_required(*OPS_ROLES, fail_closed=True)
api/routers/dispatcher_commission_v2.py:170  reject        role_required(*OPS_ROLES)
api/routers/dispatcher_commission_v2.py:188  mark_paid     role_required(*OPS_ROLES, fail_closed=True)
```

`OPS_ROLES` 展開為 `admin, operations_manager`（`api/core/deps.py:300`：`OPS_ROLES = FULL_ACCESS_ROLES + ("operations_manager",)`）。

列表端點的 scope 參數，`api/routers/dispatcher_commission_v2.py:78-84`：

```python
async def list_(
    tenantId: str = Path(...),
    dispatcher_user_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
```

`dispatcher_user_id` 為選填 query filter，非強制 scope；能呼叫此端點的角色本身就可讀全租戶。

`api/routers/dispatcher_commission_v2.py:27-30`

```python
def _guard_tenant(user: CurrentUser, tenant_id: str, *, write: bool = False) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        code = "CROSS_TENANT_WRITE" if write else "CROSS_TENANT_READ"
        raise ApiError(code, "Path tenantId does not match authenticated tenant", 403)
```

- TC 判定基準寫「技師/vendor **僅見自己 scope**」
- `dispatcher-commissions` 的 8 個端點對技師與 vendor 一律 403 `FORBIDDEN`（`api/core/deps.py:317-322`），即這兩個角色在此端點上見不到任何資料，而非「見自己的」

此處僅並陳，不裁定。

### 第 2 層 — 技師月結對帳單端點

`api/routers/technician_statement_v2.py:85-97`

```python
@router.get(
    "/tenants/{tenantId}/tech-statements",
    operation_id="listTechStatements",
    summary="列 statements (filter)",
    response_model=dict,
)
async def list_(
    tenantId: str = Path(...),
    technician_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
```

同檔 8 個端點皆為 `OPS_ROLES`（`:75`、`:96`、`:114`、`:129`、`:146`、`:166`、`:187`、`:200` 起）。

tech-portal 的對帳單頁呼叫的正是此端點，`web/tech-portal/src/app/account/statements/page.tsx:47-57`：

```tsx
      // 對帳單路由為 /tenants/{tid}/tech-statements?technician_id=（technicians.id）。
      // 先取 profile 拿 technician_id（JWT sub 為 user_id，非 technicians.id）。
      const profile = await api.get<{ data?: { id: string } }>(
        "/api/v1/technicians/me",
      );
      const techId = profile.data?.id;
      const res = await api.get<TechStatement[] | { items: TechStatement[] }>(
        tenantPath("/tech-statements"),
        techId ? { query: { technician_id: techId } } : undefined,
      );
```

即前端以 query 參數自我限縮 scope，而該端點的伺服器端守衛為 `OPS_ROLES`。此處僅並陳兩者，不裁定。

### 第 3 層 — 技師本人佣金端點（有 scope 限縮）

`api/routers/technicians.py:33`

```python
_technician_only = role_required("technician")
```

`api/routers/technicians.py:137-149`

```python
@router.get(
    "/technicians/me/commission-statements",
    operation_id="listMyCommissionStatements",
    summary="技師本人佣金對帳單（月彙總；UAT P2-5 補端點，讀 R4 佣金投影）",
)
async def list_my_commission_statements(
    limit: int = Query(default=24, ge=1, le=60, description="最多回傳期數（月）"),
    user: CurrentUser = Depends(_technician_only),
) -> dict:
    data = await technician_commission_service.list_my_commission_statements(
        tenant_id=user.tenant_id, user_id=user.user_id, limit=limit,
    )
    return {"data": data}
```

`api/services/technician_commission_service.py:160-200`

```python
async def list_my_commission_statements(
    *, tenant_id: str, user_id: str, limit: int = 24
) -> dict:
    """技師本人佣金對帳單（UAT P2-5：tech surface 缺此端點 → 對帳單頁 404）。

    來源 = technician_commission_projection（CR-0166 R4 / ADR-017 技師視角
    跨品牌 CQRS 投影，commission.accrued 事件物化；雙庫模式讀技師權威庫，
    單庫 fallback 主庫）。依月彙總（period=YYYY-MM），每期回
    {period, gross_amount, commission_amount, status}。

    誠實限制：
      - 投影欄位最小化（ADR-017 §投影隱私）只帶佣金 accrued 金額，無工單毛額
        → gross_amount 以當期佣金累計代替（＝commission_amount），待事件補帶毛額。
      - 投影無對帳單狀態機 → status 一律 'accrued'（月結中），待月結模組。
      - 無資料（含投影表尚未建立——consumer 未啟動過的部署）→ 空 items 200，不 404。
    """
    ...
    # users.id → technicians.id（投影以 technician_id 關聯；查無技師列＝尚無佣金）
    cur = await db_module._conn.execute(
        "SELECT id FROM technicians WHERE user_id = %s::uuid AND tenant_id = %s::uuid",
        (user_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        return {"items": []}
    technician_id = str(row[0])
```

該端點無任何 client 可控的 technician 識別參數，scope 由 JWT 的 `sub` 與 `tenant_id` 決定。docstring 另註明投影欄位刻意最小化（「ADR-017 §投影隱私」），即跨品牌投影只帶佣金金額。

### 第 4 層 — vendor 角色的可用端點

`api/routers/vendors_v2.py:27-52`

```python
@router.get(
    "/vendors/me",
    operation_id="getVendorSelfV2",
    summary="廠商自身 profile（CR-0029 廠商專區；以登入 user_id 取）",
    tags=["M14 Vendor"],
)
async def get_vendor_self_v2(
    user: CurrentUser = Depends(role_required("vendor")),
) -> dict:
    vendor = await vendor_service.get_vendor_by_user_id(user_id=user.user_id)
```

```
git grep -rn "\"vendor\"" -- api/core/deps.py api/routers
api/routers/auth.py:440:        email=body.email, password=body.password, allowed_roles=["vendor"]
api/routers/preferences.py:25:_BRAND_PREFERENCE_ROLES = BACKOFFICE_ROLES + ("reviewer", "viewer", "vendor")
api/routers/vendors_v2.py:34:    user: CurrentUser = Depends(role_required("vendor")),
```

`vendor` 在 `api/core/deps.py:293-305` 的任何角色群組（`FULL_ACCESS_ROLES` / `OPS_ROLES` / `DISPATCH_ROLES` / `BACKOFFICE_ROLES` / `REVIEW_ROLES` / `TECH_ACTION_ROLES`）中皆不出現。`/vendors/me` 以 `user.user_id` 取自身 profile，即該角色唯一的「自己 scope」讀取點；無佣金或對帳單端點。

### 第 5 層 — 成本欄位遮蔽

三份同值常數：

```
api/routers/catalog_v2.py:20:_COST_VISIBLE_ROLES = {"admin", "operations_manager"}  # SA-01：死角色移除
api/routers/quote_v2.py:24:_COST_VISIBLE_ROLES = {"admin", "operations_manager"}  # SA-01：死角色移除
api/routers/work_orders_v2.py:68:_COST_VISIBLE_ROLES = {"admin", "operations_manager"}  # SA-01：死角色移除
```

`api/routers/work_orders_v2.py:67`（成本欄位的定義與宣告的執行層級）：

```python
# CR-0027：成本（unit_price）僅後台管理角色可見（server 端 RBAC 遮蔽）
```

呼叫點三處：

```
api/routers/catalog_v2.py:35:    include_cost = (user.role or "") in _COST_VISIBLE_ROLES
api/routers/catalog_v2.py:52:    include_cost = (user.role or "") in _COST_VISIBLE_ROLES
api/routers/work_orders_v2.py:1068:    include_cost = (user.role or "") in _COST_VISIBLE_ROLES
api/routers/quote_v2.py:34:    return (user.role or "") in _COST_VISIBLE_ROLES
```

service 端的實際遮蔽方式（不回傳該 key，而非回 null），`api/services/payout_rule_service.py:35-47`：

```python
def _row_to_dict(r: tuple, include_cost: bool) -> dict:
    out = {
        "rule_id": r[0], "service_code": r[1], "service_name": r[2], "level_id": r[3],
        "night_surcharge_pct": float(r[5]), "urgent_surcharge_pct": float(r[6]),
        "currency": r[7],
        ...
    }
    if include_cost:
        out["base_payout"] = _dec(r[4])  # 內部敏感：僅 admin/ops 可見
    return out
```

`api/services/payout_rule_service.py:4` 的模組 docstring：「`base_payout` 為內部敏感成本 → `include_cost` RBAC 遮蔽（同 catalog `unit_price`）。」

客戶側為固定不回，`api/routers/consumer_v2.py:279-291`：

```python
    """客戶用 quote_view token 查報價 —— include_cost=False 結構上不回 unit_price。"""
        ...
        "lines": quote["lines"],  # include_cost=False → 無 unit_price
```

### 第 6 層 — statement 回傳結構是否有成本遮蔽

`api/services/dispatcher_commission_service.py:141-165`

```python
        "       base_commission, performance_bonus, penalty, net_commission, "
        ...
        "net_commission": _dec(row[12]),
```

該 service 的 `_row` 組裝無 `include_cost` 參數；`api/services/technician_statement_service.py` 全檔亦無 `include_cost` / `mask` 相關識別碼。兩張 statement 的欄位保護即整支端點的 `OPS_ROLES` 門檻。

- TC 判定基準寫「成本欄位對非授權角色遮蔽」
- 已實作的欄位級遮蔽機制（`include_cost`）覆蓋的是報價主檔、拆帳規則、工單報價明細與客戶視圖；佣金／月結 statement 的回傳不經該機制

此處僅並陳，不裁定。

---

## 既有測試證據

實跑（本機 Docker 測試庫，Windows 加 `-p winloop_plugin`）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_cr_0164_audit_immutable.py tests/test_cr_0068_audit_hash_chain.py \
  tests/test_audit_v2_endpoint.py tests/test_technician_statement.py \
  tests/test_dispatcher_commission.py -q -p winloop_plugin
50 passed in 3.67s
```

`api/tests/` 中另有 `test_technician_commission.py`、`test_statement_auto_approval.py`、`test_brand_b2b_statement.py`、`test_cr_0189_commission_outbox.py` 四檔屬同一領域。針對「技師／vendor 以自身 token 打 `dispatcher-commissions` / `tech-statements` 應為 403」的斷言，未在上述檔案中找到（`grep -n "technician_headers\|vendor" api/tests/test_dispatcher_commission.py api/tests/test_technician_statement.py` 無命中）。

---

## 事實結論

1. 派工小編佣金的 8 個端點全部限 `OPS_ROLES`（`api/routers/dispatcher_commission_v2.py:63`、`:83`、`:101`、`:116`、`:133`、`:151`、`:170`、`:188`），`OPS_ROLES` 展開為 `admin, operations_manager`（`api/core/deps.py:300`）。
2. 技師與 vendor 打上述端點會得到 403 `FORBIDDEN`（`api/core/deps.py:317-322`），即見不到任何資料，而非 TC 所述的「僅見自己 scope」。此處僅並陳，不裁定。
3. 技師月結對帳單端點（`tech-statements`）同樣限 `OPS_ROLES`（`api/routers/technician_statement_v2.py:96` 等 8 處）；其 `technician_id` 為選填 query filter，非伺服器端強制 scope。
4. tech-portal 的對帳單頁以前端取得的 `technician_id` 當 query 參數呼叫該 OPS-only 端點（`web/tech-portal/src/app/account/statements/page.tsx:47-57`）。此處僅並陳，不裁定。
5. 技師確有一支具 scope 限縮的自助端點：`GET /technicians/me/commission-statements`，限 `role_required("technician")`（`api/routers/technicians.py:33`、`:143`），scope 由 JWT 的 `user_id` → `technicians.id` 反查決定（`api/services/technician_commission_service.py:180-187`），端點無 client 可控的 technician 識別參數。
6. 該端點的資料源為 CQRS 投影，欄位刻意最小化（`technician_commission_service.py:170-172` 自述「投影欄位最小化（ADR-017 §投影隱私）只帶佣金 accrued 金額，無工單毛額」）。
7. `vendor` 角色在 `api/core/deps.py:293-305` 的所有角色群組中皆不出現；其可用端點只有 `/vendors/me`（`api/routers/vendors_v2.py:34`，以自身 `user_id` 取 profile）與品牌唯讀清單（`:51`，限 `OPS_ROLES`）。無佣金或對帳單端點。
8. 成本欄位遮蔽以 `_COST_VISIBLE_ROLES = {"admin", "operations_manager"}` 為準，三個 router 各宣告一份同值常數（`catalog_v2.py:20`、`quote_v2.py:24`、`work_orders_v2.py:68`）。
9. 遮蔽為 server 端結構性不回傳該 key（`api/services/payout_rule_service.py:44-46`），非前端隱藏；`api/routers/work_orders_v2.py:67` 註解自述「server 端 RBAC 遮蔽」。
10. 客戶 token 視圖固定 `include_cost=False`（`api/routers/consumer_v2.py:284`）。
11. 佣金／月結 statement 的回傳結構不經 `include_cost` 機制（`dispatcher_commission_service.py:165` 直接回 `net_commission`；`technician_statement_service.py` 全檔無該識別碼），其保護方式為端點角色門檻。此處僅並陳，不裁定。
12. 既有測試 50 項於本機測試庫全數通過；未找到「技師／vendor token 打佣金端點應 403」的既有斷言。
