# TC-WO-05 — 完工無客戶簽名紀錄的硬閘

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試，簽名相關 2 項通過（見步驟 5） |
| 走查時間 | 2026-08-03 19:22（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/services/work_order_service.py:1480-1488`、`:1560-1562`、`api/routers/work_orders_v2.py:886`、`web/tech-portal/src/app/my-orders/[id]/page.tsx:204-221`、`api/tests/test_cr_0039_completion_gate.py:75-90`、`api/tests/test_state_machine_optimistic_lock.py:88-96` |
| 優先級 / 路徑類型 | P0 / 例外 |
| 事實結論 | 簽名閘為兩個條件的 or-拒絕：`signature_evidence_id` 為空、或 `_signature_exists(wo_id)` 查 `digital_signatures` 查不到 `signer_role='customer'` 的列，任一成立即 422 `SIGNATURE_REQUIRED`。「真存在性」由第二個條件承擔——它查資料庫實列而非只看傳入字串是否非空。error_code 與狀態碼與 TC 判定基準相同。 |

**TC 原文**｜前置：完工無客戶簽名紀錄｜步驟：提交完工｜判定基準：422 SIGNATURE_REQUIRED（簽名真存在性驗證）｜例外｜P0｜FR-API-08、FR-API-09｜SC-06

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 技師 | 先送雙簽名 | `SignatureRecorded` | 建 `digital_signatures` 列 | `my-orders/[id]/page.tsx:208-216` | POST `/work-orders/{id}/signature` |
| 技師 | POST `/onsite/completion`（無簽名列） | `CompletionRejected(422)` | 簽名須真存在 | `work_order_service.py:1560-1562` | 422 `SIGNATURE_REQUIRED` |
| 系統 | 查簽名真存在性 | `SignatureLookup` | `document_type='work_order'` + `signer_role='customer'` | `work_order_service.py:1480-1488` | `SELECT 1 FROM digital_signatures ... LIMIT 1` |
| 系統 | 讀 policy | `PolicyLoaded` | `require_signature` 可 config 關閉 | `work_order_service.py:1560` | `if policy.get("require_signature", True):` |

---

## 走查紀錄

### 步驟 1 — 簽名閘本體

- **動作**：讀 `_enforce_completion_gate` 簽名段
- **預期**：缺簽名回 422 `SIGNATURE_REQUIRED`
- **實際**：一致

`api/services/work_order_service.py:1560-1562`

```python
    if policy.get("require_signature", True):
        if not signature_evidence_id or not await _signature_exists(wo_id):
            raise ApiError("SIGNATURE_REQUIRED", "完工需客戶簽名（簽名紀錄不存在）", 422)
```

兩個條件以 `or` 串接：只要傳入的 `signature_evidence_id` 為空**或**資料庫查無簽名列，皆拋同一個 422。

### 步驟 2 — 「真存在性」的定義

- **動作**：讀 `_signature_exists`
- **預期**：查資料庫實列，而非僅檢查字串非空
- **實際**：一致

`api/services/work_order_service.py:1480-1488`

```python
async def _signature_exists(wo_id: str) -> bool:
    """完工是否已有客戶簽名（digital_signatures；CR-0039 HD-4 驗證簽名真存在，非僅非空字串）。"""
    cur = await db_module._conn.execute(
        "SELECT 1 FROM digital_signatures "
        "WHERE document_type = 'work_order' AND document_id = %s::uuid "
        "  AND signer_role = 'customer' LIMIT 1",
        (wo_id,),
    )
    return (await cur.fetchone()) is not None
```

判定條件為三個：`document_type = 'work_order'`、`document_id = 該工單`、`signer_role = 'customer'`。技師簽名（`signer_role='technician'`）不滿足此查詢。

### 步驟 3 — `signature_evidence_id` 的實際用途

- **動作**：追該欄位在完工路徑上如何被使用
- **預期**：作為簽名憑證
- **實際**：僅作為「非空旗標」＋寫入稽核 summary，其值本身不被驗證

`api/routers/work_orders_v2.py:958-965`

```python
    photos_str = ",".join(body.photo_evidence_ids)
    summary_parts = [
        f"[ONSITE_COMPLETE] sig={body.signature_evidence_id}",
        f"photos=[{photos_str}]",
    ]
