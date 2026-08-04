# TC-QUOTE-07 — 客戶端報價視圖的成本隔離

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 5） |
| 走查時間 | 2026-08-03 18:29（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/routers/consumer_v2.py:270-294`、`api/services/quote_engine_service.py:388-417`、`api/routers/quote_v2.py:24`、`:33-34`、`:126-134`、`api/services/quote_service.py:30-49`、`api/services/work_order_document_service.py:30-45`、`web/brand-portal/src/app/quotes/[token]/page.tsx:37-58` |
| 優先級 / 路徑類型 | P0 / ⚠ 未標註 |
| 事實結論 | 內外部視圖以 `include_cost` 旗標分離：客戶端 public token 路徑硬編 `include_cost=False`，序列化時不放入 `unit_price` 鍵；內部端點依 `admin/operations_manager` 角色決定。前端客戶頁的 TypeScript 型別亦不含 `unit_price`。 |

**TC 原文**｜前置：客戶端報價檢視｜步驟：客戶以 public token 開報價｜判定基準：只見實收金額，不洩 unit_price/成本（內外部視圖分離）｜⚠ 未標註｜P0｜FR-API-02、FR-WEB-06｜SC-04

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客戶 | GET `/consumer/quotes/{token}` | `QuoteViewed(customer)` | 不含成本 | `routers/consumer_v2.py:283-285` | 硬編 `include_cost=False` |
| 系統 | 序列化明細 | `LineSerialized` | 無成本鍵 | `quote_engine_service.py:404-409` | `if include_cost:` 才加 `unit_price` |
| 系統 | 組客戶回應 | `ResponseBuilt` | 最小欄位 | `routers/consumer_v2.py:287-294` | 只回 6 欄，無 work_order_id |
| 後台 admin | GET `/tenants/{tid}/quotes/{id}` | `QuoteViewed(internal)` | 角色白名單 | `routers/quote_v2.py:33-34`、`:134` | `_cost(user)` 依 `_COST_VISIBLE_ROLES` |

---

## 走查紀錄

### 步驟 1 — 客戶端路徑的成本旗標

- **動作**：讀 public token 查詢端點
- **預期**：不回 `unit_price`
- **實際**：一致，旗標為呼叫端硬編

`api/routers/consumer_v2.py:276-294`

```python
async def get_consumer_quote(
    token: str = Path(..., min_length=32, max_length=512),
) -> dict:
    """客戶用 quote_view token 查報價 —— include_cost=False 結構上不回 unit_price。"""
    from services import quote_engine_service

    payload = _verify_quote_token(token)
    quote = await quote_engine_service.get_quote(
        tenant_id=payload.tenant_id, quote_id=payload.subject_id, include_cost=False,
    )
    # 客戶端只需金額/明細/狀態/有效期 —— 不回 work_order_id（客戶無用且為最小資料原則）
    return {
        "quote_id": quote["id"],
        "state": quote["state"],
        "total_amount": quote["total_amount"],
        "lines": quote["lines"],  # include_cost=False → 無 unit_price
        "expires_at": quote["expiry_at"],
        "snapshot_hash": quote["snapshot_hash"],
    }
