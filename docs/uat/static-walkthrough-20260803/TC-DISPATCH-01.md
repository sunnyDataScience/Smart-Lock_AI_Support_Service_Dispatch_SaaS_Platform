# TC-DISPATCH-01 — 派工媒合 API 與指派事件

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **不一致** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 7） |
| 走查時間 | 2026-08-03 17:05（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/routers/dispatch_v2.py`、`api/routers/dispatch.py`、`api/services/dispatch_service.py`、`api/services/work_order_service.py`、`api/core/event_bus.py`、`web/brand-portal/src/components/work-orders/statusGroup.ts` |
| 優先級 / 路徑類型 | P0 / happy |
| 事實結論 | 判定基準指名的 `POST /technicians:match` 與事件名 `dispatch.assigned` 在 `api`／`web`／`agent`／`SQL` 全數零命中；實際媒合端點為 `POST /tenants/{tenantId}/dispatch:auto-match`，指派後發的是 `work_order.assigned`（topic `workorder.lifecycle`），工單 DB 狀態為 `assigned`（`dispatched` 只是前端狀態分組標籤）。四項排序因子中「授權」在自動媒合為過濾條件、「可用性」以 `online_state` 判定，`levels`（等級）參數收下但不生效。 |

**TC 原文**｜前置：工單 created + 技師池有候選｜步驟：POST /technicians:match（技能/地區/授權/可用性排序）｜判定基準：回傳 top 候選；指派後發 Kafka dispatch.assigned；工單 dispatched｜happy｜P0｜FR-API-05、FR-TEC-03｜SC-05、SC-12、SC-14

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 派工小編 | `POST /technicians:match` | `CandidatesMatched` | 技能/地區/授權/可用性排序 | — | **找不到**該路徑；實際為 `dispatch:auto-match`（`routers/dispatch_v2.py:112-118`） |
| 系統 | 計算候選分數 | `CandidatesRanked` | top-N | `services/dispatch_service.py:414-478`、`:559-629` | 五因子加權 + GIS/績效 bonus + 漸進半徑，回 `max_candidates` 筆 |
| 派工小編 | 指派技師 | `dispatch.assigned` | Kafka 發布 | — | **找不到**該事件名；實際 `work_order.assigned` |
| 系統 | 發布事件 | — | topic 分派 | `services/work_order_service.py:2336-2338`、`:1007-1027` | `_publish_and_return(event_type="work_order.assigned")` → `TOPIC_WORKORDER_LIFECYCLE` |
| 系統 | 落狀態 | `WorkOrderDispatched` | 工單 → `dispatched` | `services/work_order_service.py:2264-2274` | `SET status = 'assigned'` |

---

## 走查紀錄

### 步驟 1 — 判定基準指名的端點是否存在

- **動作**：全 repo 搜尋路徑字串
- **預期**：程式碼中有 `POST /technicians:match`
- **實際**：`api`／`web` 程式碼零命中，只出現在文件與稽核紀錄

```
git grep -rn "technicians:match"
docs/4-exploration/CR-0197-brand-authorization-gate-activation.md:27
docs/system-completion-status.md:24
docs/uat/sc13-19-probe-execution-20260802.md:31
smartlock-docs/enterprise/04_SRS.md:353
smartlock-docs/enterprise/05_NFR.md:47
smartlock-docs/enterprise/07_Journey_Map.md:100
smartlock-docs/enterprise/08_User_Flow.md:202
smartlock-docs/enterprise/15_SDS.md:539
smartlock-docs/enterprise/16_API_Spec.yaml:342
```

`smartlock-docs/enterprise/04_SRS.md:353`（FR-TEC-03）記載「`POST /technicians:match`（技能/地區/品牌授權/可用性）→ 排序候選（評分/距離/工作量）」。TC 要求打此端點，程式碼中不存在。此處僅並陳，不裁定。

### 步驟 2 — 實際的媒合端點

- **動作**：讀 dispatch router
- **預期**：定位實際媒合入口
- **實際**：`POST /tenants/{tenantId}/dispatch:auto-match`（v2）與 `POST /dispatch/auto-match`（legacy，掛 Deprecation header）

`api/routers/dispatch_v2.py:112-124`

```python
@router.post(
    "/tenants/{tenantId}/dispatch:auto-match",
    operation_id="planDispatchAutoMatchV2",
    summary="依問題卡自動匹配候選技師 v2（tenant-scoped，top-N）",
    response_model=DispatchAutoMatchResponse,
    tags=["M06 Dispatch"],
)
async def plan_dispatch_auto_match_v2(
    body: DispatchAutoMatchRequest,
```

輸入為 `problem_card_id` + `urgency` + `max_candidates`（`:136-141`），非工單 id。另有 `GET /tenants/{tenantId}/dispatch:candidates`（`:48-53`）以 `work_order_id` 查候選。

### 步驟 3 — top 候選的排序因子

- **動作**：讀評分邏輯
- **預期**：技能/地區/授權/可用性四項參與排序
- **實際**：基礎分為技能 0.35 / 距離 0.25 / 評分 0.20，另疊加負載 0.10 與公平 0.10；品牌授權在 auto-match 是**過濾**、在 candidates 是**標示 + 排序前置鍵**；可用性以 `online_state` 判斷排除與 ETA

`api/services/dispatch_service.py:40-45`

```python
_W_SKILL = 0.35
_W_DISTANCE = 0.25
_W_RATING = 0.20
_W_LOAD = 0.10       # 當前在辦工單越少越高（避免塞給忙碌技師）
_W_FAIRNESS = 0.10   # 近 7 日承接越少越高（雨露均霑，工作機會分散）
_LOAD_SATURATION = 5  # 在辦 ≥5 張視為滿載（load factor → 0）
```

`api/services/dispatch_service.py:603-614`

```python
    _auth_ids = await _brand_authorized_ids(pc_brand)
    if _auth_ids is not None:
        scored = [c for c in scored if c["technician"].get("id") in _auth_ids]
    # CR-0061：GIS 距離 + 多維績效重排
    scored = await _enrich_gis_performance(scored, pc_district)
    # audit FR-API-05：補負載/公平兩因子並重排
    scored = await _enrich_workload_fairness(scored, tenant_id)
    # FR-API-05：候選池 5→10→20km 漸進擴大（近者優先，不足才擴半徑）
    scored = _apply_progressive_radius(scored)
```

可用性排除：`api/services/dispatch_service.py:391-398`

```python
def _is_excluded_by_circuit(online_state: str | None) -> bool:
    """CR-0117 S5：操作性不可派判準 —— 判 online_state（可用性域）。
    ...
    「inactive」在兩個域都不存在（死值）→ 移除；生命週期硬排除另由
    _is_dispatch_eligible 把關（兩者職責分立）。"""
    return online_state in {"on_leave", "circuit_breaker_open"}
```

### 步驟 4 — `levels`（等級）過濾參數

- **動作**：追 `levels` 參數的去向
- **預期**：參與媒合條件
- **實際**：router 收下、service 只記 warning，未傳入 `_score_rows`

`api/routers/dispatch_v2.py:59-62`

```python
    levels: list[str] | None = Query(
        default=None,
        description="⚠ 尚未實作：目前收下但不生效（TC-DISPATCH-01）。等級語意待業主定義後補。",
    ),
```

`api/services/dispatch_service.py:502-506`

```python
    if levels_filter:
        logger.warning(
            "dispatch 候選查詢帶了 levels=%s，但該過濾尚未實作（TC-DISPATCH-01）"
            "——回傳結果未依等級篩選", levels_filter,
        )
```

### 步驟 5 — 指派後的 Kafka 事件名稱

- **動作**：搜尋 `dispatch.assigned`
- **預期**：指派後發此事件
- **實際**：`api`／`web`／`agent`／`SQL` 全數零命中；命中的是 outbox push_kind 常數 `tech_dispatch_assigned`（不同語意）

```
git grep -n "dispatch\.assigned" -- api web agent SQL
（無輸出）

git grep -n "dispatch_assigned" -- api web agent SQL
api/realtime/line_push_outbox_worker.py:41:_DISPATCH_KINDS = {"tech_dispatch_assigned"}
api/services/line_push_outbox_service.py:47:    "tech_dispatch_assigned",
api/services/work_order_service.py:1695:                tenant_id=tenant_id, push_kind="tech_dispatch_assigned",
```

指派實際發出的事件：`api/services/work_order_service.py:2336-2338`

```python
    result = await _publish_and_return(
        tenant_id=tenant_id, wo_id=wo_id, event_type="work_order.assigned"
    )
```

topic 為 `TOPIC_WORKORDER_LIFECYCLE = "workorder.lifecycle"`（`api/core/event_bus.py:26`），發布點在 `api/services/work_order_service.py:1007-1027`，且為 fail-soft（`:1026-1027` 只記 log）。

TC 判定基準要求「發 Kafka dispatch.assigned」，程式碼發的是 `work_order.assigned` 且以 `event_type` 欄位塞進 `workorder.lifecycle` topic payload。此處僅並陳，不裁定。

### 步驟 6 — 工單狀態是否為 `dispatched`

- **動作**：讀指派後的 UPDATE 與狀態列舉
- **預期**：`status = 'dispatched'`
- **實際**：DB 寫入 `'assigned'`；`dispatched` 在後端 SQL schema 中不是工單狀態值，而是前端的狀態分組

`api/services/work_order_service.py:2264-2274`

```python
    _cur = await db_module._conn.execute(
        "UPDATE work_orders SET "
        "  technician_id = %s::uuid, "
        "  status = 'assigned', "
        "  dispatched_via = %s, "
        "  service_report = COALESCE(service_report, '') || E'\\n' || %s, "
        "  updated_at = NOW() "
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (technician_id, _via, note, wo_id, sorted(_ASSIGN_FROM)),
    )
```

`SQL/Schema.sql:467-469`

```sql
    status              VARCHAR(50) DEFAULT 'created',
                        -- 'created', 'assigned', 'accepted', 'in_progress',
                        -- 'completed', 'confirmed', 'cancelled'
```

`web/brand-portal/src/components/work-orders/statusGroup.ts:13`、`:20-23`

```typescript
export type StatusGroup = "pending" | "dispatched" | "in_progress" | "done" | "cancelled";
...
  accepted: "dispatched",
  scheduled: "dispatched",
  dispatching: "dispatched",
  assigned: "dispatched",
```

TC 判定基準要求「工單 dispatched」，DB 狀態為 `assigned`，前端顯示分組為 `dispatched`。此處僅並陳，不裁定。

### 步驟 7 — 執行既有測試

- **動作**：跑派工相關測試（由統籌者於本批次執行，數字沿用不重跑）
- **預期**：取得執行證據
- **實際**：第一輪無資料庫多數失敗；建立本機測試庫後重跑，八檔 52 項全數通過

第一輪（無資料庫）：

```
cd api && python -m pytest tests/test_cr_0051_dispatch_eligibility.py tests/test_cr_0030_dispatch_mode.py \
  tests/test_manual_dispatch.py tests/test_dispatch_v2_endpoint.py tests/test_dispatch_plan_v2_endpoint.py \
  tests/test_cr_0164_tech_mirror_projection.py tests/test_cr_0172_tech_dispatch_outbox.py \
  tests/test_dispatch_fairness_load.py -q --tb=no
13 failed, 39 passed in 3.87s
```

（這些檔案無 skipif 守衛，故為 failed 而非 skipped。）

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」），逐檔執行 `cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/<檔名> -q -p winloop_plugin --tb=no`：

```
test_cr_0051_dispatch_eligibility.py       8 passed in 0.38s
test_cr_0030_dispatch_mode.py              3 passed in 2.97s
test_manual_dispatch.py                   10 passed in 2.99s
test_dispatch_v2_endpoint.py               6 passed in 2.97s
test_dispatch_plan_v2_endpoint.py          8 passed in 2.96s
test_cr_0164_tech_mirror_projection.py     5 passed in 0.46s
test_cr_0172_tech_dispatch_outbox.py       5 passed in 0.40s
test_dispatch_fairness_load.py             7 passed in 0.40s
```

八檔 52 項全數通過。這些測試呼叫的路徑為 `/api/v1/dispatch/auto-match`、`/api/v1/dispatch/candidates`（`test_dispatch_v2_endpoint.py`）與 `/api/v1/dispatch/assign`、`/api/v1/work-orders/{wo_id}/assign`（`test_manual_dispatch.py`）；`api/tests/` 中找不到針對 `POST /technicians:match` 或 `dispatch.assigned` 的測試（兩者皆不存在），實跑亦無對應案例被執行。

---

## 觀測到的其他事實

- `smartlock-docs/enterprise/04_SRS.md:296`（FR-API-05）記載「候選池（5→10→20km 擴大）→ 5 因子權重（distance+skill+rating+load+fairness）」；程式碼 `_PROGRESSIVE_RADII_KM = [5.0, 10.0, 20.0]`、`_MIN_DISPATCH_POOL = 3`（`dispatch_service.py:88-89`）與該敘述同值，但漸進半徑只在 `auto_match_dispatch` 呼叫（`:614`），`list_dispatch_candidates` 未呼叫。
- 指派端點另有兩條：`POST /tenants/{tenantId}/work-orders/{id}:assign`（`routers/work_orders_v2.py:498-530`）與 `POST /tenants/{tenantId}/dispatch:plan`（`routers/dispatch_v2.py:147-179`）。
- `docs/system-completion-status.md:24` 已記載此組命名落差為「命名/契約 drift（`/technicians:match`→`/dispatch:auto-match`、`dispatch.assigned`→折進 `workorder.lifecycle`）」，並列為「待業主裁決」。
