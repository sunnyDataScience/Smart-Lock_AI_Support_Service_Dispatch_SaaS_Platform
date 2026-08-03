# Ops Scripts — 維運工具速查

> 給 ops on-boarding + 業主 reference。所有 script 純 stdlib 或最小
> deps，可獨立部署於任何 ops 機器。

## 0. 速查表

| Script | 用途 | 部署方式 | 依賴 |
|---|---|---|---|
| [`check_monitors_health.py`](#check_monitors_healthpy) | Smoke 監控 lifespan 6 cron 健康 | CI cron 5min | stdlib |
| [`classify_severity.py`](#classify_severitypy) | health JSON → severity 字串 | shell pipeline | stdlib |
| [`alert_pagerduty.py`](#alert_pagerdutypy) | PagerDuty Events API v2 | shell pipeline | stdlib |
| [`alert_slack.py`](#alert_slackpy) | Slack Incoming Webhook + Block Kit | shell pipeline | stdlib |
| [`alert_pipeline.sh`](#alert_pipelinesh) | 上述 4 個串連完整 alert 鏈 | CI cron / on-demand | shell |
| [`alert_drill_test.sh`](#alert_drill_testsh) | 6 scenario dry-run alert | manual | shell |
| [`smoke_test_production.py`](#smoke_test_productionpy) | 10 endpoint × schema check | deploy 後 / CI | stdlib (urllib) |
| [`load_test_phase_ii.py`](#load_test_phase_iipy) | Phase II 9 FR + ops 壓測 baseline | UAT / staging | aiohttp |
| [`snapshot_v1_metrics.py`](#snapshot_v1_metricspy) | P4 hourly v1 metrics snapshot | cron 每小時 | stdlib |
| [`aggregate_v1_metrics.py`](#aggregate_v1_metricspy) | P4 30 day aggregate → Stage 7 報告 | monthly | stdlib |
| [`p4_stage7_delete_v1_dry_run.py`](#p4_stage7_delete_v1_dry_runpy) | Stage 7 簽完 ops 跑 audit | on-demand | stdlib |
| [`export_openapi.py`](#export_openapipy) | Backend OpenAPI schema → JSON | dev | backend deps |
| [`sync-technicians-roster.sh`](#sync-technicians-rostersh) | 技師名冊同步 | manual | shell |
| [`diagnose-conversations.sh`](#diagnose-conversationssh) | 唯讀診斷：對話為何不進後台 | on-demand | cloud-sql-proxy + psql |

---

## 1. Lifespan + Alert Chain (6 scripts)

### `check_monitors_health.py`

Smoke check `/ops/lifespan-monitors` endpoint，回 health JSON。

```bash
SMOKE_BASE_URL=https://api.lock-ai.example \
SMOKE_AUTH_TOKEN=<token> \
python scripts/ops/check_monitors_health.py --output health.json
```

對接：CI cron 每 5 min → 跑 → 寫 file → alert_pipeline 接管。

### `classify_severity.py`

純函式：health JSON → `info` / `warning` / `error` / `critical`。

```bash
python scripts/ops/classify_severity.py --health-json health.json
# 輸出: critical / error / warning / info
```

Severity 表（13 unit tests 覆蓋）：
- `total=0` → critical（lifespan 未啟）
- `import_error >=1` → critical（部署檔損壞）
- `crashed >= total/2` → critical
- `crashed >=1` → error
- `stopping or not_started >=1` → warning
- 否則 → info

### `alert_pagerduty.py`

PagerDuty Events API v2 client，含 dedup_key。

```bash
python scripts/ops/alert_pagerduty.py \
  --routing-key $PD_KEY --source api-uat \
  --severity critical --health-json health.json
```

### `alert_slack.py`

Slack Block Kit message。

```bash
python scripts/ops/alert_slack.py \
  --webhook-url $SLACK_WH --source api-uat \
  --severity error --health-json health.json
```

### `alert_pipeline.sh`

串 health check + classify + 路由 (critical → PD / error/warning → Slack):

```bash
SMOKE_BASE_URL=... SMOKE_AUTH_TOKEN=... \
SLACK_WEBHOOK=... PD_ROUTING_KEY=... \
bash scripts/ops/alert_pipeline.sh
```

對接 GitHub Action `.github/workflows/monitors-health.yml`。

### `alert_drill_test.sh`

6 scenario dry-run（不真發 PD / Slack）：

```bash
bash scripts/ops/alert_drill_test.sh
```

驗 setup 用，UAT-010 ops drill 必跑。

---

## 2. Production Validation (2 scripts)

### `smoke_test_production.py`

Deploy 後 ≤ 30s 驗 10 endpoint（9 FR + ops_health）。

```bash
SMOKE_BASE_URL=https://api.lock-ai.example \
SMOKE_AUTH_TOKEN=<admin token> \
SMOKE_TENANT_ID=<production tenant> \
python scripts/ops/smoke_test_production.py --output-json report.json
```

exit 0 = 全綠 / 1 = 任一 fail → CI 直接判 deploy success/fail。

### `load_test_phase_ii.py`

Phase II 9 FR + ops endpoint 壓測 baseline。

```bash
LOADTEST_BASE_URL=... LOADTEST_AUTH_TOKEN=... LOADTEST_TENANT_ID=... \
uv run python scripts/ops/load_test_phase_ii.py \
  --concurrency 50 --duration 30 --output loadtest.json
```

對接壓測 SLO baseline 1.5× threshold 判斷（原 `docs/_ops/slo-baseline-phase-ii.md` 已於 0708 大掃除移除，查 git 歷史；SLO 正典見 `smartlock-docs/enterprise/25_Monitoring_Spec.md`）。

---

## 3. P4 Cutover Stage 7 (3 scripts + 1 runbook)

完整 chain：snapshot → aggregate → dry-run → ops PR。

### `snapshot_v1_metrics.py`

Hourly cron 抓 3 endpoint 寫 file：

```bash
SNAPSHOT_BASE_URL=... SNAPSHOT_AUTH_TOKEN=... \
SNAPSHOT_OUTPUT_DIR=/var/lib/v1-metrics-snapshots \
python scripts/ops/snapshot_v1_metrics.py --quiet
```

部署：`0 * * * * ...` cron 每小時 → 30 day = 720 snapshots。

### `aggregate_v1_metrics.py`

30 day aggregate → markdown report 給業主：

```bash
uv run python scripts/ops/aggregate_v1_metrics.py \
  --input-dir /var/lib/v1-metrics-snapshots \
  --window-days 30 \
  --output reports/p4-stage7-readiness.md
```

報告 5 段含 §3 Stage 7 建議（✅/❌/⚠️）。

### `p4_stage7_delete_v1_dry_run.py`

業主簽 Stage 7 後 ops 跑 audit blast radius：

```bash
uv run python scripts/ops/p4_stage7_delete_v1_dry_run.py \
  --main-py api/main.py --routers-dir api/routers \
  --safe-list reports/p4-stage7-safe-list.md \
  --output reports/p4-stage7-deletion-plan.md
```

純 read-only — 給 ops review 後走真實 PR。

完整流程原載 `docs/_ops/p4-stage7-readiness-runbook.md`（已於 0708 大掃除移除，查 git 歷史）。

---

## 4. Dev / Misc (2 scripts)

### `export_openapi.py`

Backend FastAPI schema → JSON 給 web codegen。

```bash
uv run python scripts/ops/export_openapi.py \
  --output api/openapi-runtime.json --pretty
```

對接：web `npx openapi-typescript` 自動 gen TS types。

> 原範例輸出目錄 `docs/architecture/api/` 已於 0708 大掃除移除（查 git 歷史）；script 預設輸出
> `api/openapi-runtime.json`，OpenAPI 機讀 SSOT = `api/openapi.yaml`。

### `sync-technicians-roster.sh`

技師名冊同步（與 production DB）— 細節見 script 內 header。

### `diagnose-conversations.sh`

唯讀診斷：LINE 對話明明有進 DB，品牌後台 `/conversations` 卻看不到。

原理是後台列表的查詢為 `conversations c JOIN users u ON c.user_id = u.id
WHERE u.tenant_id = <租戶>`——**對話存在不代表看得見**，還要它關聯的 user
掛在正確的租戶下。這支直接驗這條 join，五段輸出並附判讀對照：

```bash
./scripts/ops/diagnose-conversations.sh                  # 預設租戶
TENANT=<uuid> ./scripts/ops/diagnose-conversations.sh    # 指定租戶
```

判讀：② 租戶欄為 NULL 或非目標租戶 → user 沒掛對租戶，後台 join 不到（主因）；
③ 為 0 但 ② 有資料 → 同上；③ > 0 → 資料看得到，問題在前端或登入身分。

前置：`cloud-sql-proxy` 已安裝、`gcloud` 已登入。連 prod 走 `--gcloud-auth`
（ADC 常撞 `invalid_rapt`）。全部 SELECT，不寫入。

---

## 5. 環境變數速查

| 變數 | 哪個 script | 說明 |
|---|---|---|
| `SMOKE_BASE_URL` | check_monitors / smoke_test | API 端 base URL |
| `SMOKE_AUTH_TOKEN` | 同上 | Bearer token |
| `SMOKE_TENANT_ID` | smoke_test | Production tenant ID |
| `SLACK_WEBHOOK` | alert_slack / pipeline | Slack incoming webhook URL |
| `PD_ROUTING_KEY` | alert_pagerduty / pipeline | PagerDuty Events API key |
| `LOADTEST_BASE_URL` | load_test | UAT/staging API base URL |
| `LOADTEST_AUTH_TOKEN` | 同上 | UAT token |
| `LOADTEST_TENANT_ID` | 同上 | UAT tenant ID |
| `SNAPSHOT_BASE_URL` | snapshot_v1 | Production API base URL |
| `SNAPSHOT_AUTH_TOKEN` | 同上 | Admin token |
| `SNAPSHOT_OUTPUT_DIR` | 同上 | 寫檔目錄 |

## 6. Tests

對應 tests 在 `api/tests/`：

- `test_ops_classify_severity.py` (13)
- `test_ops_v1_metrics_snapshot.py` (9)
- `test_ops_p4_stage7_dry_run.py` (7)

跑：

```bash
.venv/bin/pytest api/tests/test_ops_*.py -v
```

## 7. 對齊文件

> 原 `docs/_ops/*.md` 五篇（background-monitors-runbook / alert-receivers-comparison /
> p4-stage7-readiness-runbook / slo-baseline-phase-ii / wbs-100-closeout-plan）與
> `docs/architecture/adr/ADR-0109-p4-stage7-tooling-chain.md` 已於 0708 大掃除移除，查 git 歷史。

現行維運文件正典：

- `smartlock-docs/enterprise/24_Runbook.md` — 故障診斷與止血手冊（含告警升級鏈）
- `smartlock-docs/enterprise/25_Monitoring_Spec.md` — 監控、SLI/SLO 與告警分層
- `smartlock-docs/enterprise/23_Deployment_Guide.md` — 部署與 smoke test

## 8. CI 整合

`.github/workflows/monitors-health.yml` 已串：
1. check_monitors_health.py → health.json
2. classify_severity.py → severity string
3. routing: critical → PagerDuty / error|warning → Slack

未來 roadmap：
- `loadtest-baseline.yml` (nightly load test)
- `v1-metrics-snapshot.yml` (alternative to cron)
