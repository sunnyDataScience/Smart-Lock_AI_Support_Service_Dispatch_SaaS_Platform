# TC-WO-06 — 安裝案未填序號的完工硬閘（維修案放行）

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試，序號閘三項（install 無序號 / install 有序號 / repair 放行）全數通過（見步驟 5） |
| 走查時間 | 2026-08-03 19:35（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/services/work_order_service.py:1449`、`:1563-1576`、`:487-499`、`:737`、`api/tests/test_cr_0039_completion_gate.py:93-132`、`SQL/Schema.sql:492`、`SQL/migrations/036-workorder-standard-fields.sql:27-28` |
| 優先級 / 路徑類型 | P0 / 例外 |
| 事實結論 | 序號閘以 `policy["serial_required_categories"]`（預設 `["install"]`）比對 `work_orders.service_category`，命中且 `serial_number` 空白時拋 422 `SERIAL_REQUIRED`；`service_category='repair'` 不在清單內故不觸發，維修案無 serial 放行。error_code 與狀態碼與 TC 判定基準相同。`service_category` 由建單時 `_map_service_category()` 從問題卡 category 字串關鍵字推導，無法判定時預設 `repair`。 |

**TC 原文**｜前置：安裝案未填 serial｜步驟：提交完工｜判定基準：422 SERIAL_REQUIRED；維修案無 serial 放行｜例外｜P0｜FR-API-08、FR-API-09｜SC-06

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客服 | 由問題卡開單 | `WorkOrderCreated` | 服務類別自動映射 | `work_order_service.py:487-499` | 關鍵字命中「install/安裝/新裝/新機/裝機」→ `install`，否則 fallback `repair` |
| 技師 | 安裝案完工送簽（無 serial） | `CompletionRejected(422)` | 安裝案須登錄序號 | `work_order_service.py:1563-1576` | 422 `SERIAL_REQUIRED` |
| 技師 | 維修案完工送簽（無 serial） | `WorkOrderCompleted` | 非 serial 類別不檢查 | `work_order_service.py:1571` | `svc_cat in serial_cats` 不成立 → 跳過 |
| 後台 | PATCH 工單欄位補 serial | `WorkOrderFieldsUpdated` | enum 白名單 | `work_order_service.py:737` | `{"install","warranty_in","warranty_out","repair"}` |

---

## 走查紀錄

### 步驟 1 — 序號閘本體

- **動作**：讀 `_enforce_completion_gate` 序號段
- **預期**：安裝案無 serial 回 422 `SERIAL_REQUIRED`
- **實際**：一致

`api/services/work_order_service.py:1563-1576`

```python
    serial_cats = policy.get("serial_required_categories") or []
    if serial_cats:
        cur = await db_module._conn.execute(
            "SELECT service_category, serial_number FROM work_orders WHERE id = %s::uuid",
            (wo_id,),
        )
        row = await cur.fetchone()
        svc_cat, serial = (row[0], row[1]) if row else (None, None)
        if svc_cat in serial_cats and not (serial and str(serial).strip()):
            raise ApiError(
                "SERIAL_REQUIRED",
                "此安裝案需登錄鎖體序號才可完工（BR-M10-03）",
                422,
            )
```

觸發條件為兩者同時成立：`service_category` 落在 `serial_required_categories` 內、且 `serial_number` 為 None 或去空白後為空字串。

### 步驟 2 — 「安裝案」的定義來源

- **動作**：追 `serial_required_categories` 預設值
- **預期**：僅 install
- **實際**：一致（預設清單只有 `"install"`，可 config 覆寫）

`api/services/work_order_service.py:1449`

```python
    "serial_required_categories": ["install"],
```

`service_category` 欄位定義：

`SQL/Schema.sql:492`

```sql
    service_category    VARCHAR(30),                    -- install/warranty_in/warranty_out/repair
```

後台 PATCH 的 enum 白名單同四值（`api/services/work_order_service.py:737`）：

```python
    "service_category": {"install", "warranty_in", "warranty_out", "repair"},
