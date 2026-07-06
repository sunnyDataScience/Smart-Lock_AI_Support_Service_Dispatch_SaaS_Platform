---
id: CR-0116
title: "平台 console 維運監控:品牌部署 registry + 跨品牌 /health 紅綠燈"
status: draft
tier: 4-exploration
owner: HYBRID
created: 2026-07-06
target-release: dev_new_arch
product-version: null
supersedes: null
superseded-by: null
---

# CR-0116: 平台 console 維運監控（品牌部署 registry + 跨品牌 /health 紅綠燈）

> **Tier**: 4-exploration → Change Impact Analysis（per-change ephemeral；實作後歸檔）
> **Mandated by**: `.claude/rules/change-governance.md`
> **命中觸發面**：DB schema（新表）／API contract（新端點）／External integration（呼叫品牌 /health）→ 需 CIA gate。

---

## 1. Change Statement

**As-is**：平台 console（:3003）儀表板只有「概覽（待審計數）」一種視圖。「一品牌一個 GCP 專案」部署下，要看各品牌 Cloud Run 服務（agent/api/web）活著沒，只能一家一家開 GCP Console 視窗，超過 10 個視窗還有上限，管多家分店時不可行（2026-07-02 會議 §十 + Action Item 12）。

**To-be**：平台庫新增「品牌部署 registry」（UI 可增/修/刪各監控目標的 health URL），儀表板加「**維運監控**」分頁，後端**並發探測**所有登記目標的 `/health`，一頁紅綠燈（正常／降級／掛掉）呈現全品牌服務狀態。

**Driver**：業主於架構討論中選定**方案 B（DB registry + UI 管理）**。定位＝「**給非技術者（Sunny/Irene）一眼看的紅綠燈**」，不用發 GCP 權限、打開 3003 就看到哪家亮紅燈（呼應會議 §七：Sunny 要能自己點過看狀態）。**深度指標與主動告警走 GCP 原生（Metrics Scope + Uptime Check + Alerting，方案 1/2，業主自理）**——本 CR 的 console 頁**不做**告警／歷史／uptime%，只做即時健康快照。

## 2. Affected Flow

| Flow ID | Action | Description |
|---|---|---|
| （新）`SF-platform-monitor-manage` | New | 平台管理員在 console 增/修/刪「品牌部署監控目標」（brand + label + health URL + 啟用）|
| （新）`SF-platform-monitor-probe` | New | 平台管理員檢視「維運監控」分頁 → 後端並發探測所有啟用目標 /health → 回傳即時狀態 |
| 既有品牌／師傅 flow | Unchanged | 不動任何派工/註冊/審核既有流程；純新增內部維運視圖 |

## 3. Affected Spec (FR / NFR)

| Spec ID | Action | Description |
|---|---|---|
| （新）`FR-monitor-registry-crud` | New | 監控目標 registry 的 list/create/update/delete（require_platform_admin）|
| （新）`FR-monitor-health-fanout` | New | 對所有啟用目標並發 GET `/health`，映射 200→up / 503→degraded / 逾時或其他→down，回傳 {status, httpCode, latencyMs, checkedAt} |
| （新）`NFR-monitor-probe-budget` | New | 單目標逾時上限（建議 3s）、並發探測（非序列）、總回應上限（建議 ≤5s），避免慢目標拖垮整頁 |

## 4. Affected API

全部**新增、additive、無 breaking**（新前綴 `/api/v1/platform/monitor-targets`，無既有 caller）。皆 `require_platform_admin`（platform surface）。

| API ID | Endpoint | Action | Breaking? | Notes |
|---|---|---|---|---|
| （新）`API-monitor-list` | `GET /api/v1/platform/monitor-targets` | New | No | 列 registry 全部目標 |
| （新）`API-monitor-create` | `POST /api/v1/platform/monitor-targets` | New | No | 新增一目標（brand/label/url/enabled）|
| （新）`API-monitor-update` | `PATCH /api/v1/platform/monitor-targets/{id}` | New | No | 修改目標 |
| （新）`API-monitor-delete` | `DELETE /api/v1/platform/monitor-targets/{id}` | New | No | 刪除目標 |
| （新）`API-monitor-health` | `GET /api/v1/platform/monitor-targets/health` | New | No | **並發探測**所有啟用目標，回即時狀態陣列 |

> 路由排序：字面段 `health` 需排在 `{id}` catch-all 之前（比照 lifecycle-events 慣例）。

## 5. Affected Data

平台庫（`lock_platform`）新增一表，走 `SQL/platform/Schema_platform.sql` **冪等 additive**（`CREATE TABLE IF NOT EXISTS`，與 brand_applications 同機制；**非** brand 的 `SQL/migrations/NNN`）。

| Entity | Action | Migration |
|---|---|---|
| （新）`public.monitor_target` | New table | 加入 Schema_platform.sql；套本機平台庫（idempotent 可重跑）|
| （選）狀態歷史表 | **待 §8-Q3 決定** | MVP 建議**不建**（歷史/uptime% 屬 GCP 方案 2）|

