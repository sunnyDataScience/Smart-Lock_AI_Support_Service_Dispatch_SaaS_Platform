# TC-SETTLE-01 — 月結 cron 產對帳單與 commission.accrued 事件鏈

## 結果

| 項目 | 內容 |
|---|---|
| **判定** | **部分實作** |
| **本判定以原始碼走查為主，並補實跑證據** | 未啟動應用服務；正式機金流環境不可用，本批不做執行期驗證。後續以本機 Docker 測試庫實跑既有測試，結算相關 5 檔 38 項全數通過（見步驟 6） |
| 走查時間 | 2026-08-03（UTC+8） |
| 走查基準 | commit `17aa40c5` |
| 走查範圍 | `api/realtime/job_registry.py:83-254`、`api/realtime/statement_generate_cron.py:1-177`、`api/services/technician_statement_service.py:48-153`、`api/services/reconciliation_service.py:147-296`、`api/core/event_bus.py:27-36`、`api/realtime/event_consumer.py:22-140`、`api/services/technician_commission_service.py:160-220`、`api/services/monthly_settlement_service.py:48-225`、`api/routers/settlements_v2.py:43-79`、`api/routers/monthly_settlements_v2.py:1-90`、`api/services/event_reconcile_service.py:30-96` |
| 優先級 / 路徑類型 | P0 / happy |
| 事實結論 | 排程註冊表中唯一 `schedule="monthly"` 的 job 是 `statement-generate`，它產的是技師月對帳單 draft（`saas.technician_statement`）；另一條「月結批次」（`saas.monthly_settlement_batch`／`saas.settlement`）**在 `JOB_SPECS` 中沒有任何 job 對應**，只能由 `POST /tenants/{tid}/settlements/monthly` 或 `:generate` 端點觸發。`commission.accrued` 的發出點不在月結 cron，而在對帳單核准（`reconciliation_service.approve_reconciliation`，per-job）；事件走 outbox + Kafka publish，技師平台側由 `event_consumer.handle_commission_accrued` 物化為 `technician_commission_projection`，再由 `list_my_commission_statements` 跨品牌彙總。整條 Kafka 路徑為 opt-in（`KAFKA_BOOTSTRAP` 未設即全 no-op），且期末對帳閘門預設關閉。 |

**TC 原文**｜前置：月結期末｜步驟：跑月結 cron｜判定基準：對帳單生成；佣金計費（per-job，品牌側）發 commission.accrued 事件 → 技師平台彙總結算（Billing/Settlement 分離，ADR-P014）｜需求：FR-API-12、FR-TEC-06｜旅程：SC-09

---

## 事件風暴分解

| Actor | Command | 預期 Domain Event | Policy | 程式碼落點 | 程式碼實際行為 |
|---|---|---|---|---|---|
| 排程器 | 跑月結 cron | `StatementGenerated` | 期末產對帳單 | `realtime/statement_generate_cron.py:118-173` | 對「上個自然月有完工單且尚無 statement」的技師產 draft |
| 排程器 | 跑月結 cron | `MonthlySettlementBatchCreated` | 期末產撥款批次 | `realtime/job_registry.py:83-254` | **找不到**對應 job；只有端點觸發（`routers/settlements_v2.py:43-79`） |
| 品牌 API | 核准對帳 | `commission.accrued` | per-job 計費（Billing 留品牌） | `services/reconciliation_service.py:224-240`、`:270-294` | 同交易寫 outbox + commit 後即時 publish |
| 技師平台 | 消費事件 | `CommissionProjected` | Settlement 主體彙總 | `realtime/event_consumer.py:98-114` | `ON CONFLICT (settlement_id) DO UPDATE` 冪等 upsert |
| 技師 | 讀跨品牌對帳單 | `StatementsAggregated` | 跨品牌彙總 | `services/technician_commission_service.py:186-220` | 依 `period` GROUP BY 彙總投影；表不存在時回空清單 |
| 系統 | 期末對帳閘門 | `ReconcileGateChecked` | 品牌計費 vs 平台彙總 | `services/monthly_settlement_service.py:48-96` | 由 `settlement_policy.reconcile_gate_enforce` 控，預設不啟用 |

---

## 走查紀錄

### 步驟 1 — 排程註冊表中的月結 job

- **動作**：讀背景工作 SSOT registry
- **預期**：有「月結」排程
- **實際**：`schedule="monthly"` 只有一個 `statement-generate`

`api/realtime/job_registry.py:182-193`

```python
    _job(
        "statement-generate",
        "realtime.statement_generate_cron:worker",
        kind="scheduled",
        schedule="monthly",
        scope="brand technician statements",
        idempotency="tenant + technician + statement month unique",
        timeout=1800,
        retry="Scheduler retry + unique constraint",
        compensation="manual rerun for target month",
        run_once="run_once",
    ),
```

