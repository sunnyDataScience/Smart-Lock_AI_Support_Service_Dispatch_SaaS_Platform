---
id: CR-0211
title: 工單流程細節與報表顯示 —— 四支 TC 的缺口分流與裁決
status: partially-implemented
created: 2026-08-05
author: Claude（UAT 靜態走查 2026-08-03 回查證後分流）
triggers: [User/Business flow, API contract, DB schema, Test plan]
related: [TC-WO-07, TC-WO-10, TC-WO-12, TC-WEB-REPORT-01, FR-API-07, FR-API-08, FR-API-09, FR-API-11, FR-WEB-04, BR-WO-003, BR-Disp-001, CR-0039, CR-0044, CR-0165, CR-0193]
---

# CR-0211 — 工單流程細節與報表顯示

> **實作進度（2026-08-05）**：業主裁決「CIA gate 縮限為僅金流適用」後，本 CR 的非金流項依 §8 各題**建議選項**實作。
>
> **已完成**：D1（listScheduledReports 角色閘門）（commit 見 CHANGELOG [Unreleased]）。
>
> **未完成**：其餘決策為架構／規格取捨，或涉及金流（依裁決仍走 CIA）、或需外部工具與業主授權。各節內已逐項註明。


## 1. 一句話

這四支 TC 是同一種形狀：**功能寫好了，但接不到真實入口** —— 2 小時到場 SLA 紅色告警因為錨點欄位在標準流程從不寫入而永遠不觸發、部分完工取消的「完工比例」從未被傳進計費函式而恆按全額向客戶收費、報表匯出的日期區間收下即丟（連那句「不支援」的警語在預設的 CSV 路徑都看不到）、報表排程清單漏掛角色閘門讓任何持租戶 token 的角色都能讀到收件人 email；而四者的既有測試全綠，因為測試的 fixture 都繞過了真實入口。本 CR 問業主：**這四項各自要修到哪一層，還是有哪幾項其實該改的是規格不是程式碼。**

---

## 2. 需求追溯

| TC | 需求 ID | 正典出處（檔案:行號） | 條文 |
|---|---|---|---|
| TC-WO-07 | FR-API-08 | `smartlock-docs/enterprise/04_SRS.md:299` | 到府存證：「到場證明、施工照上傳…客戶簽名」；驗收欄「**結案前證據齊備檢核**」 |
| TC-WO-07 | FR-API-09 | `smartlock-docs/enterprise/04_SRS.md:300` | 結案 hard gate：「`completed` 檢核 address + quote 確認（§2.2.4）不合回 422」 |
| TC-WO-10 | FR-API-07 | `smartlock-docs/enterprise/04_SRS.md:298` | 接單 SLA 治理：「**派工→抵達 > 2hr soft SLA 標紅 + push 主管**」；關聯 `BR-Disp-001/002`、`NFR-SLA-001~003` |
| TC-WO-12 | FR-API-11 | `smartlock-docs/enterprise/04_SRS.md:302` | 退款 / 取消費：「取消費 5 階段 system 自判 + 客服全階段可覆寫 + audit」 |
| TC-WO-12 | BR-WO-003 | `smartlock-docs/enterprise/04_SRS.md:460` | 「取消費 5 階段 system 自判 + 客服全階段可覆寫 + audit」 |
| TC-WEB-REPORT-01 | FR-WEB-04 | `smartlock-docs/enterprise/04_SRS.md:321` | 儀表板與報表：「KPI dashboard（SLA 標紅、K 系列指標）+ 報表匯出」；驗收欄「**數字與 API 對帳一致**」 |

追溯鏈另一端（測試計畫）：`smartlock-docs/enterprise/20_Test_Cases.md:79`（FR-API-07 → TC-WO-10）、`:80`（FR-API-08 → TC-WO-07）、`:81`（FR-API-09 → TC-WO-07）、`:83`（FR-API-11 → TC-WO-12）、`:430`（TC-WEB-REPORT-01 全列）。

### 2.1 正典明確站在程式碼的對面（一項）

**FR-API-07 的錨點是「派工」，不是「客戶約定時間」。**
`04_SRS.md:298` 原文為「**派工→抵達** > 2hr soft SLA 標紅」。
現行實作以 `work_orders.scheduled_at`（計畫到場時間）為起算：
`api/realtime/sla_monitor.py:224-226` 的 `scheduled_at < NOW() - (INTERVAL '1 minute' * 120)`。
這兩個錨點在 `scheduled_at ≠ 派工時刻` 時給出完全不同的結果，而在 `scheduled_at IS NULL` 時（見 §5.2，標準流程恆為 NULL）程式碼側直接不觸發。

**這一條不是「TC 措辭與實作不同」，是實作與 SRS 條文不同。** 走查文件把它列為「有落點（錨點與 TC 敘述不同）」，判輕了。

### 2.2 正典沒有規定的邊界（兩項，本身就是要裁決的事）

1. **誰可以 override 完工硬閘？** `FR-API-09`（`04_SRS.md:300`）只規定 gate 本身，**沒有任何一句規定 override 的授權範圍**。TC-WO-07 的前置寫「主管角色」，但那是測試案例作者的措辭，不是需求條文。目前實作放行 admin / operations_manager / dispatcher / **customer_service** 四種（§5.1）。
2. **S5 的「完工比例」由誰認定？** `FR-API-11` / `BR-WO-003` 只說「5 階段 system 自判 + 客服全階段可覆寫」，沒有定義比例的來源、證據要求或核准層級。TC-WO-12 的判定基準「完工比例+車馬」出自 **ADR-0102**，而 **ADR-0102 本體不在現行文件樹**（`git grep "ADR-0102" -- smartlock-docs` 只命中 `04_SRS.md:585` 的裁決記錄與 `20_Test_Cases.md:269` 的 TC 自身；ADR 本體於 2026-07-08 大掃除後只在 git 歷史）。**這條判定基準目前沒有可讀的權威來源。**

### 2.3 正典自相矛盾（一項）

`smartlock-docs/enterprise/20_Test_Cases.md:95` 對 FR-WEB-04 的追溯狀態寫「**⚠ 完全沒有案例**」，同一份檔案 `:430` 又列出 TC-WEB-REPORT-01 一整列且掛在 FR-WEB-04 底下。**同檔前後矛盾**，依 `.claude/rules/change-governance.md` 的 Source of Truth 規則，此處停下回報、不腦補（見 D7）。

### 2.4 正典詞彙在程式碼零命中（三項，屬 as-built 漂移）

| 正典詞彙 | 出處 | 程式碼命中 |
|---|---|---|
| `notify_supervisor` 積木 | `smartlock-docs/enterprise/08_User_Flow.md:268`、`15_SDS.md:161`、`:256` | `api` / `web` / `agent` / `SQL` 四樹零命中（含 `notifySupervisor` / `notify-supervisor` / 「通知主管」多種寫法複測） |
| `PT2H` | `15_SDS.md:161` | 零命中；數值對應 `api/realtime/sla_monitor.py:55` `ARRIVAL_OVERDUE_MINUTES` 預設 120 |
| 狀態 `dispatched` | `08_User_Flow.md:268`、`15_SDS.md:161` | `work_orders.status` 值域無此值（`SQL/Schema.sql:467-469`：created / assigned / accepted / in_progress / completed / confirmed / cancelled）；派工後為 `assigned` |
| flow DSL 的 `on_breach` block 機制 | `15_SDS.md:256`（「引擎於狀態進入時掛 timer」） | `on_breach` / `flow_dsl` 零命中；實作為 60 秒週期輪詢（`api/realtime/sla_monitor.py:51`、`:98-116`） |

