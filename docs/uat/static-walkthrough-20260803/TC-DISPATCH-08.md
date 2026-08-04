# TC-DISPATCH-08 — 急件補審任務建立與 SLA 逾時升級

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定為原始碼走查，非執行結果** | 未啟動任何服務；`api/tests/test_cr_0129_retro_audit.py` 需資料庫，無 DB 時 failed 而非 skipped（見步驟 5） |
| 走查時間 | 2026-08-03 17:41（UTC+8） |
| 走查基準 | commit `c8687f5d` |
| 走查範圍 | `api/services/work_order_service.py`、`api/services/quote_engine_service.py`、`api/realtime/sla_monitor.py`、`api/realtime/job_registry.py`、`api/routers/quote_v2.py`、`SQL/migrations/092-retrospective-audit-engine.sql` |
| 優先級 / 路徑類型 | P0 / timeout |
| 事實結論 | 三條子基準逐條走查：①「onsite 結束即建 retrospective_audit 任務」在程式碼中沒有獨立 task 表，任務載體為 convert 開單時建立的 `retrospective_audit_only` 佔位報價，`due=+4h` 於 `complete_order`（完工回報）寫入，非 `record_arrival` 或任何名為 onsite 結束的端點；②逾 4h 升 `ops_manager` 一致；③連 3 次逾時自動開 `emergency_audit_breach` ChangeRequest 一致，判定條件為「同 `tenant_id` 最近 3 件已起算補審報價全數逾時」。 |

**TC 原文**｜前置：急件工單 onsite 結束｜步驟：SLA timer 到期前/後檢查補審任務｜判定基準：onsite 結束即建 retrospective_audit 任務（due=+4h）進小編佇列；逾 4h 未補審 → audit alert 升主管；同品牌連 3 次逾時 → 自動開 ChangeRequest｜需求：FR-API-09、FR-API-19｜旅程：SC-03

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 客服 | 急件 convert 開單 | — | — | `api/services/work_order_service.py:694-698` | 建 `retrospective_audit_only` 佔位報價（任務載體，`audit_due_at` 尚 NULL） |
| 技師 | 完工回報 | `RetrospectiveAuditTaskCreated(due=+4h)` | onsite 結束即建 | `work_order_service.py:1491-1516`、`:1821-1826` | 寫 `audit_due_at = NOW() + 4h`（非新建任務，是為既存佔位報價起算窗） |
| 系統 | 進小編佇列 | `AuditQueued` | 佇列可見 | `api/services/quote_engine_service.py:215-246`、`api/routers/quote_v2.py:109-119` | `list_audit_queue` 撈未完成補審單，逾時在前 |
| 系統 | SLA 掃描 | `AuditOverdueAlert` | 逾 4h 升主管 | `api/realtime/sla_monitor.py:248-272` | `alert_type='audit_overdue'`、`escalated_to='ops_manager'` |
| 系統 | 連 3 次逾時 | `ChangeRequestOpened` | 同品牌連 3 次 | `sla_monitor.py:374-421` | 同 `tenant_id` 最近 3 件全逾時 → INSERT `saas.change_request` type `emergency_audit_breach` |

---

## 走查紀錄

### 步驟 1 — 「onsite 結束即建 retrospective_audit 任務（due=+4h）」

- **動作**：搜尋 retrospective_audit 任務的建立點與觸發事件
- **預期**：onsite 結束觸發建立任務，due=+4h
- **實際**：**部分實作**。程式碼無獨立的 retrospective_audit 任務表；任務載體為佔位報價，建立時點為 convert 開單、而非 onsite 結束；`due=+4h` 於完工回報寫入

migration 檔頭明示不建獨立 task 表 `SQL/migrations/092-retrospective-audit-engine.sql:9-13`

```sql
--   - quote.audit_due_at：急件單完工回報時寫入（NOW()+窗長，預設 PT4H 讀 M18
--     config emergency_audit_policy.audit_window_hours）。佔位報價本身即補審任務
--     （不建獨立 task 表）；sla_monitor 掃 audit_due_at 逾期 → audit_overdue 告警。
```

佔位報價建立於 convert（開單）`api/services/work_order_service.py:694-698`

```python
    else:
        await _qe.create_quote(
            tenant_id=tenant_id, work_order_id=new_wo_id, created_by=created_by,
            urgent=True, initial_state="retrospective_audit_only")
```

