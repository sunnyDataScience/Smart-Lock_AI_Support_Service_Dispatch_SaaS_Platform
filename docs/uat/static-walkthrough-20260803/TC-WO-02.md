# TC-WO-02 — 問題卡缺服務地址時轉工單

> ## 🔄 判定更正（2026-08-05 回程式碼查證）
>
> **原判定「部分實作」→ 更正為「一致」。以下原文保留未改動。**
>
> 兩條判定基準全數落地，差異只在 error_code 字面：實作回 422 `ADDRESS_REQUIRED_FOR_CONVERT`（`api/services/work_order_service.py:593-599`），TC 寫的是 `ADDRESS_REQUIRED`。正典＝`api/openapi.yaml:5370-5371` 的 enum，**TC 該改的是自己的字面**。
> 前端亦已落地：轉工單彈窗 `canSubmit = address.trim().length > 0 && !pending`（`web/brand-portal/src/app/problem-cards/[id]/page.tsx:1323`）＋必填星號文案（:1343-1352），四站錯誤字典皆有對映。
> UAT fixture 提醒：缺地址的問題卡必須先備妥 accepted 報價，否則會先撞報價 gate 425 `QUOTE_NOT_CUSTOMER_CONFIRMED`（`work_order_service.py:586-587`）而拿不到 422；既有測試就是這樣做的（`api/tests/test_pc_convert_to_wo.py:204` `seed_accepted_quote`）。
>
> 更正依據：對本文件引用的每個 `檔案:行號` 逐一開檔覆核、對宣稱「零命中」的識別碼
> 以多種命名寫法重跑 grep。走查基準 commit 與查證當下 HEAD 之間，
> `api/` `agent/` `web/` `SQL/` 原始碼零差異，故原引用仍然有效。
>
> **此更正不需要改動任何 code。**

---

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 5） |
| 走查時間 | 2026-08-03 17:05（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/services/work_order_service.py:589-599`、`api/services/problem_card_service.py:610-671`、`api/routers/problem_cards_v2.py:397-441`、`web/brand-portal/src/app/problem-cards/[id]/page.tsx:1319-1360`、`web/brand-portal/src/lib/apiError.ts:79` |
| 優先級 / 路徑類型 | P0 / 例外 |
| 事實結論 | 後端確有「無地址回 422」的檢查，但常數字串是 `ADDRESS_REQUIRED_FOR_CONVERT` 而非 TC 寫的 `ADDRESS_REQUIRED`；前端轉工單彈窗以 `canSubmit` 強制地址非空。另有兩道更早的閘門（完整度 422、報價 gate 425）會在地址檢查之前先觸發。 |

**TC 原文**｜前置：問題卡缺服務地址｜步驟：轉工單｜判定基準：422 ADDRESS_REQUIRED；前端強制補地址｜例外｜P0｜FR-API-04｜SC-04

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客服 | 於前端按「開單」 | `ConvertDialogOpened` | 地址必填 | `problem-cards/[id]/page.tsx:1323` | `canSubmit = address.trim().length > 0 && !pending` |
| 客服 | POST convert-to-work-order（無地址） | `ConvertRejected(422)` | 缺地址不可開單 | `work_order_service.py:593-599` | 422 `ADDRESS_REQUIRED_FOR_CONVERT` |
| 系統 | convert 前完整度檢查 | `ConvertRejected(422)` | 完整度 < 門檻 | `problem_card_service.py:666-671` | 422 `INCOMPLETE_PROBLEM_CARD`（key_fields 含 `customer_address`） |
| 系統 | convert 前報價 gate | `ConvertRejected(425)` | 非急件需 accepted 報價 | `work_order_service.py:586-587` | 425 `QUOTE_NOT_CUSTOMER_CONFIRMED` |
| 前端 | 收到 422 | `ErrorMessageShown` | 中文訊息映射 | `web/brand-portal/src/lib/apiError.ts:79` | 「請先填寫服務地址才能轉工單。」 |

---

## 走查紀錄

### 步驟 1 — 後端缺地址的 422

- **動作**：讀 convert 的地址解析段
- **預期**：無地址回 422 `ADDRESS_REQUIRED`
- **實際**：有 422，但 error_code 字串為 `ADDRESS_REQUIRED_FOR_CONVERT`

`api/services/work_order_service.py:589-599`

```python
    # 3. Resolve customer info（caller override > PC location > user profile fallback）
    #    UAT P2-8：pc.location 為本案蒐集的服務地址（L3 補址欄），比 user profile
    #    的通用地址更準——caller 未帶時優先取卡上地址，避免有卡址仍 422。
    #    CR-0165 F6a：專用碼取代泛用 VALIDATION_ERROR（比照結案 ADDRESS_REQUIRED_FOR_CLOSE）
    final_address = customer_address or pc_location or user_address
    if not final_address:
        raise ApiError(
            "ADDRESS_REQUIRED_FOR_CONVERT",
            "開單前須有服務地址——客戶資料無地址時請於轉工單時填寫",
            422,
        )
