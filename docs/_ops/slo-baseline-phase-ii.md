# Phase II 9 FR — SLO Baseline (production observation)

> Created 2026-06-05
> 對齊：`scripts/ops/load_test_phase_ii.py` + Stage 6 production 30 day 觀察
>
> 本 doc 預設 SLO 為 **baseline 期望值**，不是 contract。production 跑滿
> 7 day 後若實際 p95 持續 ≤ baseline 即標 ✅；若超 baseline 1.5× 則需
> 開 investigation 或 escalate。

---

## 0. 觀察方法

1. **UAT 環境壓測** — 跑 `load_test_phase_ii.py --concurrency 100
   --duration 60`，輸出 JSON 對比下方 baseline
2. **Production canary** — 部署後 1 week，從 Cloud SQL slow query +
   FastAPI middleware latency log 採樣
3. **CI nightly** — 加入 `monitors-health.yml` 配套 workflow 跑壓測
   30 min（roadmap，目前手動）

---

## 1. SLO baseline 表（9 FR + ops）

| Scenario | endpoint | p50 baseline | p95 baseline | p99 baseline | error rate budget |
|---|---|---|---|---|---|
| `approval_inbox` (FR-0049) | `GET /tenants/{tid}/approval-inbox` | 80ms | 200ms | 400ms | 0.1% |
| `tech_lifecycle` (FR-0044) | `GET /tenants/{tid}/technicians` | 60ms | 150ms | 300ms | 0.1% |
| `tech_statement` (FR-0045) | `GET /tenants/{tid}/me/statements` | 50ms | 120ms | 250ms | 0.1% |
| `dispatcher_commission` (FR-0046) | `GET /tenants/{tid}/me/commission-statements` | 50ms | 120ms | 250ms | 0.1% |
| `brand_b2b` (FR-0047) | `GET /tenants/{tid}/brand-b2b-statements` | 100ms | 250ms | 500ms | 0.1% |
| `gdpr_queue` (FR-0053) | `GET /tenants/{tid}/gdpr/forget-requests` | 40ms | 100ms | 200ms | 0.1% |
| `ai_governance` (FR-0050) | `GET /tenants/{tid}/ai/governance/traces` | 120ms | 300ms | 600ms | 0.1% |
| `sop_feedback` (FR-0051) | `GET /tenants/{tid}/sop-feedback` | 50ms | 120ms | 250ms | 0.1% |
| `rma_quality` (FR-0048) | `GET /tenants/{tid}/rma/quality-findings` | 60ms | 150ms | 300ms | 0.1% |
| `ops_health` (lifespan) | `GET /ops/lifespan-monitors` | 20ms | 50ms | 100ms | 0.01% |

### 為什麼這些數字

- **Statement 類 50-100ms**: 純 SELECT + 索引 (`tenant_id + status + period`)
  + 6 state machine + decimal computation。已驗 backend 372 tests 涵蓋
  filter 邏輯。
- **B2B 100-250ms**: 多 join (brand_partner + work_order aggregate) +
  `_compute_net` 計算 AR/AP/NET，預期略高於單一 statement。
- **AI governance 120-300ms**: trace 量大 + decision_type aggregation；
  index 對 `(tenant_id, created_at DESC)` 應 cover。
- **GDPR queue 40-100ms**: 量極少（高隱私事件，非熱路徑）。
- **Ops health 20ms**: 純 in-memory monitor state，不打 DB。

### 1.5× threshold 規則

若觀察期內某 scenario 持續超出 1.5× baseline (e.g. `ai_governance` p95
> 450ms)，須開 issue 走以下 root cause check:

1. Index missing → 查 `EXPLAIN ANALYZE`
2. N+1 query → 查 service `_to_dict` 是否含 nested fetch
3. tenant 資料量爆增 → 拆 partition 或加 LIMIT
4. Cron 與 user request 競爭連線 → 調 cron interval / connection pool

---

## 2. 連續壓測 → CI 自動 pass/fail

```yaml
# .github/workflows/loadtest-baseline.yml (roadmap)
- name: Run load test against UAT
  env:
    LOADTEST_BASE_URL: ${{ secrets.UAT_BASE_URL }}
    LOADTEST_AUTH_TOKEN: ${{ secrets.UAT_TOKEN }}
    LOADTEST_TENANT_ID: tenant-uat-loadtest
  run: |
    uv run python scripts/ops/load_test_phase_ii.py \
      --concurrency 50 --duration 30 \
      --output reports/loadtest-${{ github.sha }}.json

- name: Compare against SLO baseline
  run: |
    python scripts/ops/loadtest_assert_slo.py \
      reports/loadtest-${{ github.sha }}.json \
      docs/_ops/slo-baseline-phase-ii.md
```

`loadtest_assert_slo.py` 解析 baseline 表 vs report JSON，超 1.5×
threshold 即 `sys.exit(1)`。（roadmap — 本 session 不寫，留 BUILD
時實作。）

---

## 3. Stage 6 production 30 day 觀察 → Stage 7 v1 router 刪除門檻

對齊 `docs/_audit/P4-stage-2-7-prep-checklists.md` Stage 7：

- ✅ **v1 endpoint deprecation hit count = 0** 連續 30 day
- ✅ **9 FR endpoint SLO 全 PASS** 連續 30 day（用本 doc baseline）
- ✅ **無 production incident** (PagerDuty critical) 與 9 FR 相關
- ✅ **Lifespan monitor `running` 全綠** 連續 30 day
- ✅ **業主簽 P4 Stage 7 完成書**

任一條未過，延期 Stage 7，繼續觀察。

---

## 4. 用法 — UAT 跑壓測完成

```bash
export LOADTEST_BASE_URL=https://uat.lock-ai.example
export LOADTEST_AUTH_TOKEN=<從 UAT 拿 admin token>
export LOADTEST_TENANT_ID=tenant-uat-001

# 跑全部 10 scenario × 60s × 100 concurrent
uv run python scripts/ops/load_test_phase_ii.py \
    --output docs/_audit/loadtest-uat-2026-q3.json

# 或只跑 statement 類
uv run python scripts/ops/load_test_phase_ii.py \
    --scenarios tech_statement,dispatcher_commission,brand_b2b \
    --duration 30
```

完成後對齊 `docs/_ops/uat-plan-2026-q3.md` UAT-010，寫入結果。

---

## §A 不在本 baseline 範圍

- **Agent inference latency**: 屬 LiteLLM provider + model 端，由
  `lockcore/providers/litellm_provider.py` 自監測，與本 baseline 不相關
- **LINE webhook**: 屬 `scripts/line_gateway.py`，另立 SLO
- **背景 cron**: 跑批不對 user 暴露，不適用 user-facing SLO
- **背景 monitor**: 同上，用 `ops_health` endpoint 反映 collective 狀態

---

## §B 對齊文件

- `scripts/ops/load_test_phase_ii.py` — 壓測 framework
- `docs/_ops/wbs-100-closeout-plan.md` §3.3 — Stage 2-6 觀察
- `docs/_audit/P4-stage-2-7-prep-checklists.md` Stage 7
- `docs/_ops/uat-plan-2026-q3.md` UAT-010
- `docs/_ops/background-monitors-runbook.md` lifespan + cron
