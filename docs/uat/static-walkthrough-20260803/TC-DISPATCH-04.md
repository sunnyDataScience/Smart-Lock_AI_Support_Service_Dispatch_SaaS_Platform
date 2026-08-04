# TC-DISPATCH-04 — 拒單／逾時未接的候選擴大與客服通知

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **不一致** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；後續以本機 Docker 測試庫實跑既有測試（見步驟 6） |
| 走查時間 | 2026-08-03 17:41（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/realtime/sla_monitor.py`、`api/realtime/job_registry.py`、`api/services/work_order_service.py`、`api/services/dispatch_service.py`、`api/routers/work_orders_v2.py` |
| 優先級 / 路徑類型 | P1 / timeout |
| 事實結論 | 「接單時限」（一般 10min / 急件 5min）在 `api` 中零命中；沒有以「指派時刻」起算的接單逾時計時器。既有 `dispatch_delay` 告警以 `work_orders.created_at` 起算、門檻 30 分、動作只有 WS publish 到 `/realtime/sla-alerts`，不改派、不擴大候選、不通知客服。拒單路徑（`reject_order`）把工單退回 `created` 並通知建單者，未擴大候選範圍。 |

**TC 原文**｜前置：師傅拒單 / 逾時未接｜步驟：超過接單時限｜判定基準：系統擴大候選範圍 + 通知客服（🔜 SLA 引擎自動改派規劃中，上線前列 gap 追蹤）｜timeout｜P1｜FR-API-07、FR-TEC-04、FR-WEB-03｜SC-05

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 技師 | 拒單 | `WorkOrderRejected` | 回派工池 | `services/work_order_service.py:1330-1412` | 狀態 → `created`、清 `technician_id`、寫 `dispatch_logs(action='reject')` |
| 系統 | 接單逾時計時 | `AcceptanceDeadlineExceeded` | 一般 10min / 急件 5min | — | **找不到**以指派時刻起算的接單時限 |
| 系統 | 擴大候選範圍 | `CandidatePoolExpanded` | 30min 無人接 | — | **找不到**逾時觸發的擴池／改派 |
| 系統 | 通知客服 | `CustomerServiceNotified` | 30min 無人接 | — | **找不到**逾時通知客服 |
| SLA 引擎 | 逾時掃描 | `SlaAlertRaised` | `dispatch_delay` | `realtime/sla_monitor.py:159-178`、`:284-291` | 以 `created_at` 起算 30 分，WS publish 告警 |

---

## 走查紀錄

### 步驟 1 — 「接單時限」是否存在

- **動作**：搜尋接單逾時相關字串
- **預期**：有 10min／5min 門檻常數
- **實際**：`api` 全數零命中

```
git grep -rn "accept_timeout\|ACCEPT_TIMEOUT\|接單時限\|逾時未接\|no_response\|超時" -- api
（無輸出）
```

正典側的要求在 `smartlock-docs/enterprise/04_SRS.md:298`（FR-API-07）：「一般 10min / 急件 5min 接單 SLA（per-brand override）；30min 無人接 → 擴大範圍 + 通知客服」，與 `:462-463`：

```
| BR-Disp-001 | 接單 SLA 一般 10min / 急件 5min + per-brand override | FR-API-07 |
| BR-Disp-002 | 30min 無人接 → 擴大範圍 + 通知客服 | FR-API-05 |
```

`git grep -rn "BR-Disp" -- api web SQL agent` 無輸出。此處僅並陳，不裁定。

### 步驟 2 — 既有的派工逾時告警

- **動作**：讀 SLA 引擎
- **預期**：接單逾時觸發處置
- **實際**：有 `dispatch_delay` 告警，門檻預設 30 分，起算點是工單 `created_at` 而非指派時刻

`api/realtime/sla_monitor.py:53`

```python
DISPATCH_DELAY_MINUTES = int(os.environ.get("SLA_DISPATCH_DELAY_MINUTES", "30"))
```

`api/realtime/sla_monitor.py:159-178`

```python
        # ─── dispatch_delay ───────────────────────────────────────────
        cur = await db_module._conn.execute(
            "SELECT id, status "
            "FROM work_orders "
            "WHERE status IN ('created', 'assigned') "
            "  AND created_at < NOW() - (INTERVAL '1 minute' * %s)",
            (DISPATCH_DELAY_MINUTES,),
        )
        for r in await cur.fetchall():
            target_id = str(r[0])
            key = ("dispatch_delay", target_id)
            active_keys.add(key)
            if key not in self._alerted:
                new_alerts.append(
                    {
                        "alert_type": "dispatch_delay",
                        "target_id": target_id,
                        "threshold_minutes": DISPATCH_DELAY_MINUTES,
                    }
                )
