# TC-ONSITE-01 — 到場 GPS 簽到與 door-check 照片存證

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試，到場／door-check 相關 11 項全數通過（見步驟 6） |
| 走查時間 | 2026-08-03 20:10（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/routers/work_orders_v2.py:897-1035`、`api/services/work_order_service.py:915-923`、`:3211-3354`、`api/services/media_service.py:31-41`、`:142-260`、`api/routers/media_v2.py:42-92`、`SQL/Schema_media.sql:18-58`、`SQL/migrations/078-media-completion-signature.sql`、`web/tech-portal/src/app/my-orders/[id]/page.tsx:250-294`、`web/tech-portal/src/app/my-orders/[id]/door-check/page.tsx:94-172` |
| 優先級 / 路徑類型 | P0 / happy |
| 事實結論 | 到場端點 `POST /tenants/{t}/work-orders/{wo}/onsite/arrival` 收 GPS 並寫 `work_order_events` 的 `event_type='arrival'`＋補 `started_at`，door-check 照片經 `POST /tenants/{t}/media` 以 `purpose` 欄位落 `media_files`（DB CHECK 九值），此兩項與 TC 相符。TC 判定基準的「工單 `on_site`」在程式碼零命中——狀態機七值（`_WO_TRANSITIONS`，`work_order_service.py:915-923`）不含 `on_site`，`record_arrival` 也不改 `status`，只補 `started_at`。 |

**TC 原文**｜前置：師傅到場｜步驟：GPS 簽到 + 上傳 door-check 照｜判定基準：工單 on_site；evidence 入庫帶 purpose 分類｜需求：FR-API-08｜旅程：SC-06

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 技師 | 按「已到達現場」 | `GpsAcquired` | 取瀏覽器定位 | `my-orders/[id]/page.tsx:263-278` | `navigator.geolocation.getCurrentPosition`，失敗二次確認後送無座標 |
| 技師 | POST `/onsite/arrival` | `Arrived` | 狀態限 `_SUBFLOW_FROM` | `work_order_service.py:3252-3284` | 寫 `arrival` 事件＋`started_at = COALESCE(started_at, NOW())`；**不改 `status`** |
| 系統 | 推工單狀態 | `WorkOrderArrived` | WS 推播 | `work_order_service.py:3279-3281` | `_publish_and_return(event_type="work_order.arrived")` |
| 技師 | 上傳門檢照 | `EvidenceStored` | purpose 分類 | `media_service.py:147-254` | `purpose not in _ALLOWED_PURPOSES` → 422；落 `media_files.purpose` |
| 技師 | POST `/door-check` | `DoorCheckSubmitted` | 須有 arrival 前置 | `work_order_service.py:3332-3345` | 無 `arrival` 事件 → 409 `STATE_CONFLICT` |
| 系統 | 轉 `on_site` 狀態 | `WorkOrderOnSite` | — | — | **找不到**；狀態機無 `on_site` 值 |

---

## 走查紀錄

### 步驟 1 — 到場端點與 GPS 欄位

- **動作**：讀 `onsiteArrival` router
- **預期**：接受 GPS 與到場時間
- **實際**：一致；`gps` 為 optional

`api/routers/work_orders_v2.py:852-870`

```python
class _ArrivalGps(BaseModel):
    lat: float = Field(..., description="緯度")
    lng: float = Field(..., description="經度")
    accuracy_m: float | None = Field(default=None, description="GPS 精度（公尺）")


class _ArrivalEventRequest(BaseModel):
    """FR-0006 技師到場事件（GPS + timestamp evidence）。
    ...
    """

    arrived_at: str = Field(..., description="到場時間，ISO 8601 格式")
    # UAT P2-6：gps 改 optional——拒絕定位權限的技師仍可回報到場(前端二次確認
    # 後送無座標請求，事件 payload 標記 no_gps)；service 層本就接受 gps=None。
    gps: _ArrivalGps | None = Field(default=None, description="GPS 到場座標（無定位時可省略）")