```

前端明文記載同一件事：

`web/tech-portal/src/app/my-orders/[id]/page.tsx:220-225`

```tsx
      // 2) CR-0039 正規完工硬閘 /onsite/completion（照片≥3 / 簽名紀錄存在）。
      //    signature_evidence_id 後端僅寫進稽核 summary、不驗證，傳標記即可。
      await api.post<{ work_order_id: string; completed_at: string | null }>(
        tenantPath(`/work-orders/${encodeURIComponent(wo.id)}/onsite/completion`),
        {
          signature_evidence_id: "onsite-signature",
```

即前端固定傳字串常數 `"onsite-signature"`，真正決定放行與否的是步驟 2 的資料庫查詢。

### 步驟 4 — 前端建立簽名列的順序

- **動作**：讀技師 App 送出流程
- **預期**：先建簽名列，再送完工
- **實際**：一致，且對 409 做了容錯

`web/tech-portal/src/app/my-orders/[id]/page.tsx:204-219`

```tsx
      // 1) 先送雙簽名 → 建 digital_signatures 紀錄。完工硬閘 _signature_exists 認的是
      //    這個（customer 簽名紀錄），非 /media 上傳的簽名圖。與 /signature 頁同一端點。
      //    冪等：若已完整簽署（後端回 409 STATE_CONFLICT），紀錄本就存在 → 視為成功、續送完工。
      try {
        await api.post(
          tenantPath(`/work-orders/${encodeURIComponent(wo.id)}/signature`),
          {
            customer_signature: custSig,
            technician_signature: techSig,
            signed_at: new Date().toISOString(),
          },
        );
      } catch (sigErr) {
        if (!(sigErr instanceof ApiError && sigErr.status === 409)) throw sigErr;
        // 409 = 已完整簽署；digital_signatures 已存在，完工硬閘可過 → 不阻擋，續送完工。
      }
```

送出鈕另以簽名字串長度把關（`:800-808`）：`custSig.length <= 100 || techSig.length <= 100` 時停用。

### 步驟 5 — 執行既有測試

- **動作**：跑簽名閘測試（本機 Docker 測試庫）
- **預期**：取得執行證據
- **實際**：全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0039_completion_gate.py \
  tests/test_state_machine_optimistic_lock.py -q -p winloop_plugin --tb=line
20 passed in 1.67s
```

兩條斷言分別覆蓋「有 id 但無 DB 列」與「id 為空」：

`api/tests/test_cr_0039_completion_gate.py:75-90`

```python
@pytest.mark.asyncio
async def test_signature_required_when_no_record_422():
    """3 照片但簽名紀錄不存在（fake wo）→ 422 SIGNATURE_REQUIRED。"""
    assert await db_module._ensure_conn()
    with pytest.raises(ApiError) as ei:
        await _gate(wo_id=str(uuid.uuid4()), signature_evidence_id="sig-1")
    assert ei.value.error_code == "SIGNATURE_REQUIRED"


@pytest.mark.asyncio
async def test_signature_required_when_id_empty_422():
    assert await db_module._ensure_conn()
    with pytest.raises(ApiError) as ei:
        await _gate(signature_evidence_id=None)
    assert ei.value.error_code == "SIGNATURE_REQUIRED"
```

另一份測試在 seed 時明文說明「光傳參數不夠」：

`api/tests/test_state_machine_optimistic_lock.py:88-96`

```python
    # 完工閘門（CR-0039）另外要求簽名紀錄實際存在（_signature_exists 查這張表），
    # 光傳 signature_evidence_id 參數不夠。
    await conn.execute(
        "INSERT INTO digital_signatures "
        "  (signer_id, signer_role, document_type, document_id, signature_method) "
        # document_type / signer_role 必須與 _signature_exists() 的查詢條件一致
        "VALUES (%s::uuid, 'customer', 'work_order', %s::uuid, 'draw')",
        (user_id, wo_id),
    )
```

---

## 觀測到的其他事實

- 簽名閘排在照片閘之後（`work_order_service.py:1552` → `:1560`）：照片不足 3 張時先收 `INSUFFICIENT_PHOTOS`，看不到 `SIGNATURE_REQUIRED`。
- `require_signature` 可由 M18 config `completion_policy` 關閉（`work_order_service.py:1536-1539`、`:1560`），關閉後整段簽名檢查跳過。
- `signature_evidence_id` 在 request schema 為必填（`api/routers/work_orders_v2.py:886`，`min_length=1`），缺欄位時先由 pydantic 回 422 `VALIDATION_ERROR`（測試 `test_onsite_completion_v2_missing_signature_422`，`api/tests/test_work_orders_onsite_v2_endpoint.py:179-190`）。
- 前端錯誤字典四站台皆有此鍵：`web/brand-portal/src/lib/apiError.ts:76`、`web/tech-portal/src/lib/apiError.ts:79`、`web/landing/src/lib/apiError.ts:76`、`web/platform-console/src/i18n/messages/zh-TW.json:67`，文案「請先完成簽名。」
- override 路徑（`is_override=True`）在簽名閘之前就 return（`work_order_service.py:1541-1549`），不執行本檢查。
