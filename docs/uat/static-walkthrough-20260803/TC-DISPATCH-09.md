# TC-DISPATCH-09 — 空候選池、不合格技師、急件規則與重試不重複

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 6） |
| 走查時間 | 2026-08-03 18:48（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/services/dispatch_service.py`、`api/services/work_order_service.py`、`api/services/line_push_outbox_service.py`、`api/core/idempotency.py`、`api/routers/dispatch_v2.py` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |
| 事實結論 | 四項判定基準中：「不合格者永不入選」有實作（生命週期硬排除 + 可用性排除 + 授權過濾）；「急件規則」有實作（`urgency=='emergency'` → score ×1.05）；「空池 → dispatch_pending + alert」**找不到**（`dispatch_pending` 全 repo 零命中，空池回 `{"candidates": []}` 無 alert）；「重試不重複指派或通知」為部分——指派有 `Idempotency-Key` guard 與樂觀 UPDATE 條件，但派工推播 kind `tech_dispatch_assigned` 不在 outbox 嚴格去重集合內。 |

**TC 原文**｜前置：可控候選池、急件規則、通知與技師 availability fixture｜步驟：先令候選池為空，再加入不合格技師、合格技師；模擬第一次通知失敗後重試｜判定基準：空池只能進 dispatch_pending 並 alert；不合格者永不入選；合格者出現後按急件規則媒合；重試不重複指派或通知｜failure＋recovery｜P0｜FR-API-05｜SC-05、SC-14

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 系統 | 媒合但候選池為空 | `DispatchPending` | 進 `dispatch_pending` + alert | — | **找不到**；回 `{"candidates": []}`（`dispatch_service.py:617-629`） |
| 系統 | 過濾不合格技師 | `CandidateExcluded` | 永不入選 | `dispatch_service.py:430-433` | 生命週期 4 狀態硬排除 + `online_state` 2 值排除 |
| 系統 | 急件媒合 | `EmergencyMatched` | 急件覆寫權重 | `dispatch_service.py:616-619` | score ×1.05（上限 1.0），權重本身不變 |
| 派工小編 | 重送同一次指派 | `IdempotentReplay` | 不重複指派 | `core/idempotency.py:285-308`、`work_order_service.py:2271-2274` | `Idempotency-Key` 回放 + `WHERE status = ANY(...)` 樂觀條件 |
| 系統 | 通知重試 | `NotificationDeduped` | 不重複通知 | `line_push_outbox_service.py:58-64` | `tech_dispatch_assigned` 不在 `_STRICT_DEDUP_KINDS` |

---

## 走查紀錄

### 步驟 1 — 空候選池的處置

- **動作**：搜尋 `dispatch_pending`；讀空池分支
- **預期**：進 `dispatch_pending` 狀態並發 alert
- **實際**：字串全 repo 零命中；空池只是回空陣列

```
git grep -rn "dispatch_pending" -- api web SQL agent
（無輸出）
```

`api/services/dispatch_service.py:616-629`

```python
    boost = 1.05 if urgency == "emergency" else 1.0
    candidates: list[dict] = []
    for c in scored[:max_candidates]:
        s_norm = min(1.0, (c["score"] / 100.0) * boost)
        t = c["technician"]
        candidates.append({
            "technician_id": t["id"],
            "technician_name": t.get("name") or None,
            "score": round(s_norm, 4),
            "distance_km": c.get("distance_km"),
            "eta_minutes": c.get("availability_eta_minutes"),
            "rating": t.get("rating"),
        })
    return {"candidates": candidates}
```

`scored` 為空時迴圈不執行，函式回 `{"candidates": []}`；`auto_match_dispatch` 全函式（`:559-629`）無 `raise`、無 alert、無狀態變更。`_apply_progressive_radius`（`:92-117`）在 `not candidates` 時原樣回傳。

`smartlock-docs/enterprise/04_SRS.md:296`（FR-API-05）記載「候選池空 → dispatch_pending + alert」。程式碼無對應實作。此處僅並陳，不裁定。

### 步驟 2 — 不合格技師的排除

- **動作**：讀候選過濾
- **預期**：不合格者永不入選
- **實際**：三道排除，其中生命週期不受參數影響

`api/services/dispatch_service.py:426-441`

```python
    for r in rows:
        status = r[9]  # 對齊 _TECH_SELECT（生命週期）
        online_state = r[11]  # 對齊 _TECH_SELECT（操作可用性,CR-0117 S5 熔斷判此欄）
        # CR-0051 / BR-M06：生命週期不可派工（未核准/停權/終止/退回）一律硬排除，不受 exclude_circuit 影響
        if not _is_dispatch_eligible(status):
            continue
        if exclude_circuit and _is_excluded_by_circuit(online_state):
            continue
        tech = _tech_row_to_dict(r)
        if skills_filter and not _intersect_lower(tech["skills"], skills_filter):
            continue
        if areas_filter and not _intersect_lower(tech["service_areas"], areas_filter):
            continue
        if rating_min is not None and tech["rating"] < float(rating_min):
            continue