```

條件為 `status IN ('created','assigned')`，未區分「已指派但技師未接」與「尚未指派」。

### 步驟 3 — 告警觸發後的動作

- **動作**：讀 alert 後續處置
- **預期**：擴大候選 + 通知客服
- **實際**：只 WS publish；只有 `arrival_overdue` 與 `audit_overdue` 兩型另有 audit log 處置，`dispatch_delay` 無

`api/realtime/sla_monitor.py:284-297`

```python
        try:
            from realtime.ws_hub import hub

            for alert in new_alerts:
                await hub.publish(
                    "/realtime/sla-alerts",
                    {"type": "sla.alert", "payload": alert},
                )
                # F-016 紅色警報需額外寫 audit log（PM Q5=B Soft SLA 政策）
                if alert["alert_type"] == "arrival_overdue":
                    await self._write_arrival_overdue_audit(alert)
                # CR-0129：急件補審逾時 → audit log + 連 3 逾時自動開 ChangeRequest
                if alert["alert_type"] == "audit_overdue":
                    await self._handle_audit_overdue(alert)
```

`sla_monitor.py` 全檔未 import `dispatch_service`、`notification_service` 或 `work_order_service`，亦無任何 `reassign` / `auto_match` 呼叫。

### 步驟 4 — 拒單路徑的實際行為

- **動作**：讀 `reject_order`
- **預期**：拒單後擴大候選範圍 + 通知客服
- **實際**：工單退回 `created`、清空技師，通知對象是 `work_orders.created_by`（建單者）

`api/services/work_order_service.py:1372-1384`

```python
    # CR-0199：樂觀條件——避免把「已被取消/已被他人改派」的單打回派工池
    _cur = await db_module._conn.execute(
        "UPDATE work_orders SET status = 'created', technician_id = NULL, "
        "  status_reason = %s, updated_at = NOW() "
        "WHERE id = %s::uuid AND status = ANY(%s)",
        (reason, wo_id, sorted(_REJECT_FROM)),
    )
    _assert_transition_applied(_cur, allowed=_REJECT_FROM, action="拒單")
    await db_module._conn.execute(
        "INSERT INTO dispatch_logs (work_order_id, action, technician_id, rejection_reason, notes) "
        "VALUES (%s::uuid, 'reject', %s::uuid, %s, %s)",
        (wo_id, tech_ctx["id"], reason, note),
    )
```

`api/services/work_order_service.py:1394-1407`

```python
    # 通知派工小編（best-effort）＋稽核
    try:
        if created_by:
            await _auto_notify(
                tenant_id, created_by, "work_order_rejected",
                "技師拒接工單", f"工單已被技師退回派工池，原因：{reason}",
                wo_id=wo_id,
            )
        from services import audit_log_service
        await audit_log_service.log_event(
            event_type="dispatch_decision", actor_id=actor_user_id, actor_role=actor_role,
            action="technician_reject", target_type="work_order", target_id=wo_id,
            payload={"technician_id": tech_ctx["id"], "reason": reason},
        )
```

通知目標由 `created_by` 決定，非以角色（客服）為對象；`reject_order` 內無任何候選重算或再派工呼叫。

### 步驟 5 — 是否有其他逾時 cron 承擔改派

- **動作**：檢視背景工作註冊表
- **預期**：有接單逾時 job
- **實際**：註冊的 SLA 類工作為 `sla-monitor` 與 `family-review-sla`，範圍分別為「brand work-order/quote SLA」與家族覆核

`api/realtime/job_registry.py:97-101`

```python
        "sla-monitor",
        "realtime.sla_monitor:monitor",
```

```python
        scope="brand work-order/quote SLA",
```

`api/realtime/job_registry.py:243-251` 為 `family-review-sla`，`compensation="manual SLA escalation review"`。`git grep -rn "dispatch_pending" -- api web SQL` 無輸出。

### 步驟 6 — 執行既有測試

- **動作**：跑派工相關測試（由統籌者於本批次執行，數字沿用不重跑）
- **預期**：取得執行證據
- **實際**：第一輪無資料庫多數失敗；建立本機測試庫後重跑，八檔 52 項全數通過，其中不含接單時限相關案例

第一輪（無資料庫）：

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

八檔 52 項全數通過。`api/tests/` 中找不到「接單逾時 → 擴大候選 / 通知客服」的測試，實跑亦無對應案例被執行。

---

## 觀測到的其他事實

- TC 原文自帶註記「🔜 SLA 引擎自動改派規劃中，上線前列 gap 追蹤」。
- `smartlock-docs/enterprise/20_Test_Cases.md` 對 FR-API-07 的追溯與本 TC 一致。
- `dispatch_delay` 的重複告警抑制為 process 內記憶體 set（`realtime/sla_monitor.py:62` `self._alerted`），並由分散式鎖 `_ensure_leader("sla_monitor")`（`:100`）限單一實例掃描。
