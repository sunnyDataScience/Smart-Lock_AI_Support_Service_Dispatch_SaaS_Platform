# TC-QUOTE-06 — 急件完工後 4h 內補 retrospective quote

> ## 🔄 判定更正（2026-08-05 回程式碼查證）
>
> **原判定「部分實作」→ 更正為「一致」。以下原文保留未改動。**
>
> 本文件引用逐一覆核無誤，但判定基準的「audit_lag 檢核」在實作中是以 `quote.audit_due_at` 逾窗檢核的形式落地（`api/services/quote_engine_service.py:238` 的 overdue 與 `api/realtime/sla_monitor.py:250-272` 的 `audit_overdue` 告警），而非一個叫 audit_lag 的數值指標。語意等價，屬命名差異。
> 若業主確實要一個數值型 audit_lag 指標，那是新增需求，需另開 CR（會命中 API contract）。
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
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務；`api/tests/test_cr_0129_retro_audit.py` 需資料庫，無 DB 時 failed 而非 skipped（見步驟 6） |
| 走查時間 | 2026-08-03 17:22（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/services/work_order_service.py`、`api/services/quote_engine_service.py`、`api/realtime/sla_monitor.py`、`api/routers/quote_v2.py`、`SQL/migrations/091-quote-before-dispatch.sql`、`SQL/migrations/092-retrospective-audit-engine.sql` |
| 優先級 / 路徑類型 | P1 / 例外 |
| 事實結論 | `retrospective_audit_only` 標記、4h 補審窗（`quote.audit_due_at`）、逾時升 `ops_manager` 三者在程式碼中連續可追；判定基準指名的 `audit_lag` 檢核在 `api`／`web`／`agent`／`SQL` 全數零命中，只出現於 `smartlock-docs/enterprise/20_Test_Cases.md`。 |

**TC 原文**｜前置：急件（locked_out 等）完工後｜步驟：客服 4h 內補 retrospective quote｜判定基準：retrospective_audit_only 標記 + audit_lag 檢核；逾時升主管 review｜需求：FR-API-01、FR-API-02｜旅程：SC-03

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客服 | 急件開單（convert） | `EmergencyBypassed` | 急件跳過事前報價閘 | `api/services/work_order_service.py:694-698`、`:700-716` | 建 `retrospective_audit_only` 佔位報價 + 寫 `emergency_bypass` audit log |
| 技師 | 完工回報 | `AuditWindowStarted` | 完工起算 4h | `work_order_service.py:1491-1516`、`:1821-1826` | `UPDATE quote SET audit_due_at = NOW() + INTERVAL '1 hour' * hours` |
| 客服 | 補明細 → 補審完成 | `RetrospectiveAuditCompleted` | 僅急件單可走 | `api/services/quote_engine_service.py:41`、`:489-504` | `audit_complete`：`{retrospective_audit_only, sent} → accepted`，`sent` 起點加急件驗證 |
| 系統 | 逾時掃描 | `AuditOverdueAlerted` | 升主管 | `api/realtime/sla_monitor.py:247-272` | 產 `audit_overdue` alert，`escalated_to='ops_manager'` |
| 系統 | audit_lag 檢核 | `AuditLagChecked` | — | — | **找不到** `audit_lag` 於程式碼 |

---

## 走查紀錄

### 步驟 1 — `retrospective_audit_only` 標記是否存在並在急件開單時建立

- **動作**：讀 convert 分支
- **預期**：急件（`pc.emergency_class` 非空）建佔位報價
- **實際**：一致

`api/services/work_order_service.py:694-698`

```python
    else:
        await _qe.create_quote(
            tenant_id=tenant_id, work_order_id=new_wo_id, created_by=created_by,
            urgent=True, initial_state="retrospective_audit_only")
        # 15_SDS §4.5 步驟1：急件跳過事前報價開單，audit 記 emergency_bypass（fail-soft）
        from services.audit_log_service import log_event