**這四項是文件詞彙漂移，不是程式缺陷。** 走查人員照文件字面走查，判成「無落點」是照規矩辦事；但要求程式碼去長出一個叫 `notify_supervisor` 的積木是本末倒置（見 D7）。

---

## 3. 歷史成因（為什麼會長成這樣，不是罵人）

- **TC-WO-10**：`scheduled_at` 這個欄位從 `SQL/Schema.sql:474` 建表就存在，但整條「客戶預約」流程是後來才長出來的 —— 目前唯四的寫入點全是**改期語意**（`api/services/work_order_service.py:2745` 改期提案、`:3600` 客戶 LINE RSVP、`:3825` `request_reschedule`、`:3951/3961` 駁回還原）。「第一次約幾點」從來沒有被建模成一個動作，所以沒有寫入點。SLA 監控（`sla_monitor.py`）晚於這些路徑寫成，直接假設欄位有值。
- **TC-WO-12**：`cancellation_service.py:11-13` 的檔頭自己寫明「⚠ 現行 schema 無 quote_version 表 → S1_5 / S5 的精確判定以 reason_code 字典為權威 + best-effort 推算。完整 quote lifecycle 接入見 gap audit §7 波次 P3」。`compute_fees` 預留了 `completed_ratio` 參數（`:163`）等資料源到位，資料源始終沒到位，參數就一直空著。**這是有意識的欠債，不是漏寫。**
- **TC-WEB-REPORT-01 的匯出日期**：`api/services/report_export_service.py:196-201` 的 docstring 逐字寫著「參數收下即丟，匯出的一直是全期間資料…真正支援日期區間需要改四個下游 service 的查詢，**屬 API contract 變更（要走 CIA）**」。開發者 2026-08-02 掃描時就知道，並刻意選了「標注可見」的折衷（`CHANGELOG.md:67` 有記載）。**本 CR 就是那份 docstring 在等的 CIA。**
- **TC-WO-07**：`CR-0039` 把 `:complete` 定位成「後台 override 路徑」，技師改走 `/onsite/completion` 硬閘（`api/routers/work_orders_v2.py:579-586` 註解自述）。當時解決的是「技師繞過照片閘」，角色白名單就順著既有的 `TECH_ACTION_ROLES` 扣掉 technician，沒有再往上收窄。

---

## 4. 查證補正 —— 走查沒抓到 / 判錯的四件事

走查文件對 `sla_monitor.py` / `SlaAlertBanner.tsx` / `cancellation_service.py` / `report_export_service.py` 的**所有行號引用經逐一開檔核對皆正確**。以下是補正：

### 4.1 走查文件的事實錯誤（TC-WO-10）

`docs/uat/static-walkthrough-20260803/TC-WO-10.md:306` 寫「`api/tests/` 中無針對 `sla_monitor` 的測試檔（`ls api/tests | grep sla` 無命中）」「本 TC 無對應可執行的既有測試」—— **完全錯誤**。實際存在：

- `api/tests/test_sla_monitor_arrival_overdue.py`：8 支測試（`:126` 偵測、`:151` 未逾時不觸發、`:173` completed 不觸發、`:195` dedup、`:222` 到場後 recovery、`:259` payload 無賠償欄、`:309` WS envelope、`:351` 寫 audit_events）
- `api/tests/test_sla_monitor.py`：3 支 `dispatch_delay` 測試
- 另有 `api/tests/test_cr_0019_sla_gate.py`、`api/tests/test_ops_alert_slack.py`

這個更正很重要，因為那 8 支測試**全綠**，而下面 4.2 說的缺口它們一支都測不到。

### 4.2 走查判輕：arrival_overdue 在標準流程上永遠不觸發（TC-WO-10）

告警查詢硬帶 `scheduled_at IS NOT NULL`（`api/realtime/sla_monitor.py:225`）。而 `work_orders.scheduled_at` 的寫入點盤點：

| 路徑 | 程式碼落點 | 寫 `scheduled_at`？ |
|---|---|---|
| 問題卡轉工單（建單 INSERT） | `api/services/work_order_service.py:615-628` | ❌ 欄位清單無此欄 |
| 返修子單 INSERT | `api/services/work_order_service.py:872-882` | ❌ 連原單的都不複製 |
| 手動派工 UPDATE | `api/services/work_order_service.py:2265-2273` | ❌ |
| 改派 UPDATE | `api/services/work_order_service.py:2432-2440` | ❌ |
| 改期提案 | `api/services/work_order_service.py:2744-2746` | ✅ |
| 客戶 LINE RSVP 選時段 | `api/services/work_order_service.py:3599-3601` | ✅ |
| `request_reschedule` | `api/services/work_order_service.py:3824-3826` | ✅ |
| 改期駁回還原 | `api/services/work_order_service.py:3951/3961` | ✅ |

Request model 側同樣沒有入口：`api/models/generated.py` 對 `scheduled_at` **零命中**；`api/routers/` 只出現 `new_scheduled_at`（`work_orders_ops_v2.py:88`、`work_order_actions.py:36`），即改期專用欄位。

**結論**：走「問題卡 → 轉工單 → 派工 → 等 2 小時」的標準流程，`scheduled_at` 恆為 NULL，`arrival_overdue` 紅色告警與 dashboard 標紅**永遠不會觸發**。要讓它觸發，唯一辦法是先對這張單呼叫一次「改期」（`_RESCHEDULE_FROM = {"assigned", "accepted", "in_progress"}`，`api/services/work_order_service.py:939`）—— 也就是**把「第一次約時間」當成「改期」來下**。

8 支測試之所以全綠：fixture 直接 INSERT `scheduled_at`（`api/tests/test_sla_monitor_arrival_overdue.py:78-81`）。

### 4.3 走查判輕：報表排程清單沒有角色閘門（TC-WEB-REPORT-01）

走查文件把「低權角色 403」判為**一致**，但同一份文件的端點表（`TC-WEB-REPORT-01.md:271`）自己列出了反例卻沒回收進判定。實測：

```python
# api/routers/scheduled_reports_v2.py:67-71
async def list_scheduled_reports(
    tenantId: str = Path(...),
    report_type: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    user: CurrentUser = Depends(require_tenant),      # ← 無 role_required
) -> dict:
```

同檔的 create（`:41`）與 cancel（`:95`）都是 `Depends(role_required(*OPS_ROLES))`。**只有 list 漏掛。**
而 list 回傳 `recipients`（收件人 email 陣列）與 `filters`：`api/services/scheduled_report_service.py:103`（SELECT 欄位）、`:117`（`recipients` 反序列化進 response）。

**任何持有效租戶 token 的角色**（customer_service / dispatcher / reviewer / technician / accountant）都能列舉本租戶的報表排程與收件人 email。