**提案表結構（欄位集待 §8-Q1/Q2 定案）**：

```sql
CREATE TABLE IF NOT EXISTS monitor_target (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand       VARCHAR(80)  NOT NULL,          -- 分組標籤（品牌 key，如 locksmart）
    label       VARCHAR(80)  NOT NULL,          -- 服務標籤（API / Agent / Web）
    url         VARCHAR(500) NOT NULL,          -- 完整 health URL（含 path）
    enabled     BOOLEAN      NOT NULL DEFAULT TRUE,
    sort_order  INT          NOT NULL DEFAULT 0,
    note        VARCHAR(255),                   -- 選填備註
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

無狀態機變更。無既有資料 migration（新表，本機 seed 三個本地目標供測試）。

## 6. Affected Test

| Test ID | Action | Description |
|---|---|---|
| （新）`TC-monitor-crud` | New | registry CRUD + RBAC（401 未帶 token / 403 非 platform_admin）|
| （新）`TC-monitor-health-mock` | New | fan-out probe：mock 目標回 200/503/timeout → 映射 up/degraded/down |
| （新）`TC-monitor-route-order` | New | `health` 字面段不被 `{id}` 吃掉 |

覆蓋率：+3 TC（platform surface）。

## 7. Affected Architecture

| Concern | Action | Notes |
|---|---|---|
| Module boundary | 新增 | platform-api 加 `monitor` service + router（隔離於 /platform surface）|
| **External integration** | **新增** | platform-api **主動外呼**各品牌 Cloud Run `/health`（跨 GCP 專案，走公開 URL；deploy script 佐證 /health 無 auth）|
| 出站 HTTP client | 需確認 | 用 httpx（若已為 dep）否則 stdlib asyncio + urllib in thread；per-target timeout + 並發 |
| 容器網路 | 注意 | **本機**：platform-api 容器打其他 stack 需用 docker 服務名（非 localhost）；**正式**：品牌 Cloud Run 公開 URL |
| 新 ADR? | 否（輕量）| 探測採「前端輪詢 → 後端 fan-out、不存歷史」，與 GCP 告警分工明確，不需獨立 ADR（除非 §8-Q3/Q4 改走排程+歷史）|

## 8. Human Decisions Required

✅ **§8 已於 2026-07-06 由業主裁決完畢，解除封鎖。**

| # | 問題 | 選項 | 我的建議 | Status | 裁決（2026-07-06 業主）|
|---|---|---|---|---|---|
| 1 | **監控粒度** | (a) 一品牌一列（只監 api /health） (b) **一目標一列**（brand+label 分組，agent/api/web 各可獨立一列）| **(b)** 最彈性，flat registry 好維護 | ✅ resolved | **(b) 一目標一列 flat** |
| 2 | **registry 欄位集** | (a) 最小（brand/label/url/enabled/sort） (b) 加 project_id/region/note (c) 其他 | **(a) + note 選填**（§5 提案）| ✅ resolved | **(a) 最小 + note 選填**（採建議）|
| 3 | **要不要存狀態歷史 + uptime%？** | (a) **不存**，只做即時紅綠燈 (b) 存歷史表 + 算 uptime% | **(a)**——歷史/uptime/告警是 GCP 方案 2 的事，console 不重造 | ✅ resolved | **(a) 不存歷史，即時紅綠燈**（MVP）|
| 4 | **探測執行點** | (a) **前端輪詢 → 後端 fan-out**（page 開才打） (b) 後端 Cloud Scheduler 定時 | **(a)** 簡單、無排程、與「即時看」定位一致 | ✅ resolved | **(a) 前端輪詢 → 後端 fan-out** |
| 5 | **URL 存法** | (a) **存完整 health URL** (b) 存 base，後端自動加 /health | **(a)** 最直白（各服務 health path 可能不同，各自填）| ✅ resolved | **(a) 存完整 health URL**（採建議）|
| 6 | **探測憑證** | /health 皆公開免 auth（deploy script curl 無 auth 佐證）→ 無需存憑證 | 確認採此前提（低風險）| ✅ resolved | **公開免 auth，不存憑證**（採建議）|
| 7 | **輪詢頻率 / 逾時** | 前端每 N 秒輪詢；單目標逾時 | 建議每 **30s** 輪詢、單目標逾時 **3s**、總上限 5s | ✅ resolved | **30s 輪詢 / 3s 單目標逾時 / 5s 總上限**（採建議）|

> **淨結果**：flat registry（一目標一列）、最小欄位 + note、**無歷史表/無排程**（純即時）、前端 30s 輪詢後端並發 fan-out、存完整 health URL、目標免 auth。→ §5 提案表結構原案採用，不加歷史表。

## 9. Suggested Implementation Order

§8 定案後，依序（單一分支 `feat/platform-ops-monitoring`，--no-ff 併回 dev_new_arch）：

1. **Schema** → `SQL/platform/Schema_platform.sql` 加 `monitor_target`（依 §8-Q1/Q2 定欄位）；套本機平台庫
2. **Backend service** → `platform_monitor_service`（CRUD + fan-out probe：並發、per-target timeout、狀態映射）
3. **Router** → `platform_monitor.py` 5 端點（require_platform_admin，路由排序 health 先於 {id}），mount `main.py`（platform surface allowlist）
4. **本機 seed** → 三本地目標（dispatch api / tech api / platform api 的 /health，用 docker 服務名）供測試
5. **Frontend** → `/platform` 儀表板改**分頁**（`概覽` ｜ `維運監控`）；維運監控 tab＝registry 管理（增/修/刪 modal）+ 紅綠燈狀態格（依 brand 分組）+ 前端輪詢
6. **Tests** → `TC-monitor-*` ×3
7. **Docs 三同步** → CHANGELOG `[Unreleased]` + `system-completion-status.md` + 本 CR §進度；docs_html regen（復原未追蹤 20260701/20260709）
8. **驗證** → pytest 全綠 + tsc 0 + 重建 platform api+web + Playwright（新增目標→紅綠燈→停某服務轉紅）

## 10. Risks & Rollback

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| 慢/掛的目標拖垮整頁 | Medium | Medium | per-target timeout（3s）+ 並發（非序列）+ 總上限；逾時即標 down 不 block |
| 容器網路：本機打不到其他 stack | Medium | Low | 本機 seed 用 docker 服務名（非 localhost）；正式用公開 Cloud Run URL |
| platform-api 出站被當跳板（SSRF 面）| Low | Medium | URL 僅 platform_admin 可設；MVP 可接受，未來加 allowlist/私網限制 |
| 與 GCP 方案 1/2 功能重疊 | Low | Low | 定位切割清楚：console＝即時紅綠燈；GCP＝深度指標+告警+歷史 |

**Rollback**：功能隔離於 /platform 監控分頁 + 獨立表/端點。回退＝移除分頁與端點；`monitor_target` 表 additive（IF NOT EXISTS，不影響既有），可留可 drop。

## 11. Out of Scope

- **告警/通知**（Uptime Check + Alerting → LINE/Email）→ GCP 方案 2，業主自理
- **uptime% / 狀態歷史報表** → GCP 方案 2（除非 §8-Q3 改 (b)）
- **自動從 GCP 探索服務清單**（方案 C）→ 未採用
- **Cloud SQL / DB / 非 Cloud Run 資源的深度指標** → GCP Metrics Scope（方案 1）
- **platform console 上雲部署**（監控頁看正式環境的前提）→ 既有 roadmap 待辦，非本 CR

## 12. Sign-off

| Role | Name | Date | Approved? |
|---|---|---|---|
| Product（業主）| Sunny | 2026-07-06 | ✅ §8 七項裁決 |
| Architect | | | |
| Engineering Lead | 啟恆 | | |
| QA Lead | | | |

## 13. 實作進度

- ✅ **S1 done**（branch `feat/platform-ops-monitoring`）：Schema `monitor_target`（`SQL/platform/Schema_platform.sql` 冪等 additive）+ 本機平台庫套用 + seed 三本機目標（dispatch/tech/platform api /health，docker 服務名）。
- ✅ **S2 done**：後端 `platform_monitor_service`（registry CRUD + `probe_health`：aiohttp 並發、單目標逾時 3s、狀態映射 200→up/503→degraded/其他→down、不落庫）+ `platform_monitor.py` 5 端點（`health` 字面段先於 `{id}`，全 `require_platform_admin`）+ mount main.py（platform surface 天然涵蓋 `/api/v1/platform` 前綴）。
- ✅ **S3 done**：前端 `/platform` 儀表板改分頁（概覽｜維運監控）+ `OpsMonitorPanel`（registry 增/修/刪 modal + 依 brand 分組紅綠燈 + 30s 輪詢 + 立即檢查）。
- ✅ **S4 done**：`test_platform_monitoring.py` 11 項通過（CRUD / RBAC 401·403 / 驗證 422 / `_map_status` 純函式 / probe 只回啟用目標且 `health` 路由不被 `{id}` 吃）。
- ✅ **S5 done**：驗證 —— tsc 0；重建 platform api+web；curl 佐證（3 目標 up 200；打不通目標 status=down err=ClientConnectorDNSError 快速失敗）；Playwright 端到端（登入→維運監控 3 目標全綠依品牌分組→新增打不通目標顯示「異常」紅燈、摘要 1 異常→30s 自動輪詢延遲更新→清測試目標）。
- ⏳ **雲端**：待 platform console 上雲部署 + 業主以 UI 登記正式各品牌 Cloud Run health URL（`https://<svc>-<hash>.run.app/health`）。

> **與 GCP 方案分工再述**：本 CR = console 即時紅綠燈（非技術者一眼看）。業主自理 GCP 方案 1（Metrics Scope 跨專案 dashboard）+ 方案 2（Uptime Check + Alerting → LINE/Email，主動告警與歷史）。兩者互補，不重疊。
