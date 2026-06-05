# CR-0019 Load Testing — 100 技師併發

依 CIA HD-1=(b) Locust / HD-2 保守門檻 / HD-3=(a) 100 VU 30min / HD-4=(a) Staging Cloud Run / HD-5=(b) PR mini + pre-release full 推薦立場實作。

## 目標

驗證 100 個技師同時用 app 時，API 不退步：
- 業務 mix 對齊 CIA §3.3 (40% pool / 25% accept / 15% subflow / 10% reschedule / 5% complete / 5% misc)
- SLA 門檻（HD-2 保守）：p95 GET 500ms / p95 POST 1000ms / error ≤ 1% / throughput ≥ 100 req/s

## 檔案

| 檔案 | 用途 |
|---|---|
| `locustfile.py` | TechnicianUser 場景，6 task 加權 @task(40/25/15/10/5/5) |
| `sla.py` | 讀 Locust CSV stats → 比對 4 門檻 → exit 0/1 |
| `results/` | CSV 報告輸出目錄（gitignore） |

## 跑法

### Mini smoke（PR-level，HD-5=b 前段）

```bash
locust -f loadtest/locustfile.py --headless \
    -u 10 -r 2 -t 60s \
    --host https://api-staging.example.com \
    --csv loadtest/results/mini
python loadtest/sla.py loadtest/results/mini_stats.csv
```

10 VU / 60s — 純 smoke 驗 endpoint 結構，不期待達 SLA 門檻（throughput 不會到 100 r/s）。
PR 防退步用 — 由 `.github/workflows/loadtest-mini.yml` 驅動。

### Full run（pre-release，HD-5=b 後段）

```bash
locust -f loadtest/locustfile.py --headless \
    -u 100 -r 5 -t 30m \
    --host https://api-staging.example.com \
    --csv loadtest/results/full
python loadtest/sla.py loadtest/results/full_stats.csv
```

100 VU rampup 5/s 達成 5 分 → 持續 30 分。SLA 門檻全套驗。

## 環境變數

| ENV | 預設 | 用途 |
|---|---|---|
| `LOADTEST_TENANT_ID` | `00000000-...-1` | tenant scoping path |
| `LOADTEST_TECH_TOKENS` | 空 | 預先 seed 100 個 technician access token CSV |

`LOADTEST_TECH_TOKENS` 由 staging 部署時注入，避開壓測時還跑 `/auth/login` 增加 latency 雜訊。生成方式：

```bash
# 用 admin 後台批次 mint 100 個技師 token
python scripts/loadtest/mint_tokens.py --count 100 > tokens.csv
export LOADTEST_TECH_TOKENS=$(cat tokens.csv | tr '\n' ',')
```

## SLA 門檻（HD-2 保守）

| 指標 | 門檻 | 理由 |
|---|---|---|
| p95 GET latency | 500ms | 容忍 Cloud Run cold-start |
| p95 POST latency | 1000ms | write 含 DB transaction |
| error rate | ≤ 1% | 含 5xx + 4xx 異常 |
| throughput | ≥ 100 req/s | 100 VU × avg 1 req/s per VU |
| WS 連線穩定 | ≥ 99% | (Phase II 才測) |

調整 `loadtest/sla.py` 的 `SlaThresholds` dataclass。

## CI 整合

`.github/workflows/loadtest-mini.yml`（CR-0019 Stage 2）：
- PR-level 自動跑 mini smoke（10 VU / 60s）
- SLA 用較寬鬆門檻（避免每 PR 都 noisy）
- 報告 artifact 留 30 天

Pre-release full run 為 manual trigger（避免 staging budget 失控）。

## 不在本 BUILD 範圍

- HD-3 (c) soak test 4hr — Phase II 收尾
- HD-3 (d) spike test 0→200→0 — Phase II
- WebSocket scenario — 需另寫 WS user class；Phase II 補
- GCP Cloud Run staging instance 採購 — 待業主批 budget

## 相關 ADR / CR

- CR-0019 CIA: `docs/_audit/CR-0019-load-testing-100-concurrent-technicians-cia.md`
- Flow 14 排班衝突: 壓測會觸發 schedule_conflict detector (CR-0017)
- Flow 13 EX5: 壓測完 cron 跑可能 detect amount_mismatch（測試資料髒）