同表另有 `statement-auto-approval`（daily，`:170-181`）與 `reconciliation-exception-detector`（daily，`:134-145`）。整份 `JOB_SPECS`（`:83-254`）共 14 個 job，**沒有**任何一個的 `object_path` 指向 `monthly_settlement_service`。

### 步驟 2 — 對帳單生成的實際內容

- **動作**：讀 `statement_generate_cron.run_once`
- **預期**：期末產生對帳單
- **實際**：以「上個自然月」為期間，對有完工單且尚無該期 statement 的 (tenant, technician) 產 draft

`api/realtime/statement_generate_cron.py:126-160`

```python
        year, month = _previous_month(today or date.today())
        start, nxt = _month_bounds(year, month)

        # 候選：期間內有完工單的 (tenant, technician)；排除已有該期 statement 者
        cur = await db_module._conn.execute(
            "SELECT DISTINCT wo.tenant_id, wo.technician_id "
            "FROM work_orders wo "
            "WHERE wo.technician_id IS NOT NULL "
            "  AND wo.completion_status = ANY(%s) "
            "  AND wo.completed_at >= %s AND wo.completed_at < %s "
            "  AND NOT EXISTS ("
            "    SELECT 1 FROM saas.technician_statement s "
            ...
            for tenant_id, technician_id in rows:
            try:
                await technician_statement_service.generate_statement(
```

檔頭 `:14-15` 自述「產生的是 **draft**（不自動 submit）」。金額來源為 `technician_commission_service.compute_monthly_commission`（`services/technician_statement_service.py:93-102`），即品牌側工單完工明細 × 技師等級費率，非來自 `commission.accrued` 投影。

冪等：`generate_statement` 先 SELECT 既有列（`:77-90`），INSERT 帶 `ON CONFLICT (tenant_id, technician_id, period_year, period_month) DO NOTHING`（`:128`）。

### 步驟 3 — `commission.accrued` 的發出點

- **動作**：查事件發出者
- **預期**：月結 cron 發事件
- **實際**：發出點是「對帳單核准」（per-job），不在任何 cron

`api/services/reconciliation_service.py:212-240`

```python
        cur = await db_module._conn.execute(
            "INSERT INTO settlements "
            "  (reconciliation_id, technician_id, amount, currency, status) "
            "VALUES (%s::uuid, %s::uuid, %s, 'TWD', 'pending') "
            ...
        # 佣金事件 outbox（同交易）—— 與 settlement 同生共死，取代「publish 失敗只 log」
        # 的永久遺失。event_id 在此固定，worker 重送時原樣帶入，消費端 dedup 才有效。
        await db_module._conn.execute(
            "INSERT INTO commission_event_outbox "
            "  (event_id, tenant_id, topic, event_key, reconciliation_id, settlement_id, payload) "
            ...
            (commission_event_id, tenant_id, "commission.accrued", str(row[1]),
```

commit 後即時投遞（`:270-291`）：

```python
        from core.event_bus import TOPIC_COMMISSION_ACCRUED, publish_event
        ok = await publish_event(
            TOPIC_COMMISSION_ACCRUED,
            {
                "tenant_id": tenant_id,
                "reconciliation_id": recon_id,
                "settlement_id": settlement["id"],
                "technician_id": technician_id,
                "amount": settlement["amount"],
```

topic 常數 `api/core/event_bus.py:27`：

```python
TOPIC_COMMISSION_ACCRUED = "commission.accrued"
```

駁回路徑不建 settlement 也不發事件（`reconciliation_service.py:309-315` docstring）。v2 co-sign 路徑有等價寫法（`services/reconciliation_v2_service.py:311`、`:338-340`）。

- TC 判定基準：「跑月結 cron」後「發 commission.accrued 事件」
- 程式碼：事件由 `approve_reconciliation` / `co_sign_reconciliation` 於核准當下發出（`reconciliation_service.py:224`、`reconciliation_v2_service.py:311`），與月結 cron 無呼叫關係

此處僅並陳，不裁定。

### 步驟 4 — 技師平台端的彙總

- **動作**：追事件消費與彙總讀取
- **預期**：技師平台彙總跨品牌結算
- **實際**：consumer 冪等 upsert 投影；讀端依 period 彙總

`api/realtime/event_consumer.py:98-114`

```python
async def handle_commission_accrued(conn, event: dict) -> None:
    """commission.accrued → upsert 佣金投影（跨品牌 accrued 明細）。"""
    await conn.execute(
        "INSERT INTO technician_commission_projection "
        "  (settlement_id, tenant_id, reconciliation_id, technician_id, "
        "   amount, currency, accrued_at) "
        "VALUES (%s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s) "
        "ON CONFLICT (settlement_id) DO UPDATE SET "
```

`api/services/technician_commission_service.py:190-205`

