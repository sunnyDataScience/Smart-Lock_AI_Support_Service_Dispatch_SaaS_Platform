---
id: CR-0112
title: 師傅端與派工方前後端拆分為兩套 docker compose(含 DB 配置)
status: implemented
created: 2026-07-03
owner: sunny
tier: 4
related: [ADR-0107, CR-0110, 20260702 會議記錄 §三]
---

# CR-0112 — 師傅端/派工方雙 stack 拆分 Change Impact Analysis

## §1 變更請求

業主(2026-07-03)要求:「把師傅的前後端跟派工方的前後端分開成兩個 docker yaml 來起;
資料庫也要按照規劃方式設計 —— 師傅是全部共用,派工方是單獨。」

對應 20260702 會議 §三拍板:一品牌一 GCP 專案 + 獨立 DB;**師傅端例外** ——
師傅平台只有一個(所有品牌共用),不做獨立部署。

## §2 觸發面向

命中 CIA 硬性觸發:**Architecture boundary**(新增部署單元、移動服務邊界)、
**External integration**(跨 stack 網路)、**DB schema / 資料拓撲**(每品牌獨立 DB 實例)。

## §3 現況事實(2026-07-03 四路盤點,精準到行號)

### 3.1 🛑 Source of Truth 衝突(必須先裁決)

- **會議記錄 §三**:「師傅資料庫已獨立」
- **Code 現實**:全系統**單一 DB、單一全域連線**(`api/core/db.py:17-41`,唯一
  `POSTGRES_URI`;agent 亦同一顆,`agent/lockcore/agent/user_memory/provider.py:102`)。
  技師主檔在 `public.technicians`(`SQL/Schema.sql:435`),無第二 DB URI、無
  TECH_POSTGRES、無 search_path 切換 —— 「已獨立」最多只能解讀為 saas.* schema
  前綴之分,且大量跨 schema 同交易(如 `technician_lifecycle_service.py:99-122`)。

### 3.2 物理拆庫的五大斷點(技師庫 ↔ 品牌庫)

| # | 斷點 | 證據 |
|---|---|---|
| 1 | 搶單/指派狀態機:技師 accept 與派工 assign 更新**同一** work_orders row | `work_order_service.py:845` vs `:1450` |
| 2 | 技師核准單一 transaction 跨 public.technicians + public.users + saas.technician_lifecycle_event | `technician_lifecycle_service.py:99-122` |
| 3 | 月結單條 SQL JOIN public.work_orders × saas.settlement/reconciliation | `monthly_settlement_service.py:130-133` |
| 4 | 完工證據硬閘:技師上傳 media/簽名,品牌側發票/爭議讀同批表 | `work_order_service.py:949`、`invoice_service.py:88-92` |
| 5 | 排班:技師申請與 admin 核准同表同列 | `technician_schedule_service.py:279/:328` |

共 10+ 張雙邊讀寫耦合表(work_orders、technicians、users、work_order_events、
digital_signatures、media_files、technician_schedule_requests、saas.technician_statement 等)。
**結論:資料面物理拆分需先建跨庫同步/內部 API 層,約 1-2 週工程,7/9 UAT 前不可行。**

### 3.3 服務面拆分的既有阻礙(可低成本解)

- `api/main.py:212-321` include_router 無條件全掛,無 surface flag。
- `api/main.py:133-172` lifespan 啟動 10 個 in-memory 背景 worker(SLA、LINE push
  outbox、cron)—— **兩個 API 實例接同一 DB 會雙跑**(重複推播/重複告警),拆分時必須閘。
- Realtime WS 為 in-memory pubsub(`main.py:389-523`):事件只在「發生所在實例」廣播。
  雙實例後跨端即時推播斷;前端有優雅降級(空 base = 不訂閱、照常 fetch,`realtime.ts:148`)。
- Web 端兩側 chrome 已天然分離(Sidebar / TechShell 各頁自掛,無共用 layout),唯一
  全域交會點 AuthGuard(`AuthGuard.tsx:23-32`);`NEXT_PUBLIC_APP_MODE` 全 repo 零出現,
  同 code 兩 build 約動 7 檔。
- compose DB 新機器起來是**空的**(pgdata 為 2026-06-16 手動 restore 遺產,
  `docker-compose.yml:3-5`);拆 stack 順帶需要可重現的 init(Schema.sql → Schema_*.sql
  → migrations → seeds,順序見 `scripts/dev/quickstart.sh:105-144`)。
