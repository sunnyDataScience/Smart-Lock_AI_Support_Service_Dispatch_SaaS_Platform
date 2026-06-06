# P4 Stage 7 Readiness Runbook

> 2026-06-06 建立 — 給業主待裁決事項 1（P4 Stage 7 v1 router 刪除）的
> 30 day 觀察期 + 簽核流程。

## 0. 為何需要

`docs/_audit/P4-stage-2-7-prep-checklists.md` Stage 7 要求 v1 endpoint
deprecation hit count = 0 連續 30 day。但 deprecation middleware 是
**in-memory counter**，server 重啟即清空 — 若中間有重啟，無 persistent
trail 證明真 0 traffic。

本 runbook 解決：用 hourly snapshot + 30 day aggregate 重建真實流量。

## 1. 部署 hourly snapshot cron

部署在能訪問 production API 的 host 上：

```bash
# /etc/cron.d/v1-metrics-snapshot
0 * * * * appuser cd /opt/repo && \
  SNAPSHOT_BASE_URL=https://api.lock-ai.example \
  SNAPSHOT_AUTH_TOKEN="${V1_METRICS_TOKEN}" \
  SNAPSHOT_OUTPUT_DIR=/var/lib/v1-metrics-snapshots \
  /opt/repo/.venv/bin/python scripts/ops/snapshot_v1_metrics.py \
  --quiet 2>> /var/log/v1-metrics-snapshot.err
```

每 1 小時跑一次 → 30 day = 720 snapshots。每個 ~1KB → ~720KB total。

## 2. Snapshot 結構

```
/var/lib/v1-metrics-snapshots/
  2026-06-06/
    00-00.json
    01-00.json
    ...
    23-00.json
  2026-06-07/
    ...
```

每檔內含 3 endpoint 的 response snapshot：

```json
{
  "captured_at": "2026-06-06T00:00:00+00:00",
  "captured_at_epoch": 1780617600,
  "base_url": "https://api.lock-ai.example",
  "endpoints": {
    "v1_metrics": {"status": 200, "data": {"items": [...]}},
    "v1_inventory": {"status": 200, "data": {"items": [...]}},
    "no_traffic": {"status": 200, "data": {...}}
  }
}
```

## 3. 30 day Aggregate → Stage 7 Readiness Report

每月 1 號 ops 跑 aggregate 生 markdown report 給業主：

```bash
uv run python scripts/ops/aggregate_v1_metrics.py \
  --input-dir /var/lib/v1-metrics-snapshots \
  --window-days 30 \
  --output reports/p4-stage7-readiness-$(date +%Y-%m-%d).md
```

Report 結構：

- **§1 安全可刪除（Stage 7 候選）** — 真 0 traffic 的 endpoint list（含 first→last seen）
- **§2 仍有流量** — 保留 / 延期觀察候選（含 total_hits / max_hourly / snapshots_with_traffic）
- **§3 Stage 7 建議** — 3 種情境自動判：
  - ✅ 全綠（0 traffic）→ 建議業主簽 Stage 7 整批刪
  - ❌ 全紅（仍有流量）→ 延期 Stage 7 + 找 caller
  - ⚠️ 混合 → 階段性刪除 §1 安全集，§2 繼續觀察

## 4. 業主 Stage 7 簽核流程

1. **Day 30**: ops 跑 aggregate → 寫 report → 上傳到 business decision 資料夾
2. **Day 31**: 業主 review report → 對應 `pending-business-decisions-2026-06-06.html` 事項 1
3. **Day 32**: 業主對下列三選一簽核：
   - 選項 1: 直接刪 v1 router（推薦，若 §1 全綠）
   - 選項 2: 留 v1 但永久 410 Gone（若有零星 traffic 想保險）
   - 選項 3: 延期觀察至 60 day（若 §2 仍 ≥1 endpoint 有流量）
4. **Day 33**: 依業主決議走對應實作（backend code change）

## 5. 失效情境

| 情境 | 影響 | Mitigation |
|---|---|---|
| Cron 漏跑（host 重啟） | snapshot 缺一兩個檔，aggregate 仍可用 (best-effort) | systemd timer 取代 cron + auto-restart |
| Auth token 過期 | 全 snapshot fail | exit code 1 觸發 alerting（外接 alertmanager） |
| Aggregate 拿空目錄 | exit 1 + stderr warning | 業主 review 時看 report 缺漏即知 |
| Counter middleware 被換掉 | metrics endpoint 結構改 | 同步改 `_summarize` + `aggregate` parser |

## 6. 對應測試

`api/tests/test_ops_v1_metrics_snapshot.py` 9 tests：
- snapshot day-dir rotation
- summarize total_hits extraction
- aggregate per-endpoint hits sum
- classify_for_stage7 zero vs active 分流
- render_report 全綠 / 全紅 / 混合三情境建議
- load_snapshots window-days 過濾

跑：`.venv/bin/pytest api/tests/test_ops_v1_metrics_snapshot.py -v`

## §A 對齊文件

- `scripts/ops/snapshot_v1_metrics.py` — hourly snapshot
- `scripts/ops/aggregate_v1_metrics.py` — 30 day aggregate
- `api/routers/deprecation_metrics.py` — in-memory counter source
- `api/routers/v1_inventory.py` — mounted endpoint inventory source
- `api/middleware/deprecation.py` — counter implementation
- `docs/_audit/P4-stage-2-7-prep-checklists.md` Stage 7 條件
- `docs/_ops/wbs-100-closeout-plan.md` §2.1 + §3.3
- `pending-business-decisions-2026-06-06.html` 事項 1
- `docs/architecture/adr/ADR-0108-business-decisions-recon-pricing-defer.md` 業主裁決範式
