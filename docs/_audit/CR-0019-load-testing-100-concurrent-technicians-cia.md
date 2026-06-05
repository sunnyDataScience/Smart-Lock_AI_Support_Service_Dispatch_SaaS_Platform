---
title: CR-0019 — 100 人技師併發壓測 CIA
date: 2026-06-05
status: open-awaiting-decisions
tier: 4
blocks: [WBS 1.2.7.3.3]
---

# CR-0019 — 100 人技師併發壓測 CIA

## 1. 動機

WBS 1.2.7.3.3 「師傅端 100 人併發壓測」標 ⬜ 0% — 取證 `docs/_audit/wbs-1.2.7.3-2-3-4-audit.md` 確認工具/scenario/SLA baseline 全空。屬 UAT 前 NFR 必驗項，但工具引入觸發 Architecture boundary（測試基礎建設層）+ SLA 目標需業主裁決，須走 CIA。

## 2. 範圍

**In scope**：壓測工具選型 + 場景設計 + SLA pass/fail 門檻 + 整合至 CI/Cloud Run。

**Out of scope**：
- E2E 功能測試（1.2.7.3.1 已 ✅）
- 安全壓測（DDoS / OWASP — 另 scope）
- DB query 慢查 audit（非黑箱壓測範疇）

## 3. 取證

### 3.1 既有資源 ✅

- FastAPI backend uvicorn 部署 Cloud Run（auto-scale 0-100 instances 預設）
- Cloud Run health endpoint `/health` 已就緒
- API smoke test `tests/smoke/api.sh` 已存在

### 3.2 0% 段 ❌

- `find . -name "*.k6.js" -o -name "locustfile.py"` 全空
- 無 GCP Cloud Load Testing 配置
- 無 Artillery / Gatling / JMeter 配置
- `scripts/perf/` 目錄不存在
- 無 baseline metrics（p50/p95/p99 latency / throughput / error rate）

### 3.3 真實併發場景（業務側）

100 個技師日常行為 mix：
- **40%** GET `/work-orders/pool`（每 30 秒輪詢 + WS broadcast 補強）
- **25%** POST `:accept` / `:assign`（接案）
- **15%** POST `subflows`（material-request / delay / scope-change / door-check）
- **10%** PATCH 排班 / 改期
- **5%** POST `:complete`
- **5%** 雜項（GET 詳情、media upload）

## 4. Human Decisions Required

### HD-1 — 工具選型

| 選項 | 優點 | 缺點 |
|---|---|---|
| (a) k6（JS scenario）| Cloud-native；GCP/Datadog integration；scenario 寫得快；CSV/JSON 報告 | 收費版才能分布式；OSS 單機限 ~5000 VU |
| (b) Locust（Python）| Python 與 backend 同語言；scenario 靈活；分布式免費；Web UI | 性能比 k6 略差；scenario 寫起來啰嗦 |
| (c) Artillery（YAML）| YAML 易讀；輕量；快速啟動 | scenario 表達力弱；社群小 |
| (d) GCP Cloud Load Testing | 與 GCP 深度整合；免維運 | vendor lock-in；scenario 表達力中 |

**建議**：(b) Locust — Python 與既有 codebase 共棲；分布式免費；可直接 reuse api/services helper（如 token mint）

### HD-2 — SLA pass/fail 門檻

| 指標 | 候選門檻 |
|---|---|
| p95 GET latency | 200ms / 300ms / 500ms |
| p95 POST latency | 500ms / 1000ms / 2000ms |
| error rate (5xx) | 0.1% / 1% / 5% |
| throughput | 50 req/s / 100 req/s / 200 req/s |
| WebSocket 連線穩定度 | 100% / 99% / 95% |

**建議**：保守 — p95 GET 500ms / p95 POST 1000ms / error 1% / 100 req/s / WS 99%（容許 Cloud Run cold-start）

### HD-3 — 100 VU 模擬深度

| 選項 |
|---|
| (a) 100 持續活躍技師（rampup 5min → 持續 30min）|
| (b) 200 註冊技師 50% 活躍切換（更貼近現實打分布）|
| (c) Soak test 100 持續 4hr（驗 memory leak / DB connection pool）|
| (d) Spike test：0→200→0 衝擊（驗 auto-scale 速度）|

**建議**：(a) MVP scope；(c) 與 (d) Phase II 收尾再做

### HD-4 — 環境

| 選項 |
|---|
| (a) Staging Cloud Run（同 prod 配置）|
| (b) 本地 docker-compose（DB + uvicorn 單機）|
| (c) Dedicated 壓測環境（新 GCP project）|

**建議**：(a) — 同 prod 配置最有 reference value；缺點是需 staging instance budget

### HD-5 — CI/CD 整合策略

| 選項 |
|---|
| (a) 一次性手動跑（每次 release 前 manual trigger）|
| (b) PR-level 跑 mini 壓測（10 VU smoke）+ pre-release 跑 full（100 VU）|
| (c) Nightly full run + weekly trend report |

**建議**：(b) — PR mini 防退步 + pre-release full 驗 NFR

## 5. 不立即 BUILD 的理由

- HD-1 工具選型影響 ~3-5 day scenario 撰寫工時
- HD-2 SLA 門檻直接決定 pass/fail，需業主拍板
- HD-3 模擬深度涉 staging budget（Cloud Run instance hours）
- HD-4 staging 環境若採選項 (a) 需另開 staging project（採購決策）

## 6. 推薦立場（如業主全採推薦）

- HD-1=(b) Locust
- HD-2=保守門檻 (p95 GET 500ms / POST 1000ms / error 1% / 100 r/s / WS 99%)
- HD-3=(a) MVP 100 VU 30min
- HD-4=(a) Staging Cloud Run
- HD-5=(b) PR mini + pre-release full

預估 BUILD：5-7 day（Locust scenario 撰寫 + GCP scheduled job + 1 次 baseline + 報告 dashboard）

## 7. 依賴

- 解凍：WBS 1.2.7.3.3 (0% → 100%)
- 鏡像：CR-0018 (Flow 13 EX5)、CR-0017 (LINE Flex)等本 batch CIA
- 前置：staging 環境 budget 業主批准

## 8. status

`open-awaiting-decisions` — 等 5 HD 業主裁決後切 CR-0019-BUILD。