```

`api/routers/work_orders_v2.py:897-935`

```python
@router.post(
    "/tenants/{tenantId}/work-orders/{woId}/onsite/arrival",
    operation_id="onsiteArrival",
    summary="技師到場回報 v2（tenant-scoped，FR-0006 GPS + timestamp；idempotent）",
    status_code=201,
    tags=["M07 Onsite"],
)
async def onsite_arrival_v2(
    ...
    user: CurrentUser = Depends(role_required(*TECH_ACTION_ROLES)),
    idem: IdempotencyContext | None = Depends(idempotency_guard),
) -> dict:
    ...
    order = await work_order_service.record_arrival(
```

### 步驟 2 — 到場對工單狀態的實際影響

- **動作**：讀 `record_arrival`
- **預期**：工單轉 `on_site`
- **實際**：只寫 `started_at` 與 `arrival` 事件，`status` 不變

`api/services/work_order_service.py:3252-3284`

```python
    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _SUBFLOW_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot record ARRIVAL in status '{current}'; expected one of {sorted(_SUBFLOW_FROM)}",
            409,
        )
    # 補到場時點（started_at；COALESCE 不覆蓋既有，arrival KPI 用）
    _cur = await db_module._conn.execute(
        "UPDATE work_orders SET started_at = COALESCE(started_at, NOW()), updated_at = NOW() "
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (wo_id, sorted(_SUBFLOW_FROM)),
    )
    ...
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="arrival",
        payload={"arrived_at": arrived_at, "gps": g, "gps_proof": gps_proof},
    )
```

`_SUBFLOW_FROM` 與狀態機七值：

`api/services/work_order_service.py:915-923`、`:2836`

```python
_WO_TRANSITIONS: dict[str, set[str]] = {
    "created":     {"assigned", "accepted", "cancelled"},
    "assigned":    {"assigned", "accepted", "created", "cancelled"},
    "accepted":    {"assigned", "in_progress", "completed", "cancelled"},
    "in_progress": {"assigned", "completed", "cancelled"},
    "completed":   {"confirmed"},
    "confirmed":   set(),
    "cancelled":   set(),
}
```

```python
_SUBFLOW_FROM = {"assigned", "accepted", "in_progress"}
```

`on_site` 在 `api` / `SQL` / `web` 的搜尋結果：

```
$ grep -rn "on_site" --include=*.py --include=*.sql --include=*.ts --include=*.tsx --include=*.yaml api SQL web
api/services/requote_service.py:22:# 工單狀態機無 on_site(ADR-027 語彙)——現場作業對映 in_progress
```

唯一命中為註解，非狀態值。

- TC 判定基準寫「工單 `on_site`」
- 程式碼狀態機無此值，到場後 `status` 維持 `assigned` / `accepted` / `in_progress`（`work_order_service.py:3264-3267`）
- API 回應以 `state: "arrived"` 字面回傳（`work_orders_v2.py:927-931`），該字串不寫入 DB

此處僅並陳，不裁定。

### 步驟 3 — GPS 到場 proof 的實際計算條件

- **動作**：讀 `compute_arrival_gps_proof` 與前端送出的欄位
- **預期**：GPS 簽到可判定是否在服務地址附近
- **實際**：需要 `ref_lat` / `ref_lng` 參考座標；前端未帶

`api/services/work_order_service.py:3211-3234`

```python
def compute_arrival_gps_proof(
    ref_lat: float | None,
    ref_lng: float | None,
    gps_lat: float | None,
    gps_lng: float | None,
    tolerance_m: float = _ARRIVAL_GPS_TOLERANCE_M_DEFAULT,
) -> dict | None:
    """到場 GPS proof：回 {distance_m, tolerance_m, within_tolerance}；座標缺漏 → None。"""
    if None in (ref_lat, ref_lng, gps_lat, gps_lng):
        return None
```

前端送出的 body：

`web/tech-portal/src/app/my-orders/[id]/page.tsx:283-289`

```tsx
      await api.post(
        tenantPath(`/work-orders/${encodeURIComponent(wo.id)}/onsite/arrival`),
        gps
          ? { arrived_at: new Date().toISOString(), gps }
          : { arrived_at: new Date().toISOString() },
      );
```

`gps` 物件只含 `lat` / `lng`（`:270-272`），無 `ref_lat` / `ref_lng`，故此路徑 `gps_proof` 恆為 `None`。

### 步驟 4 — door-check 照片的 purpose 分類

- **動作**：讀上傳端點與 DB CHECK
- **預期**：evidence 入庫帶 purpose 分類
- **實際**：一致

`api/routers/media_v2.py:42-52`

```python
_PURPOSE = Literal[
    "door_check_before",
    "door_check_after",
    "completion_before",
    "completion_during",
    "completion_after",
    "completion_signature",
    "dispute_evidence_customer",
    "dispute_evidence_technician",
    "other",
]
```

`api/services/media_service.py:147-151`

```python
    if purpose not in _ALLOWED_PURPOSES:
        raise ApiError(
            "VALIDATION_ERROR",
            f"purpose must be one of {sorted(_ALLOWED_PURPOSES)}",
            422,
        )