```

狀態列舉定義於 `SQL/migrations/091-quote-before-dispatch.sql:34-36`（`'急件另有 retrospective_audit_only →（補審簽認）accepted（ADR-015①/CR-0128）'`），OpenAPI 亦列於 `api/openapi.yaml:5715`。

### 步驟 2 — 4h 窗是否從完工起算

- **動作**：讀 timer
- **預期**：完工回報時寫 `audit_due_at = NOW()+4h`
- **實際**：一致。窗長預設 4，可由 M18 config `emergency_audit_policy.audit_window_hours` 覆蓋

`api/services/work_order_service.py:1496-1516`

```python
    hours = 4
    cfg = await config_m18_service.read_global_value(namespace="emergency_audit_policy")
    if isinstance(cfg, dict):
        try:
            hours = int(cfg.get("audit_window_hours", 4))
        except (TypeError, ValueError):
            pass
    cur = await db_module._conn.execute(
        "UPDATE quote q SET audit_due_at = NOW() + (INTERVAL '1 hour' * %s), updated_at = NOW() "
        "FROM work_orders wo JOIN problem_cards pc ON wo.problem_card_id = pc.id "
        "WHERE q.work_order_id = wo.id AND wo.id = %s::uuid "
        "  AND pc.emergency_class IS NOT NULL "
        "  AND q.audit_due_at IS NULL "
        "  AND q.state IN ('retrospective_audit_only', 'sent')",
        (hours, wo_id),
    )
```

呼叫點在 `complete_order`（`work_order_service.py:1821-1826`），以 try/except 包住，起算失敗記 exception 但不阻斷完工。

欄位定義 `SQL/migrations/092-retrospective-audit-engine.sql:20-25`

```sql
ALTER TABLE quote
    ADD COLUMN IF NOT EXISTS audit_due_at TIMESTAMP WITH TIME ZONE;
COMMENT ON COLUMN quote.audit_due_at IS
    '急件補審截止（CR-0129/15_SDS §4.5）：急件單完工回報時寫 NOW()+PT4H（config 可調）；'
    'NULL=非急件補審單。sla_monitor 掃逾期告警升主管；連 3 件逾時自動開 ChangeRequest';
```

### 步驟 3 — 客服補報價的路徑

- **動作**：讀狀態機與補審端點
- **預期**：4h 內可補明細並完成補審
- **實際**：一致。`add_line` 允許 `retrospective_audit_only` 加品項；`audit_complete` 由佔位態或 `sent` 轉 `accepted`

`api/services/quote_engine_service.py:38-41`

```python
    # retrospective_audit_only 佔位報價 → 完工回報起算 4h 窗（audit_due_at）→
    # 客服補明細 → LIFF 事後確認（send→accept）或紙本簽認（audit_complete）→ accepted。
    # audit_complete 亦允許 sent 起點（已送 LIFF 但客戶改簽紙本）——service 層限定急件單。
    "audit_complete": ({"retrospective_audit_only", "sent"}, "accepted"),
```

`api/services/quote_engine_service.py:489-497`

```python
    # CR-0129：audit_complete 僅限急件補審單——佔位態（retrospective_audit_only）天然急件；
    # sent 起點須為急件補審（曾為佔位/已起算 audit_due_at 或急件 PC），防一般 sent 報價
    # 繞過客戶 LIFF 確認。
    if action == "audit_complete" and cur[0] == "sent":
        em = await (await conn.execute(
            "SELECT 1 FROM quote q "
            "LEFT JOIN problem_cards pc ON q.problem_card_id = pc.id "
            "WHERE q.id = %s::uuid AND (q.audit_due_at IS NOT NULL OR pc.emergency_class IS NOT NULL) "
            "LIMIT 1", (quote_id,))).fetchone()
```

`api/services/quote_engine_service.py:298`（`add_line` 允許態）

```python
    if q[0] not in ("draft", "pending_approval", "retrospective_audit_only"):
        raise ApiError("STATE_CONFLICT", f"cannot add line to quote in '{q[0]}'", 409)
