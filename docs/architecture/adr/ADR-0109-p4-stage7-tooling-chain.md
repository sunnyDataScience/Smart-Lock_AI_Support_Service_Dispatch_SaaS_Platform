---
adr_id: ADR-0109
title: P4 Stage 7 v1 router 刪除 — backend tooling chain 設計
status: accepted
date: 2026-06-06
deciders: tech lead
related: [ADR-0108, P4-stage-2-7-prep-checklists]
tags: [p4-cutover, ops, audit-trail, append-only]
---

# ADR-0109 — P4 Stage 7 backend tooling chain

## Context

`docs/_audit/P4-stage-2-7-prep-checklists.md` Stage 7 條件需 v1 endpoint
deprecation hit = 0 連續 30 day。但 deprecation middleware 是 in-memory
counter，server 重啟會清。原規劃僅有 ad-hoc curl + manual review，缺
audit trail + 業主簽核流程。

## Decision

建立 4 階段 backend tooling chain：

```
Stage 6 觀察期           Stage 7 簽核              Stage 7 執行
       │                       │                       │
       ▼                       ▼                       ▼
  hourly snapshot   →   30 day aggregate   →   dry-run plan   →   ops PR
  (cron 每小時)         (markdown report)      (audit script)      (人工)
```

### Tool 1: `scripts/ops/snapshot_v1_metrics.py`

- 純 stdlib (urllib) — production 機器 zero-deps
- 一次抓 3 endpoint: `/admin/deprecation/v1-metrics` +
  `/admin/v1-inventory` + `/admin/v1-inventory/no-traffic`
- write rotate by day: `snapshots/YYYY-MM-DD/HH-MM.json`
- 部署 cron 每小時 → 30 day = 720 snapshots
- exit 0 OK / 1 all-fail / 2 config error 給 alerting 接

### Tool 2: `scripts/ops/aggregate_v1_metrics.py`

- 從 720 snapshots aggregate per-endpoint stats
- classify_for_stage7: 真 0 traffic (safe) vs 仍有流量 (keep)
- render_report markdown 5 段含 §3 業主建議:
  - ✅ 全綠 → 整批刪
  - ❌ 全紅 → 延期 + 找 caller
  - ⚠️ 混合 → 階段性刪除

### Tool 3: `scripts/ops/p4_stage7_delete_v1_dry_run.py`

- 業主簽 Stage 7 後 ops 跑此 audit blast radius
- parse main.py 抓 v1 import + include_router 行 + alias
- 對應 router files 列出 + size
- 接受 aggregate report markdown 直接 input safe list
- 純 read-only — 不改 code、不碰 git
- 產 markdown plan §1-§5 含後續 PR 9 步 checklist + risk mitigation

### Tool 4: ops PR (非 script)

業主 + ops review dry-run plan 後走正規 PR 流程刪除。

## Rationale

### 為何 hourly 而非 minute / day

- minute: 1 day = 1440 snapshot / 30 day = 43200 — 過量
- day: 流量峰谷會被平均，business hour 流量會被半夜 0 流量掩蓋
- hour: 折衷 — 720 snapshot 易管理 + business hour 可獨立辨識

### 為何 file 而非 DB

- DB schema 變更需 CIA + migration — 跨更多 reviewer
- file 易 backup + grep + curl 拿
- 不污染 production schema
- 重啟 / 換 host 只需移檔不需 migrate

### 為何 dry-run 不直接刪

- 業主簽 Stage 7 是業務決策，code change 是 tech 決策
- dry-run 給 ops 評估後仍可選擇延期/部分刪除
- 真實刪除走 PR review = 第二道 audit
- 若 dry-run 偵測 inventory 漏項 / shared service / dead code，
  可在 PR 階段補 lib 處理

### 為何 markdown 而非 JSON 輸出

- 業主 / ops 直接 review，markdown 在 GitHub / GitLab 渲染
- 對接 ADR / decision log 可直接貼

## Consequences

### Positive

- Stage 7 完整 audit trail: snapshot file + aggregate report + dry-run plan
- 業主簽核流程明確 (Day 30 report / Day 31 review / Day 32 簽 / Day 33 PR)
- Counter 重啟事件不再遮蔽真實流量
- ops 不需 ad-hoc curl + manual review

### Negative

- 需部署 cron host (非 zero infra cost)
- snapshot file 累積 ~720KB / 30 day (需 retention policy)
- dry-run parser 用 regex 非 ast — main.py 大幅重構可能需更新 parser

### Neutral

- Tool 1+2+3 純 stdlib + 純 read-only — 可獨立部署於任何 ops 機器
- 16 tests (snapshot 9 + dry-run 7) 確保未來重構不破回歸

## Compliance Audit Trail

- Backend code: `scripts/ops/{snapshot,aggregate,p4_stage7_delete_v1_dry_run}_v1_metrics.py`
- Tests: `api/tests/test_ops_v1_metrics_snapshot.py` + `test_ops_p4_stage7_dry_run.py`
- Runbook: `docs/_ops/p4-stage7-readiness-runbook.md`
- 對應業主裁決: `pending-business-decisions-2026-06-06.html` 事項 1
- 對應 closeout plan: `docs/_ops/wbs-100-closeout-plan.md` §2.1 + §3.3

## See also

- ADR-0108 — Recon UX + 計價 GUI 業主裁決 (相關業主決議範式)
- `docs/_audit/P4-stage-2-7-prep-checklists.md` — 原 Stage 7 條件
- `docs/_audit/P4-cutover-v1-caller-inventory-2026-06-05.md` — v1 caller 盤點
- `docs/_ops/p4-stage7-readiness-runbook.md` — 部署 + 業主簽核流程