```python
        cur = await conn.execute(
            "SELECT to_char(date_trunc('month', COALESCE(accrued_at, created_at)), 'YYYY-MM') "
            "         AS period, "
            "       SUM(amount), COUNT(*), MAX(currency) "
            "FROM technician_commission_projection "
            "WHERE technician_id = %s::uuid "
            "GROUP BY period ORDER BY period DESC LIMIT %s",
```

同函式 docstring（`:166-176`）自述三項限制：投影不帶工單毛額故 `gross_amount` 以佣金累計代替、無對帳單狀態機故 `status` 一律 `'accrued'`、投影表不存在時回空清單。

整條事件路徑 opt-in：`api/core/event_bus.py:35-36`

```python
def enabled() -> bool:
    return bootstrap_servers() is not None
```

consumer 同樣以 `KAFKA_BOOTSTRAP` 為啟動條件（`realtime/event_consumer.py:26-27`、`:150`）。

### 步驟 5 — 月結批次與期末對帳閘門

- **動作**：讀 `generate_monthly_batch` 與其觸發點
- **預期**：cron 觸發批次
- **實際**：只有兩個端點觸發；閘門預設關閉

`api/routers/settlements_v2.py:73-78`

```python
    batch = await monthly_settlement_service.generate_monthly_batch(
        tenant_id=tenantId, period_year=year, period_month=month,
        triggered_by="manual",
    )
    return {"data": batch}
```

`api/services/monthly_settlement_service.py:63-70`

```python
    try:
        cfg = await config_m18_service.read_global_value(namespace="settlement_policy")
    except Exception:  # noqa: BLE001 — config 讀取失敗視同未配置（gate 預設 off）
        cfg = None
    if not (isinstance(cfg, dict) and cfg.get("reconcile_gate_enforce")):
        return

    result = await event_reconcile_service.reconcile_commission(tenant_id=tenant_id)
```

`generate_monthly_batch` 的 `triggered_by` 參數預設值為 `"cron"`（`:99-105`），但 repo 中的兩個呼叫端都顯式傳 `"manual"`（`routers/settlements_v2.py:76`、`routers/monthly_settlements_v2.py:86-89`）。

閘門比對邏輯（`services/event_reconcile_service.py:56-95`）以「品牌 `settlements` vs 技師 `technician_commission_projection`」逐筆對金額，Kafka 未啟用時回 `skipped=True, gate_pass=False`（`:36-51`）。

### 步驟 6 — 執行既有測試

- **動作**：跑結算相關測試
- **預期**：取得執行證據
- **實際**：5 檔 38 項全數通過

```
cd api && POSTGRES_URI=<本機測試庫> python -m pytest tests/test_cr_0012_monthly_settlement.py \
  tests/test_settlement_reconcile_gate.py tests/test_settlements_v2_endpoint.py \
  tests/test_cr_0189_commission_outbox.py tests/test_cr_0073_settlement_versioning.py \
  -q -p winloop_plugin --tb=line

38 passed in 3.02s
```

`test_cr_0012_monthly_settlement.py` 的 12 項為純函式與 router 形狀斷言（CSV 表頭、operation_id、tenant-scoped path、pydantic 驗證），**未**覆蓋 cron 觸發。`test_settlement_reconcile_gate.py` 5 項覆蓋閘門四種分支（預設 off／mismatch 阻擋／pass 放行／Kafka off skipped／config 讀取失敗預設 off）。

**無對應測試**：`statement_generate_cron.run_once` 在 `api/tests/` 中無專屬測試檔（grep `statement_generate` 於 `api/tests/` 零命中）。

---

## 觀測到的其他事實

- `smartlock-docs/enterprise/04_SRS.md:356`（FR-TEC-06）記載「品牌 per-job 計費（Billing 留品牌）發事件 → 技師平台彙總跨品牌 statement / 對帳 / payout；期末 reconcile 閘門」，與 TC 判定基準同源；`:355` 之 ADR-P014 §2.1 為其依據。
- `smartlock-docs/enterprise/04_SRS.md:587` 記載裁決 E1：「7 帳本」語意由各域專表分別承載，`ledger_type` 統一單表設計不採。
- 事件即時投遞失敗不影響核准，只留 outbox 由 `commission-outbox` worker 依 backoff 重送（`services/reconciliation_service.py:292-294`；worker spec 見 `realtime/job_registry.py:121-133`，8 次指數退避後轉 dead）。
- `saas.settlement` 的 `settled_eligible` 由「該對帳單對應工單是否有未結案 dispute」決定（`services/monthly_settlement_service.py:187-197`），CSV 匯出只納入 `settled_eligible = true`（`:284`）。
- 月結批次去重條件為「任何 settlement 引用該 reconciliation 即排除」（`services/monthly_settlement_service.py:161-173`），註解記載此為 UAT-0718 W1-1 修正。