補充兩點對裁決有用的事實：
- 這三支端點**不在 `api/openapi.yaml`**（`grep "scheduled-report" api/openapi.yaml` 零命中），只在 runtime spec（`api/openapi-runtime.json`）。契約 SSOT 從未宣告過它的角色閘門，所以這不是「契約說 A 實作做 B」，是**契約缺頁**。
- 前端唯一的呼叫端是 `web/brand-portal/src/components/admin/ScheduledReportsListModal.tsx:75`，只被 `web/brand-portal/src/app/admin/reports/kpi/page.tsx:409` 使用，而 `/admin/reports` 前綴的前端路由政策已經只放行 `admin` / `operations_manager`（`web/brand-portal/src/lib/rolePolicy.ts:56`）。**收窄到 `OPS_ROLES` 對現有 UI 零影響。**

### 4.4 走查沒抓到：那句「日期區間不支援」的警語在 CSV 路徑看不到（TC-WEB-REPORT-01）

`report_export_service.py:192-209` 的折衷是「標注進報表 subtitle」。但 subtitle 只被 PDF 用到（`:387` `Paragraph(meta.get("subtitle", ""), subtitle_style)`），而 CSV 路徑直接把 meta 丟掉：

```python
# api/services/report_export_service.py:297-305
    rows, _meta = await _build_rows(...)      # ← meta 收進底線變數
    for row in rows:
        yield _csv_line(row)                  # ← 只吐 rows
```

而 CSV 是**預設格式**（`web/brand-portal/src/components/admin/reports/ReportExportModal.tsx:72` `useState<ExportFormat>("csv")`），也是 `api/openapi.yaml:2380-2417` 對 v2 匯出端點**唯一宣告的格式**（`content: text/csv`，description 明寫「CSV only; PDF excluded from v2」）。

**所以那個「讓它看得見」的緩解措施，在使用者實際會走的路徑上不存在。** 使用者在營收頁選了日期區間按匯出，拿到的是全期間 CSV，而且沒有任何提示。

同時 `api/openapi.yaml:2404-2410` 明確宣告了 `from` / `to` 兩個 `format: date` 參數 —— **契約承諾了、實作沒做**，這是 tier-2 契約與程式碼的直接衝突。

---

## 5. 程式碼現狀（逐 TC，含未爭議的部分）

### 5.1 TC-WO-07 — override 結案

三條判定基準：

| 判定基準 | 狀態 | 證據 |
|---|---|---|
| override 通過（跳過證據閘） | ✅ 一致 | `api/services/work_order_service.py:1541-1549`，`if is_override:` 的 `return` 位於照片閘（`:1552` 起）之前，七道閘全不執行；未填 reason → 422（`:1544-1545`） |
| 技師走 override 路徑 → 403 | ✅ 一致 | v2 `api/routers/work_orders_v2.py:581-586`、v1 `api/routers/work_orders.py:234-240`，皆 `if (user.role or "") == "technician"` 顯式擋 |
| audit 記 `COMPLETE_OVERRIDE` + 角色 + reason | ⚠ 半落地 | 見下 |

`COMPLETE_OVERRIDE` 全 repo 只有兩處命中：產生處 `api/services/work_order_service.py:1547`、測試斷言 `api/tests/test_cr_0039_completion_gate.py:155`。它作為 summary 前綴被寫進 `work_orders.service_report`：

```python
# api/services/work_order_service.py:1792-1796
    "UPDATE work_orders SET "
    "  status = 'completed', "
    ...
    "  service_report = %s, "      # ← 無條件覆寫
```

三個問題：
1. `service_report` 是**可變自由文字欄且被無條件覆寫**（對比派工路徑是 append：`:2268` `service_report = COALESCE(service_report,'') || E'\n' || %s`）—— 完工這一步會把先前累積的派工註記一起蓋掉。
2. `complete_order`（`:1727` 起）**全函式無任何 `audit_log_service.log_event` 呼叫**（唯一的留痕是 `:1893-1905` 的 `_insert_wo_event`）。而 `audit_events` 是本系統唯一有 append-only sha256 hash chain 的防竄改稽核表（`api/services/audit_log_service.py:27-29`）；`work_order_events` 沒有 hash chain（`SQL/Schema_work_order_events.sql:18-40` 無 `entry_hash` / `prev_hash`）。同檔其他治理動作都有寫 `audit_events`：急件 bypass（`:700-712`）、拒單（`:1402-1409`）、reschedule / delay（`_audit_action`）—— **唯獨完工 override 沒有**。
3. 角色與範圍：`role_required(*TECH_ACTION_ROLES)`（`api/routers/work_orders_v2.py:575`）扣掉 technician，實效等同 `BACKOFFICE_ROLES` ＝ admin / operations_manager / dispatcher / **customer_service**（`api/core/deps.py:293-297`）。且 `override_reason=body.summary`（`work_orders_v2.py:594`、`work_orders.py:249`）—— 完工摘要即 override 理由，`CompletionReport` 無獨立 reason 欄。

### 5.2 TC-WO-10 — 2 小時到場 SLA

功能面**寫得很完整**，不是沒做：閾值 120 分（`api/realtime/sla_monitor.py:55`）、60 秒週期掃描 + 分散式 leader 鎖（`:98-116`）、`severity="red"` / `escalated_to="ops_manager"`（`:236-245`）、WS 推播（`:288-291`）、寫 `audit_events`（`:310-339`）、前端 banner 紅色判定與 `data-severity="red"`（`web/brand-portal/src/components/dashboard/SlaAlertBanner.tsx:147-149`、`:181-192`）。

缺的只有一件事：**觸發條件用的欄位在標準流程沒人寫**（§4.2）。

附帶兩項與正典的差距：
- FR-API-07 寫「+ push 主管」，`arrival_overdue` 路徑上除 WS 推播與 audit log 外**無任何 push / mail / LINE 外送呼叫**（`sla_monitor.py:284-297`；同檔的 `audit_overdue` 路徑另有自動開 ChangeRequest 分支 `:396-421`，`arrival_overdue` 無對應分支）。是否算「push 主管」取決於「後台 dashboard 即時紅色橫幅」算不算 push。
- 前端 e2e `web/brand-portal/tests/e2e/admin/sla-alerts.spec.ts:60-61` 為 `@wip` 且關鍵斷言（`:106-115`）整段註解掉。

### 5.3 TC-WO-12 — 六階段取消

六個 `fee_type` 與 TC 列舉一一對應，**五個階段完全正確**（走查以本機測試庫探針實測：S1=0/0、S1.5=0/0、S2=300/0、S3=500/500、S4=1100/500）。config 定義 `api/services/cancellation_service.py:43-53`、reason code 字典 `:56-105`、計費 `:169-188`。缺 `reason_code` → pydantic 422 `VALIDATION_ERROR`（`api/models/internal.py:88-89`）、未知 code → 422 `REASON_CODE_UNKNOWN`（`:125-134`），皆一致。

缺口只有 S5：

```python
# api/services/cancellation_service.py:326-330
    base_amount = wo["final_price"] if wo["final_price"] is not None else wo["estimated_price"]
    customer_fee, travel_fee = compute_fees(
        stage, reason_entry, cancellation_config,
        base_amount=base_amount, distance_km=distance_km,   # ← 無 completed_ratio
    )
```

```python
# api/services/cancellation_service.py:182-184
    if fee_type == "partial_formula":
        ratio = 1.0 if completed_ratio is None else max(0.0, min(1.0, float(completed_ratio)))
        return (round(base * ratio, 2), _travel_fee(cancellation_config, distance_km))
```