- agent(LINE bot)歸品牌側:每品牌一個 LINE 官方帳號,internal bridge 打品牌 API
  (`docker-compose.yml:73`),記憶庫用同 DB `agent.*` schema。

## §4 方案

### 方案 A(推薦)— 服務面拆到位,資料面此輪仍讀品牌庫

- `docker-compose.dispatch.yml`(品牌 stack,**每品牌一套**):brand-db(獨立實例
  + 獨立 volume,以 `BRAND` 環境變數參數化名稱/埠)+ api + agent + web(dispatch build)
  + 一次性 db-init(套 schema/migrations/seeds)。
- `docker-compose.tech.yml`(師傅 stack,**全品牌共用一套**):tech-api
  (`API_SURFACE=tech`:只掛技師面 router、關背景 worker)+ tech-web(tech build)。
  **不帶自己的 DB** —— 經 external network 連品牌 DB(UAT 期單品牌)。
- 技師共用庫的物理拆分(同步層設計)記入 AI-2/AI-3 待辦,設計定案後遷移。

### 方案 B — 技師身分庫先拆半套

tech DB 放 users(technician)/technicians/schedule,工單留品牌庫。斷 §3.2 之 1/2/3/5,
需改 5+ service 成跨庫呼叫。**1-2 週,7/9 前不可行。**

### 方案 C — 雙全庫 + 排程同步

兩庫全 schema、腳本對拷。一致性風險極高(工單狀態雙寫衝突),不建議。

## §5 API contract 影響

無 endpoint 新增/刪除/схema 變動。新增部署層環境變數:`API_SURFACE`
(all|dispatch|tech,預設 all —— 既有部署/測試零行為變化)。

## §6 DB 影響

無 schema 變動。新增「每品牌一顆 Postgres 實例」的部署拓撲;新 stack 空庫由
db-init 一次性服務套既有 Schema/migrations/seeds(不新增 migration)。

## §7 測試影響

- 既有 pytest 全綠必須維持(API_SURFACE 預設 all)。
- 新增驗證:tech stack 起來後技師登入/看池;dispatch stack 起來後 admin 登入;
  tech-api 上派工端點不存在(404);背景 worker 只在 dispatch api 跑。

## §8 Human Decisions Required(業主 2026-07-03 已裁決)

1. **資料面策略**:✅ **方案 A** —— 服務面拆到位,資料面此輪共用品牌庫;
   技師共用庫物理拆分列 AI-2/AI-3 設計案。
2. **tech API 形式**:✅ **獨立 tech-api 實例**(`API_SURFACE=tech`,只掛技師面
   路由、背景 worker 停用)。
3. **前端拆法**:✅ **同 code 兩 build**(`NEXT_PUBLIC_APP_MODE=dispatch|tech`,
   build-time 烤入;`NEXT_PUBLIC_PEER_PORTAL_URL` 供跨端連結)。
4. **SoT 衝突**:✅ **接受現實解讀** —— 會議「師傅資料庫已獨立」視為目標規劃
   而非現況;本 CR §3.1 為正式記錄。

### 進度

- ✅ S1-S4 done:api `API_SURFACE`(surface 過濾 + worker 閘,預設 all 零影響)、
  web 兩 build(appMode.ts + AuthGuard + landing/交叉連結 + Dockerfile ARG)、
  `docker-compose.dispatch.yml`(BRAND 參數化 + db-init profile)、
  `docker-compose.tech.yml`(external network 連品牌 DB)。api 全套 1544 passed、
  tsc 0;預設品牌 pgdata 由舊 volume clone 為 `lock-dispatch-locksmart-pgdata`
  (舊 volume 留備援)。

## §9 Suggested Implementation Order(依 §8 裁決後)

1. api:`API_SURFACE` surface map + worker 閘(`main.py`,預設 all 零影響)
2. web:`NEXT_PUBLIC_APP_MODE` 兩 build(appMode.ts、AuthGuard、rolePolicy 跨端
   落點、landing/交叉連結、Dockerfile ARG)
3. `docker-compose.dispatch.yml`(BRAND 參數化 + db-init profile)
4. `docker-compose.tech.yml`(external network 連品牌 DB)
5. pytest 全綠 + tsc + 兩 stack 實起驗證(§7)
6. 文件:本 CR 進度、CHANGELOG、completion-status、docs_html regen