```

`_DISPATCH_INELIGIBLE_STATUSES = {"pending_approval", "suspended", "terminated", "rejected"}`（`:187`）；`_is_excluded_by_circuit` 判 `{"on_leave", "circuit_breaker_open"}`（`:398`）。

指派端另有 `status != 'active'` 的 409 檢查：`api/services/work_order_service.py:2231-2236`

```python
    if tech_row[1] != "active":
        raise ApiError(
            "TECHNICIAN_NOT_AVAILABLE",
            f"Technician status is '{tech_row[1]}'; only 'active' technicians can accept assignments",
            409,
        )
```

注意 `auto_match_dispatch` 呼叫 `_score_rows(rows, brand=..., district=...)`（`:602`）時未帶 `exclude_circuit`，取預設 `True`（`:422`）。

### 步驟 3 — 急件規則

- **動作**：追 `urgency` 的用法
- **預期**：急件覆寫權重（distance↓ rating↑）
- **實際**：只有一個 5% 的整體 score 乘數，權重常數未依 urgency 改變

`api/services/dispatch_service.py:616`

```python
    boost = 1.05 if urgency == "emergency" else 1.0
```

`urgency` 由 router 取自 request body：`api/routers/dispatch_v2.py:133-141`

```python
    urgency_str = (
        body.urgency.value if body.urgency and hasattr(body.urgency, "value") else (body.urgency or "normal")
    )
    result = await dispatch_service.auto_match_dispatch(
        tenant_id=tenantId,
        problem_card_id=str(body.problem_card_id),
        urgency=urgency_str,
        max_candidates=body.max_candidates or 3,
    )