`completed_ratio` 全 repo 三處命中：定義 `:163`、使用 `:183`、**只在 pure 函式單元測試傳值**（`api/tests/test_cancellation_6stage.py:110` 傳 0.5）。request model `CancellationRequest`（`api/models/internal.py:85-95`）沒有這個欄位，伺服器端也無推算來源。

**後果**：部分完工取消時，`ratio` 靜默取 1.0 ＝ 向客戶收工項**全額** + 車馬費（探針實測 2000 + 500）。金額直接寫進 `cancellation.customer_fee`（`:377-388`）與 hash-chained `audit_events`（`:366-374`）成為帳務憑據。**預設值站在對客戶最不利的那一端，而且無聲。**

次要（P3）：`audit_events` payload（`:348-366`）有 `cancellation_stage` / `original_amount` / `new_amount` / `travel_fee` / `technician_penalty`，但發起人只有 `operator_id`（取自 `X-Initiator` header，`api/routers/cancellation.py:54-57` 註解自承「仍是 client 提供的字串而非取自 token…SoD 的『發起人』欄位本身仍不可信」）與派生的 `technician_initiated` 布林 —— body 的 `initiator_role` 四個值（customer / customer_service / technician / system_auto）在稽核表被壓成一個 False/True，前三者不可分辨。原值落在 `cancellation` 表欄與 `work_order_events` payload（`:419-433`），但那兩處都沒有 hash chain。

### 5.4 TC-WEB-REPORT-01 — 儀表板與報表

| 判定基準逐條 | 狀態 | 依據 |
|---|---|---|
| 數字一致 | 無法靜態判定 | 畫面呈現屬執行期觀測；KPI 頁與匯出同呼 `kpi_service.get_kpi_report`（`web/.../kpi/page.tsx:120-125` / `api/services/report_export_service.py:225-227`） |
| 篩選一致 | ❌ 不一致 | §4.4。營收匯出連 `granularity` 都不傳（`report_export_service.py:233` `get_revenue_summary(tenant_id=tenant_id)`），而營收畫面會送 `granularity` + `start_date` + `end_date`（`web/.../revenue/page.tsx:155-164`） |
| 時區一致 | 無法靜態判定 | `Asia/Taipei` 於 `api` / `web/brand-portal/src` / `SQL` 字面零命中；三軌並行 —— 期間過濾用 DB `NOW()`（`api/services/kpi_service.py:40-45`）、`generated_at` 與匯出檔名用 UTC（`report_export_service.py:67-68`）、前端用瀏覽器本地時區渲染（`web/.../kpi/page.tsx:42-46`）。另 `web/brand-portal/src/app/settings/page.tsx:207-208` 顯示一個寫死的時區標籤（i18n 值 `web/brand-portal/src/i18n/messages/zh-TW.json:43` = 「(UTC+8) 台北」），**沒有任何行為支撐它** |
| 低權角色 403 | ⚠ 有一個洞 | 報表主端點閘門正確（`OPS_ROLES`，`api/routers/reports_v2.py:55`、`:97`；匯出為 admin/ops/accountant，`:29`+`:144`），但 `listScheduledReports` 漏掛（§4.3） |
| 失敗時不顯示舊租戶資料 | ⚠ 部分 | 快取層有隔離：key 含 tenant（`web/brand-portal/src/lib/api.ts:471-474`）、失敗不入快取（`web/brand-portal/src/lib/cache.ts:70-73`）、登出 `cacheClear()`（`api.ts:809-812`）。但 KPI（`kpi/page.tsx:126-132`）、營收（`revenue/page.tsx:167-171`）、技師排行（`technician-ranking/page.tsx:150-155`）三頁的 `catch` 都只 `setError`，不清空既有 state，403 / timeout 後前次數字續留畫面 |

**重要限縮**：`auth.setTenantId` 在四站台各定義一次但**全 `web/` 樹無任何呼叫端**（`web/brand-portal/src/lib/api.ts:167` 等），session 內沒有切換租戶的入口。所以「失敗時留舊數字」是**留自己租戶的舊數字，不是跨租戶外洩** —— TC 判定基準寫的「不顯示舊**租戶**資料」那個原意，已由快取 key 含 tenant 達成。這一條的真實性質是 UX 不是資安。

其他事實：`api/tests/test_reports_v2_endpoint.py` 只有 200 結構驗證與 cross-tenant 403，`customer_service` 於該檔零命中 —— **沒有任何一支測試驗過「低權角色讀報表 403」**。`brand-portal` 的 `api.ts` 對 `timeout` / `AbortController` 零命中，無 client 端逾時上限，TC 步驟「令 API timeout」在前端無對應行為可觀測。

---

## 6. 影響評估

### 6.1 rewrite vs refactor 九維打分表（`.claude/rules/change-governance.md`）

| 維度 | 分數 | 理由 |
|---|---|---|
| 產品目標是否改變？ | **0** | 沒變。四支都是既有功能的補完 |
| 核心 User Flow 是否改變？ | **1** | 新增分支：派工／轉單需要一個「首次預約到場時間」入口（TC-WO-10）、取消流程需要一個「完工比例」輸入或推算（TC-WO-12）。主流程不重寫 |
| Domain Model 是否改變？ | **1** | 新增概念：「約定到場時間」要不要成為派工的一等公民、「完工比例」需要一個可稽核的來源。核心概念不改 |
| API Contract 是否大量破壞？ | **0** | 全部是加法或單點收窄：request 加可選欄位、`listScheduledReports` 補閘門（現行 UI 零影響，§4.3）、匯出把 `openapi.yaml:2404-2410` 已宣告的參數真的接上（**修的是實作向契約靠攏，不是改契約**） |
| DB Schema 是否需重建？ | **1** | 視裁決而定：D3 選 dispatch_logs 版＝零 migration；選 `assigned_at` 欄位版＝一支 ADD COLUMN（`work_orders` 目前無 `assigned_at`，`SQL/Schema.sql:474-477` 只有 accepted_at / started_at / completed_at）。D4 選伺服器推算＝需要新的完工項目資料源。migration 可處理，不痛 |
| 模組邊界是否錯誤？ | **0** | 邊界清楚。`sla_monitor` / `cancellation_service` / `report_export_service` / `work_order_service` 各司其職，缺口是欄位沒接上，不是切錯 |
| 測試是否可信？ | **2** | **本 CR 最糟的一維，且是系統性的**。四支 TC 中三支的核心缺口都被綠燈測試掩蓋，且掩蓋機制同型：① TC-WO-10 的 8 支測試全綠，但 fixture 直接 INSERT `scheduled_at`（`api/tests/test_sla_monitor_arrival_overdue.py:78-81`），繞過了真實流程寫不到該欄的事實；② TC-WO-12 的 33 支全綠，S5 只有 pure 函式測試直接餵 `ratio=0.5`（`test_cancellation_6stage.py:110`），端到端 S5 金額無人斷言，端點測試只建 S1/S2/S3 情境；③ TC-WEB-REPORT-01 的 31 支全綠，全是正向與 cross-tenant，無任何「低權角色 403」負向案例（`test_reports_v2_endpoint.py` 對 `customer_service` 零命中），所以 `listScheduledReports` 漏閘門沒被抓到。**綠燈在這四項上不構成任何保證** |
| 文件是否可信？ | **2** | 四支的判定基準有三支引用的正典詞彙在程式碼零命中（`notify_supervisor` / `PT2H` / `dispatched`，§2.4）；一支的權威來源 ADR-0102 本體已不在文件樹（§2.2）；`20_Test_Cases.md` 同檔對 FR-WEB-04 自相矛盾（§2.3）；FR-API-07 的錨點與實作直接相反（§2.1）；`openapi.yaml:2404-2410` 承諾了實作沒做的參數（§4.4）。**走查文件本身也有一處事實錯誤**（§4.1）。地圖跟世界確實脫節 |
| 團隊/AI 是否還理解系統？ | **0** | 這是本組唯一亮點。三個主缺口**都是開發者自己在註解裡標記過的已知債**：`report_export_service.py:196-201`（自述「參數收下即丟…屬 API contract 變更，要走 CIA」）、`cancellation_service.py:11-13`（自述 S5 是 best-effort，指向 gap audit §7 波次 P3）、`cancellation.py:54-57`（自述 X-Initiator 不可信）。系統是被理解的，債是被記錄的，不是失控 |
| **總分** | **7 / 18** | |