`due` 寫入點為 `complete_order`（完工回報）`api/services/work_order_service.py:1819-1826`

```python
    # CR-0129 / 15_SDS §4.5：急件單完工回報＝補審 4h 窗起算——佔位/已送補審報價寫
    # audit_due_at（窗長讀 M18 config emergency_audit_policy.audit_window_hours，缺省 4h）。
    # fail-soft：起算失敗記 ERROR（可告警人工補），不阻斷完工。
    try:
        await _start_retrospective_audit_timer(wo_id)
    except Exception:  # noqa: BLE001 — timer 起算失敗不可卡死完工主流程
        logger.exception("急件補審 timer 起算失敗（需人工補 audit_due_at）wo=%s", wo_id)
```

工單子流程中與現場有關的端點為 `record_arrival`（`work_order_service.py:3237-3245`），其語意為「技師到場」（`event_type='arrival'`、補 `started_at`），與補審窗起算無關聯；程式碼中**找不到**名為 onsite 結束／onsite_end 的觸發點。

TC 判定基準寫「onsite 結束即建 retrospective_audit 任務（due=+4h）」，程式碼為「convert 開單時建佔位報價、完工回報時寫 due=+4h」。此處僅並陳，不裁定。

### 步驟 2 — 4h 窗長常數

- **動作**：讀窗長來源
- **預期**：+4h
- **實際**：一致。預設 `hours = 4`，可由 M18 config `emergency_audit_policy.audit_window_hours` 覆蓋；程式碼中**找不到** `14400` 秒常數（以 SQL `INTERVAL '1 hour' * hours` 表示）

`api/services/work_order_service.py:1496-1513`

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
        ...
