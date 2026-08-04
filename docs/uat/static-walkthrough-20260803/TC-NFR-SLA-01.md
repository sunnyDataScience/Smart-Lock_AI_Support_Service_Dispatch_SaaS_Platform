# TC-NFR-SLA-01 — 2 小時 SLA 邊界、通知 fallback 與升級鏈

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **無法靜態判定** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 6） |
| 走查時間 | 2026-08-03 19:55（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/realtime/sla_monitor.py`、`api/realtime/job_registry.py`、`api/services/work_order_service.py`、`api/services/notification_service.py`、`api/services/email_provider.py`、`api/core/distributed_lock.py` |
| 優先級 / 路徑類型 | P0 / failure＋recovery |
| 事實結論 | 判定基準需可控時鐘與 push/email/on-call fixture 的執行期觀測，無程式碼可據以判定。靜態查得：2 小時門檻常數 `ARRIVAL_OVERDUE_MINUTES=120` 存在、SQL 用嚴格 `<` 比較但錨點是 `scheduled_at` 而非派工時刻、掃描週期 60s；標紅（`severity: "red"`）與 `escalated_to: "ops_manager"` 只寫進 alert payload 與 audit log，`sla_monitor.py` 未 import 任何通知／email service；「retry queue」「email fallback」「主管離線 → 升 operations_director」在 `api` 中**找不到**；技師主動回報延遲（`notify_delay`）與 SLA 掃描之間無任何關聯程式碼。 |

**TC 原文**｜前置：可控時鐘、派工、push/email/on-call fixture｜步驟：在 T+2:00:00/T+2:00:01、技師主動延遲、push 失敗與主管離線時執行｜判定基準：邊界判定正確；標紅、retry、email fallback 與升級鏈可觀測且不重複通知｜failure＋recovery｜P0｜NFR-SLA-001、NFR-SLA-002、NFR-SLA-003｜SC-05、SC-06

---

## 為何無法靜態判定

判定基準包含四組執行期行為：①在 T+2:00:00 與 T+2:00:01 兩個時點的邊界判定②技師主動延遲後的 alert 抑制與 breach 標記③push 失敗後的 retry 與 email fallback④主管離線時的升級鏈。這些都需要可控時鐘、可注入失敗的通知通道與 on-call fixture 才能觀測。原始碼可以顯示門檻常數與比較運算子，但無法產生「在該時點是否觸發、是否重複通知」的事實。本批走查的前提是不啟動服務，故此條無法取得判定所需事實。

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| SLA 引擎 | 掃描逾時 | `SlaBreached` | T+2:00:01 進 breach | `realtime/sla_monitor.py:220-228` | `scheduled_at < NOW() - INTERVAL '1 minute' * 120`（嚴格 `<`） |
| 系統 | dashboard 標紅 | `AlertMarkedRed` | 標紅 | `realtime/sla_monitor.py:236-244` | payload 帶 `"severity": "red"` |
| 系統 | push 主管 | `ManagerNotified` | push operations_manager | `realtime/sla_monitor.py:284-291` | 僅 WS publish 到 `/realtime/sla-alerts` |
| 系統 | push 失敗 | `PushRetried` | retry queue + email fallback | — | **找不到** |
| 系統 | 主管離線 | `EscalatedToDirector` | 升 operations_director | — | **找不到**（`operations_director` 全 repo 未見於 `api`） |
| 技師 | 主動回報延遲 | `DelayReported` | 不發 alert 但仍標 breached | `services/work_order_service.py:3992-4052` | 寫 `work_order_events(event_type="delay")`；與 SLA 掃描無關聯 |

---

## 走查紀錄

### 步驟 1 — 2 小時門檻與邊界運算子

- **動作**：讀 arrival_overdue 掃描
- **預期**：T+2:00:00 不 breach、T+2:00:01 breach
- **實際**：門檻 120 分、嚴格 `<`；錨點為 `scheduled_at`

`api/realtime/sla_monitor.py:55`

```python
ARRIVAL_OVERDUE_MINUTES = int(os.environ.get("SLA_ARRIVAL_OVERDUE_MINUTES", "120"))
```

`api/realtime/sla_monitor.py:216-228`

```python
        # ─── arrival_overdue（F-016 SLA 紅色警報，2hr 到場破線）──────────
        # 條件：技師已派 (status='assigned') + 排程時間已超過閾值 + 仍未開工
        # 注意：scheduled_at 為計畫到場時間；started_at 為實際到場 / 開工時間。
        # 完成 (status='completed','confirmed','cancelled') 不再警示。
        cur = await db_module._conn.execute(
            "SELECT id, technician_id "
            "FROM work_orders "
            "WHERE status = 'assigned' "
            "  AND scheduled_at IS NOT NULL "
            "  AND started_at IS NULL "
            "  AND scheduled_at < NOW() - (INTERVAL '1 minute' * %s)",
            (ARRIVAL_OVERDUE_MINUTES,),
        )
