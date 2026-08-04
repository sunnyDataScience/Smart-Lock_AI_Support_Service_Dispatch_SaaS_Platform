# TC-WO-10 — 工單 dispatched 逾 SLA（PT2H）觸發 notify_supervisor 與 dashboard 標紅

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| 判定語彙 | 一致 / 不一致 / 部分實作 / 無法靜態判定 |
| **本判定以原始碼走查為主** | 未啟動應用服務；SLA timer 到期為時間驅動行為，掃描迴圈本身不在本次執行範圍 |
| 走查日期 | 2026-08-04 |
| 證據型態 | 靜態原始碼走查 |
| 走查基準 | commit `2cfeca92` |
| 走查範圍 | `api/realtime/sla_monitor.py:1-427`、`api/realtime/job_registry.py:97-98`、`web/brand-portal/src/components/dashboard/SlaAlertBanner.tsx:27-192`、`SQL/Schema.sql:462-470`、`smartlock-docs/enterprise/15_SDS.md:161`、`:256`、`smartlock-docs/enterprise/04_SRS.md:298` |
| 優先級 / 路徑類型 | P1 / timeout |

TC 指名的識別碼 `notify_supervisor` 在 `api` / `web` / `agent` / `SQL` 全數零命中，只出現在文件（`smartlock-docs/enterprise/08_User_Flow.md:268`、`15_SDS.md:161`、`:256`）；`PT2H` 字面同樣只在文件出現。TC 描述的來源狀態 `dispatched` 在 `work_orders.status` 的值域中不存在（`SQL/Schema.sql:468-469` 列的是 `created / assigned / accepted / in_progress / completed / confirmed / cancelled`）。另一方面，功能面的對應物存在且完整：`arrival_overdue` 告警以預設 120 分鐘閾值（`api/realtime/sla_monitor.py:55`）掃 `status='assigned'` 且逾排程未開工的工單，payload 帶 `severity="red"` 與 `escalated_to="ops_manager"`（`:236-245`），推 `/realtime/sla-alerts` 並寫 `audit_events`（`:288-294`、`:310-339`）；前端 dashboard banner 以 `severity === "red" || alert_type === "arrival_overdue"` 判定並套紅色樣式（`web/brand-portal/src/components/dashboard/SlaAlertBanner.tsx:147-149`、`:181-192`）。因此「dashboard 標紅」有落點、「觸發 notify_supervisor 積木」在程式碼中無同名物件。「T+2:00:01 起算 breach」的時間精度屬 runtime 行為，非靜態可判。

---

## TC 原文

| 欄位 | 內容 |
|---|---|
| 章節 | 4. 工單生命週期案例（TC-WO） |
| 前置 | 工單 dispatched 超過 SLA（PT2H） |
| 步驟 | SLA timer 到期 |
| 預期結果（判定基準） | 觸發 `notify_supervisor` 積木；dashboard 標紅（T+2:00:01 起算 breach） |
| 路徑類型 | timeout |
| 驗證面向 | 功能 |
| 優先級 | P1 |
| 驗證哪些需求 | FR-API-07 |
| 屬於哪條旅程腳本 | — |

---

## 逐條驗收條件對照

| 條件 | 程式碼落點 | 狀態 |
|---|---|---|
| 前置狀態 `dispatched` | `SQL/Schema.sql:468-469` 的狀態值域無 `dispatched`；`api/services/work_order_service.py:929` `_ASSIGN_FROM = {"created", "assigned"}` | 無同名狀態 |
| SLA 閾值 PT2H（120 分鐘） | `api/realtime/sla_monitor.py:55` `ARRIVAL_OVERDUE_MINUTES = int(os.environ.get("SLA_ARRIVAL_OVERDUE_MINUTES", "120"))` | 有落點（值相同，`PT2H` 字面零命中） |
| SLA timer 機制 | `api/realtime/sla_monitor.py:91-117` asyncio 週期掃描（預設 60s，`:51`）；非 per-state timer | 有落點（機制不同型） |
| 觸發 `notify_supervisor` 積木 | `git grep notify_supervisor -- api web agent SQL` → 零命中 | 無落點 |
| 升級主管 | `api/realtime/sla_monitor.py:240-241` payload `"escalated_to": "ops_manager"`；`:320-337` 寫 `audit_events`（`action="sla.arrival_overdue"`） | 有落點（以欄位與稽核承載，非具名積木） |
| dashboard 標紅 | `web/brand-portal/src/components/dashboard/SlaAlertBanner.tsx:147-149`、`:181-192`（`data-severity="red"`） | 有落點 |
| T+2:00:01 起算 breach | 掃描為週期輪詢（`sla_monitor.py:51` 預設 60s），SQL 條件為 `scheduled_at < NOW() - INTERVAL`（`:226`） | 無法靜態判定 |
| 計時錨點 | `api/realtime/sla_monitor.py:224-226`：以 `scheduled_at`（計畫到場時間）為錨，非以派工時刻 | 有落點（錨點與 TC 敘述不同） |