```

### 步驟 3 — 維修案為何放行

- **動作**：檢查 repair 是否落入清單
- **預期**：不在清單內、不觸發
- **實際**：一致

`repair` 不在 `["install"]` 內，`svc_cat in serial_cats` 為 False，整段 `if` 不成立，直接往下一道閘。建單時的類別映射把「無法判定」歸為 `repair`：

`api/services/work_order_service.py:487-499`

```python
def _map_service_category(pc_category: str | None) -> str:
    """CR-0043 HD-1：pc.category（自由字串，可中/英）→ work_orders.service_category
    enum（install/warranty_in/warranty_out/repair）。無法判定預設 repair，可後台 PATCH 改。"""
    c = (pc_category or "").strip().lower()
    if not c:
        return "repair"
    if any(k in c for k in ("install", "安裝", "新裝", "新機", "裝機")):
        return "install"
    if any(k in c for k in ("warranty_in", "保內", "保内")):
        return "warranty_in"
    if any(k in c for k in ("warranty_out", "保外")):
        return "warranty_out"
    return "repair"
```

### 步驟 4 — 閘的先後順序

- **動作**：確認要走到序號閘須先通過哪些條件
- **預期**：可單獨觸發
- **實際**：序號閘排在照片閘與簽名閘之後（`work_order_service.py:1552` → `:1560` → `:1563`）

既有測試以「3 張照片 + 已插入客戶簽名列」的前置直接落到序號閘：

`api/tests/test_cr_0039_completion_gate.py:108-119`

```python
@pytest.mark.asyncio
async def test_install_without_serial_422():
    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    await _insert_wo(wo_id, service_category="install", serial=None)
    await _insert_customer_signature(wo_id)
    try:
        with pytest.raises(ApiError) as ei:
            await _gate(wo_id=wo_id)
        assert ei.value.error_code == "SERIAL_REQUIRED"
    finally:
        await _cleanup(wo_id)
```

### 步驟 5 — 執行既有測試

- **動作**：跑序號閘三項（本機 Docker 測試庫）
- **預期**：取得執行證據
- **實際**：全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0039_completion_gate.py \
  tests/test_state_machine_optimistic_lock.py -q -p winloop_plugin --tb=line
20 passed in 1.67s
```

其中維修案放行的斷言：

`api/tests/test_cr_0039_completion_gate.py:94-105`

```python
@pytest.mark.asyncio
async def test_repair_with_signature_passes():
    """維修案（非 serial 類別）+ 3 照片 + 簽名存在 → 通過，回原 summary。"""
    assert await db_module._ensure_conn()
    wo_id = str(uuid.uuid4())
    await _insert_wo(wo_id, service_category="repair")
    await _insert_customer_signature(wo_id)
    try:
        out = await _gate(wo_id=wo_id)
        assert out == "完工"
    finally:
        await _cleanup(wo_id)
```

安裝案有 serial 亦通過（`:122-132` `test_install_with_serial_passes`，`serial="SN-CR39-001"`）。

---

## 觀測到的其他事實

- 專案另有一處同名 error_code：庫存領用 `SERIAL_REQUIRED`（`api/services/inventory_v2_service.py:381`，ADR-0053，語意為「serial_required=true 的料件領用未帶序號」），與完工閘為不同流程共用同一字串。
- `service_category` 為 `NULL`（例如直接 INSERT 未帶欄位）時 `svc_cat in serial_cats` 不成立，序號閘不觸發。
- `serial_required_categories` 可由 M18 config `completion_policy` 覆寫（`work_order_service.py:1536-1539`）；設為空清單時整段 `if serial_cats:` 不成立，序號閘停用。
- 前端錯誤字典 grep 結果：`git grep -n "SERIAL_REQUIRED" -- web` 零命中，四站台 `apiError.ts` 無此鍵。
- `serial_number` 欄位可由後台 PATCH `/tenants/{tenantId}/work-orders/{id}/fields` 補填（`api/routers/work_orders_v2.py:308`）。
