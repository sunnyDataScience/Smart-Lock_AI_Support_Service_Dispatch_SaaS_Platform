---
id: P4-PROGRESS-DASHBOARD
title: P4 Cutover Progress Dashboard
status: open
created_at: 2026-06-05
purpose: P4 Cutover 7 stage 進度即時看板；一處看 backend 完成度 / 待 prod 任務 / 風險。
---

# P4 Progress Dashboard

> 對齊 `P4-cutover-v1-caller-inventory-2026-06-05.md` §3 全 stage roadmap。
> 每次 P4 BUILD 進展更新本 doc。

## §1 Overall Progress

```
Stage 1 ████████████████████░  95% (5/6 tasks; Task 6 待 prod metrics)
Stage 2 ░░░░░░░░░░░░░░░░░░░░   0% (待 prep)
Stage 3 ░░░░░░░░░░░░░░░░░░░░   0%
Stage 4 ░░░░░░░░░░░░░░░░░░░░   0%
Stage 5 ░░░░░░░░░░░░░░░░░░░░   0% (產品 UX 工作)
Stage 6 ░░░░░░░░░░░░░░░░░░░░   0%
Stage 7 ░░░░░░░░░░░░░░░░░░░░   0% (高風險，30d 觀察前置)

Overall: ~14% (Stage 1 backend 完成；剩 Stage 2-7)
```

## §2 Stage 1 完成成果（本 session）

| Task | Status | Commit | 改動 |
|:---|:---:|:---|:---|
| 1. admin/refunds stale comment | ✅ | `e049de22` | comment 修正 |
| 2. admin/refunds 100% v2 確認 | ✅ | (Task 1 同) | 無改動 (已驗證) |
| 3. admin/reports/revenue TODO | ✅ | `2d6ff10e` | comment 修正 |
| 4. admin/reports/technician-ranking TODO | ✅ | (Task 3 同) | comment 修正 |
| 5. admin/roles comment 精確化 | ✅ | `70e32a46` | comment 修正 + P4 ref |
| 6. metrics reset + 7d 觀察 | 🟡 | — | 需 prod env |

合計 backend 改動：3 個 commit / 4 個 file / 4 個 comment line / 0 個 runtime 改動

## §3 待遷 v1 refs 統計（修正後）

```
Original (P4 inventory §1):       38 refs / 12 prefix
扣 user-scoped (auth/me 系列):   -  6 refs
扣 multipart upload:              -  1 refs
─────────────────────────────────────────────────
真實待遷:                          31 refs / ~10 prefix
```

| Prefix | refs | 永久保留 | 真實待遷 |
|:---|:---:|:---:|:---:|
| accounting | 1 | 0 | 1 (Stage 5 UX) |
| auth | 6 | 6 | 0 (user-scoped) |
| config | 7 | 0? | 7 (Stage 4) |
| foo | 1 | 1 | 0 (docstring 範例) |
| knowledge-base | 3 | 0 | 3 (Stage 2) |
| manuals | 2 | 1 | 1 (Stage 2) |
| public | 4 | 0 | 4 (Stage 6) |
| refunds | 1 | 0 | 1 (Stage 1 已驗) |
| reports | 1 | 0 | 1 (Stage 1 已驗) |
| roles | 1 | 0 | 1 (Stage 1 已驗) |
| technicians | 8 | 3 | 5 (Stage 3) |
| work-orders | 4 | 0 | 4 (Stage 3) |
| **Total** | **38** | **11** | **27** |

> 註：config 7 refs 中可能有 system config vs M18 config 分軌（Stage 4 case-by-case 確認）；
> 此處 7 全列待遷為保守估計。

## §4 工時預估（修正）

| Stage | Original est | 修正後 | 已完 |
|:---|:---:|:---:|:---:|
| 1 | 半天 | 半天 | ✅ backend 部分 |
| 2 | 半天 | 3-4 hr (扣 manuals upload) | — |
| 3 | 1d | 6-8 hr (扣 me 系列) | — |
| 4 | 1d | 6 hr + 業主審 | — |
| 5 | 1-2d | 1-2d (產品 UX) | — |
| 6 | 1d | 6 hr | — |
| 7 | 1d | 1d + 30d 觀察 | — |
| 8 (OpenAPI regen) | 半天 | 半天 (自動) | — |
| **Total** | **5-7d** | **~4.5-6d** | **0.5d done** |

## §5 P4 Tooling Status

| Tool | Status | Endpoint / Path |
|:---|:---:|:---|
| Deprecation hit metrics | ✅ active | `GET /api/v1/admin/deprecation/v1-metrics` |
| Hit metrics reset | ✅ active | `POST /api/v1/admin/deprecation/v1-metrics:reset` |
| V1 routers inventory | ✅ active | `GET /api/v1/admin/v1-inventory` |
| No-traffic candidates | ✅ active | `GET /api/v1/admin/v1-inventory/no-traffic` |
| Lifespan health | ✅ active | `GET /api/v1/admin/lifespan-monitors/health` |
| Ops smoke script | ✅ active | `scripts/ops/check_monitors_health.py` |
| GH Actions monitor health | ✅ active | `.github/workflows/monitors-health.yml` (/30min) |

## §6 Risk Watch

| Stage | Status | Top Risk |
|:---|:---:|:---|
| 1 | ✅ done | (none) |
| 2 | ⏳ pending | manuals upload multipart 殘留須留 |
| 3 | ⏳ pending | technicians me 系列分流；work-orders subflow 漏遷 |
| 4 | ⏳ pending | M18 vs system config 兩軌混淆 |
| 5 | ⏳ pending | dual-sign UX 流失資料 |
| 6 | ⏳ pending | LINE Flex 舊 URL 失效 |
| 7 | ⏳ blocked | 30d 觀察 + 業主批准 |

## §7 啟動下一 Stage 條件

**Stage 2 可啟動**：
- ✅ Stage 1 backend 完成
- 🟡 Stage 1 部署到 production
- 🟡 Stage 1 metrics reset 跑 7d 看 no-traffic 候選含 kb/manuals

**Stage 7 可啟動**（最終）：
- 🟡 Stage 1-6 全 merge to production
- 🟡 production 跑 30+ 天 metrics 觀察
- 🟡 `GET /admin/v1-inventory/no-traffic` 顯示 ≥80% 無流量
- 🟡 客戶端 0 v1 流量
- 🟡 業主批准

## §8 Lessons learned (session 累積)

1. **Inventory 統計可能高估** — 多輪 grep + 文件審查後實際待遷比原統計少 ~20%
2. **User-scoped path 永久保留** — auth/me/availability 系列不該強遷 tenant-scoping
3. **Multipart upload 保留 v1** — HTTP semantic 與 path-based routing 互動
4. **Tooling 先於 BUILD** — 本 session 落 metrics + inventory + health + script + CI 5 件，
   Stage 7 BUILD 時直接有自動候選清單，不需重盤點
5. **三同步紀律** — code commit 必同步 docs 進度 marker；本 dashboard 即聚合單一事實來源

---

**未來 BUILD 啟動人**：從本 dashboard §7 看條件是否滿足，再對應 Stage checklist 走 step-by-step。