```

### 步驟 3 — 進小編佇列

- **動作**：讀佇列 service 與端點
- **預期**：補審任務出現在佇列
- **實際**：一致。含未起算窗者（`audit_due_at` 為 NULL 但仍為佔位態），逾時在前

`api/services/quote_engine_service.py:224-235`

```python
    rows = await (await conn.execute(
        "SELECT q.id, q.version, q.state, q.total_amount, q.audit_due_at, "
        "       q.work_order_id, wo.document_number, wo.customer_name, "
        "       (q.audit_due_at IS NOT NULL AND q.audit_due_at < NOW()) AS overdue, "
        "       pc.emergency_class "
        "FROM quote q "
        ...
        "  AND q.state IN ('retrospective_audit_only', 'sent') "
        "  AND (q.audit_due_at IS NOT NULL OR q.state = 'retrospective_audit_only') "
        "ORDER BY overdue DESC, q.audit_due_at ASC NULLS LAST",
```

端點 `api/routers/quote_v2.py:109-119`

```python
@router.get(
    "/tenants/{tenantId}/quotes/audit-queue",
    operation_id="listAuditQueueV2",
    summary="急件補審佇列（CR-0129/15_SDS §4.5：待補審報價＋剩餘時間/逾時）", tags=["M04 Quote"],
)
async def list_audit_queue_v2(
    tenantId: str = Path(...),
    user: CurrentUser = Depends(role_required(*OPS_ROLES)),
) -> dict:
```

前端渲染 `web/brand-portal/src/app/admin/quotes/page.tsx:587-620`（急件補審佇列區塊，含剩餘時間 badge 與 `emergency_class` 標籤）。

### 步驟 4 — 逾 4h 未補審 → audit alert 升主管；連 3 次 → 自動開 ChangeRequest

- **動作**：讀 SLA 掃描與 CR 開立
- **預期**：兩者都有實作
- **實際**：一致（連 3 次的判定範圍為 `tenant_id`）

`api/realtime/sla_monitor.py:250-272`

```python
        cur = await db_module._conn.execute(
            "SELECT q.id, q.work_order_id, q.tenant_id, q.audit_due_at "
            "FROM quote q "
            "WHERE q.audit_due_at IS NOT NULL "
            "  AND q.audit_due_at < NOW() "
            "  AND q.state IN ('retrospective_audit_only', 'sent')",
        )
        for r in await cur.fetchall():
            ...
                        "alert_type": "audit_overdue",
                        "severity": "red",
                        "escalated_to": "ops_manager",
```

`api/realtime/sla_monitor.py:374-394`

```python
            cur = await db_module._conn.execute(
                "SELECT q.state, q.audit_due_at, q.updated_at "
                "FROM quote q "
                "WHERE q.tenant_id = %s::uuid AND q.audit_due_at IS NOT NULL "
                "ORDER BY q.audit_due_at DESC LIMIT 3",
                (tenant_id,),
            )
            rows = await cur.fetchall()
            if len(rows) < 3:
                return

            def _overdue(row) -> bool:
                state, due, updated = row
                if state in ("retrospective_audit_only", "sent"):
                    return True  # 本 scan 由逾期觸發；未完成且列入近 3 件即逾時中
                return bool(due and updated and updated > due)  # 完成但晚於窗

            if not all(_overdue(r) for r in rows):
                return
```

`api/realtime/sla_monitor.py:396-415`

```python
            # 已有未結案同型 CR → 不重複開
            cur = await db_module._conn.execute(
                "SELECT 1 FROM saas.change_request "
                "WHERE tenant_id = %s::uuid AND type_code = 'emergency_audit_breach' "
                "  AND state IN ('draft', 'pending_approval') LIMIT 1",
                (tenant_id,),
            )
            if await cur.fetchone():
                return
            await db_module._conn.execute(
                "INSERT INTO saas.change_request "
                "  (tenant_id, type_code, state, payload_diff, reason, created_by) "
                "VALUES (%s::uuid, 'emergency_audit_breach', 'pending_approval', %s::jsonb, %s, "
                "        '00000000-0000-0000-0000-000000000000')",
```

型別碼 seed 於 `SQL/migrations/092-retrospective-audit-engine.sql:38-41`

```sql
-- 連 3 逾時自動開 ChangeRequest 的類型碼（BR-WO-04）
INSERT INTO saas.change_request_type_dim (code, category, description) VALUES
    ('emergency_audit_breach', 'governance', '急件補審連續逾時（同租戶連 ≥3 件逾 4h 未補審）——自動開立，主管檢討急件流程')
ON CONFLICT (code) DO NOTHING;
```

TC 判定基準寫「同品牌連 3 次逾時」，程式碼判定鍵為 `quote.tenant_id`，SQL 註解與 migration 描述稱之為「同租戶」。此處僅並陳，不裁定。

### 步驟 5 — 執行既有測試

- **動作**：跑 CR-0129 測試
- **預期**：取得執行證據
- **實際**：16 failed / 2 passed（含 CR-0128 同批），失敗原因為無資料庫

```
cd api && python -m pytest tests/test_cr_0129_retro_audit.py tests/test_cr_0128_quote_gate.py -q --tb=no -rf
FAILED tests/test_cr_0129_retro_audit.py::test_completion_starts_audit_window_and_close_blocked
FAILED tests/test_cr_0129_retro_audit.py::test_audit_overdue_scan_and_consecutive_breach_cr
FAILED tests/test_cr_0129_retro_audit.py::test_audit_queue_lists_pending_and_overdue
FAILED tests/test_cr_0129_retro_audit.py::test_emergency_bypass_audit_logged
...
16 failed, 2 passed in 0.48s
```

失敗訊息為 `ERROR api.db:db.py:48 環境變數 POSTGRES_URI 未設定` → `AttributeError: 'NoneType' object has no attribute 'execute'`。兩檔皆無 skipif 守衛，故顯示為 failed 而非 skipped。針對第三條子基準的測試存在：`api/tests/test_cr_0129_retro_audit.py:171 test_audit_overdue_scan_and_consecutive_breach_cr`。

---

## 觀測到的其他事實

- SLA 掃描非 cron 而是 asyncio 常駐迴圈：`DEFAULT_INTERVAL = max(30, int(os.environ.get("SLA_MONITOR_INTERVAL_SECONDS", "60")))`（`sla_monitor.py:52`），並以 `_ensure_leader("sla_monitor")` 做單一 leader 控制（`:100`）。註冊於 `api/realtime/job_registry.py:98`（`"realtime.sla_monitor:monitor"`）。
- `audit_overdue` 為 CR-0129 於原 spec 四類 alert 之外新增的第五類，`sla_monitor.py:28-29` 註明「窗長由完工時依 M18 config 寫入，本監測不再另設閾值 env」，故此類無獨立的 `SLA_*_MINUTES` 環境變數。
- 重複告警抑制走 in-memory `self._alerted` 集合（`sla_monitor.py:274-279`），程序重啟後狀態不保留。
- CR 開立與 audit log 皆以 try/except 包住，失敗只記 exception（`sla_monitor.py:370-371`、`:422-423`），不中斷 SLA 掃描。
