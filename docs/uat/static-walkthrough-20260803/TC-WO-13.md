# TC-WO-13 — 照片附加規則與轉工單欄位帶入

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務；轉工單測試因無資料庫而失敗（見步驟 5） |
| 走查時間 | 2026-08-03 16:28（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/services/problem_card_service.py:891-933`、`api/services/work_order_service.py:502-643`、`api/routers/problem_cards_v2.py:413`、`:439-440` |
| 優先級 / 路徑類型 | P0 / happy |
| 事實結論 | 三條判定基準皆有對應實作：照片查詢帶 24h 窗與 LIMIT 5 並以 `reversed()` 轉為時間正序、合併為 append-only 聯集；轉工單的 SELECT 與 INSERT 皆含 serial；重送有四層去重（前置查既有單、DB partial UNIQUE、狀態檢查、HTTP 冪等鍵）。 |

**TC 原文**｜前置：問題卡含姓名、電話、地址、品牌、型號、serial；同對話近 24h 有 7 張照片、窗外 1 張｜步驟：AI 建卡後由客服轉工單並重送一次｜判定基準：問題卡只附同對話近 24h 最多 5 張且時間正序、append-only；轉工單完整帶入客戶與設備欄位含 serial；重送不產生第二張工單｜需求：FR-API-01｜旅程：SC-02

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 系統 | 反查對話照片 | `MediaAttached(≤5)` | 近 24h、最多 5 張、時間正序 | `problem_card_service.py:898-909` | `INTERVAL '24 hours'` + `LIMIT %s`（預設 5）+ `reversed(rows)` |
| 系統 | 合併照片 | `MediaMerged` | append-only 不覆蓋 | `problem_card_service.py:915-931` | 聯集後才 UPDATE |
| 客服 | 轉工單 | `WorkOrderCreated` | 客戶與設備欄位含 serial | `work_order_service.py:529-538`、`:614-629` | SELECT 與 INSERT 皆含 serial |
| 客服 | 重送同一請求 | （不應發生）`WorkOrderCreated` ×2 | 不產生第二張 | `work_order_service.py:569-579`、`:631-641` | 前置查既有單回傳；UniqueViolation 兜底 |

---

## 走查紀錄

### 步驟 1 — 照片的 24h 窗、5 張上限與排序

- **動作**：讀照片反查函式
- **預期**：三條規則齊備
- **實際**：一致

`api/services/problem_card_service.py:891-912`

```python
async def _conversation_media_urls(conv_id: str, limit: int = 5) -> list[str]:
    """CR-0179：反查該對話近 24h 的照片 URL（時間正序）。
    ...
    session 終身同 conv → 必須加時間窗防陳年舊照；
    fail-soft：查詢失敗回 []（照片是加值，建卡是主流程）。
    """
    try:
        cur = await db_module._conn.execute(
            "SELECT COALESCE(metadata->>'image_url', metadata->>'media_url') AS u "
            "FROM messages "
            "WHERE conversation_id = %s::uuid "
            "  AND COALESCE(metadata->>'image_url', metadata->>'media_url') IS NOT NULL "
            "  AND created_at > NOW() - INTERVAL '24 hours' "
            "ORDER BY created_at DESC LIMIT %s",
            (conv_id, limit),
        )
        rows = await cur.fetchall()
        return [r[0] for r in reversed(rows) if r[0]]
```

查詢以 `DESC` 取最新 5 筆，再由 `reversed()` 轉為時間正序回傳；窗外照片不進結果集。

### 步驟 2 — append-only

- **動作**：讀合併函式
- **預期**：不覆蓋既有照片
- **實際**：一致

`api/services/problem_card_service.py:915-931`

```python
async def _merge_media_urls(pc_id: str, new_urls: list[str]) -> None:
    """CR-0179：media_urls append-only 聯集（沿 TI-M03-07——不覆蓋客服手附證據照）。"""
    try:
        mcur = await db_module._conn.execute(
            "SELECT media_urls FROM problem_cards WHERE id = %s::uuid", (pc_id,)
        )
        mrow = await mcur.fetchone()
        existing_media = mrow[0] if mrow and isinstance(mrow[0], list) else []
        merged: list[str] = list(existing_media)
        for u in new_urls:
            if u not in merged:
                merged.append(u)