### 6.2 對分數的誠實拆解 —— 別被 7 分嚇到

7 分踩在「7–12：架構重審 + 模組拆分（多 CR + 跨 sprint）」的最低邊界。但拆開看：

- **程式碼側六維（目標／flow／domain／contract／schema／邊界）合計 3 分** —— 穩穩落在「0–6：改文件 + 局部重構」。實際要動的程式碼很小：一個 `Depends`、一個 SQL 的 `COALESCE`、一個實參透傳、四個下游查詢條件。
- **7 分是被「測試可信」與「文件可信」兩個 2 分拉上去的**，而那兩維指向的不是要改的 code，是**驗收基準本身**。

所以本 CR 的行動建議是：**程式碼工作按局部重構一次性做完（§9 步驟 1-5）；另外把「測試設計」與「正典 as-built 標注」當成兩件獨立的事各開一張卡（§9 步驟 6-7）** —— 那就是打分表說的「多 CR」的實質內容，不是把這四支小改包成大案。

### 6.3 誠實分流 —— 哪些其實不該修，哪些該降級

**① 可降級為 CIA 豁免、不必等 §8 裁決的（1 項）**

- **TC-WO-07 的 audit 寫入**：在 `complete_order` 的 override 分支補一筆 `audit_log_service.log_event(...)`，比照同檔 `:700-712` 的 fail-soft 寫法，再補一支測試斷言 `audit_events` 有該列。**單一 function 內新增稽核寫入，無 API / DB / flow 契約變動** —— 依 `change-governance.md` §Exempted 屬「純內部 refactor，無 contract 變動」。這一項不需要業主決定任何事，可以立刻做（§9 步驟 0）。

**② 不該改 code、該改文件的（4 項）**

- `notify_supervisor` 積木、`PT2H` 字面、`dispatched` 狀態、flow DSL `on_breach` 機制（§2.4）。這四項要求程式碼去長出文件裡的詞彙，是本末倒置。建議在 `20_Test_Cases.md` 的 TC-WO-10 列補 as-built 標注（比照 `15_SDS.md:221` 既有的同型標注慣例），**只新增標注、不改寫原文**。→ D7

**③ 本 CR 範圍外、建議單獨開卡的（3 項）**

- **時區正規化**：需要先裁定基準時區，再一次性落到 DB session、API 輸出、前端渲染三處，是跨模組決策，不該夾在本輪。`settings/page.tsx:207-208` 那個寫死的「(UTC+8) 台北」標籤要一併處理（現在它是純裝飾且會誤導）。
- **前端 client timeout 上限**：`api.ts` 無 `AbortController`，TC 步驟「令 API timeout」目前無行為可測。這是一個獨立的前端韌性需求，不是報表功能的缺口。
- **`X-Initiator` 取自 header 而非 token**（`cancellation.py:54-57` 自述）：屬 SoD 身分可信度問題，與 RBAC/SoD 那條線同源，不應在本 CR 解。

**④ 我認為判定基準本身該修的（1 項）**

- **TC-WEB-REPORT-01「失敗時不顯示舊租戶資料」**：這條的原意（跨租戶外洩）已經達成 —— 快取 key 含 tenant、失敗不入快取、登出清快取，且 session 內根本沒有切租戶入口（`auth.setTenantId` 全樹無呼叫端）。剩下的「留自己租戶的舊數字」是 UX 問題。建議把判定基準拆成兩條：資安條（已通過）與 UX 條（D6 決定怎麼做）。

### 6.4 不修的代價

| 項目 | 不修的後果 | 現在有沒有在發生 |
|---|---|---|
| TC-WO-12 S5 完工比例 | 部分完工取消向客戶收全額，金額進 hash-chained `audit_events` 成帳務憑據，事後校正要走 reversal | **無法確認** —— 我沒有 prod 讀權限，未查 prod 有多少張 S5 取消單。這一項列入 D4 的子問題 |
| TC-WO-10 SLA 錨點 | 一個 P1 的 soft SLA 治理機制寫完了但從不觸發；更糟的是它**看起來有在運作**（有 job、有測試、有前端 banner），下一個讀這段的人會以為到場 SLA 已受控 | 是。除非有人先對該單下過一次「改期」 |
| TC-WEB-REPORT-01 匯出日期 | 使用者選定期間匯出，拿到全期間資料且**無任何提示**（CSV 路徑看不到 subtitle 警語）；若拿去對帳會直接對錯 | 是 |
| TC-WEB-REPORT-01 排程清單 RBAC | 同租戶內低權角色可讀報表排程與收件人 email（PII） | 是（但需持有效租戶 token，非匿名） |
| TC-WO-07 override 角色 | 客服可跳過照片≥3／簽名／序號的 P0 完工硬閘結案 | 是 |

---

## 7. 可行路徑（技術選項，不含裁決）

### 7.1 TC-WO-10 的兩條路

**路線 A —— 補資料（讓 `scheduled_at` 有第一次寫入點）**
在轉工單／派工請求加可選 `scheduled_at`：`api/models/generated.py` 的轉單／派工 body、`api/routers/problem_cards_v2.py` 轉單端點、`api/routers/work_orders_v2.py` assign 端點、`api/services/work_order_service.py:615` INSERT 與 `:2265` UPDATE 各補一欄；brand-portal 派工對話框補時間輸入。
命中 **API contract + User/Business flow**。零 migration（欄位已存在）。

**路線 B —— 改錨點（讓查詢不依賴 `scheduled_at`）**
`api/realtime/sla_monitor.py:220-228` 的查詢改為 `COALESCE(scheduled_at, <派工時刻>)`。派工時刻兩個取法：
- **B1（零 migration）**：join `dispatch_logs`，取該單最近一筆 `action IN ('assign','reassign')` 的 `created_at`。該表在手動派工（`work_order_service.py:2278-2282`）與改派（`:2445`）都已寫入，欄位定義見 `SQL/Schema.sql:807-818`。
- **B2**：新增 `work_orders.assigned_at` 欄（現行無此欄，`SQL/Schema.sql:474-477`）＋ migration ＋ 派工路徑回填。
命中 **DB schema**（B2）或僅查詢改寫（B1）。B1 只改一段 SQL。

