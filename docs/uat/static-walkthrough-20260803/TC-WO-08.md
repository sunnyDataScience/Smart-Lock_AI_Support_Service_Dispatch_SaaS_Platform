# TC-WO-08 — 非法狀態轉移的 409 與事件不落庫

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **一致** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（12 項）＋一支置於 scratchpad 的探針（未入 repo），實測 `created → completed` 回 409 且 `work_order_events` 筆數 0→0（見步驟 5） |
| 走查時間 | 2026-08-03 20:05（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/services/work_order_service.py:927-929`、`:1164-1214`、`:1751-1759`、`:1810-1819`、`:1893-1905`、`api/services/cancellation_service.py:317-322`、`:398-412`、`api/tests/test_state_machine_optimistic_lock.py` |
| 優先級 / 路徑類型 | P0 / 例外 |
| 事實結論 | 各 transition 皆為「前置狀態集合檢查 → 409 `STATE_CONFLICT`」；`created → completed` 因 `created ∉ _COMPLETE_FROM` 在 `complete_order:1754` 即拋 409，`_insert_wo_event` 位於 UPDATE 成功之後（`:1895`），故拒絕路徑不寫事件。UPDATE 另帶 `AND status = ANY(...)` 樂觀條件，rowcount 為 0 時由 `_assert_transition_applied` 補拋同一個 409（`:1208-1214`）。 |

**TC 原文**｜前置：任意狀態｜步驟：嘗試非法狀態轉移（如 created → completed）｜判定基準：409 拒絕；work_order_events 無新增｜例外｜P0｜⚠ 未被任何需求指定｜SC-06

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 技師 | 對 created 單送完工 | `TransitionRejected(409)` | 僅 accepted / in_progress 可完工 | `work_order_service.py:1753-1759` | 409 `STATE_CONFLICT`，訊息列出允許集合 |
| 系統 | 寫入前再驗一次 | `OptimisticCheck` | UPDATE 綁允許集合 | `work_order_service.py:1810`、`:1819` | `AND status = ANY(%s)`；rowcount 0 → 409 |
| 系統 | 事件落庫 | `WorkOrderEventInserted` | 僅成功轉移才寫 | `work_order_service.py:1895-1905` | 位於 UPDATE 與 `_assert_transition_applied` 之後 |
| 客服 | 對 completed 單取消 | `TransitionRejected(409)` | terminal 不可取消 | `cancellation_service.py:317-322` | 409 `WO_STATE_INVALID` |

---

## 走查紀錄

### 步驟 1 — 允許集合的定義

- **動作**：讀狀態集合常數
- **預期**：`created` 不在完工允許集合內
- **實際**：一致

`api/services/work_order_service.py:927-929`

```python
_COMPLETE_FROM = {"accepted", "in_progress"}
_CANCEL_FROM = {"created", "assigned", "accepted", "in_progress"}
_ASSIGN_FROM = {"created", "assigned"}  # 允許重派（assigned → assigned 換人）
```

### 步驟 2 — 前置檢查拋 409

- **動作**：讀 `complete_order` 開頭
- **預期**：非法來源狀態即 409
- **實際**：一致

`api/services/work_order_service.py:1751-1759`

```python
    if not await _ensure_conn():
        raise ApiError("DB_UNAVAILABLE", "Database unavailable", 503)
    current = await _fetch_status_for_update(wo_id, tenant_id)
    if current not in _COMPLETE_FROM:
        raise ApiError(
            "STATE_CONFLICT",
            f"Cannot complete work order in status '{current}'; expected one of {sorted(_COMPLETE_FROM)}",
            409,
        )
```

`_fetch_status_for_update` 查不到工單（或跨租戶）時先拋 404（`:1174-1182`）。

### 步驟 3 — 事件寫入的位置

- **動作**：確認 `_insert_wo_event` 相對於拒絕點的順序
- **預期**：拒絕路徑不寫事件
- **實際**：一致——事件寫在 UPDATE 與 rowcount 檢查之後

`api/services/work_order_service.py:1810-1819`（節錄）

```python
        # CR-0199：樂觀條件——完工不可覆蓋期間被取消的單。綁「允許集合」而非讀到的
        # 快照值：客戶核可範圍變更會把 accepted 合法推進到 in_progress，兩者都可完工
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (summary, final_price,
         ...
         wo_id, sorted(_COMPLETE_FROM)),
    )
    _assert_transition_applied(_cur, allowed=_COMPLETE_FROM, action="完工回報")
```

事件寫入在其後（`:1895-1905`），因此步驟 2 的 `raise` 與 `_assert_transition_applied` 的 `raise` 都不會經過 `_insert_wo_event`。

第二道 409 的實作：

`api/services/work_order_service.py:1208-1214`

```python
    if cur.rowcount == 0:
        raise ApiError(
            "STATE_CONFLICT",
            f"工單狀態已被其他操作變更（{action}需要狀態為 {'、'.join(sorted(allowed))}），"
            "請重新載入後再試",
            409,
        )