---

## Event Storming

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 排程器 | 週期掃描 | `SlaScanTicked` | 每 60s、單一 leader | `api/realtime/sla_monitor.py:98-107`、`:100`（`_ensure_leader("sla_monitor")`） | 分散式鎖，非 leader 待命 |
| 系統 | 偵測逾時 | `ArrivalOverdueDetected` | `status='assigned'` ∧ `scheduled_at` 已逾 ∧ `started_at IS NULL` | `api/realtime/sla_monitor.py:220-228` | SQL 條件三項全帶 |
| 系統 | 發告警 | `SlaAlertPublished` | WS 推播 | `api/realtime/sla_monitor.py:288-291` | `hub.publish("/realtime/sla-alerts", {...})` |
| 系統 | 通知主管 | `SupervisorNotified` | 升 Ops Manager | `api/realtime/sla_monitor.py:240-241`、`:320-337` | payload `escalated_to="ops_manager"` + `audit_events` 一列；**無** `notify_supervisor` 具名積木、無 push/mail 呼叫 |
| Dashboard | 收 WS 訊息 | `BannerTurnedRed` | red 優先 | `SlaAlertBanner.tsx:122-149`、`:181-192` | `hasRed` 為真 → 紅色樣式 + `data-severity="red"` |
| 系統 | 條件解除 | `SlaAlertRecovered` | 不再符合即移除 | `api/realtime/sla_monitor.py:275-279` | `recovered = self._alerted - active_keys` |
| 系統 | 賠償／退款 | （不應發生） | Soft SLA（PM Q5=B） | `api/realtime/sla_monitor.py:31-34`、`:313-316` | 檔內明文「嚴禁串接賠償／自動退款」，`_write_arrival_overdue_audit` 不 import refund/voucher/settlement |

---

## 逐層走查

### 第 1 層 — TC 指名識別碼的命中情況

```
git grep -rn "notify_supervisor" -- api web agent SQL smartlock-docs
smartlock-docs/enterprise/08_User_Flow.md:268:**SLA 範例**：`dispatched` 狀態逾 2 小時未到場 → 觸發 `notify_supervisor` block。
smartlock-docs/enterprise/15_SDS.md:161:  "sla": [ {"state":"dispatched","due":"PT2H","on_breach":["block:notify_supervisor"]} ]
smartlock-docs/enterprise/15_SDS.md:256:SLA 宣告於 flow DSL（如 {"state":"dispatched","due":"PT2H",...}）…
smartlock-docs/enterprise/20_Test_Cases.md:267:| TC-WO-10 | FR-0016 | 工單 dispatched 超過 SLA（PT2H）| …
```

`api` / `web` / `agent` / `SQL` 四個樹零命中。同樣地：

```
git grep -rn "on_breach\|flow DSL\|flow_dsl" -- api web agent SQL
（無輸出，exit=1）
```

`15_SDS.md:256` 描述的機制為「引擎於狀態進入時掛 timer（Redis/分散式排程），逾時觸發 breach block」。程式碼中的對應物為週期輪詢（見第 2 層），非狀態進入時掛 timer。

- TC 判定基準寫「觸發 `notify_supervisor` 積木」（出處：`smartlock-docs/enterprise/20_Test_Cases.md:267`）
- 程式碼以 `arrival_overdue` 告警 + `escalated_to="ops_manager"` 欄位 + `audit_events` 一列承載升級（`api/realtime/sla_monitor.py:236-245`、`:320-337`），無名為 `notify_supervisor` 的積木、函式或設定值

此處僅並陳，不裁定。

### 第 2 層 — SLA 引擎：掃描機制與閾值

`api/realtime/sla_monitor.py:51-55`

```python
DEFAULT_INTERVAL = max(30, int(os.environ.get("SLA_MONITOR_INTERVAL_SECONDS", "60")))
QUOTE_EXPIRING_MINUTES = int(os.environ.get("SLA_QUOTE_EXPIRING_MINUTES", "1440"))
DISPATCH_DELAY_MINUTES = int(os.environ.get("SLA_DISPATCH_DELAY_MINUTES", "30"))
RESPONSE_OVERDUE_MINUTES = int(os.environ.get("SLA_RESPONSE_OVERDUE_MINUTES", "30"))
ARRIVAL_OVERDUE_MINUTES = int(os.environ.get("SLA_ARRIVAL_OVERDUE_MINUTES", "120"))
```

