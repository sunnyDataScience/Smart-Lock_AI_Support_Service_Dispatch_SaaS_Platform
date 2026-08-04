# TC-WO-04 — 完工照片不足 3 張的硬閘

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試，`test_cr_0039_completion_gate.py` 8 項全數通過（見步驟 5） |
| 走查時間 | 2026-08-03 19:10（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/services/work_order_service.py:1446-1453`、`:1519-1559`、`:1751-1775`、`api/routers/work_orders_v2.py:878-989`、`web/tech-portal/src/app/my-orders/[id]/page.tsx:220-232`、`:704-712`、`:795-808`、`api/tests/test_cr_0039_completion_gate.py:66-72` |
| 優先級 / 路徑類型 | P0 / 例外 |
| 事實結論 | 完工硬閘 `_enforce_completion_gate` 在技師正規路徑（`is_override=False`）比對 `len(photo_evidence_ids) < min_photos` 時拋 `ApiError("INSUFFICIENT_PHOTOS", ..., 422)`，error_code 字串與 HTTP 狀態碼皆與 TC 判定基準相同。門檻 3 為 `_COMPLETION_POLICY_DEFAULTS["min_photos"]`，執行期可被 M18 config `completion_policy` 覆寫。前端技師端以 `completionPhotos.length < 3` 停用送出鈕。 |

**TC 原文**｜前置：in_progress、完工照片僅 2 張｜步驟：師傅提交完工｜判定基準：422 INSUFFICIENT_PHOTOS（≥3 張 gate）｜例外｜P0｜FR-API-08、FR-API-09｜SC-06

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 技師 | 於 App 選 2 張照片送出 | `CompletionSubmitBlocked` | 前端 ≥3 張才可送 | `my-orders/[id]/page.tsx:804` | `disabled={... completionPhotos.length < 3 ...}` |
| 技師 | POST `/onsite/completion`（2 張） | `CompletionRejected(422)` | 照片數 < min_photos | `work_order_service.py:1552-1559` | 422 `INSUFFICIENT_PHOTOS` |
| 系統 | 進入硬閘前先驗狀態 | `StateChecked` | 僅 accepted / in_progress 可完工 | `work_order_service.py:1753-1759` | 非該集合 → 409 `STATE_CONFLICT` |
| 系統 | 讀門檻 | `PolicyLoaded` | 門檻可 config 覆寫 | `work_order_service.py:1536-1539` | `completion_policy` 覆寫 defaults |
| 技師 | POST 空照片陣列 | `ValidationRejected(422)` | pydantic `min_length=1` | `routers/work_orders_v2.py:887` | 422 `VALIDATION_ERROR`（非 `INSUFFICIENT_PHOTOS`） |

---

## 走查紀錄

### 步驟 1 — 硬閘的照片條件與 error_code

- **動作**：讀 `_enforce_completion_gate` 的照片段
- **預期**：照片不足回 422 `INSUFFICIENT_PHOTOS`
- **實際**：一致

`api/services/work_order_service.py:1551-1559`

```python
    # 技師正規完工 — 三道硬閘
    min_photos = int(policy.get("min_photos", 3))
    n_photos = len(photo_evidence_ids or [])
    if n_photos < min_photos:
        raise ApiError(
            "INSUFFICIENT_PHOTOS",
            f"完工照片至少 {min_photos} 張（目前 {n_photos} 張）",
            422,
        )
```

error_code 字串為 `INSUFFICIENT_PHOTOS`、狀態碼 422，與 TC 判定基準逐字相同。

### 步驟 2 — 門檻 3 的來源

- **動作**：追 `min_photos` 的預設值與覆寫來源
- **預期**：預設 3
- **實際**：預設 3，且執行期讀 M18 config 可覆寫

`api/services/work_order_service.py:1446-1453`

```python
_COMPLETION_POLICY_DEFAULTS = {
    "min_photos": 3,
    "require_signature": True,
    "serial_required_categories": ["install"],
    "allow_supervisor_override": True,
    # CR-0043 Tier④：完工前是否強制三段免責同意（預設 off 避免回歸破壞；config 開才擋）
    "require_consents": False,
}
```

`api/services/work_order_service.py:1536-1539`

```python
    policy = dict(_COMPLETION_POLICY_DEFAULTS)
    cfg = await config_m18_service.read_global_value(namespace="completion_policy")
    if isinstance(cfg, dict):
        policy.update(cfg)