**語意差別要說清楚**：`scheduled_at` ＝「跟客戶約好幾點」，派工時刻 ＝「單子丟給師傅的時間」。這是兩個不同的 SLA，不是同一個的兩種算法。`04_SRS.md:298` 的條文是後者。

### 7.2 TC-WO-12 的兩條路

**路線 1 —— request 加欄位（快）**
`CancellationRequest`（`api/models/internal.py:85-95`）加 `completed_ratio: float | None = Field(default=None, ge=0, le=1)`；`api/routers/cancellation.py:72-89` 透傳；`api/services/cancellation_service.py:327-330` 傳進 `compute_fees`；brand-portal 取消對話框補輸入。命中 **API contract + User/Business flow**（S5 收費金額改變＝對客戶端行為變更）。

**路線 2 —— 伺服器推算（正解）**
由完工項目 / quote line item 的完成標記推算比例。現行 schema **無此來源**（`cancellation_service.py:11-13` 明載，指向 gap audit §7 波次 P3）。需先設計資料源 → 額外命中 **DB schema + Domain model**，規模升到「大」。

**一個獨立的守線子問題**：不論走哪條，`completed_ratio` 沒帶時要不要繼續靜默用 1.0？現在的預設值是「對客戶最不利且無聲」。

### 7.3 TC-WEB-REPORT-01 的三塊

- **RBAC**：`api/routers/scheduled_reports_v2.py:71` 補 `Depends(role_required(*OPS_ROLES))`，與同檔 `:41` / `:95` 對齊；補一支 `customer_service token → 403` 的負向測試；順便把三支端點補進 `api/openapi.yaml`（目前缺頁，§4.3）。
- **匯出日期區間**：`report_export_service.py:212-236` 的 `_build_rows` 把 `from_date` / `to_date` / `granularity` 往下游傳。下游能力盤點：**kpi 已有** `_date_range_clause`（`api/services/kpi_service.py:48-53`）；**revenue 已收** `start_date` / `end_date`（`api/routers/reports_v2.py:107-112` 已在用）；`technician_ranking` / `accounting` 需新增查詢條件。
  UI 側的實際流量：只有營收頁會送 `from` / `to`（`revenue/page.tsx:507-511`），KPI 頁送 `period`（`kpi/page.tsx:399`），技師排行送 `filters={{}}`（`technician-ranking/page.tsx:477`），`accounting` **沒有任何 UI 入口**（只能直接打 API）。→ **接上 kpi + revenue 就覆蓋了 100% 的 UI 流量。**
- **失敗清畫面**：三頁的 `catch` 各補一行，或改成 error 態時不渲染卡片。

---

## 8. 🛑 Human Decisions Required

> 每個決策點只需回「D<n> 選 <字母>」。有子問題的會標明。

### D1：`listScheduledReports` 沒有角色閘門（TC-WEB-REPORT-01，安全）

任何持有效租戶 token 的角色都能列出本租戶的報表排程與收件人 email（`api/routers/scheduled_reports_v2.py:71` 只掛 `require_tenant`；回傳含 `recipients`，`api/services/scheduled_report_service.py:103`、`:117`）。同檔 create / cancel 都是 `OPS_ROLES`。

- **(a)** 對齊同檔 create / cancel，收窄到 `OPS_ROLES`（admin / operations_manager）
  - 代價：**零**。唯一呼叫端 `ScheduledReportsListModal.tsx:75` 只被 `/admin/reports/kpi` 頁使用，該前綴前端路由已只放行 admin / operations_manager（`web/brand-portal/src/lib/rolePolicy.ts:56`）
- **(b)** 放寬到 `BACKOFFICE_ROLES`（含 dispatcher / customer_service），但 response 遮蔽 `recipients`
  - 代價：要在 service 加欄位遮蔽邏輯；且沒有任何 UI 需要低權角色看排程
- **(c)** 維持現狀，只把三支端點補進 `api/openapi.yaml` 宣告「唯讀清單不設角色閘門」
  - 代價：把漏設正當化，且 email 是 PII

**我的建議：(a)。** 理由：同檔另兩支已是 `OPS_ROLES`，不對稱本身就是漏設而非設計；`recipients` 是 email PII；收窄對現有 UI 零影響（已實測呼叫端）。這是本組唯一「有洞、範圍最小、無爭議」的一項。

---

### D2：報表匯出的日期區間怎麼處理（TC-WEB-REPORT-01）

`api/openapi.yaml:2404-2410` 宣告了 `from` / `to`，實作收下即丟（`report_export_service.py:196-201` 自述），而那句「不支援」的警語只寫進 PDF subtitle，CSV（預設格式、openapi 唯一宣告格式）看不到（§4.4）。

- **(a) 全部接上**：四個下游 service（kpi / revenue / technician_ranking / accounting）都吃 `from` / `to` + `granularity`
  - 代價：最大。`accounting` 的期間語意（入帳日 vs 完工日 vs 結算日）需要另外裁決，會把本 CR 拖進會計口徑討論
- **(b) 接上 kpi + revenue，另兩種明確回 422 拒收 `from`/`to`**
  - 代價：小。下游能力現成（kpi 有 `_date_range_clause`、revenue 已收 start/end_date）；且 UI 只有營收頁送 `from`/`to`，技師排行送空 filters，accounting 無 UI 入口 → **422 在現行 UI 上永遠不會發生**
- **(c) 全部回 422**，前端拿掉日期欄位，明確宣告匯出只支援全期間
  - 代價：打壞既有 UI；使用者確實需要期間匯出（營收對帳）
- **(d) 維持現狀，把警語塞進 CSV 第一列**
  - 代價：治標。使用者拿到的還是錯資料，只是這次知道錯了

**我的建議：(b)。** 理由：讓「畫面上有的篩選＝匯出裡有的篩選」在有下游能力的兩種報表上真的成立，另兩種明確拒絕遠比靜默給全期間安全；且避開 accounting 期間口徑這個獨立的大問題（可另開卡）。

---

### D3：2 小時到場 SLA 告警的計時錨點（TC-WO-10，功能目前是死的）

`arrival_overdue` 查詢要 `scheduled_at IS NOT NULL`（`api/realtime/sla_monitor.py:225`），而 `scheduled_at` 只有改期／RSVP／延誤四條路徑會寫，建單、派工、改派、返修全不寫（§4.2）→ 標準流程上告警永遠不觸發。而 `04_SRS.md:298` 的條文錨點是「**派工**→抵達」。

- **(a) 只補資料**：轉單／派工請求加可選 `scheduled_at`，前端派工對話框補時間欄位（§7.1 路線 A）
  - 代價：改 API contract + 前端表單 + 營運習慣（派工時要多填一個時間）；**沒填的單仍然不觸發告警**
- **(b) 只改錨點**：查詢改 `COALESCE(scheduled_at, dispatch_logs 最近一筆 assign/reassign 的 created_at)`（§7.1 路線 B1，零 migration）
  - 代價：一段 SQL。語意變成「派工後 2 小時未開工就標紅」—— 這正是 `04_SRS.md:298` 的字面。缺點是不知道客戶約幾點，對「約明天下午」的單會誤報