```

DB 端 CHECK：`SQL/Schema_media.sql:24-35`

```sql
    purpose             VARCHAR(40) NOT NULL CHECK (
                            purpose IN (
                                'door_check_before',
                                'door_check_after',
                                'completion_before',
                                'completion_during',  -- CR-0054 施工中拓孔結構照
                                'completion_after',
                                'dispute_evidence_customer',
                                'dispute_evidence_technician',
                                'other'
                            )
                        ),
```

`completion_signature` 由 `SQL/migrations/078-media-completion-signature.sql:26` 以 DROP+ADD 補入 CHECK。

前端門檢頁上傳時帶入 purpose：

`web/tech-portal/src/app/my-orders/[id]/door-check/page.tsx:102-112`

```tsx
      const fd = new FormData();
      fd.append("file", file);
      fd.append(
        "purpose",
        section === "before" ? "door_check_before" : "door_check_after",
      );
      fd.append("work_order_id", id);
      const res = await api.upload<{
```

`media_files.work_order_id` 為 FK（`SQL/Schema_media.sql:22`），照片與工單有外鍵關聯。

### 步驟 5 — door-check 的 arrival 前置閘

- **動作**：讀 `submit_door_check_v2`
- **預期**：到場後才能提門檢
- **實際**：一致，缺 `arrival` 事件回 409

`api/services/work_order_service.py:3332-3345`

```python
    cur = await db_module._conn.execute(
        "SELECT 1 FROM work_order_events "
        "WHERE work_order_id = %s::uuid "
        "  AND tenant_id = %s::uuid "
        "  AND event_type = 'arrival' "
        "LIMIT 1",
        (wo_id, tenant_id),
    )
    if not await cur.fetchone():
        raise ApiError(
            "STATE_CONFLICT",
            "door-check requires prior arrival event (CR-0007 HD-01)",
            409,
        )
```

門檢送出時前端另有「檢核全勾＋前後照各至少 1 張」的前端條件：

`web/tech-portal/src/app/my-orders/[id]/door-check/page.tsx:137-140`

```tsx
  const allChecked = checked.size === CHECKLIST_KEYS.length;
  const hasBefore = photos.some((p) => p.section === "before");
  const hasAfter = photos.some((p) => p.section === "after");
  const canSubmit = allChecked && hasBefore && hasAfter && !submitting;
```

後端 `_DoorCheckSubmitRequest`（`work_orders_v2.py:1000-1006`）的 `photos_before` / `photos_after` 皆為 `default_factory=list`，無最少張數約束。

### 步驟 6 — 執行既有測試

- **動作**：跑到場／門檢相關測試
- **預期**：取得執行證據
- **實際**：11 項全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  tests/test_work_orders_onsite_v2_endpoint.py tests/test_cr_0053_arrival_doorcheck.py \
  -q -p winloop_plugin --tb=line
11 passed
```

其中 `test_cr_0053_arrival_doorcheck.py::test_doorcheck_blocked_before_arrival_then_passes_after`（`:46`）覆蓋 409 前置閘與 `actual_arrival` 落值（`:59`）：

`api/tests/test_cr_0053_arrival_doorcheck.py:55-59`

```python
        # 到場：寫 arrival 事件 + 補 started_at（→ actual_arrival 出現在 dict）
        ...
        assert order.get("actual_arrival") is not None  # CR-0053 bug2：started_at 已落
```

該批測試無任何斷言檢查 `status == 'on_site'`。

---

## 觀測到的其他事實

- `actual_arrival` 非獨立欄位，是 `started_at` 的輸出別名：`api/services/work_order_service.py:9` 註記「`started_at` → `actual_arrival`（best-effort proxy；DB 沒獨立 arrival 欄位）」，映射在 `:104`。
- `smartlock-docs/enterprise/04_SRS.md:299`（FR-API-08）將本項的前置寫為「WO in_progress」，與 TC 判定基準的 `on_site` 用字不同。
- 到場端點 RBAC 為 `TECH_ACTION_ROLES`（`api/core/deps.py:304` = `BACKOFFICE_ROLES + ("technician",)`），後台角色亦可代打到場回報。
- `onsite/arrival` 掛 `idempotency_guard`（`work_orders_v2.py:905`），`test_work_orders_onsite_v2_endpoint.py:79` 驗缺 `Idempotency-Key` 的行為。