```

`smartlock-docs/enterprise/05_NFR.md:74-75` 記載 NFR-SLA-001 為「派工→技師抵達 SLA（soft）」、NFR-SLA-002 為「T+2:00:00 可接受；T+2:00:01 進 breach」。程式碼的計時錨點為 `scheduled_at`（計畫到場時間），非派工時刻。此處僅並陳，不裁定。

掃描週期：`api/realtime/sla_monitor.py:51`

```python
DEFAULT_INTERVAL = max(30, int(os.environ.get("SLA_MONITOR_INTERVAL_SECONDS", "60")))
```

### 步驟 2 — 標紅與升級標記

- **動作**：讀 alert payload
- **預期**：標紅 + 升級可觀測
- **實際**：`severity`／`escalated_to` 為 payload 欄位

`api/realtime/sla_monitor.py:234-245`

```python
            if key not in self._alerted:
                new_alerts.append(
                    {
                        "alert_type": "arrival_overdue",
                        "target_id": target_id,
                        "threshold_minutes": ARRIVAL_OVERDUE_MINUTES,
                        "severity": "red",
                        "escalated_to": "ops_manager",
                        # 額外 context（非 spec 必填，但前端有用）
                        "technician_id": tech_id,
                    }
                )
```

audit 側：`api/realtime/sla_monitor.py:317-337`

```python
            from services.audit_log_service import log_event

            await log_event(
                event_type="escalation",
                actor_id=None,
                actor_role="system",
                action="sla.arrival_overdue",
                ...
                payload={
                    "alert_type": "arrival_overdue",
                    ...
                    "policy": "Q5=B Soft SLA",
                    "compensation": "none",
                    "auto_refund": False,
                },
            )
```

### 步驟 3 — push 通道與 retry / email fallback

- **動作**：查 alert 的實際投遞通道與失敗補償
- **預期**：push → 失敗 → retry queue → email fallback
- **實際**：只有一條 WS publish；整段包在單一 `try/except` 中，失敗只記 log

`api/realtime/sla_monitor.py:284-308`

```python
        try:
            from realtime.ws_hub import hub

            for alert in new_alerts:
                await hub.publish(
                    "/realtime/sla-alerts",
                    {"type": "sla.alert", "payload": alert},
                )
                ...
        except Exception:  # noqa: BLE001
            logger.exception("ws publish sla.alert failed (non-fatal)")