- **(c) 兩者都做**：有 `scheduled_at` 用 `scheduled_at`，沒有就退回派工時刻（先做 (b)，(a) 另開卡）
- **(d) 不修**：承認 v1 不提供到場 SLA 告警，在 `20_Test_Cases.md` 標注 TC-WO-10 為 deferred，並在 `sla_monitor.py` 加註解說明它目前不具效力
  - 代價：留一個「看起來有在運作、實際不運作」的治理機制 —— 比明確關掉更危險

**我的建議：(c)，且先做 (b)。** 理由：`04_SRS.md:298` 的錨點本來就是派工，現行實作把「約定時間 +2h」當成「派工 +2h」是根本錯配；(b) 零 migration、單檔一段 SQL，能讓告警在**既有資料上立刻活起來**；(a) 是正確但需要營運配合的長線工作，不該擋住 (b)。
**子問題 D3-2**：`04_SRS.md:298` 還寫了「+ push 主管」，現行只有 WS 推播到後台 dashboard 與寫 `audit_events`，無 push / mail / LINE 外送（`sla_monitor.py:284-297`）。後台紅色橫幅算不算「push 主管」？算 → 不動；不算 → 需要新增外送通道（**另開卡，不在本 CR**）。

---

### D4：S5「完工比例」從未被套用，部分完工取消恆收全額（TC-WO-12）

`cancel_work_order_6stage` 呼叫 `compute_fees` 時不傳 `completed_ratio`（`api/services/cancellation_service.py:327-330`），`ratio` 靜默取 1.0（`:183`）→ 向客戶收工項全額 + 車馬（探針實測 2000 + 500）。request model 沒有這個欄位，伺服器端也無推算來源。

- **(a) request 加 `completed_ratio` 欄位**，由客服在取消對話框輸入（§7.2 路線 1）
  - 代價：改 request schema + 前端；「比例由誰認定、要不要證據」全靠人為判斷，可能被客訴挑戰
- **(b) 伺服器推算**：由完工項目 / quote line item 完成標記推算（§7.2 路線 2）
  - 代價：現行 schema 無此資料源，要先設計；規模升到「大」，跨 sprint
- **(c) 明確關掉比例計費**：S5 改成固定費率（比照 S4 的 檢測費+取消費），承認 v1 不做比例計費
  - 代價：與 ADR-0102 的判定基準不符，但 ADR-0102 本體已不在文件樹（§2.2），需要你重新拍板
- **(d) 不動**，在 `20_Test_Cases.md` 標注 S5 為 deferred
  - 代價：繼續向部分完工取消的客戶收全額

**我的建議：(a) + 守線。** 理由：(b) 是正解但要等資料源，中間這段時間客戶還在被收全額；(c) 需要你重新定義商業規則且沒有正典可依；(a) 能立刻讓「收多少」變成一個有人負責的決定。
**子問題 D4-2（守線，我強烈建議一起做）**：`completed_ratio` 沒帶時要不要繼續靜默用 1.0？
  - **(i)** 改為 422 要求明確填寫（含明確填 1.0）
  - **(ii)** 維持靜默 1.0
  我建議 **(i)**：現在的預設值站在對客戶最不利的一端而且無聲，至少要讓「收全額」是有人按下去的。
**子問題 D4-3**：既有已用 ratio=1.0 收費的 S5 取消單要不要追溯校正？
  - **(i)** 不追溯（視為 v1 既定政策）
  - **(ii)** 追溯，走 reversal entry
  - **(iii)** 先查 prod 有幾張再決定
  我建議 **(iii)**：**我沒有 prod 讀權限，未查過實際筆數**（本 CR 全程未連線 prod），這個數字會直接決定 (i) / (ii)。

---

### D5：override 完工的角色範圍與理由欄位（TC-WO-07）

`:complete` 端點放行 admin / operations_manager / dispatcher / **customer_service**（`api/routers/work_orders_v2.py:575` + `:581-586`、`api/core/deps.py:293-297`），即客服可跳過照片≥3／簽名／序號的 P0 完工硬閘；且 `override_reason = body.summary`（`work_orders_v2.py:594`），完工摘要即 override 理由，無獨立欄位。**FR-API-09 沒有規定 override 的授權範圍**（§2.2）。

- **(a)** 收窄到 `OPS_ROLES`（admin / operations_manager）＋ `CompletionReport` 加獨立 `override_reason` 欄
  - 代價：dispatcher 不能代結案（實務上派工員可能需要）；契約加欄位 + 前端表單改
- **(b)** 收窄到 `DISPATCH_ROLES`（＋dispatcher，排除 customer_service）＋ 加獨立 `override_reason` 欄
  - 代價：同上但保留 dispatcher；客服要代結案得走 escalation
- **(c)** 只收窄角色到 `DISPATCH_ROLES`，不加獨立理由欄位
  - 代價：理由與摘要仍無法區分，稽核時看不出「為什麼跳過硬閘」
- **(d)** 都不改，在 `20_Test_Cases.md` 標注 TC-WO-07 前置的「主管角色」實為後台四角色
  - 代價：客服繼續能繞過 P0 完工硬閘

**我的建議：(b)。** 理由：TC 前置寫「主管角色」，而客服是最沒有現場資訊的角色，讓它能跳過照片／簽名硬閘與 FR-API-08「結案前證據齊備檢核」的意圖相衝；dispatcher 有派工上下文，實務上確實可能需要代結。獨立 `override_reason` 欄位值得加 —— 現在稽核時看到的是一段完工摘要，看不出為什麼跳閘。
（若你要嚴格照 TC 字面「主管」，就是 (a)。）

---

### D6：報表頁失敗時，畫面上的舊數字怎麼辦（TC-WEB-REPORT-01）

KPI / 營收 / 技師排行三頁的 `catch` 都只 `setError`，不清空既有 state（`kpi/page.tsx:126-132`、`revenue/page.tsx:167-171`、`technician-ranking/page.tsx:150-155`）。**注意**：這是「留自己租戶的舊數字」，不是跨租戶外洩（§5.4、§6.3-④）。

- **(a) 清空**：`setReport(null)`，錯誤時畫面全空 + 錯誤訊息
  - 代價：暫時性網路抖動也會把整頁清掉，體感很差
- **(b) 保留但標示為過期**：灰階 + 「資料為 HH:mm 的快照，本次更新失敗」
  - 代價：多一點前端工作（三頁各一個 stale 標示）
- **(c) 不改**，把 TC 判定基準拆成資安條（已通過）與 UX 條（列 backlog）

**我的建議：(b)。** 理由：判定基準的原意（跨租戶）已由快取 key 含 tenant（`api.ts:471-474`）+ 登出 `cacheClear()`（`:809-812`）達成，而且 session 內根本沒有切租戶入口（`auth.setTenantId` 全樹無呼叫端）。剩下的是 UX 問題，(b) 的資訊量比 (a) 高 —— 使用者看得到數字，也知道它不是最新的。

---

### D7：正典側的三項標注（不改 code）

依 `smartlock-docs/` 只可新增標注、不可改寫原文的規則，以下三項要你點頭才動：