```

呼叫點：新建卡時直接寫入 INSERT（`problem_card_service.py:1094-1095`）；併入既有卡時走合併（`:1064-1066`）。

### 步驟 3 — 轉工單的欄位帶入（含 serial）

- **動作**：讀 SELECT 與 INSERT
- **預期**：客戶與設備欄位齊備，serial 有帶
- **實際**：一致

`api/services/work_order_service.py:529-538`

```python
"       pc.brand, pc.model, pc.category, pc.media_urls, pc.emergency_class, "
"       pc.location, pc.contact_phone, pc.extracted_fields, "
# CR-0178 UAT-0720-09 續 2：序號一併帶入（原 CR-0026 只複製 brand/model/媒體，獨漏 serial）
"       pc.serial "
```

`api/services/work_order_service.py:614-629`

```python
"   customer_name, customer_phone, customer_address, created_by, document_number, "
"   brand, model, problem_type, service_category, photos, tenant_id, quote_gate_applied, "
"   serial_number) "
...
(pc_id, priority, final_name, final_phone, final_address, created_by, final_address,
 pc_brand, pc_model, pc_category, _map_service_category(pc_category),
 json.dumps(pc_media, ...) if pc_media else None, tenant_id,
 pc_serial or None),
```

姓名／電話／地址的取值優先序在 `work_order_service.py:554-601`（caller 傳入 > `pc.extracted_fields`／`contact_phone`／`location` > users profile）；無地址時回 422 `ADDRESS_REQUIRED_FOR_CONVERT`（`:594-599`）。

### 步驟 4 — 重送不產生第二張工單

- **動作**：找去重機制
- **預期**：重送回傳既有工單
- **實際**：四層

1. 前置查既有工單 → 直接回傳（`work_order_service.py:569-579`，回 `created=False`）
2. DB partial UNIQUE 兜底：捕 `UniqueViolation`（constraint `uq_work_orders_problem_card`）後回既有單（`:631-641`）
3. 狀態檢查：`pc_status != 'confirmed'` → 409 `STATE_CONFLICT`（`:562-567`）
4. HTTP 冪等鍵：`api/routers/problem_cards_v2.py:413` `idem: IdempotencyContext = Depends(idempotency_guard)`，`:439-440` 存回應；`:437` 依 `created` 決定 201／200

### 步驟 5 — 執行既有測試

- **動作**：跑轉工單測試
- **預期**：取得執行證據
- **實際**：7 項全數失敗，原因為無資料庫

```
cd api && python -m pytest tests/test_pc_convert_to_wo.py ... -q --tb=no -rf

FAILED tests/test_pc_convert_to_wo.py::test_convert_happy_path - AttributeErr...
FAILED tests/test_pc_convert_to_wo.py::test_convert_idempotent - AttributeErr...
FAILED tests/test_pc_convert_to_wo.py::test_convert_draft_rejected - Attribut...
...
22 failed, 25 passed in 5.36s
```

同批 `test_cr_0119_line_photo_ingest.py` 的 4 項照片測試亦因無資料庫失敗。

---

## 觀測到的其他事實

- `agent/tests/` 與 `api/tests/` 中找不到針對「最多 5 張／24h 窗／時間正序」的行為測試，也找不到「轉工單帶 serial」的端到端測試（`api/tests/test_cr_0026_wo_fields.py:43,61` 測的是 serializer 映射，非 convert 路徑）。
- `serial` 欄位定義於 `SQL/migrations/093-pc-dual-gate.sql:35`，工單側欄位為 `work_orders.serial_number`。
- 照片反查與合併皆為 fail-soft：查詢或合併失敗只記 warning，不擋建卡（`problem_card_service.py:910-912`、`:932-933`）。