```

`sla_monitor.py` 全檔的 import 只有 `asyncio` / `logging` / `os` / `core.db` / `core.distributed_lock`（`:41-47`），以及函式內 lazy import 的 `realtime.ws_hub.hub` 與 `services.audit_log_service.log_event`。無 `notification_service`、無 `email_provider`、無 `line_push_outbox_service`。

`git grep -rn "on_call\|on-call" -- api` 無輸出；`operations_director` 在 `api/core/deps.py:293-304` 的角色集合中不存在。

`smartlock-docs/enterprise/05_NFR.md:76` 記載 NFR-SLA-003：「push 失敗 → retry queue + email fallback；主管離線 → 升 operations_director」。此處僅並陳，不裁定。

### 步驟 4 — 技師主動回報延遲

- **動作**：讀 `notify_delay`
- **預期**：回報後不發 alert 但仍標 breached
- **實際**：寫 `work_order_events(event_type="delay")` 並推 LINE；未改 `scheduled_at`／`started_at`／`status`，SLA 掃描的三個條件不受影響

`api/services/work_order_service.py:4044-4052`

```python
    # 寫結構化事件（重用 _append_subflow_event 但避免重複狀態檢查 — 直接 INSERT）
    payload = {
        "delay_minutes": delay_minutes,
        "reason": reason.strip()[:500],
        "channel_attempt": "line",
    }
    await _insert_wo_event(
        wo_id=wo_id, tenant_id=tenant_id, actor_user_id=actor_user_id,
        event_type="delay", payload=payload,
```

`api/realtime/sla_monitor.py:220-228` 的 SQL 未 JOIN `work_order_events`，亦無任何 `delay` 相關排除條件。程式碼中找不到「技師主動回報延遲 → 抑制 alert」的關聯。

### 步驟 5 — 不重複通知的機制

- **動作**：讀重複抑制
- **預期**：不重複通知
- **實際**：process 內記憶體 set + 分散式 leader 鎖；鎖不可用時退單機語意

`api/realtime/sla_monitor.py:60-62`

```python
    def __init__(self, interval_seconds: int = DEFAULT_INTERVAL) -> None:
        self._interval = interval_seconds
        # 用 (alert_type, target_id) 當 key
        self._alerted: set[tuple[str, str]] = set()
```

`api/realtime/sla_monitor.py:275-279`

```python
        # 從 _alerted 移除已恢復（不再符合條件）的告警
        recovered = self._alerted - active_keys
        if recovered:
            logger.info("SLA recovered: %d alerts cleared", len(recovered))
        self._alerted = active_keys
```

`api/core/distributed_lock.py:37-55`

```python
async def ensure_leader(job: str) -> bool:
    """本實例是否為 job 的 leader（詳見模組 docstring）。絕不 raise。"""
    if job in _held:
        return True
    try:
        if not await _ensure_conn():
            return True  # DB 不可用 → 單機 degraded，照跑
        cur = await db_module._conn.execute(
            "SELECT pg_try_advisory_lock(%s, %s)", (_LOCK_NS, _job_key(job)),
        )
        row = await cur.fetchone()
        got = bool(row and row[0])
        if got:
            _held.add(job)
            logger.info("cron leader acquired: %s（本實例接手排程）", job)
        return got
    except Exception:  # noqa: BLE001 — 鎖機制故障不可癱瘓 cron；退單機語意
        logger.exception("ensure_leader(%s) 異常——退單機語意照跑", job)
        return True
```

`_alerted` 為記憶體狀態，無持久化；程式重啟後既有 alert 會在下次掃描重新視為 new。

### 步驟 6 — 既有測試

- **動作**：找相關測試
- **預期**：能提供邊界證據
- **實際**：`api/tests/` 中找不到 arrival_overdue 邊界或 SLA fallback 的測試；派工相關測試第一輪在無 DB 環境下多數失敗，第二輪於本機測試庫全數通過，但兩輪皆未觸及 SLA 路徑

第一輪（無資料庫，由統籌者於本批次執行，數字沿用）：

```
cd api && python -m pytest tests/test_cr_0051_dispatch_eligibility.py tests/test_cr_0030_dispatch_mode.py \
  tests/test_manual_dispatch.py tests/test_dispatch_v2_endpoint.py tests/test_dispatch_plan_v2_endpoint.py \
  tests/test_cr_0164_tech_mirror_projection.py tests/test_cr_0172_tech_dispatch_outbox.py \
  tests/test_dispatch_fairness_load.py -q --tb=no
13 failed, 39 passed in 3.87s
```

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

八檔 52 項全數通過，內容皆為派工授權／評分／outbox，未涵蓋 `sla_monitor` 的 2 小時門檻、標紅升級或 push／email fallback；本機測試庫也不提供可控時鐘與可注入失敗的通知通道，故第二輪不提供 SLA 判讀所需的觀測。

---

## 判定所需的前置條件

要把此 TC 從「無法靜態判定」推進到可判定，需要：可運行的 API 與 SLA 引擎、可控時鐘（或可注入的 `NOW()`）、可注入失敗的 push 通道與 email fixture、on-call／主管離線狀態的模擬來源，以及一組已派工且 `scheduled_at` 落在邊界時點的工單資料。

---

## 觀測到的其他事實

- `smartlock-docs/enterprise/20_Test_Cases.md:153-155` 對 NFR-SLA-001/002/003 標註「⚠ 完全沒有案例」。
- `api/realtime/sla_monitor.py:31-34` 記載 PM Q5=B（Soft SLA）拍板：「arrival_overdue 觸發後僅做 dashboard 紅燈 + Ops Manager 通知 + audit log」「嚴禁串接賠償 / 自動退款 / 抵用券發放 / 沖銷 邏輯」。
- 專案內另有 email 供應者模組 `api/services/email_provider.py`，未被 `sla_monitor.py` 引用。
- 另一支 SLA cron `api/realtime/family_review_sla_cron.py`（家族覆核 24h 逾時升級）有獨立的通知路徑（`:140`），與工單到場 SLA 無關。