1. **TC-WO-10 的 as-built 標注**：在 `20_Test_Cases.md` 的 TC-WO-10 列補注 —— `notify_supervisor` 積木 / `PT2H` / `dispatched` 為 flow DSL 的 to-be 詞彙，現行 as-built 為「60 秒週期輪詢 + `SLA_ARRIVAL_OVERDUE_MINUTES` 環境變數閾值 + `escalated_to=ops_manager` 欄位 + `audit_events` 留痕」，狀態對映 `dispatched → assigned`（比照 `15_SDS.md:221` 既有的同型標注）
2. **FR-WEB-04 追溯矛盾**：`20_Test_Cases.md:95` 寫「⚠ 完全沒有案例」，`:430` 又列 TC-WEB-REPORT-01 —— 兩者擇一標注更正
3. **ADR-0102 本體遺失**：TC-WO-12 的判定基準（六階段費用公式）目前沒有可讀的權威來源，只有 `04_SRS.md:585` 的裁決記錄。建議在 `04_SRS.md` FR-API-11 旁補注「六階段費率的現行 as-built 定義見 `api/services/cancellation_service.py:43-105`」，或從 git 歷史撈回 ADR-0102 重新歸檔

- **(a)** 三項都做
- **(b)** 只做 1（TC-WO-10 標注），2 / 3 另議
- **(c)** 都不做，維持現狀

**我的建議：(a)。** 理由：三項都是純新增標注、零程式碼風險，而它們正是 §6.1 「文件可信 = 2 分」的具體來源。不處理的話，下一輪走查會再判一次同樣的「不一致」。

---

## 9. Suggested Implementation Order

**步驟 0 可在裁決前開始**（CIA 豁免，§6.3-①）；**步驟 1 起須等 §8 裁決**。

| # | 工作 | 相依 | 可平行？ | 驗證方式 |
|---|---|---|---|---|
| **0** | **TC-WO-07 audit 寫入**：`complete_order` override 分支補 `audit_log_service.log_event(event_type="work_order", action="complete_override", …)`，比照 `work_order_service.py:700-712` 的 fail-soft 寫法 | 無（CIA 豁免） | ✅ 與所有步驟平行 | 新增測試斷言 `audit_events` 有該列且 `payload` 含 `override_reason` / `actor_role`；`pytest api/tests/test_cr_0039_completion_gate.py` |
| **1** | **D1 RBAC**：`scheduled_reports_v2.py:71` 補 `Depends(role_required(*OPS_ROLES))` ＋ 三支端點補進 `api/openapi.yaml` | D1 | ✅ 與 2/3/4/5 平行 | 新增負向測試：`customer_service` token → 403；`admin` token → 200。跑 `api/tests/test_reports_v2_endpoint.py` 全套對照基線 |
| **2** | **D3-(b) SLA 錨點**：`sla_monitor.py:220-228` 查詢改 `COALESCE(scheduled_at, dispatch_logs.created_at)` | D3 | ✅ | **必須新增**一支測試：工單只有 `dispatch_logs` 派工紀錄、`scheduled_at IS NULL` → 逾 120 分應觸發（現行 8 支測試全部繞過這個情境，`test_sla_monitor_arrival_overdue.py:78-81`） |
| **3** | **D4-(a) S5 完工比例**：`internal.py:85-95` 加 `completed_ratio` → `cancellation.py:72-89` 透傳 → `cancellation_service.py:327-330` 傳入；D4-2 若選 (i) 則 `partial_formula` 未帶 ratio 改 422 | D4、D4-2 | ✅ | **端到端**測試（非 pure 函式）：S5 帶 ratio=0.5 且 `estimated_price=2000` → `cancellation.customer_fee` 落庫為 1000；未帶 ratio → 依 D4-2 斷言 422 或 2000 |
| **4** | **D5 override 角色/理由**：`work_orders_v2.py:575` 與 `work_orders.py:231` 的 `role_required` 收窄；若加欄位則 `CompletionReport` + 兩支 router + 前端完工表單 | D5、**步驟 0**（先有 audit 寫入才驗得到 reason 落點） | ⚠ 依賴步驟 0 | 負向測試：`customer_service` token 打 `:complete` → 403；`operations_manager` → 200 且 `audit_events` 的 `override_reason` 為獨立欄位值 |
| **5** | **D2 匯出日期區間**：`report_export_service.py:212-236` 的 `_build_rows` 往下游傳 `from_date`/`to_date`/`granularity`；kpi 走 `kpi_service._date_range_clause`、revenue 走既有 `start_date`/`end_date`；另兩種依 D2 決定 422 或不動 | D2、**步驟 1**（同檔區域，避免衝突） | ⚠ 排在 1 之後 | 測試：帶 `from`/`to` 的 kpi 匯出 rows 數 ≠ 全期間 rows 數；revenue 同理；`technician_ranking` 帶 `from` → 依 D2 斷言 |
| **6** | **D6 前端失敗態**：三頁 `catch` 依裁決改 | D6 | ✅ 與 1-5 全平行（純前端） | brand-portal `npm run build` + TS 0 error；手動或 e2e 驗 403 後畫面標示 |
| **7** | **D7 正典標注**：`20_Test_Cases.md` 補 TC-WO-10 as-built 標注、FR-WEB-04 矛盾更正、FR-API-11 補 as-built 指向 | D7 | ✅ | 人工複核「只新增、未改寫原文」 |
| **8** | **測試設計補洞（獨立卡，§6.2）**：把「fixture 直接寫入真實流程寫不到的欄位」這個模式當成 review checklist 條目；報表端點補齊低權角色負向案例 | 步驟 1-5 完成後 | — | 另開 CR |
| **9** | 收尾：`CHANGELOG.md` `[Unreleased]`、`27_Roadmap` WBS 對應項、本 CR §8 加「### 進度」區塊記 commit sha | 全部 | — | — |

**序列相依只有兩處**：步驟 4 依賴步驟 0（要先有 `audit_events` 寫入，才驗得到 override reason 有沒有正確落到獨立欄位）；步驟 5 排在步驟 1 之後（同一批報表檔案，避免衝突）。其餘全可平行。

**驗證基線注意**：依 `.claude/context` 既有慣例，跑 api 全套前先用 stash + pre-migration dump 建基線對照，判斷失敗是否為本次造成；**不要對 5433 埠的 UAT 庫跑 pytest**。

---

## 附錄：本 CR 的查證方式

- 全部結論以 `git` 工作區 HEAD（`01114100`）為準逐一開檔核對，非沿用走查文件的 commit（`17aa40c5` / `2cfeca92`）。行號若與走查文件不同，以本 CR 為準。
- 「零命中」皆為實跑 `git grep` 結果，非推測；`notify_supervisor` 另以 `notifySupervisor` / `notify-supervisor` / 「通知主管」三種寫法複測。
- `scheduled_at` 寫入點盤點以 `grep -n "scheduled_at" api/services/work_order_service.py` 全檔掃描 + 逐段開檔確認 UPDATE/INSERT 欄位清單，非只看註解。
- **未連線 prod、未跑任何 pytest、未啟動任何服務。** 因此 D4-3（既有 S5 取消單筆數）標記為「無法確認」，需要有 prod 讀權限的人補查。
- 走查文件 `TC-WO-10.md:306` 的「無 sla_monitor 測試」一句經 `ls api/tests | grep sla` 實測為誤，已於 §4.1 更正。