```

`_fetch_status_for_update` 的 docstring 明載「這裡沒有列鎖」，兩段式檢查的理由與限制記於 `:1164-1173`：

```python
    """讀取當前 status（含 tenant 守衛），查不到就 404。

    ⚠️ **名字裡的 `for_update` 是歷史遺留，這裡沒有列鎖，也不可能有。**
    本專案的連線是 autocommit、無顯式交易，`FOR UPDATE` 的鎖不跨語句
    （見 CR-0199 §3.2 與本檔 L607 的 UAT R3-6 註解）。
```

### 步驟 4 — 其他 transition 的同型結構

- **動作**：抽查 assign / cancel / confirm
- **預期**：同樣 409 且事件在成功後才寫
- **實際**：一致

`assign_order`：前置檢查 `:2203-2206`，UPDATE 帶 `sorted(_ASSIGN_FROM)`（`:2272`），`_assert_transition_applied`（`:2274`）。
`cancel_order`：前置檢查 `:1922`，UPDATE `:1951`，檢查 `:1953`。
六階段取消（`cancellation_service.py`）用的是排除清單：

`api/services/cancellation_service.py:317-322`

```python
    wo = await _fetch_wo_for_cancel(wo_id, tenant_id)
    if wo["status"] in _TERMINAL_STATUSES:
        raise ApiError(
            "WO_STATE_INVALID",
            f"Cannot cancel work order in terminal status '{wo['status']}'",
            409,
        )
```

其 UPDATE 亦帶樂觀條件並在 rowcount 0 時拋 409（`:398-412`），事件寫入在其後（`:419-433`）。此路徑的 error_code 為 `WO_STATE_INVALID` 而非 `STATE_CONFLICT`，兩者狀態碼同為 409。

### 步驟 5 — 執行測試與探針

- **動作**：跑既有樂觀鎖測試；另以 scratchpad 探針直接量測事件筆數
- **預期**：409 且事件不增
- **實際**：一致

既有測試（本機 Docker 測試庫）：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0039_completion_gate.py \
  tests/test_state_machine_optimistic_lock.py -q -p winloop_plugin --tb=line
20 passed in 1.67s
```

`test_state_machine_optimistic_lock.py` 12 項覆蓋 reject / accept / complete / cancel / confirm / assign / reassign 在競態下的 409（例：`:261-276` `test_complete_loses_race_to_cancel`）。

事件筆數的直接量測：一支置於 scratchpad 的探針（**未寫入 repo**），對 `created` 狀態工單呼叫 `complete_order` 與 `confirm_order`，前後各查一次 `work_order_events` 筆數：

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest \
  <scratchpad>/test_wo08_probe.py -q -p winloop_plugin -s

ERROR_CODE= STATE_CONFLICT STATUS= 409
EVENTS before/after = 0 0
.ERROR_CODE= STATE_CONFLICT STATUS= 409
EVENTS before/after = 0 0
.
2 passed, 1 warning in 0.51s
```

第一筆為 `created → completed`（帶 3 張照片 + `signature_evidence_id`，即完工硬閘條件齊備），第二筆為 `created → confirmed`；兩者皆 409 `STATE_CONFLICT`，且 `work_order_events` 筆數維持 0。

---

## 觀測到的其他事實

- TC 判定基準未指名 error_code；程式碼在工單狀態機使用 `STATE_CONFLICT`（`work_order_service.py`），六階段取消使用 `WO_STATE_INVALID`（`cancellation_service.py:319`、`:408`），兩者 HTTP 皆 409。
- `work_order_events.event_type` 受 migration 122 的 CHECK 約束（`SQL/migrations/122-wo-events-seq-and-lifecycle.sql:72-88`），清單含 `created` / `accepted` / `completed` / `cancelled` / `reopened` 等；`_insert_wo_event` 的 docstring 記載「新增 event_type 一律要同步改該 CHECK」（`work_order_service.py:1128-1129`）。
- `_insert_wo_event` 以單語句 `COALESCE(MAX(seq), 0) + 1` 取 per-工單連號，撞號時重試至多 5 次（`work_order_service.py:1115`、`:1147-1161`）。
- 端點層另有更早的攔截：`/onsite/completion` 缺 `Idempotency-Key` 回 400（`api/core/idempotency.py:198-206`），不存在的工單回 404 或 409（`api/tests/test_work_orders_onsite_v2_endpoint.py:149-159`）。
- `smartlock-docs/enterprise/20_Test_Cases.md:265` 的本 TC 列在來源需求欄填的是 `FR-0038`，而該表上半的需求→測試對照表（`:80-81` FR-API-08 / FR-API-09）未列入 TC-WO-08，與 TC 原文「⚠ 未被任何需求指定」一致。
