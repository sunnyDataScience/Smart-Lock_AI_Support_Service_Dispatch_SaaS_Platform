---
id: P4-CUTOVER-INVENTORY
title: P4 Cutover v1 caller 盤點（2026-06-05）
status: open
created_at: 2026-06-05
related_cr: CR-0003 P4
purpose: P4 Cutover 啟動前的 v1 caller 完整清單；分類成可刪 / 須遷 / 慎刪三類供 BUILD 決策。
---

# P4 Cutover v1 Caller 盤點

> 2026-06-05 在本 session 大躍進完成 Phase II 9 FR + 多 cron 後盤點；
> dev_new_arch 此時 commit ~`931ed836`。

## §1 Web 端殘留 `/api/v1/*` 統計

```
prefix              refs    分類    建議
─────────────────────────────────────────────
accounting          1       慎刪    Reconciliation dual-sign UX rework
auth                6       可遷    auth/login/refresh 已有 v2
config              7       慎刪    系統設定 v2 已有但部分 UI 用 v1
foo                 1       Mock    測試 mock 路徑，刪即可
knowledge-base      3       可遷    cases/manuals v2 有 (CR-0005 落)
manuals             2       可遷    v2 既有 (CR-0005)
public              4       慎刪    consumer_v2 涵蓋部分；scope/track 各端
refunds             1       可遷    refunds_v2 已落 (Track B S2)
reports             1       可遷    reports v2 + 本 session 加 KPI 擴充
roles               1       可遷    auth_v2 已有
technicians         8       可遷    technicians_v2 + 本 session 加 workload_heatmap
work-orders         4       可遷    work_orders_v2 + work_orders_ops_v2 已落 (CR-0003)
─────────────────────────────────────────────
Total               38 refs across 12 v1 prefixes
```

## §2 分類詳述

### 🟢 可刪/遷（v2 已 100% 對齊；遷移即可）

| Prefix | refs | 對應 v2 router | 狀態 |
|:---|:---:|:---|:---|
| `auth` | 6 | `auth_v2.py`、`core/auth.py` | v2 endpoint 100% 完成 |
| `foo` | 1 | — | mock 路徑可直接刪 |
| `knowledge-base` | 3 | `kb_cases / kb_manuals` (CR-0005 落) | v2 caller 在 cases/cases-v2 已 90% |
| `manuals` | 2 | `kb_manuals` | 同上 |
| `refunds` | 1 | `refunds_v2.py` (Track B S2) | v2 100% (含 dual-sign) |
| `reports` | 1 | `reports_v2 / reports_kpi / 本 session 加 KPI` | v2 比 v1 多 |
| `roles` | 1 | `auth_v2 + permissions_v2` | v2 100% |
| `technicians` | 8 | `technicians_v2 + workload_heatmap` (本 session) | v2 100% |
| `work-orders` | 4 | `work_orders_v2 + work_orders_ops_v2` (CR-0003) | v2 100% |

**P4 Step 1 — 安全遷移目標**：上述 9 個 prefix / 27 refs。

### 🟡 慎刪/慎遷（產品 UX / 業務決策）

| Prefix | refs | 不能直接遷的理由 |
|:---|:---:|:---|
| `accounting` | 1 | `accounting/page.tsx` 仍用 v1 單簽 `/approve`；v2 改 `:review` + `:co-sign` 兩步流，須前端 UX rework |
| `config` | 7 | `settings/page.tsx` 等管 system config；v2 部分 config 已 M18 governance，但仍有 7 個 v1 ref 須一個個檢查 |
| `public` | 4 | `scope-change/[token]` + `track/[token]` 各有獨立 token endpoint；consumer_v2 涵蓋部分但不全；deprecation 須確認消費者 LINE Flex / Web tunnel 全已遷 |

### 🟢 **永久保留 v1**（user-scoped 不適合 tenant-scoping）— **2026-06-05 補充**

session 末段重新分析發現：原統計的 38 v1 refs 中部分為 **user-scoped 設計**（依 JWT 取 user_id），
非 tenant-scoped business logic，**不該強行遷 v2**。這些屬永久 v1 保留範圍：

| Caller | v1 Endpoint | 為何留 v1 |
|:---|:---|:---|
| `settings/page.tsx` | `POST /api/v1/auth/change-password` | user 改密碼為 user-scoped；無需 tenant path |
| `account/page.tsx` | `GET /api/v1/technicians/me` | 技師 self profile；JWT 取 user_id 即可 |
| `account/schedule/page.tsx` | `PATCH /api/v1/technicians/me/availability` | 同上 |
| `lib/api.ts` | `POST /api/v1/auth/refresh` (line 198) | token refresh 為 auth flow；user-scoped |