```

補審佇列端點 `api/routers/quote_v2.py:109-119`（`GET /tenants/{tenantId}/quotes/audit-queue`，`role_required(*OPS_ROLES)`），service 為 `quote_engine_service.list_audit_queue`（`:215-246`），回傳含 `audit_due_at` 與 `overdue` 布林。

### 步驟 4 — `audit_lag` 檢核

- **動作**：全 repo 搜尋
- **預期**：程式碼中有 `audit_lag` 檢核
- **實際**：**找不到**。`audit_lag` 在程式碼零命中

```
git grep -rn "audit_lag"
smartlock-docs/enterprise/20_Test_Cases.md:282:| TC-QUOTE-06 | FR-0002 | 急件（locked_out 等）完工後 | 客服 4h 內補 retrospective quote | `retrospective_audit_only` 標記 + audit_lag 檢核；逾時升主管 review | 例外 | P1 |
```

TC 判定基準要求「audit_lag 檢核」；程式碼中最接近的量測為 `list_audit_queue` 以 SQL 計算的 `overdue` 布林（`quote_engine_service.py:238`：`(q.audit_due_at IS NOT NULL AND q.audit_due_at < NOW()) AS overdue`），以及 `_handle_audit_overdue` 判斷「完成但晚於窗」的 `updated_at > due`（`sla_monitor.py:389-391`），兩者皆非名為 `audit_lag` 的欄位或檢核。此處僅並陳，不裁定。

### 步驟 5 — 逾時升主管 review

- **動作**：讀 SLA 掃描
- **預期**：逾 `audit_due_at` 未完成 → 升主管
- **實際**：一致。`escalated_to` 硬編 `"ops_manager"`，`severity='red'`，並寫 audit log

`api/realtime/sla_monitor.py:248-272`

```python
        # ─── audit_overdue（CR-0129 急件補審逾時，15_SDS §4.5 步驟5）────────
        cur = await db_module._conn.execute(
            "SELECT q.id, q.work_order_id, q.tenant_id, q.audit_due_at "
            "FROM quote q "
            "WHERE q.audit_due_at IS NOT NULL "
            "  AND q.audit_due_at < NOW() "
            "  AND q.state IN ('retrospective_audit_only', 'sent')",
        )
        for r in await cur.fetchall():
            ...
                new_alerts.append(
                    {
                        "alert_type": "audit_overdue",
                        "target_id": target_id,
                        "severity": "red",
                        "escalated_to": "ops_manager",
```

audit log 落點 `sla_monitor.py:351-368`（`event_type="escalation"`、`action="sla.audit_overdue"`、`payload.policy="15_SDS §4.5 逾時升級"`）。掃描週期 `DEFAULT_INTERVAL = max(30, SLA_MONITOR_INTERVAL_SECONDS 預設 60)`（`sla_monitor.py:52`）。

### 步驟 6 — 執行既有測試

- **動作**：跑 CR-0129 / CR-0128 測試
- **預期**：取得執行證據
- **實際**：16 failed / 2 passed，失敗原因為無資料庫

```
cd api && python -m pytest tests/test_cr_0129_retro_audit.py tests/test_cr_0128_quote_gate.py -q --tb=no -rf
FAILED tests/test_cr_0129_retro_audit.py::test_completion_starts_audit_window_and_close_blocked
FAILED tests/test_cr_0129_retro_audit.py::test_normal_sent_quote_cannot_audit_complete
FAILED tests/test_cr_0129_retro_audit.py::test_audit_queue_lists_pending_and_overdue
FAILED tests/test_cr_0128_quote_gate.py::test_convert_emergency_carveout_creates_audit_placeholder
FAILED tests/test_cr_0128_quote_gate.py::test_audit_complete_transition
...
16 failed, 2 passed in 0.48s
```

失敗訊息為 `ERROR api.db:db.py:48 環境變數 POSTGRES_URI 未設定` → `AttributeError: 'NoneType' object has no attribute 'execute'`。兩檔皆無 skipif 守衛，故顯示為 failed 而非 skipped。`api/tests/` 中找不到針對 `audit_lag` 的測試（該名稱不存在）。

---

## 觀測到的其他事實

- 急件加價目錄項 `URG-01` 於 `SQL/migrations/092-retrospective-audit-engine.sql:29-36` seed，`suggested_customer_price = 1500`（CR-0129 D1a）。
- 完工結案受補審結果影響：`work_order_service.py:1602-1610` 以 `state = 'accepted' OR state = 'retrospective_audit_only' ...` 判斷（migration 092 檔頭記為「D2a 補審完成擋結案（completed→confirmed）」）。
- 前端補審佇列顯示於 `web/brand-portal/src/app/admin/quotes/page.tsx:587-615`（橘色卡片區塊 + 剩餘時間 badge），資料來源 `GET /quotes/audit-queue`（`:309`）。
- `emergency_class` 由 problem card 帶入 convert（`work_order_service.py:660-666` 的 payload），四類 carve-out 定義於 `SQL/migrations/101-emergency-class-check.sql`。