迴圈本體，`api/realtime/sla_monitor.py:98-116`：

```python
        while not self._stopping.is_set():
            # SA-02（CR-0134）分散式鎖：他實例為 leader → 本實例待命（leader 斷線自動接手）
            if not await _ensure_leader("sla_monitor"):
                ...
            try:
                await self._scan_once()
            except Exception:  # noqa: BLE001
                logger.exception("SLAMonitor scan_once failed")
            try:
                await asyncio.wait_for(
                    self._stopping.wait(), timeout=self._interval
                )
                return
            except asyncio.TimeoutError:
                continue
```

註冊於 job registry，`api/realtime/job_registry.py:97-98`：

```python
        "sla-monitor",
        "realtime.sla_monitor:monitor",
```

- TC 判定基準寫「T+2:00:01 起算 breach」
- 程式碼以固定週期輪詢偵測（預設 60 秒一輪，`api/realtime/sla_monitor.py:51`），SQL 條件為嚴格不等式 `scheduled_at < NOW() - (INTERVAL '1 minute' * 120)`（`:226`）

輪詢間隔導致的偵測延遲屬 runtime 觀察範圍，靜態走查不判定該秒級精度。

### 第 3 層 — 偵測查詢：狀態、錨點、條件

`api/realtime/sla_monitor.py:216-245`

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
        for r in await cur.fetchall():
            target_id = str(r[0])
            tech_id = str(r[1]) if r[1] else None
            key = ("arrival_overdue", target_id)
            active_keys.add(key)
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

DB 的狀態值域，`SQL/Schema.sql:462-470`：

```sql
CREATE TABLE work_orders (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    problem_card_id     UUID REFERENCES problem_cards(id) ON DELETE RESTRICT,
    technician_id       UUID REFERENCES technicians(id) ON DELETE SET NULL,
    created_by          UUID REFERENCES users(id) ON DELETE SET NULL,
    status              VARCHAR(50) DEFAULT 'created',
                        -- 'created', 'assigned', 'accepted', 'in_progress',
                        -- 'completed', 'confirmed', 'cancelled'
```

- TC 前置寫「工單 `dispatched` 超過 SLA」
- 程式碼中 `work_orders.status` 無 `dispatched` 值（`SQL/Schema.sql:468-469`），派工後的狀態為 `assigned`（`api/services/work_order_service.py:929` `_ASSIGN_FROM = {"created", "assigned"}`）；`dispatched` 一詞在 `SQL` 中只出現在 `work_orders.dispatched_via` 欄（派工來源標記，`SQL/migrations/039-dispatch-mode.sql:17-20`）與 `total_dispatched_orders` 統計欄（`SQL/migrations/026-dispatcher-commission.sql:19`）

此處僅並陳，不裁定。

計時錨點方面：查詢以 `scheduled_at`（計畫到場時間）為起算，`started_at IS NULL` 為未到場。TC 前置的敘述為「工單 `dispatched` 超過 SLA」，即以派工時刻起算。兩者在 `scheduled_at ≠ 派工時刻` 時不同。此處僅並陳，不裁定。

另有一支同表的 `dispatch_delay` 告警以 `created_at` 為錨、閾值 30 分鐘（`api/realtime/sla_monitor.py:160-178`），對應 `smartlock-docs/enterprise/04_SRS.md:298` FR-API-07 前半段的「30min 無人接 → 擴大範圍 + 通知客服」；該告警的 `severity` 未設值。

### 第 4 層 — 升級主管的實際動作

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
```

`api/realtime/sla_monitor.py:310-339`

```python
    async def _write_arrival_overdue_audit(self, alert: dict) -> None:
        """記錄 F-016 SLA 紅色警報事件到 audit_events。

        PM Q5=B 拍板：Soft SLA — 警報只升級 Ops Manager + 寫稽核日誌，
        不串接賠償 / 自動退款 / 抵用券發放 / 沖銷。本函式刻意 **不** import 任何
        refund / voucher / settlement service。
        """
        try:
            from services.audit_log_service import log_event

            await log_event(
                event_type="escalation",
                actor_id=None,
                actor_role="system",
                action="sla.arrival_overdue",
                ...
                    "policy": "Q5=B Soft SLA",
                    "compensation": "none",
                    "auto_refund": False,
                },
            )