```

即 `3` 不是寫死常數，而是「defaults 3、config 有值就覆寫」。

### 步驟 3 — 觸發此閘的入口與 override 例外

- **動作**：追哪一條 API 會帶 `is_override=False`
- **預期**：技師完工送簽走硬閘
- **實際**：`/onsite/completion` 明確傳 `is_override=False`；`:complete` 傳 `is_override=True` 並在硬閘第一段就 return，不執行照片檢查

`api/routers/work_orders_v2.py:967-982`（節錄）

```python
    order = await work_order_service.complete_order(
        tenant_id=tenantId,
        wo_id=woId,
        summary=summary,
        actual_amount=None,
        # CR-0039 完工硬閘：技師現場送簽走正規閘（照片≥config / 簽名存在 / 安裝案序號）
        photo_evidence_ids=body.photo_evidence_ids,
        signature_evidence_id=body.signature_evidence_id,
        is_override=False,
```

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

### 步驟 4 — 前端技師端的照片計數

- **動作**：讀技師 App 完工表單
- **預期**：不足 3 張不可送出
- **實際**：一致

`web/tech-portal/src/app/my-orders/[id]/page.tsx:800-808`

```tsx
                  onClick={submitCompletion}
                  disabled={
                    submitting ||
                    completionPhotos.length < 3 ||
                    custSig.length <= 100 ||
                    techSig.length <= 100
                  }
```

計數提示同以 3 為分界（`:704-712`）：

```tsx
                <span
                  className={
                    completionPhotos.length >= 3
                      ? "text-[11px] text-[var(--text-success)]"
                      : "text-[11px] text-[var(--text-warning)]"
                  }
                >
                  {tForm("photosCounter", { n: completionPhotos.length })}
                </span>
```

### 步驟 5 — 執行既有測試

- **動作**：跑完工硬閘測試（本機 Docker 測試庫，環境見 README「本機測試資料庫」）
- **預期**：取得執行證據
- **實際**：全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0039_completion_gate.py \
  tests/test_state_machine_optimistic_lock.py -q -p winloop_plugin --tb=line
20 passed in 1.67s
```

對應本 TC 的斷言在 `api/tests/test_cr_0039_completion_gate.py:66-72`：

```python
@pytest.mark.asyncio
async def test_insufficient_photos_422():
    assert await db_module._ensure_conn()
    with pytest.raises(ApiError) as ei:
        await _gate(photo_evidence_ids=["p1", "p2"])  # 2 < 3
    assert ei.value.status_code == 422
    assert ei.value.error_code == "INSUFFICIENT_PHOTOS"
```

---

## 觀測到的其他事實

- 照片為 0 張時走的是另一條路徑：`_CompletionSubmitRequest.photo_evidence_ids` 標有 `min_length=1`（`api/routers/work_orders_v2.py:887`），pydantic 先回 422 `VALIDATION_ERROR`，不會到達 `INSUFFICIENT_PHOTOS`。既有測試 `test_onsite_completion_v2_empty_photo_list_422`（`api/tests/test_work_orders_onsite_v2_endpoint.py:163-176`）釘住此行為。
- 硬閘之前另有兩道檢查會先觸發：狀態集合 `_COMPLETE_FROM = {"accepted", "in_progress"}`（`work_order_service.py:927`、`:1753-1759`，非該集合 → 409）與 `_assert_not_high_risk_hold`（`:1765`）。
- 前端錯誤字典 `web/tech-portal/src/lib/apiError.ts` 有 `SIGNATURE_REQUIRED`（`:79`）與 `OVERRIDE_NOT_ALLOWED`（`:46`），**無** `INSUFFICIENT_PHOTOS` 鍵；grep 結果：

```
git grep -n "INSUFFICIENT_PHOTOS" -- web
（零命中）
```

- `_enforce_completion_gate` 在照片閘之後尚有簽名（`:1560-1562`）、序號（`:1563-1576`）、三段同意（`:1577-1584`）、pending scope（`:1585-1591`）、結案地址（`:1592-1600`）、報價（`:1601-1617`）等閘，照片閘為第一道。