v1 docstring 已明示：`api/routers/technicians.py:8` 「只允許登入技師讀寫自己的 profile；admin list/get 僅需 tenant 隔離」— 確認 me/availability 為設計上的 v1。

**追加 (2026-06-05 session 後段)**：

| Caller | v1 Endpoint | 為何留 v1 |
|:---|:---|:---|
| `web/src/app/knowledge-base/manuals/page.tsx:421` | `POST /api/v1/knowledge-base/manuals/upload` | **multipart form 設計上保留 v1**；`api/routers/kb_v2.py:30` + `:214` 明示「若需上傳 PDF 仍走 legacy /api/v1/knowledge-base/manuals/upload」 |

**結論修正**：原統計 38 refs / 12 prefix → 扣掉 ~6 個 user-scoped + 1 multipart upload = ~7 refs 後實際 **待遷 ~31 refs / ~10 prefix**。

P4 Stage 7 (刪 v1 router) **必須保留**：`auth.py` / `technicians.py` 內 me/availability 系列。新 P4 計畫表：
- 刪 v1 router 改為「刪沒有合法 user-scoped 路徑的 v1 router」
- `technicians.py` v1：保留 `me / me/availability / me/profile`；刪 admin list/get/update（v2 已替代）
- `auth.py` v1：全保留（user-scoped）

**P4 Step 2 — 業務 UX 決策**：上述 3 個 prefix / 12 refs；需業主裁決或設計回顧。

### 🟢 已知無 web caller 的 v1 router（可直接刪）

待 P4 BUILD 時 grep 確認下列 v1 router 是否完全無 web caller：
- `api/routers/refunds.py` (有 refunds_v2)
- `api/routers/dashboard.py` (有 dashboard_v2)
- `api/routers/conversations.py` (有 conversations_v2)
- `api/routers/customers.py` (有 customers_v2)
- ... (約 40 個 v1 router)

## §3 P4 Cutover Stage 規劃建議

| Stage | 範圍 | 工時 | 風險 |
|:---:|:---|:---:|:---:|
| **1** | foo mock 刪 + reports/roles/refunds v1 caller 遷 (3 prefix / 3 refs) | 半天 | 🟢 低 |
| **2** | auth (6 refs) + knowledge-base/manuals (5 refs) 遷 | 半天 | 🟢 低 |
| **3** | technicians (8) + work-orders (4) 遷 | 1 天 | 🟢 低 |
| **4** | config (7) 遷 — 須 case-by-case 檢查 | 1 天 | 🟡 中 |
| **5** | accounting (1) Reconciliation dual-sign UX rework | 1-2 天 | 🟡 中（產品 UX 工作）|
| **6** | public (4) consumer token endpoints 整合 | 1 天 | 🟡 中（消費者前端）|
| **7** | 刪所有無 caller 的 v1 router + auth 扁平化 + DeprecationMiddleware 刪 | 1 天 | 🔴 高（破壞性，須 staging 完整驗證） |
| **8** | OpenAPI / generated types 重生 | 半天 | 🟢 低（自動）|

**總估**：5-7 day（對齊 system-completion-status §8 P0 P4 Cutover 工時）。

## §4 風險與緩解

| 風險 | 機率 | 緩解 |
|:---|:---:|:---|
| Web 殘留 v1 caller 漏遷 → runtime 404 | M | Stage 7 前須 grep 全 web 確認 0 v1 reference |
| v1 router 內部互相依賴 → 刪一個破壞另一個 | L | Stage 7 須對所有 v1 router import graph 分析 |
| 客戶端（mobile / 第三方）仍用 v1 endpoint | M | 先在 Cloud Run access log 觀察 30 天確認流量 |
| OpenAPI breaking change | L | Stage 8 自動 regenerate；contract test 驗證 |

## §5 不在 P4 範圍

- 重建 v2 endpoint（已 100% 完成；只遷 caller）
- 業務邏輯重構（純 routing migration）
- Test 重寫（既有 test_*.py 已對 v2）
- 部署環境變動（Cloud Run config 不需動）

## §6 啟動條件

- 業主確認 stage 7 destructive 時機（建議 staging 全測完 + 流量觀察 30 天）
- ops 確認 mobile / 第三方無 v1 流量
- staging 完整 e2e Playwright 跑過

---

**本盤點供 P4 BUILD 啟動前參考**；正式 BUILD 時應重新 grep 確認本 doc 統計仍 accurate（web caller 可能在 P4 啟動前已遷移完成或新增）。