```

`arrival_overdue` 路徑上除 WS 推播與 audit log 外，無其他外送通道呼叫（同檔的 `audit_overdue` 路徑另有自動開 ChangeRequest 的分支，`:396-421`；`arrival_overdue` 無對應分支）。

### 第 5 層 — 前端 dashboard 標紅

`web/brand-portal/src/components/dashboard/SlaAlertBanner.tsx:83-91`

```tsx
  arrival_overdue: {
    // F-016 SLA 紅色警報 — Q5=B Soft SLA：dashboard 變紅 + 升 Ops Manager
    // 嚴禁串接賠償 / 自動退款
    Icon: AlertTriangle,
    bg: "#FEE2E2",
    border: "#DC2626",
    color: "#7F1D1D",
    href: (id) => `/admin/work-orders/${id}`,
  },
```

`web/brand-portal/src/components/dashboard/SlaAlertBanner.tsx:147-149`

```tsx
  const hasRed = alerts.some(
    (a) => a.severity === "red" || a.alert_type === "arrival_overdue",
  );
```

`web/brand-portal/src/components/dashboard/SlaAlertBanner.tsx:180-192`

```tsx
  // 紅色警報（arrival_overdue / severity=red）優先 — F-016
  const headerBorder = hasRed ? "border-red-300" : "border-amber-200";
  const headerBg = hasRed ? "bg-red-50" : "bg-amber-50";
  ...
  return (
    <section
      data-testid="sla-alert-banner"
      data-severity={hasRed ? "red" : "amber"}
```

WS 訂閱的角色白名單，`web/brand-portal/src/components/dashboard/SlaAlertBanner.tsx:20-25`：

```tsx
const SLA_WS_ALLOWED_ROLES = new Set([
  "admin",
  "operations_manager",
  "dispatcher",
  "customer_service",
]);
```

---

## 既有測試證據

`web/brand-portal/tests/e2e/admin/sla-alerts.spec.ts:61` 的測試以 `@wip` 標記：

```
web/brand-portal/tests/e2e/admin/sla-alerts.spec.ts:61:
  test('@wip dashboard banner turns red when arrival_overdue arrives', async ({
```

同檔 `:107` 起的斷言區段為註解狀態：

```
web/brand-portal/tests/e2e/admin/sla-alerts.spec.ts:107:
    //   .locator('[data-testid="sla-alert-item"][data-alert-type="arrival_overdue"]')
```

`api/tests/` 中無針對 `sla_monitor` 的測試檔（`ls api/tests | grep sla` 無命中）。本 TC 無對應可執行的既有測試。

---

## 事實結論

1. `notify_supervisor` 在 `api` / `web` / `agent` / `SQL` 零命中，只存在於 `smartlock-docs/enterprise/08_User_Flow.md:268`、`15_SDS.md:161`、`:256` 三處文件。
2. `PT2H` 字面同樣零命中於程式碼；數值上的對應為 `ARRIVAL_OVERDUE_MINUTES` 預設 120（`api/realtime/sla_monitor.py:55`），可由環境變數 `SLA_ARRIVAL_OVERDUE_MINUTES` 覆寫。
3. `work_orders.status` 無 `dispatched` 值（`SQL/Schema.sql:468-469`）；派工後為 `assigned`。SLA 查詢以 `status='assigned'` 為條件（`api/realtime/sla_monitor.py:222`）。
4. 逾時計時錨點為 `scheduled_at`（計畫到場時間）而非派工時刻（`api/realtime/sla_monitor.py:224-226`）。
5. 「升級主管」以 payload 欄位 `escalated_to="ops_manager"`（`:241`）與 `audit_events` 一列 `action="sla.arrival_overdue"`（`:324`）承載；該路徑無 push / mail / LINE 外送呼叫，且檔內註解明載「嚴禁串接賠償 / 自動退款」（`:31-34`、`:313-316`）。
6. 「dashboard 標紅」在前端有完整落點：`arrival_overdue` 對應紅色 tone（`SlaAlertBanner.tsx:83-91`）、`hasRed` 判定（`:147-149`）、`data-severity="red"`（`:192`）。
7. SLA 機制為週期輪詢（預設 60 秒，`api/realtime/sla_monitor.py:51`）而非 `15_SDS.md:256` 描述的「狀態進入時掛 timer」；`on_breach` / flow DSL 相關識別碼在程式碼零命中。
8. 「T+2:00:01 起算 breach」的秒級精度需 runtime 觀測，靜態走查無法判定。
9. 前端 e2e 測試 `sla-alerts.spec.ts` 以 `@wip` 標記且關鍵斷言為註解狀態；`api/tests/` 無 `sla_monitor` 對應測試。
