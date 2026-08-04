# TC-SEC-TENANT-01

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查（未啟動應用服務；另以本機 Docker 測試庫實跑既有測試） |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/core/deps.py:198-212`、`api/routers/*.py`（206 處跨租戶守衛）、`api/services/customer_service.py`、`api/services/media_service.py`、`api/services/work_order_service.py:334-377`、`api/services/audit_log_service.py`、`api/tests/test_cross_tenant_error_code_class.py`、`test_work_order_read_ownership.py`、`test_auth_guards.py` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |

TC 判定基準三段。「403/404」在程式碼中有對應實作：header 與 token claim 不符回 403 `TENANT_MISMATCH`（`api/core/deps.py:206-211`），path tenantId 與 claim 不符回 403 `CROSS_TENANT_READ` / `CROSS_TENANT_WRITE`（`api/routers/` 共 206 處字面命中），repository 層查詢一律帶 `tenant_id` 條件、查無回 404（`api/services/customer_service.py:207-212`、`api/services/media_service.py:274-281`）。「不洩存在性」在客戶／媒體／工單三處皆以 404 收尾且註解明載此意圖（`api/services/media_service.py:269`、`api/services/work_order_service.py:353-355`）。**「audit 記 `cross_tenant_violation_attempted`」在 repo 中零命中**——該字串僅出現於 `smartlock-docs/enterprise/20_Test_Cases.md:335`（TC 自身），`api/` 全樹無任何 audit 寫入點與此事件對應。「100 組 mutation 0 洩漏」需實際發送 100 組跨租戶寫入請求，本次未執行。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 8. 權限與 RBAC 案例（TC-SEC-RBAC） |
| 前置 | tenant_A 帳號 |
| 步驟 | 讀/寫 tenant_B 之客戶/工單/媒體 |
| 預期結果（判定基準） | 403/404，不洩存在性；audit 記 `cross_tenant_violation_attempted`；100 組 mutation 0 洩漏 |
| 路徑類型 | ⚠ 未標註 |
| 驗證面向 | 功能 |
| 優先級 | P0 |
| 驗證哪些需求 | FR-DAT-03、NFR-Priv-006 |
| 屬於哪條旅程腳本 | — |

出處：`smartlock-docs/enterprise/20_Test_Cases.md:335`。

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| `X-Tenant-ID` 與 token claim 不符 → 403 | `api/core/deps.py:206-211`（`TENANT_MISMATCH`） | 一致 |
| path tenantId 與 claim 不符 → 403（讀） | `api/routers/work_orders_v2.py:144-150`（`CROSS_TENANT_READ`），全 routers 共 206 處 | 一致 |
| path tenantId 與 claim 不符 → 403（寫） | `api/routers/work_orders_v2.py:153-159`（`CROSS_TENANT_WRITE`） | 一致 |
| 讀寫碼分類正確（純 GET 不用 WRITE 碼） | `api/tests/test_cross_tenant_error_code_class.py:47-73`（AST 掃描，本次通過） | 一致 |
| 客戶：repository 層 tenant 過濾 | `api/services/customer_service.py:100-101`、`:207-208`、`:388-389`、`:437-441` | 一致 |
| 工單：repository 層 tenant 過濾 | `api/services/work_order_service.py`（tenant_id 為 `work_orders` 欄位，INSERT 於 `:614-623`） | 一致 |
| 媒體：repository 層 tenant 過濾 | `api/services/media_service.py:276-277`、`:311-314`、`:352-354`、`:381-383` | 一致 |
| 查無 → 404 不洩存在性（客戶） | `api/services/customer_service.py:210-212` | 一致 |
| 查無 → 404 不洩存在性（媒體） | `api/services/media_service.py:269`、`:280-281`、`:283-285` | 一致 |
| 同租戶內工單擁有權 → 404 不洩存在性 | `api/services/work_order_service.py:353-355`、`:366-377` | 一致 |
| audit 記 `cross_tenant_violation_attempted` | 全 repo 零命中（僅 `20_Test_Cases.md:335`） | 不一致 |
| 100 組 mutation 0 洩漏 | 需實際發送 100 組跨租戶寫入請求 | 無法靜態判定 |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| tenant_A 帳號 | 帶 `X-Tenant-ID: tenant_B` 打任何 tenant-scoped 端點 | `RequestRejected(403)` | header 綁定 claim | `api/core/deps.py:206-211` | `TENANT_MISMATCH`，403 |
| tenant_A 帳號 | 打 `/tenants/{tenant_B}/work-orders` | `RequestRejected(403)` | path 綁定 claim | `api/routers/work_orders_v2.py:144-150` | `CROSS_TENANT_READ`，403 |
| tenant_A 帳號 | 寫 `/tenants/{tenant_B}/...` | `RequestRejected(403)` | 同上 | `api/routers/work_orders_v2.py:153-159` | `CROSS_TENANT_WRITE`，403 |
| tenant_A 帳號 | 讀 tenant_B 的 customer_id（自己的 tenant path） | `RequestRejected(404)` | repository tenant 過濾 | `api/services/customer_service.py:207-212` | `NOT_FOUND`，404 |
| tenant_A 帳號 | 讀 tenant_B 的 media_id | `RequestRejected(404)` | 同上 | `api/services/media_service.py:276-281` | `NOT_FOUND`，404 |
| technician | 讀同租戶內非自己的工單 | `RequestRejected(404)` | per-work-order 擁有權 | `api/services/work_order_service.py:366-377` | `NOT_FOUND`，404＋server log |
| 系統 | 跨租戶請求被擋 | `CrossTenantViolationAttempted`（audit） | 記錄違規嘗試 | — | **找不到**：`cross_tenant_violation_attempted` 在 `api/` 零命中；`api/core/errors.py` 的錯誤處理器不呼叫 `audit_log_service.log_event` |

---

## 逐層走查

### 步驟 1 — 第一層：header 綁定 token claim

`api/core/deps.py:198-212`：

```python
async def require_tenant(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> CurrentUser:
    """同時驗 JWT + 比對 X-Tenant-ID 與 claim 一致。"""
    user = await get_current_user(request, authorization)
    tenant = await resolve_tenant_id(x_tenant_id)
    if user.tenant_id and user.tenant_id != tenant:
        raise ApiError(
            error_code="TENANT_MISMATCH",
            message="X-Tenant-ID does not match token claim",
            status_code=403,
        )
    return user
```

缺 header 時由 `api/core/tenant.py:18-23` 先回 400 `MISSING_TENANT`。

### 步驟 2 — 第二層：path tenantId 綁定 token claim

`api/routers/work_orders_v2.py:144-159`：

```python
def _cross_tenant_read(user: CurrentUser, tenant_id: str) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        raise ApiError(
            "CROSS_TENANT_READ",
            "Path tenantId does not match authenticated tenant",
            403,
        )


def _cross_tenant_write(user: CurrentUser, tenant_id: str) -> None:
    if user.tenant_id and user.tenant_id != tenant_id:
        raise ApiError(
            "CROSS_TENANT_WRITE",
            "Path tenantId does not match authenticated tenant",
            403,
        )
```

同型守衛在 `api/routers/` 共 206 處字面命中：

```
$ grep -rn "CROSS_TENANT_READ\|CROSS_TENANT_WRITE" api/routers/ | wc -l
206
```

`api/routers/media_v2.py:74-79` 為媒體上傳端的同型守衛：

```python
    # cross-tenant guard（ADR-0030）
    if user.tenant_id and user.tenant_id != tenantId:
```

`api/routers/media_v2.py:111-112` 為媒體下載端。

### 步驟 3 — 第三層：repository 層 tenant 過濾（客戶）

`api/services/customer_service.py:11`（模組 docstring）：

```
租戶隔離：users.tenant_id 直接過濾。Cursor: (created_at, id) 倒序。
```

列表（`api/services/customer_service.py:100-101`）：

```python
    where = ["u.tenant_id = %s::uuid", "u.role = 'line_user'"]
    args: list = [tenant_id]
```

單筆讀（`api/services/customer_service.py:204-212`）：

```python
    cur = await db_module._conn.execute(
        f"SELECT {_CUSTOMER_SELECT} FROM users u "
        f"WHERE u.id = %s::uuid AND u.tenant_id = %s::uuid AND u.role = 'line_user'",
        (customer_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Customer not found", 404)
```

寫入（`api/services/customer_service.py:437-441`）：

```python
    args: list = [*data.values(), customer_id, tenant_id]
    ...
        f"WHERE id = %s::uuid AND tenant_id = %s::uuid AND role = 'line_user' "
```

`api/services/customer_service.py:340` 註解記載此設計：

```python
#   - 跨租戶寫入：service 端用 tenant_id 條件守住，404 路徑保證不洩露其他 tenant
```

### 步驟 4 — 第三層：repository 層 tenant 過濾（媒體）

`api/services/media_service.py:264-281`：

```python
async def get_media(
    *, tenant_id: str, media_id: str, role: str | None = None
) -> tuple[bytes, str, str]:
    """讀檔。回傳 (bytes, content_type, filename)。

    CR-0040：角色不可見的 purpose（如品牌看環境照）→ 404（不洩漏存在性）；軟刪 → 404。
    """
    ...
    cur = await db_module._conn.execute(
        "SELECT storage_path, content_type, filename, purpose "
        "FROM media_files "
        "WHERE id = %s::uuid AND tenant_id = %s::uuid AND deleted_at IS NULL",
        (media_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise ApiError("NOT_FOUND", "Media not found", 404)
```

角色可見性亦收斂為 404（`api/services/media_service.py:283-285`）：

```python
    # CR-0040 角色可見性：不可見 → 404（避免向品牌洩漏該照存在）
    if purpose in _hidden_purposes(role):
        raise ApiError("NOT_FOUND", "Media not found", 404)
```

儲存路徑本身以 tenant 分層（`api/services/media_service.py:8`、`:93-97`）：

```python
儲存策略（MVP）：本機檔案系統 MEDIA_ROOT/{tenant_id}/{YYYY-MM}/{media_id}{ext}
...
def _build_storage_path(*, tenant_id: str, media_id: str, content_type: str) -> Path:
    """產生 storage path：{tenant_id}/{YYYY-MM}/{media_id}{ext}"""
```

工單媒體列表與爭議媒體列表同樣帶 tenant 條件（`api/services/media_service.py:311-314`、`:381-383`）。

### 步驟 5 — 同租戶內的第四層：工單擁有權

`api/services/work_order_service.py:334-377`：

```python
async def assert_technician_may_read(
    *, wo_id: str, actor_role: str | None, actor_user_id: str | None
) -> None:
    """技師讀「單筆工單／其子資源」的擁有權守衛（2026-08-02）。
    ...
    對照組已排除「守衛整支沒掛」：換租戶 id 時 admin 與技師都 403 CROSS_TENANT_READ，
    所以缺的是同租戶內的 per-work-order 擁有權檢查。
    ...
    **回 404 而非 403**：技師沒有任何合法管道得知這張單存在（自己的列表濾掉了、
    池子也濾掉了），回 403 等於確認存在性、可被拿來枚舉租戶內的工單 id。
    真正的原因記在 server log，營運查得到、客戶端問不出來。
    """
    if actor_role != "technician":
        return
    ...
    logger.warning(
        "技師讀取未授權工單被擋 wo=%s actor_user=%s assigned_to=%s status=%s",
        wo_id[:8], str(actor_user_id)[:8], (assigned_to or "-")[:8], status,
    )
    raise ApiError("NOT_FOUND", "Work order not found", 404)
```

工單列表對技師的收斂在 `api/services/work_order_service.py:321-331`，查無對應 technicians 列時回 `_NO_TECHNICIAN_SENTINEL` 而非「不過濾」：

```python
    if actor_role != "technician":
        return requested
    tech = await _fetch_technician_for_user(actor_user_id)
    if not tech:
        # 有技師 token 但品牌庫查無對應 technicians 列 → 不得退回「不過濾」
        logger.warning(
            "technician token 查無對應 technicians 列 user=%s → 工單列表收斂為空",
            str(actor_user_id)[:8],
        )
        return _NO_TECHNICIAN_SENTINEL
```

### 步驟 6 — audit 事件比對

TC 指名的事件名在全 repo 的命中：

```
$ rg -n "cross_tenant_violation_attempted"
smartlock-docs\enterprise\20_Test_Cases.md:335:| TC-SEC-TENANT-01 | api B-01 | tenant_A 帳號 | 讀/寫 tenant_B 之客戶/工單/媒體 | 403/404，不洩存在性；audit 記 `cross_tenant_violation_attempted`；100 組 mutation 0 洩漏 | P0 |
```

唯一命中為 TC 自身所在的文件行。`api/` 下零命中。

audit 寫入的公開入口為 `api/services/audit_log_service.py:476` 的 `log_event` 與 `:527` 的 `log_event_returning_id`；`api/core/errors.py` 的統一錯誤處理器（`api/core/errors.py:1-` 全檔）不呼叫這兩支：

```
$ grep -rn "log_event" api/core/errors.py api/main.py
（無輸出）
```

跨租戶被擋時的可觀測輸出為 `api/services/work_order_service.py:373-376` 的 `logger.warning`（僅工單擁有權路徑），以及各層的 HTTP 403/404 回應本身。

TC 判定基準寫「audit 記 `cross_tenant_violation_attempted`」（出處 `smartlock-docs/enterprise/20_Test_Cases.md:335`）／`api/` 全樹無此事件名、且跨租戶守衛的 raise 點（`api/core/deps.py:207`、`api/routers/*.py` 206 處）皆未呼叫 `audit_log_service.log_event`。此處僅並陳，不裁定。

### 步驟 7 — 錯誤碼分類的守門

`api/tests/test_cross_tenant_error_code_class.py:1-14`：

```python
"""UAT-D-003：純 GET 端點不得以 CROSS_TENANT_WRITE 回報跨租戶違規。

WHY 這條值得一支測試：
  阻擋行為本來就對（都是 403），錯的只是**分類**——所以功能測試永遠測不出來，
  只有靠靜態掃描。而分類錯的後果是實質的：治理／安全告警若依 error_code 分流，
  會把「跨租戶讀取」計入「跨租戶寫入」，讓事故等級判斷失真。

  codebase 本身明確區分兩碼（READ 與 WRITE 各有數十處），所以這是 mislabel
  而非設計選擇——2026-07-29 掃 215 個純 GET 端點抓到 6 個。
```

該測試以 AST 掃 `api/routers/`（`:47-73`），本次執行通過。

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

對到 TC 步驟的測試：

`api/tests/test_auth_guards.py:34-42`（跨租戶 header → 403）：

```python
async def test_tenant_mismatch_returns_403(client, admin_token):
    # 故意傳錯 tenant 不對應的 X-Tenant-ID
    headers = {
        "Authorization": f"Bearer {admin_token}",
        "X-Tenant-ID": "ffffffff-ffff-ffff-ffff-ffffffffffff",
    }
    res = await client.get("/api/v1/work-orders", headers=headers)
    assert res.status_code == 403
```

`api/tests/test_work_order_read_ownership.py:1-20`（同租戶內工單擁有權，404 不洩存在性），該檔檔頭記載其對照組結論：

```python
對照組已排除「守衛整支沒掛」：換租戶 id 時 admin 與技師都 403 CROSS_TENANT_READ。
缺的是同租戶內的 per-work-order 擁有權檢查。
...
回 404 而非 403 是刻意的：技師沒有合法管道得知那張單存在（自己的列表與池子都濾掉了），
回 403 等於確認存在性、可被拿來枚舉租戶內的工單 id。
```

`api/tests/test_cross_tenant_error_code_class.py` 兩支測試（純 GET 不得用 WRITE 碼、兩碼都仍在用）本次通過。

`api/tests/` 中無斷言 audit 記錄跨租戶違規的測試（`cross_tenant_violation_attempted` 零命中）。

---

## 事實結論

1. 跨租戶阻擋有三層：`X-Tenant-ID` vs token claim（403 `TENANT_MISMATCH`，`api/core/deps.py:206-211`）、path tenantId vs claim（403 `CROSS_TENANT_READ` / `CROSS_TENANT_WRITE`，`api/routers/` 共 206 處）、repository 查詢帶 `tenant_id` 條件（查無回 404）。
2. 三層的第二、三層均帶 `if user.tenant_id and ...` 前置條件；token 無 `tenant_id` claim 時（`CurrentUser.tenant_id` 為空字串，`api/core/deps.py:185`）該比對不執行。
3. 客戶、媒體、工單三種資源的 repository 查詢皆帶 tenant 條件（`api/services/customer_service.py:207-208`、`api/services/media_service.py:276-277`、媒體另以 `MEDIA_ROOT/{tenant_id}/` 分層儲存 `:93-97`）。
4. 存在性不洩漏以 404 收尾，且三處註解明載此意圖（`api/services/customer_service.py:340`、`api/services/media_service.py:269`、`api/services/work_order_service.py:353-355`）。
5. 同租戶內另有 per-work-order 擁有權守衛，技師讀非自己且非搶單池的工單回 404 並記 server log（`api/services/work_order_service.py:359-377`）。
6. TC 指名的 audit 事件 `cross_tenant_violation_attempted` 在 `api/` 全樹零命中；唯一命中為 `smartlock-docs/enterprise/20_Test_Cases.md:335`（TC 自身）。跨租戶 raise 點未呼叫 `audit_log_service.log_event`。
7. 「100 組 mutation 0 洩漏」需實際發送 100 組跨租戶寫入請求，本次未執行。
8. 錯誤碼分類（純 GET 不得用 `CROSS_TENANT_WRITE`）有 AST 靜態掃描測試守門（`api/tests/test_cross_tenant_error_code_class.py`），本次通過。