```

`_W_SKILL` / `_W_DISTANCE` / `_W_RATING` / `_W_LOAD` / `_W_FAIRNESS`（`dispatch_service.py:40-44`）為模組層常數，無依 urgency 分支的覆寫。`smartlock-docs/enterprise/04_SRS.md:296` 記載「急件覆寫權重（distance↓ rating↑）」。此處僅並陳，不裁定。

### 步驟 4 — 重試不重複「指派」

- **動作**：讀冪等機制
- **預期**：重送不產生第二次指派
- **實際**：兩層——端點層 `Idempotency-Key` 回放、DB 層樂觀條件

`api/routers/dispatch_v2.py:119-124`（auto-match）與 `:154-158`（plan）皆掛 `idem: IdempotencyContext | None = Depends(idempotency_guard)`。

`api/core/idempotency.py:285-297`

```python
async def idempotency_guard(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> AsyncIterator[IdempotencyContext | None]:
    """寫操作建議套用此 dependency（yield 形式）。

    - 缺 key → 回 None（呼叫方決定是否強制要求）
    - 既有 completed 命中 → 拋 IdempotencyReplay 回放已存 response
    - 同 key in_progress → 409 IDEMPOTENCY_IN_PROGRESS
    - 成功先佔 → 回 IdempotencyContext，handler 完成後手動 save()；
      未 save（handler 拋錯）由本 dependency finally 釋放佔位列
    """
```

缺 `Idempotency-Key` header 時回 `None`（`:301-303`），端點照常執行。

DB 層：`api/services/work_order_service.py:2263-2274`

```python
    # CR-0199：樂觀條件——指派不可覆蓋期間被取消或已被他人指派的單
    _cur = await db_module._conn.execute(
        "UPDATE work_orders SET "
        ...
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (technician_id, _via, note, wo_id, sorted(_ASSIGN_FROM)),
    )
    _assert_transition_applied(_cur, allowed=_ASSIGN_FROM, action="指派")
```

### 步驟 5 — 重試不重複「通知」

- **動作**：讀 outbox enqueue 的去重集合
- **預期**：派工通知重試不重複送
- **實際**：派工推播 kind 不在嚴格去重集合；worker 端另有 LINE retry key

`api/services/line_push_outbox_service.py:53-64`

```python
# CR-0175 R13：事件型、不可重複的 push_kind — enqueue 走 ON CONFLICT DO NOTHING 去重
# （對齊 migration 111 的 partial unique index uq_outbox_ref_kind_strict）。業主裁決
# 2026-07-20：「可更新後再推」的 kind（quote_proposal / reschedule_proposal /
# scope_change_proposal / schedule_conflict）不在此集合，維持無條件 INSERT（允許合法
# 重推）；兩者皆由 worker 端 x_line_retry_key（CR-0175 C）擋 crash-replay 重送。
_STRICT_DEDUP_KINDS: frozenset[str] = frozenset({
    "work_order_assigned",
    "work_order_accepted",
    "work_order_document",
    "scope_change_result",
})
```

派工時 enqueue 兩個 kind：`work_order_assigned`（客戶 LINE，`work_order_service.py:2311-2320`，在去重集合內）與 `tech_dispatch_assigned`（技師推播，`:1694-1697`，不在集合內）。

`api/services/work_order_service.py:1691-1699`

```python
    if _tech_dispatch_via_outbox():
        try:
            from services import line_push_outbox_service
            await line_push_outbox_service.enqueue(
                tenant_id=tenant_id, push_kind="tech_dispatch_assigned",
                payload=payload, reference_id=wo_id, reference_table="work_orders",
            )
        except Exception:  # noqa: BLE001 — enqueue 失敗 non-fatal
            logger.exception("tech dispatch enqueue 失敗(non-fatal)wo=%s", wo_id)
```

worker 端對 `_DISPATCH_KINDS = {"tech_dispatch_assigned"}`（`realtime/line_push_outbox_worker.py:41`）走內部端點 `/api/v1/internal/technicians/notify-assign`（`:97`），非 LINE push，因此 `x_line_retry_key`（`:246-248`、`:340-345`）不套用於此 kind。

### 步驟 6 — 執行既有測試

- **動作**：跑 outbox 冪等與派工測試
- **預期**：取得執行證據
- **實際**：第一輪 fake-conn outbox 測試通過、DB 相關測試失敗；建立本機測試庫後重跑，派工八檔 52 項與 outbox 兩檔 11 項全數通過，`test_cr_0166_event_backbone.py` 仍有 3 項因技師庫未建而失敗

第一輪（無資料庫）：

```
cd api && python -m pytest tests/test_cr_0017_outbox_worker.py tests/test_cr_0175_outbox_idempotency.py \
  tests/test_cr_0166_event_backbone.py -q --tb=no
3 failed, 15 passed in 0.47s
```

（3 個 failed 全在 `test_cr_0166_event_backbone.py`，原因為 `POSTGRES_URI` 未設 → `db_module._conn` 為 `None`。）

統籌者於本批次另跑（數字沿用不重跑）：

```
cd api && python -m pytest tests/test_cr_0051_dispatch_eligibility.py tests/test_cr_0030_dispatch_mode.py \
  tests/test_manual_dispatch.py tests/test_dispatch_v2_endpoint.py tests/test_dispatch_plan_v2_endpoint.py \
  tests/test_cr_0164_tech_mirror_projection.py tests/test_cr_0172_tech_dispatch_outbox.py \
  tests/test_dispatch_fairness_load.py -q --tb=no
13 failed, 39 passed in 3.87s
```

第二輪（本機 Docker 測試庫，環境見 README「本機測試資料庫」），逐檔執行 `cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/<檔名> -q -p winloop_plugin --tb=no`：

```
test_cr_0017_outbox_worker.py              7 passed in 0.25s
test_cr_0175_outbox_idempotency.py         4 passed in 0.40s
test_cr_0166_event_backbone.py             3 failed, 4 passed in 0.42s

test_cr_0051_dispatch_eligibility.py       8 passed in 0.38s
test_cr_0030_dispatch_mode.py              3 passed in 2.97s
test_manual_dispatch.py                   10 passed in 2.99s
test_dispatch_v2_endpoint.py               6 passed in 2.97s
test_dispatch_plan_v2_endpoint.py          8 passed in 2.96s
test_cr_0164_tech_mirror_projection.py     5 passed in 0.46s
test_cr_0172_tech_dispatch_outbox.py       5 passed in 0.40s
test_dispatch_fairness_load.py             7 passed in 0.40s
```

`test_cr_0172_tech_dispatch_outbox.py`（步驟 4-5 引用的派工 outbox 冪等）5 項通過。`test_cr_0166_event_backbone.py` 的 3 項失敗原因為 `technician_workorder_projection`、`technician_commission_projection`、`event_consumer_dedup` 三張表在測試庫不存在。

第三輪：該三表 DDL 位於 `SQL/tech_authority/Schema_cqrs_projection.sql`，套用至品牌測試庫後重跑 `test_cr_0166_event_backbone.py` → **7 passed in 0.55s**，九檔合計 **59 passed**、無失敗。

> 更正：本文件第二輪原記為「需 `scripts/db/split-tech-db.sh` 建技師庫、本次未建」。該敘述不正確——該腳本搬的是技師身分域表（`:23`），不含這三張投影表；且本測試檔取用品牌連線 `db_module._conn` 而非技師庫連線，在 `TECH_POSTGRES_URI` 未設的單庫 fallback 下（`api/core/db.py:244`）投影表本就落於品牌庫。實際所缺僅為該 schema 檔未套用。

`api/tests/` 中找不到「空候選池」情境的測試，實跑亦無對應案例被執行。

---

## 觀測到的其他事實

- `api/services/dispatch_service.py:87-89` 定義 `_PROGRESSIVE_RADII_KM = [5.0, 10.0, 20.0]` 與 `_MIN_DISPATCH_POOL = 3`；`_apply_progressive_radius` 在三級皆不足時 `selected = list(candidates)`（`:111-112`）全納，而非判定為空池。
- `urgency` 另出現在 outbox lag 指標的標籤（`api/tests/test_outbox_lag_metric.py:42-61` 呼叫 `record_outbox_lag_seconds(..., urgency="emergency")`）。
- `auto_match_dispatch` 的候選來源為 `_fetch_tenant_technicians(tenant_id)`（`dispatch_service.py:401-411`），以 `technicians.tenant_id` 過濾，讀技師權威庫連線。
