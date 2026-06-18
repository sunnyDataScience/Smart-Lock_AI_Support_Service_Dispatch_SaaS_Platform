---
id: OPS-ALERT-RECEIVERS-COMPARISON
title: Alert Receivers Comparison — PagerDuty vs Slack
status: active
created_at: 2026-06-05
purpose: 給 ops 選擇本 session 落地的 2 個 alert bridge (PagerDuty / Slack) 的決策表。
---

# Alert Receivers Comparison — PagerDuty vs Slack

> 本 session 補齊 monitors observability alert 鏈雙路徑：
> - `scripts/ops/alert_pagerduty.py` (`ec22b3ad`)
> - `scripts/ops/alert_slack.py` (`9677353e`)

## §1 Decision Matrix

| Criteria | PagerDuty | Slack | 建議 |
|:---|:---|:---|:---|
| **24/7 oncall escalation** | ✅ 自帶 | ❌ 需手動 @here | PagerDuty |
| **Mobile push notification** | ✅ critical 可繞 silent | ✅ 一般 | PagerDuty (critical) |
| **Audit / incident log** | ✅ 完整 timeline | ⚠️ Slack 訊息可刪 | PagerDuty |
| **Cost** | $$$ per seat | $0 webhook (含 workspace) | Slack |
| **Setup complexity** | medium (routing key + service) | low (webhook URL) | Slack |
| **Multi-team routing** | ✅ escalation policy | ⚠️ 多 channel | PagerDuty |
| **Rich format** | basic summary | ✅ Block Kit | Slack |
| **Daily noise tolerance** | low (warns = warning) | high | Slack |
| **Dedup** | ✅ built-in `dedup_key` | ❌ 重複訊息 | PagerDuty |
| **Integration ecosystem** | 200+ tools | 廣泛 | tie |
| **Mobile UX** | optimized push | normal app | PagerDuty |

## §2 Recommended Strategy

### 2.1 Single-team / 小團隊

**僅用 Slack**：
- 簡單；成本低；team 已用 Slack
- 把 GH Actions `monitors-health.yml` `if: failure()` 接 `alert_slack.py`
- on-call 在 `#ops-alerts` channel 主動關注

### 2.2 Production-critical / 中大團隊

**雙路徑（推薦）**：

| Severity | Receiver |
|:---|:---|
| `critical` (e.g. all crashed) | PagerDuty → 24/7 oncall escalation |
| `error` (e.g. 1-2 crashed) | Slack `#ops-alerts` |
| `warning` (e.g. stopping) | Slack `#ops-info` |
| `info` (e.g. by_state stats) | None / log only |

實作：CI workflow 用 severity routing:

```yaml
- name: Alert critical → PagerDuty
  if: failure() && env.SEVERITY == 'critical'
  run: python scripts/ops/alert_pagerduty.py ...

- name: Alert error/warning → Slack
  if: failure() && env.SEVERITY != 'critical'
  run: python scripts/ops/alert_slack.py ...
```

### 2.3 SRE / 大型團隊

**PagerDuty 主導 + Slack 為輔**：
- PagerDuty 主 incident management；Slack 為 status channel
- PD incident 啟動時自動 mirror 到 Slack（PD 內建 integration）
- 不需本 session 的 alert scripts 分流（PD → Slack 走 PD 自己 webhook）

## §3 Severity Classification

對齊 `lifespan_health` summary 用 severity mapping:

| Condition | Severity | Receiver (per §2.2) |
|:---|:---:|:---|
| `by_state.crashed >= total / 2` | critical | PagerDuty |
| `by_state.crashed >= 1` | error | Slack `#ops-alerts` |
| `by_state.stopping >= 1` | warning | Slack `#ops-info` |
| `by_state.import_error >= 1` | critical | PagerDuty (部署檔損壞) |
| `total == 0` (lifespan not started) | critical | PagerDuty |

未來可寫 `scripts/ops/classify_severity.py` 從 health JSON → severity 字串自動化（本 session 留 future BUILD）。

## §4 Cost / ROI

| Scenario | PagerDuty | Slack | 合計 |
|:---|:---:|:---:|:---|
| Small team (1 oncall) | ~$25/mo | $0 | $25/mo |
| Mid team (3 oncall) | ~$75/mo | $0 | $75/mo |
| Large team (10 oncall) | ~$250/mo + features | $0 | $250+/mo |
| One-incident cost saved | ≥ $1000 (downtime + ops) | — | ≥ $1000 |

**結論**：PagerDuty cost 通常 << 1 個 incident 避免成本。

## §5 啟動步驟（雙路徑 §2.2 場景）

1. **Slack**：
   - Slack workspace 建 #ops-alerts + #ops-info channel
   - Slack App 加 Incoming Webhook
   - 把 webhook URL 加 GH secrets `SLACK_WEBHOOK_URL`

2. **PagerDuty**：
   - Sign up PagerDuty Free trial
   - 建 Service「Smart-Lock-API-Monitors」
   - 取 Events API v2 routing key
   - 加 GH secrets `PD_ROUTING_KEY`
   - 設 escalation policy (oncall 5min → backup 15min → manager 30min)

3. **GH Actions** 改 monitors-health.yml 加 severity routing step（見 §2.2 yaml example）

4. **Drill test**：
   - 設 monitor 模擬 crash (改 env 大 interval)
   - 跑 workflow_dispatch → 驗 PagerDuty incident + Slack 訊息都到
   - 移除模擬恢復

## §6 相關 docs

- `docs/_ops/background-monitors-runbook.md` — 8 monitor 完整 ops runbook
- `docs/_archive/_ops/release-checklist-2026-06-05.md`（已歸檔）— production deploy checklist
- `scripts/ops/check_monitors_health.py` — health 查詢 smoke
- `scripts/ops/alert_pagerduty.py` — PD 整合
- `scripts/ops/alert_slack.py` — Slack 整合
- `.github/workflows/monitors-health.yml` — schedule cron 工作流

---

**選擇 receiver 後**：對應 `docs/_ops/background-monitors-runbook.md` §4 排錯流程。