```

`include_cost` 為位置無關的關鍵字引數且無預設值（`quote_engine_service.py:388`：`async def get_quote(*, tenant_id: str, quote_id: str, include_cost: bool) -> dict:`），呼叫端必須明示。

### 步驟 2 — 序列化層的結構性隔離

- **動作**：讀 `get_quote` 的明細組裝
- **預期**：`unit_price` 不進 dict
- **實際**：一致（非遮蔽成 null，而是鍵不存在）

`api/services/quote_engine_service.py:400-417`

```python
    lines_rows = await (await conn.execute(
        "SELECT id, item_name, category, unit_price, quantity, customer_price, service_code, material_code "
        "FROM quote_line_items WHERE quote_id = %s::uuid ORDER BY created_at", (quote_id,))).fetchall()
    lines = []
    for lr in lines_rows:
        line = {"id": str(lr[0]), "item_name": lr[1], "category": lr[2], "quantity": int(lr[4]),
                "customer_price": _dec(lr[5]), "service_code": lr[6], "material_code": lr[7]}
        if include_cost:
            line["unit_price"] = _dec(lr[3])
        lines.append(line)
    return {
        "id": str(r[0]), "work_order_id": str(r[1]) if r[1] else None, "version": int(r[2]),
        "state": r[3], "total_amount": _dec(r[4]), "deposit_required": _dec(r[5]),
        "expiry_at": r[6].isoformat() if r[6] else None, "snapshot_hash": r[7],
        "is_mock": bool(r[8]), "lines": lines, "cost_visible": include_cost,
```

SQL 仍 SELECT `unit_price`（`:401`），隔離發生在 Python 組裝層而非查詢層。頂層 dict 另回 `cost_visible` 旗標。

### 步驟 3 — 內部視圖的角色判定

- **動作**：讀後台端點
- **預期**：內外部視圖分離
- **實際**：一致

`api/routers/quote_v2.py:24`、`:33-34`、`:126-134`

```python
_COST_VISIBLE_ROLES = {"admin", "operations_manager"}  # SA-01：死角色移除
...
def _cost(user: CurrentUser) -> bool:
    return (user.role or "") in _COST_VISIBLE_ROLES
...
async def get_quote_v2(
    tenantId: str = Path(...), id: str = Path(...),
    # CR-0183 補漏（2026-07-27）：同資源的 list 端點已上守衛、本明細端點卻只有
    # require_tenant → 低權限角色只要知道/猜到 ID 就能直接讀明細，繞過 list 守衛。
    # 守衛不得弱於同資源的 list。
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
    _xt(user, tenantId)
    return {"data": await qe.get_quote(tenant_id=tenantId, quote_id=id, include_cost=_cost(user))}
```

即後台 `OPS_ROLES` 中非 `admin/operations_manager` 的角色也讀不到 `unit_price`。

### 步驟 4 — 其他對客戶輸出面

- **動作**：搜其他可能外洩 `unit_price` 的序列化點
- **預期**：皆不含成本
- **實際**：一致

`api/services/work_order_document_service.py:30`、`:45`

```python
    """只取 customer-facing 欄位（嚴禁 unit_price）。tenant 隔離走 users join。"""
...
    # 只取 item_name / quantity / customer_price —— **不 SELECT unit_price**
```

`api/services/invoice_service.py:262-263`

```python
    金額取報價客戶價（不含內部成本 unit_price）；稅 mock 0（待 esales Q-07）；is_mock 沿報價旗標。
    line_items 結構：[{item_name, category, quantity, customer_price}] —— **不含 unit_price**（成本不外洩）。
```

CR-0027 公單成本拆項 service 走同型旗標：

`api/services/quote_service.py:30-43`

```python
def _row_to_item(row: tuple, *, include_cost: bool) -> dict:
    """row 對齊 _ITEM_SELECT。include_cost=False 時不輸出 unit_price。"""
    out = {
        "id": str(row[0]),
        "work_order_id": str(row[1]),
        "item_name": row[3],
        "category": row[4],
        "quantity": int(row[6]),
        "customer_price": _dec(row[7]),
        "is_mock": bool(row[8]),
    }
    if include_cost:
        out["unit_price"] = _dec(row[5])  # 內部成本 — 僅後台
    return out
```

前端客戶頁型別亦不含成本欄：

`web/brand-portal/src/app/quotes/[token]/page.tsx:37-45`

```tsx
interface ConsumerQuoteLine {
  id: string;
  item_name: string;
  category: string;
  quantity: number;
  customer_price: string | null;
  service_code: string | null;
  material_code: string | null;
}
```

### 步驟 5 — 執行既有測試

- **動作**：跑報價序列化測試
- **預期**：取得執行證據
- **實際**：第一輪無資料庫全數失敗；建立本機測試庫後重跑，三檔 22 項全數通過

第一輪（無資料庫）：

```
cd api && python -m pytest tests/test_cr_0152_ai_quote_gate.py tests/test_cr_0128_quote_gate.py tests/test_cr_0032_quote_engine.py -q -rs --tb=no
FFFFFFFFFFFF..FFFFFFFF                                                   [100%]
20 failed, 2 passed in 2.82s
```

錯誤原文 `ERROR api.db:db.py:48 環境變數 POSTGRES_URI 未設定`。

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0032_quote_engine.py -q -p winloop_plugin --tb=no
8 passed in 3.64s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0128_quote_gate.py -q -p winloop_plugin --tb=no
11 passed in 1.09s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0152_ai_quote_gate.py -q -p winloop_plugin --tb=no
3 passed in 2.94s
```

`api/tests/test_cr_0032_quote_engine.py:1-8` docstring 列有「include_cost RBAC 遮蔽 unit_price」項目，該檔 8 項在第二輪皆通過。

---

## 觀測到的其他事實

- token 驗證含 purpose 與 tenant 檢查，失敗一律 404 且不區分原因（`api/routers/consumer_v2.py:248-267`）。
- 客戶回應含 `snapshot_hash`（`consumer_v2.py:293`），為凍結快照的 sha256 摘要（`quote_engine_service.py:840`），其 payload 內容只含 `name/cat/price/qty` 與 discount_policy（`:833-838`），不含 `unit_price`。
- `quote_line_items.unit_price` 的欄位註解已標示存取邊界：`SQL/migrations/037-quote-line-items.sql:39`「內部成本（僅 admin/operations_manager 可讀；客戶端電子工單絕不含）」。