```

- TC 判定基準寫 error code `ADDRESS_REQUIRED`
- 程式碼實際字串為 `ADDRESS_REQUIRED_FOR_CONVERT`（`work_order_service.py:596`）
- 全 repo 搜 `"ADDRESS_REQUIRED"` 作為獨立 error_code 常數：**找不到**；只存在 `ADDRESS_REQUIRED_FOR_CONVERT` 與 `ADDRESS_REQUIRED_FOR_CLOSE` 兩個字串（`web/brand-portal/src/lib/apiError.ts:78-79`）

此處僅並陳，不裁定。

### 步驟 2 — 觸發順序：地址檢查不是第一道閘門

- **動作**：追 router → service 的檢查順序
- **預期**：缺地址即回 422 `ADDRESS_REQUIRED*`
- **實際**：地址檢查排在第三順位，前面兩道閘門會先擋

`api/routers/problem_cards_v2.py:421-436`

```python
    # CR-0042 BR-M03：轉 WO 前完整度 gate（<門檻 → 422，主管帶 reason 可 override）
    await problem_card_service.assert_completeness(
        tenant_id=tenantId,
        pc_id=id,
        customer_address=body.customer_address if body else None,
        actor_role=user.role,
        override_reason=override_reason,
    )
    wo, created = await work_order_service.create_from_problem_card(
```

完整度 gate 的 key_fields 內含 `customer_address`，其 fallback 只讀 `u.address`：

`api/services/problem_card_service.py:651-671`

```python
    values = {
        "brand": row[0],
        "model": row[1],
        "symptom": "x" if symptom_ok else None,
        "urgency": row[4],
        "customer_address": customer_address or row[5],
    }
    missing = [f for f in key_fields if not _field_filled(values.get(f))]
    score = round((len(key_fields) - len(missing)) / max(len(key_fields), 1), 2)
    ...
    if score < min_c and not overridden:
        raise ApiError(
            "INCOMPLETE_PROBLEM_CARD",
            f"問題卡完整度 {score} < {min_c}（缺：{', '.join(missing) or '—'}）；補齊欄位或主管 override",
            422,
```

`row[5]` 來源為 `u.address`（`problem_card_service.py:640`），未含 `pc.location`；而 `create_from_problem_card` 的 fallback 為 `customer_address or pc_location or user_address`（`work_order_service.py:593`）。兩處 fallback 來源不同。

第二道閘門為報價 gate，位於地址檢查之前：

`api/services/work_order_service.py:584-587`

```python
    from services import quote_engine_service as _qe

    if pc_emergency_class is None:
        await _qe.assert_pc_quote_confirmed(tenant_id=tenant_id, problem_card_id=pc_id)
```

即「非急件、缺地址、且無 accepted 報價」的請求會先收 425 `QUOTE_NOT_CUSTOMER_CONFIRMED`（`quote_engine_service.py:177-183`），而非 422。

### 步驟 3 — 前端強制補地址

- **動作**：讀轉工單彈窗
- **預期**：地址為必填，空值不可送出
- **實際**：一致

`web/brand-portal/src/app/problem-cards/[id]/page.tsx:1319-1332`

```tsx
  const [address, setAddress] = useState(initialAddress ?? "");
  const [name, setName] = useState(initialName ?? "");
  const [phone, setPhone] = useState(initialPhone ?? "");
  const [overrideReason, setOverrideReason] = useState("");
  const canSubmit = address.trim().length > 0 && !pending;
  const submit = (override?: string) =>
    onSubmit(
      {
        customer_address: address.trim(),
```

彈窗文案明示必填：

`web/brand-portal/src/app/problem-cards/[id]/page.tsx:1343-1352`

```tsx
        <p className="mb-3 text-[13px] text-[var(--text-secondary)]">
          請填寫服務地址後開單（AI 草擬卡未含地址，需客服確認）。地址為必填，缺地址無法派工。
        </p>
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-[13px] font-medium text-[var(--text-primary)]">
              服務地址 <span className="text-[var(--error)]">*</span>
            </span>
```

### 步驟 4 — 錯誤碼在前端的中文映射

- **動作**：查 apiError 字典
- **預期**：422 有對應的使用者訊息
- **實際**：一致（鍵名為 `ADDRESS_REQUIRED_FOR_CONVERT`）

`web/brand-portal/src/lib/apiError.ts:78-79`

```ts
  ADDRESS_REQUIRED_FOR_CLOSE: "請先填寫地址才能結案。",
  ADDRESS_REQUIRED_FOR_CONVERT: "請先填寫服務地址才能轉工單。",
```

字典中**找不到** `ADDRESS_REQUIRED` 鍵。

### 步驟 5 — 執行既有測試

- **動作**：跑轉工單測試
- **預期**：取得執行證據
- **實際**：第一輪無資料庫全數失敗；建立本機測試庫後重跑，`test_pc_convert_to_wo.py` 7 項全數通過，同批三檔共 21 項通過、3 項失敗

第一輪（無資料庫）：

```
cd api && python -m pytest tests/test_pc_convert_to_wo.py tests/test_cr_0095_quote_line_approval.py tests/test_cr_0144_requote_channel.py -q --tb=no -rf

FAILED tests/test_cr_0095_quote_line_approval.py::test_customer_respond_accept_twice_idempotent
FAILED tests/test_cr_0095_quote_line_approval.py::test_customer_respond_conflict_codes
FAILED tests/test_cr_0144_requote_channel.py::test_command_creates_quote_v_plus_1_and_replays
...
21 failed, 3 passed in 3.58s
```

錯誤原文為 `ERROR api.db:db.py:48 環境變數 POSTGRES_URI 未設定`。

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_pc_convert_to_wo.py -q -p winloop_plugin --tb=no
7 passed in 3.33s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0095_quote_line_approval.py -q -p winloop_plugin --tb=no
3 failed, 9 passed in 3.68s

cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0144_requote_channel.py -q -p winloop_plugin --tb=no
5 passed in 3.07s
```

轉工單路徑的 `test_pc_convert_to_wo.py` 7 項全通過；3 項失敗全部集中在 `test_cr_0095_quote_line_approval.py` 的客戶回覆路徑，與轉工單地址檢查無關（該三項的失敗點見 TC-QUOTE-08 步驟 5）。

---

## 觀測到的其他事實

- convert 端點掛有 `idempotency_guard`（`api/routers/problem_cards_v2.py:413`），但 422/425 屬 handler 拋錯路徑，錯誤回應不入冪等快取（`api/core/idempotency.py:138-151`）。
- 前端 convert 彈窗另有 override 欄位（`overrideReason`），對應 router 的 `override_reason` query 參數（`problem_cards_v2.py:408-411`），僅作用於完整度 gate，不影響 `ADDRESS_REQUIRED_FOR_CONVERT`。
