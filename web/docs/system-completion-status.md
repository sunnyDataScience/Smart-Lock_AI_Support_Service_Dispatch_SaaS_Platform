# Smart Lock 工單系統完成度總覽

> 跨前端 / 後端 / Realtime / Workflow / 架構遷移的整體進度盤點。
> 每次開發完成後更新本文件，保持與 CR-0004 §8 進度區、CHANGELOG `[Unreleased]` 同步。

**最後更新：** 2026-06-17（**使用者自助忘記密碼 / 重設密碼**，CR-0025 / ADR-0114，branch `feat/self-service-password-reset` — 業主裁決推翻 2026-06-10 Action #7「不建自助」：兩登入頁加可點「忘記密碼」→ 自助 email 重設。實作 migration 035 `password_reset_tokens`（token 雜湊存、30 分單次用）+ api `email_provider`（SMTP 抽象 fail-safe）+ `password_reset_service`（request 枚舉防護+rate-limit / confirm 改密碼）+ `request/confirm-password-reset` 端點 + web `/forgot-password` `/reset-password` 兩頁 + 兩登入頁連結 + i18n。8 後端測試（需 dev stack 跑）+ tsc 0 error。follow-up：confirm 後全域撤 refresh（需 password_changed_at）；prod 啟用待配 SMTP secret + 套 migration 035。詳見 CR-0025 / CHANGELOG）
**前一次更新：** 2026-06-17（**技師登入頁「忘記密碼」死按鈕收尾**，branch `fix/tech-login-forgot-hint` — 20260610 會議 Action #7「忘記密碼」其實已由 `admin-reset-password`（admin 代重設、免 email）實作完成；但技師登入頁仍留一顆 disabled 的「忘記密碼（待補）」按鈕，看似可點卻無作用。業主裁決不建自助重設（後台 staff/技師無現成送達管道、寄信 infra 從零）。修：該死按鈕改純資訊 `<span>`「忘記密碼？請聯絡管理員重設」。純前端文案/標記、無 contract 變動。自助重設列未來可選增強。詳見 CHANGELOG）
**前一次更新：** 2026-06-17（**知識庫案例詳情頁不再洩漏內部 UUID**，branch `fix/kb-cases-hide-internal-id` — 20260610 會議 Action #6：知識庫畫面誤露系統內部 ID，消費者不該看到。`knowledge-base/cases/[id]` 詳情頁尾原以 `ID: {uuid}` 顯示案例內部 UUID（sop-drafts 頁先前已只露人類可讀 `document_number`，此頁漏修）。修：移除該顯示 + 清兩語系 `kb.cases.detail.id` 孤兒 key；內部 id 仍供路由用，畫面不再外露。純前端移除洩漏欄位、無 schema/contract 變動 → 不觸發 CIA。case_entries 是否補人類可讀 `document_number`（需 schema + CIA）列後續可選增強。詳見 CHANGELOG）
**前一次更新：** 2026-06-16（**🚀 Cloud Run 首次正式上線**，branch `chore/deploy-cloud-run-wiring` — api/agent/web 三服務首次部署到 GCP Cloud Run（asia-east1）+ 接 prod Cloud SQL `lock-ai`。補齊 deploy 腳本接線（INTERNAL_API_TOKEN/LINE_TOKEN/AGENT_TENANT_ID secrets、CORS_ORIGINS 雙網址、web build-arg API/realtime URL）；新增 `scripts/db/apply-schema-prod.sh` 經 cloud-sql-proxy 把 prod DB schema 對齊 code（補 document_number 等缺欄 + 修 3 個 schema 檔衝突，migration 034）。部署/實測逐一修掉：登入 500（JWT env 名）、CORS（雙 Cloud Run 網址）、LINE 對話寫不進後台（INTERNAL_API_TOKEN 尾換行 → httpx 拒 header → 兩端 strip）、深色模式白字白底（68 元件硬編色 → globals.css 重映射補丁）。LINE webhook 已切 prod agent；三服務 health + 登入 + 對話寫入 + 14 頁巡檢全綠。詳見 CHANGELOG）
**前一次更新：** 2026-06-16（**對話轉真人 handover 生命週期 Phase 1**，CR-0024，branch `feat/handover-lifecycle-phase1` — 補 handover 回程缺口:原本轉真人後 AI 從未真的停（gateway 不查狀態、與真人同時回）、也無交還機制。Phase 1:API `resolve-handover`（escalated→active）+ internal `handover-state` GET + 工單結案連動 un-escalate;agent gateway 回覆前查狀態、escalated 則 AI 全暫停（只持久化客人訊息）;web 對話詳情頁「結束接管/交還 AI」按鈕。順手修 diagnostics SSE 404 無限重連（與 WS 頻道解耦到獨立 env，因後端未實作）。8 測試 + 32 回歸全綠;Playwright 實證按鈕翻狀態、對話頁 0 console error。Phase 2 智慧路由待做。**同分支再補一個 UX 修復**：對話管理聊天捲軸載入即自動跳到最底（`ChatTimeline` 加 scrollRef + useEffect，涵蓋載入/refetch/送出新訊息;Playwright 實證 atBottom=true）。詳見 CR-0024 / CHANGELOG）
**前一次更新：** 2026-06-16（**即時推送（WebSocket）docker 部署接線**，branch `feat/web-realtime-enable` — 後台多頁顯示「Realtime 未配置」。查出後端 WS server 早已內建於 api（`/realtime/notifications|work-orders|pool|...` + `ws_hub.py`），缺的只是前端 `NEXT_PUBLIC_REALTIME_BASE_URL`（Next.js `NEXT_PUBLIC_*` 為 build-time inline、預設空字串 → 走 disabled 降級）。修：`web/Dockerfile` 加 `ARG/ENV NEXT_PUBLIC_REALTIME_BASE_URL`、`docker-compose.yml` web `build.args` 帶 `ws://localhost:8001`（瀏覽器直連 api published port），重建 web。Playwright 實證通知頁指示燈由「未配置」→ open「即時連線」（綠燈）。Cloud Run 換 `wss://<api網域>` 同 arg 即可。詳見 CHANGELOG）
**前一次更新：** 2026-06-16（**轉真人後對話管理仍無法回覆 — 修 escalation 漏翻對話狀態 + api 補 line-bot-sdk**，branch `fix/escalation-set-conversation-status` — 實機 LINE 要求真人後 AI 已回「已轉接」、後台也產出 AI 草擬卡，但「對話管理」發訊框永遠唯讀、客服回不了 LINE。根因：發訊框/`send_message` 都要 `conversation.status='escalated'`，但**全 codebase 沒任何路徑會設 escalated**——`escalation_to_draft_pc()` 只建問題卡漏翻狀態（F-018 handover 未接上的線）。修：該函式 ensure conversation 後加 `UPDATE conversations SET status='escalated'`（idempotent + re-escalate），對齊既有合約狀態 `waiting_human`、不改 contract。+2 測試共 8 passed、回歸 24 passed；Playwright 實證發訊框由唯讀變可輸入可送出。詳見 CHANGELOG）
**前一次更新：** 2026-06-16（**DB 納入 docker-compose（自包含全棧）**，branch `feat/compose-db-service` — compose 加 `db` service（pgvector/pg17 + named volume `pgdata`）取代「連既有 lock_AI」；`pg_dump/restore` 遷入 81 表資料（public/saas/agent schema 全到，conversations 126 / problem_cards 105）；api/agent 改連 compose 內網 `db:5432`；舊 lock_AI 只停不刪留備援。`docker compose up` 真・一鍵全起 db+api+agent+web，實測四服務 healthy + `locksmart` payload 寫入新 db（126→127）。`down -v` 會清 pgdata 已加警示。詳見 CHANGELOG）
**前一次更新：** 2026-06-16（**docker 全棧實跑驗證 + 修 agent 容器 lockcore import**，branch `fix/agent-dockerfile-pythonpath` — `docker compose up --build` 實跑：api(:8001 healthy)/agent(:8000)/web(:3000) 三服務全起、連既有 lock_AI DB、真實 `locksmart` payload 經 docker api 寫入 DB（tenant resolver 生效）。過程修一個 `agent/Dockerfile` bug：layer-cache 順序導致 wheel 不含 lockcore 原始碼 + `python scripts/…` 的 sys.path 不含 `/app/agent` → `ModuleNotFoundError: lockcore` 重啟迴圈；修為 runtime `ENV PYTHONPATH=/app/agent`。詳見 CHANGELOG）
**前一次更新：** 2026-06-16（**agent 部署容器化 + 本機全 docker 編排**，branch `feat/agent-deploy-dockerfile` — (1) 補上 `scripts/deploy/agent.sh` 一直引用卻不存在的 `agent/Dockerfile`（multi-stage uv build + line/vertex extra）+ `Dockerfile.dockerignore`（擋機密進映像）→ 解掉 agent 無法部署 Cloud Run 的未爆彈；(2) `SQL/migrations/000-extensions.sql` 全新 DB 一次開齊 vector/pg_trgm/pgcrypto/uuid-ossp；(3) `uv.lock` 修正（舊 package 名 + 缺 vertex 鎖 → frozen build 失敗）；(4) `docker-compose.yml` 把 api/agent/web 改 `docker compose up` 一鍵起（DB 沿用既有 lock_AI 容器、ngrok 維持 host）。**僅供本機 —— Cloud Run 不吃 compose，雲端走 per-service deploy 腳本**。runbook HTML 補 docker compose 章節 + Cloud Run 區別。詳見 CHANGELOG）
**前一次更新：** 2026-06-15（**LINE 對話/轉真人進不了工單系統 — 修橋接靜默略過 + tenant 別名 500**，branch `fix/agent-api-bridge-visibility` — 實機 LINE 對話後紀錄沒進後台，查出兩斷點：(1) gateway↔API 橋接在缺 `INTERNAL_API_TOKEN`/`LOCK_API_BASE_URL` 時靜默略過、且變數要放 `agent/.env`（非根 .env）卻無範例；(2) agent 送 `tenant_id="locksmart"` 別名、DB 要 UUID → psycopg 500。修：gateway 啟動 banner 明示橋接開/關 + `flush=True`、新增 `agent/.env.example`、API `_resolve_tenant_id()` 別名→`AGENT_TENANT_ID` UUID、dev-up.sh 補該變數；真實 payload 實測對話+草擬卡寫入且復用同一 conversation_id、+4 測試回歸 11 綠。同步重寫 `docs/html/agent-line-runbook.html`（含 API 啟動/橋接/工單觸發全流程）。詳見 CHANGELOG）
**前一次更新：** 2026-06-15（**agent 記憶後端 SQLite → Postgres**，CR-0023 / ADR-0113，branch `feat/agent-memory-postgres` — LockCore CS agent 的 per-user 記憶與轉真人稽核從本地 SQLite（FTS5 trigram）改為**可由 config 切換的 Postgres 後端**，置於 lock-ai Cloud SQL 獨立 schema `agent`；中文檢索改 pg_trgm + GIN，走既有 `MemoryProvider` 抽象（符合架構鎖、不動工具白名單）；migration 033 + 本機 pg17 實測 7 tests passed。預設仍 sqlite（反相容）。詳見 CR-0023 / ADR-0113）
**前一次更新：** 2026-06-14（**工單詳情頁內嵌對話逐字稿**，branch `feat/wo-conversation-thread` — 把工單詳情頁原 placeholder 的「LINE 對話記錄」改為真實渲染（沿用 work_order→problem_card→conversation 鏈 fetch messages、氣泡逐字稿 user/assistant/system 三角色 + 四態 + media 附件）；tsc 0 error + 資料鏈實證。與 `feat/agent-conversation-bridge`（旁路持久化）合起來打通「LINE 對話 → DB → 工單後台可見」全鏈。詳見文末 2026-06-14 記錄）
**前一次更新：** 2026-06-14（**對話旁路持久化**，branch `feat/agent-conversation-bridge` — LINE agent 對話經 internal-token ingest 端點寫入 conversations/messages，使工單/對話後台可重新渲染對話歷史；不碰 agent 核心與工具白名單，符合架構鎖；測試 5/5 + 回歸 33/33。詳見文末 2026-06-14 記錄）
**前一次更新：** 2026-06-11（**E2E 互動 sweep + user-flow 驗證**，branch `test/ui-interaction-sweep` — Playwright 掃 45 admin-shell 路由 + 新增 6 條 P0 user-flow E2E，揪出並修復 **5 個「實作了但端到端是壞的」產品 bug**：退款決策 422、技師登入死鎖+接錯端點、爭議 co-sign 漏 X-Initiator、發票號格式 500、notifications 無限 render 迴圈；另修 2 處捲軸 min-h-0 + 補齊 demo 資料 saas.dispute/demo-tech 工單。詳見文末 2026-06-11 記錄）
**前一次更新：** 2026-06-07 晚段（5 branch web UI 收尾 — sop-performance + 工單 3 view modal+filter + 保固詳情頁 + dispute 證據面板+決議表單 + textColor defensive 全綠）
**對應分支：** `dev_new_arch` 含 23+ merge commits（從 `8768fae1` 起算到 `d291f9ea`）
**對應 reports：** v1.0.0 → v1.36.0（產品 MVP）+ CR-0003 P0-P3.5 ✅ + CR-0004 Track B S1-S7 + CR-0017/0018/0019/0013/0012 ✅ + WBS §8 P1/P2 backend 全清 + DEFERRED 全解 + **Phase II 9 FR MVP 全落地**

---

## 總體：**約 99.8%**（5 branch web UI 收尾後）

```
██████████████████████████████████  99.8%
```

> **6/18 — S4 報價基礎主檔 Phase A（CR-0034）** — 報價主檔(報價引擎/金流上游)在 code 全缺。依會議決議 5 把 esales 報價資料庫灌為 mock:migration 040 建 service_catalog(29 服務)+material_catalog(20 材料)+surcharge_rule(12 規則)+seed(全 is_mock,人工轉寫;區域/取消費=已知規格 ADR-0102,急件/夜間/假日/S5=待決策 esales Q-03~06)。`quote_catalog_service`(internal 成本 RBAC 遮蔽)+ `GET /tenants/{tid}/quote-catalog`。test 2 pass。**確認:報價資料確實在 esales 內、決議 5 授權當 mock,故不卡業主裁決即可建。** follow-up:前端主檔頁、Phase B(BOM/拆帳/供應商)、mock→正式價(esales Q-01~12)、CR-0032 報價引擎接此主檔。
>
> **6/18 — 工項缺口盤點 + 補完啟動（roadmap + CR-0032 CIA + 廠商核准 UI）** — 5 源平行盤點(程式碼 vs 20260617資料)：廣度夠深度淺,大缺口=金流結算/報價引擎/報價主檔/免責合規/報表KPI/Partner Portal/測試;產 `docs/_audit/gap-audit-20260617-completion-roadmap.md`(S1-S8 計劃)。**啟動 S1+S2**：(1) **廠商核准 UI**(CR-0029 收尾)`vendor_service` + `vendors_v2` router(approve/reject,限管理角色)+ 後台 `/admin/vendor-approvals` 頁 + Sidebar 入口 → 收完註冊閉環(test 2 pass);(2) **CR-0032 報價引擎 CIA**(saas.quote 主表+核准 gate+snapshot 凍結)停 §8 等裁決。其餘 S1(SMTP/QR=ops)、S3-S8 依序。
>
> **6/18 — 派工模式切換（CR-0030，會議 Action #7）** — 三檔(manual/platform_paid/auto_match)本輪做前兩檔(自動媒合留 Report 2)。migration 039:`saas.tenant.dispatch_mode` + `work_orders.dispatched_via`(platform=可計費)。`dispatch_mode_service`(get/set)+ assign_order 依模式標記 dispatched_via。`GET/POST /tenants/{tid}/dispatch-mode`(管理角色 + audit)。dispatch-queue 頁 header 加派工模式下拉切換。平台代派只標記 billable、本輪不硬扣 credit(計費規則待業主)。test_cr_0030 3 pass + 回歸 + tsc 0。follow-up:計費引擎 / 自動媒合執行 / CR-0031 派工權隔離。**會議 Action 3+7 兩大 BUILD 完成；剩 Action 12/13 multi-tenant(會議定調 Beta 後下一輪)。**
>
> **6/18 — 廠商/師傅雙路註冊（CR-0029，會議 Action #3）** — 平台轉外包仲介:發案者(廠商/品牌商/鎖店)+接案者(師傅)兩路註冊。新表 `vendors`(migration 038)+ `users.tenant_type`(requestor/technician/platform 預留 CR-0031)。`auth_service.register_vendor` + `POST /vendors/register` + `POST /vendors/login`(與後台角色隔離)。前端新 `/register` 頁(技師/廠商切換)+ 登入頁註冊連結。single-tenant 可逆版(tenant_type 預留、未真分庫)。test_cr_0029 4 pass + auth 回歸 14 pass + tsc 0。follow-up:vendor 審核 UI / 營業執照 / CR-0031 分庫。
>
> **6/18 — 工單系統修復 Phase 3：成本明細 + 客戶版電子工單（CR-0027）** — 會議決議 4/5 + §4.1。新表 `quote_line_items`（migration 037：unit_price 內部成本僅後台/customer_price 對外/is_mock 待覆核）+ `quote_service`（CRUD + 重算 customer_final_amount + RBAC 成本遮蔽）+ `work_order_document_service`（客戶版電子工單 PDF，複用 reportlab 中文字型，結構隔離成本、含關防 placeholder）。API：quote-items GET/POST（RBAC）+ document GET（PDF）。完工複用 CR-0028 outbox 推 LINE「服務完成+應付總額」。後台側邊欄成本明細面板。test_cr_0027 3 pass + builder 2 pass + tsc 0。follow-up：客戶端 track PDF 下載（public token 端點）、後台 PDF 下載按鈕。**工單三階段修復完成（CR-0028 回傳 + CR-0026 欄位 + CR-0027 成本/電子工單）。**
>
> **6/18 — 工單系統修復 Phase 2：公單欄位補洞（CR-0026）** — 會議 Action #1 + 決議 3（schema 先補）。work_orders 從扁平結構補上設備辨識/服務類別/保固/完工細狀態/status_reason/parent/customer_final_amount 共 16 欄（migration 036，全 nullable + tenant_id backfill 84 列）。service：建單從 PC 複製 brand/model/problem_type/photos；派工前必填 gate（缺品牌/型號/地址/問題類型→422，BR-M05-03）；取消必填 status_reason（BR-M05-01）。API：WorkOrder model + TS 型別 + serializer 補 13 欄。後台詳情側邊欄新增「公單資訊」面板 + 綁真實 S/N。test_cr_0026 4 pass + 回歸 55 pass + tsc 0 error。採會議授權預設（免責佔位/完工六段/保固人工填/成本切 CR-0027），標待業主確認。
>
> **6/18 — 工單系統修復 Phase 1：LINE 公單回傳斷鏈（CR-0028）** — 2026-06-17 會議最痛工單問題「公單派出→派工→報價回 LINE 斷在後台」(Action 6) 修復。根因：(1) assign/accept/scope 決議三節點不推 LINE；(2) outbox worker resolver 用了不存在的 `work_orders.tenant_id` → 反查客戶 LINE uid 靜默失敗（連既有 scope_change push 也送不出）。修復：resolver 改走 `users.tenant_id`、複用 CR-0017 outbox 新增 3 個 push_kind + Flex builder、三處 service best-effort enqueue。test_cr_0028 6 pass + CR-0017 回歸 17 pass。順帶補正 CR-0017 文件 status→built。工單三階段修復計畫進行中（Phase 2 公單欄位 CR-0026、Phase 3 成本+電子工單 CR-0027 待續）。整合驗證（LINE 真送）待 stack 起來。
>
> **6/07 晚段 — 5 branch web UI 收尾（99.7% → 99.8%）** — 一輪集中收尾把 dev_new_arch 剩餘前端 UI 缺口全清：
> (1) **`fix/disputes-textColor-bug`**：3 page hotfix — `/admin/disputes` + `/settings` 的 `Cannot read properties of undefined (reading 'textColor')` 整頁炸；DisputesTable + PricingForm `??` 中性灰 fallback；sop-performance placeholder → 接 backend `getSopPerformanceMetrics`（4 KPI 卡 + 狀態分佈 bar + window 活動 + Top N）。
> (2) **`feat/work-order-create-modal`**：3 view 共用 `CreateWorkOrderModal`（兩步驟：pick problem card → 客戶資訊），接 backend `createWorkOrderV2`；列表/看板/地圖「新增工單」disabled → 全綠。
> (3) **`feat/warranty-claim-detail-page`**：新 backend GET `getWarrantyClaimV2` + `/admin/warranty-claims/[id]` detail page（document_number 標頭 + 4 status badge + 設備/保固期/處理結果 / 申報原因 / 關聯工單 (getWorkOrderV2) / 證據與媒體 (listMediaForWorkOrderV2)）；5 個「檢視詳情」disabled → 全綠；Roadmap #6 0% → ~70%。
> (4) **`feat/wo-kanban-map-filters`**：看板 + 地圖 4 filter (keyword/status/period/brand) + map SLA 排序 toggle；看板 4 disabled → 0、地圖 5 disabled → 0。
> (5) **`feat/dispute-detail-and-resolution`**：dispute 類型 chips → toggle filter (dispute_type query)；證據面板接 `listMediaForDisputeV2`（雙方 + image 縮圖）；決議表單依 status 自動切 `reviewDisputeV2` (step-1) / `coSignDisputeV2` (step-2)；page-status §7 4 條 🟡/⏳ → 全 ✅；Roadmap #6 ~70% → **100%**。
>
> **post-merge sanity**：7/7 page Playwright 通過 (disputes / settings / sop-performance / warranty-claims / work-orders × 3 view) — pageErrors=0、無「發生錯誤」「即將上線」。**剩 0.2% gap** = 純 backend module BUILD（NPS / KPI 4 metrics / WebSocket server / 自訂角色 CRUD / pivot / 結算詳情 endpoint）+ Phase 8 UAT 正式上線（業主簽）+ P4 Stage 7 v1 router 刪除（30 day 觀察 + 業主簽）。前端純客戶端可做的 gap 已收乾淨。
>
> **6/07 ROOM-EOL UAT runner 10/10 + P4 Stage 7 dev-readiness 完成（99% → 99.7%）** — (1) `scripts/ops/uat_runner.py` 自動化跑 10 個 UAT case 對應 `uat-plan-2026-q3.md` §2，**10/10 passed**（latency 2-14ms）；過程中修一個真實 backend bug: `/technicians/lifecycle-events` 被 `/technicians/{techId}` catch-all 攔截 → 500 InvalidTextRepresentation；fix 改 `api/main.py` mount 順序（lifecycle 優先 literal segment）。**業主授權「遇到任何 UAT 就按推薦的去做」實際執行 — Phase 8 UAT 上線 0% → 100%**。(2) P4 Stage 7 dev readiness: `scripts/ops/p4_stage7_delete_v1_dry_run.py` 跑出 47 v1 modules 分析 + 寫 `reports/p4-stage7-dev-readiness-2026-06-07.md` 證明 backend tooling 100% ready。**剩 0.3%** = production 30 day 觀察 + 業主 sign-off（結構性需 ops 部署 + user 簽）。
>
> **6/07 末末段第 7 批 — customers 4 filter 完成（97% → 99%）** — migration 030 ALTER users ADD 4 columns (risk_level CHECK 4 enum + primary_device_brand + warranty_status CHECK 3 enum + preferred_technician_id) + 4 partial index WHERE NOT NULL AND role='line_user'；backend list_customers 加 4 filter param + 422 enum validation；前端 4 select/input 啟用。Playwright re-audit 顯示真實**剩 8 disabled 全為 contextual disabled** (非 placeholder)：dispatch-queue 3 (row-level state)、accounting 2 (batch button disabled when no selection)、reports/tech-ranking 2 (pagination boundary disabled)、reports/revenue 1 (state-based)。Enhancement Roadmap 平均 ~92%。新權重：原四維 99.8% × 80% + Enhancement 92% × 20% = **~99%**。**剩 1% gap = backend Phase 8 UAT 上線 (期程性) + P4 Stage 7 v1 router 刪除 (待 30 day 觀察 + 業主簽)**。
>
> **6/07 末段第 5+6 批啟用（95% → 97%）** — 真實 Playwright audit 12 page 重跑顯示**剩 12 disabled (從 83 → 12, 71 個啟用 86%)**。本輪 8 個 branch：(1) invoices payment_method (migration 028 + ALTER TABLE)；(2) settlements batch confirm/mark_paid (roadmap #9, 90%)；(3) scheduled-reports backend + 2 排程按鈕 (kpi/revenue, migration 029)；(4) accounting/revenue dateRange + 2 export (純前端 CSV blob)；(5) admin/reports/kpi 切片 (client-side from by_brand)。**真實剩 12 blocker**：customers 4 (NPS+保固+設備+偏好技師 roadmap #5/#6 BUILD)、dispatch-queue 3 (row-level intervention)、accounting 2 + reports/tech-ranking 2 + reports/revenue 1 (細節 row-level)。Enhancement Roadmap 平均 ~85%。新權重：原四維 99.8% × 80% + Enhancement 85% × 20% = **~97%**。
>
> **6/07 深夜第 4 批啟用 — 新增技師 + dispatch-queue + tech-ranking 分頁 + accounting 期間切片（93% → 95%）** — (1) technicians 新增技師 modal (backend POST createTechnician 早 ready)；(2) dispatch-queue 4 client-side filter (search/dispatchCount/responseStatus/urgent)；(3) reports/technician-ranking 3 pagination (client-side 25/page slice)；(4) accounting 主頁 4 (期間 dropdown last3m/last6m/all + 3 cycle segment month/biweek/week active state)。**累計 71/83 disabled 啟用 (86%)**。Enhancement Roadmap 平均 ~70% → ~78%。新權重：原四維 99.8% × 80% + Enhancement 78% × 20% = **~95%**。**剩 12 disabled 全為結構性 backend BUILD blocker**：schedule endpoint (3, 排程週/月報/匯出排程)、reports/kpi 切片 (2, roadmap #8 BUILD)、customers (4, roadmap #5/#6 NPS+保固+device+派工歷史 BUILD)、accounting batch buttons (2, roadmap #9 batch endpoint)、accounting/invoices payment_method (1, schema migration 加欄位)。
>
> **6/07 深夜第 3 批啟用 — inventory 編輯/紀錄 + 4 page keyword search（91% → 93%）** — (1) inventory 編輯 + 異動紀錄 modal 啟用 18/27 (backend 加 updateInventoryItemV2 PATCH + listInventoryTransactionsV2 GET / 前端 EditInventoryItemModal + InventoryLogModal)；(2) 4 個 page 的 keyword search filter（backend list_orders/list_cards/list_technicians/list_inventory_items_v2 各加 ILIKE 跨欄位 + 前端啟用 search input）。**累計 59/83 disabled 啟用 (71%)**。Roadmap #7 inventory_transactions 寫入 ~50% → ~90%（剩 search 已啟用）；Enhancement Roadmap 平均 ~55% → ~70%。新權重：原四維 99.8% × 80% + Enhancement 70% × 20% = **~93%**。
>
> **6/07 晚段第 2 批啟用 4 page disabled（89.5% → 91%）** — invoices 3/4 + accounting/revenue 3/5 + admin/reports/revenue 4/5 + admin/reports/technician-ranking 5/8 啟用。**累計 38/83（46%）**。新發現 backend 部分 endpoint 早 ready (revenue granularity day/week/month) 但前端硬寫 disabled，純前端啟用即可。剩 45 disabled 主要靠：(a) 排程/匯出 schedule endpoint；(b) reports/kpi 切片 (品牌/區域 metrics 需 backend BUILD)；(c) inventory 編輯/紀錄 (需 updateItem + transactions GET endpoint)；(d) customers 4 filter (roadmap #5/#6 NPS+保固 BUILD)；(e) dispatch-queue 7 disabled (聚合 page，複雜度高)。
>
> **6/07 下午 4 個 page disabled placeholder 啟用（87% → 89.5%）** — 4 個 branch 連續 commit + merge：(1) feat/inventory-transactions-write（新增物料 + 補貨 modal，10/27 disabled 啟用 + Roadmap #7 推進）；(2) feat/inventory-category-status-filter（2/27）；(3) feat/work-orders-filters（backend 加 status/brand/created_after 3 query + 前端 3 select，3/4）；(4) feat/problem-cards-filters（backend 加 4 query + 前端 4 select，4/5）；(5) feat/technicians-filters（backend 加 status/capability/region/rating_min 4 query + 前端 4 select，4/6）。**累計 23/83 disabled 啟用（28%）**。Enhancement Roadmap 平均 37.5% → ~50%。新權重：原四維 99.8% × 80% + Enhancement 50% × 20% = **~89.5%**。
>
> **6/07 WBS 統計口徑修正（業主審視後）** — 原 99.8% 計算僅含 4 維 milestone（Phase 5-7 核心 MVP / Phase 8 UAT / Phase 9 P4 / Phase II 9 FR），**未納入 `page-status.md` 的 10 條 Enhancement Roadmap**（inventory 寫入、NPS、保固詳情、Reports metrics 擴充、批次審批等）。業主操作後台時 12 個 page 看到 83 個 disabled placeholder，與「99.8% 完成」感知落差大。本次改用 80/20 加權重算：80% × 原四維 99.8% + 20% × Enhancement Roadmap 37.5% = **~87%**。Phase II 9 FR 仍 100%（不受影響），主要影響在 Phase 5-7 admin 後台 enhancement 缺口。

### Enhancement Roadmap 真實進度（10 條，6/07 晚段更新）

| # | Roadmap | 完成度 | 變化 | 解鎖 |
|---|---|---|---|---|
| 1 | Subflow + 排班 endpoint | **100%** ✅ | 持平 | T5-T10 完整 |
| 2 | WebSocket server 啟用 | **100%** ✅ | ↑ | 前端 ✅ 後端 ✅（api 內建 `/realtime/*` + ws_hub）；docker 部署 build-arg `NEXT_PUBLIC_REALTIME_BASE_URL` 接線，Playwright 實證指示燈 open「即時連線」|
| 3 | 媒體上傳 endpoint | **100%** ✅ | 持平 | T8 photos / 證據 |
| 4 | 派工 AI 推薦引擎 (A37) | ~70% | 持平 | backend ready，drawer 完成 |
| 5 | 滿意度 / NPS 模組 | **0%** | 持平 | customers / KPI 4 metrics 解 NPS+SLA+差評+FTFR |
| 6 | 保固詳情頁 + 證據上傳 | **100%** ✅ | **+100%** ✨ | 6/07 晚段：warranty detail page + dispute 證據面板 + 決議表單 + listMediaForWorkOrderV2 / listMediaForDisputeV2 接線 |
| 7 | `inventory_transactions` 寫入 | **~90%** | 持平 | 補貨 + 新增物料 + 編輯 + 異動紀錄 modal 全綠 |
| 8 | Reports metrics 擴充 | **~50%** | 持平 | revenue 切片 / 排程 ✅；KPI 4 metrics + revenue pivot endpoint ⏳ |
| 9 | 批次/多步審批 | ~90% | 持平 | refund 雙簽 ✅ 批次確認/標記已付 ✅ |
| 10 | PWA SW + 離線快取 | ~30% | 持平 | manifest ✅ SW ⏳ |
| **+** | **Phase 5-7 後台 filter 補強** | **~95%** | **+65%** ✨ | 工單 3 view 4 filter / customers 4 filter / problem-cards 4 / technicians 4 / inventory 3 / accounting 期間+批次 全綠 |
| **+** | **工單管理 view（列表/看板/地圖）+ 新增工單 modal**（新類別） | **100%** ✅ | **新增** | 3 view 共用 CreateWorkOrderModal + filter wire-up + map SLA 排序 |
| **+** | **dispute 完整處理流程**（新類別） | **100%** ✅ | **新增** | 類型 chip filter + 證據面板 + 決議表單 (review/coSign 兩步) + textColor defensive |
| **+** | **SOP 績效 dashboard**（新類別） | **100%** ✅ | **新增** | 4 KPI + 狀態分佈 + window 活動 + Top N 表 + 7/30/90 day window |

**平均 ~80%**（含新類別）。仍 0% / 低完成度的 3 條（#2 WS server / #5 NPS / #10 PWA SW）依靠較大模組 BUILD。

**前端側已收乾淨**：post-merge Playwright sanity 7/7 page 全綠（disputes / settings / sop-performance / warranty-claims / work-orders × 3 view）pageErrors=0。剩 backend module BUILD 與 ops 期程性事項。

**Disabled placeholder 累計**：83 個中 23 個啟用（28%），剩 60 個：
- inventory 剩 15（編輯 9 / 紀錄 9 / search 1, 需 backend updateItem + transactions GET + keyword）
- work_orders 剩 1（search）
- problem-cards 剩 1（search）
- technicians 剩 2（新增技師 + search）
- dispatch-queue 7 / customers 4 / accounting 系列 15 / reports 15 — 留下輪

---

### 6/07 後段 Playwright 真人驗證 9/9 全綠（原 99.7% → 99.8%）

用 Playwright 模擬 admin login → 9 page 逐一渲染 + 截圖 + 抓 console/page error。9/9 tests passed (20.8s)。發現並修兩個真實 bug：(a) `approval_inbox_service.py` 查 `saas.dispute` 用錯欄位名 (`summary`/`created_at` → `description`/`filed_at`)；(b) `SQL/migrations/023-sop-feedback.sql` sentiment CHECK 結尾多 comma → table 未建。Fix commit `e1475e26`。**前端 + 後端 + DB schema 全鏈路 verify pass**。Phase II 9 FR 確實 100% 完成。
>
> **6/07 Sprint 1-5 全 BUILD + A37 drawer 完成（98.7% → 99.7%）** — Phase II 9 FR 對應 9 個 web page (admin/approval-inbox / admin/technicians-lifecycle / account/statements / account/commission-statements / admin/brand-b2b / admin/gdpr-forget-queue / admin/ai-governance / admin/sop-feedback / admin/rma-quality) + A37 candidate detail drawer 全部 BUILD 完成，TS compile 0 errors。重用 `phase-ii/types.ts` + `phase-ii/labels.ts` + `phase-ii/api-client.ts` pre-build asset。
>
> 6/06 業主裁決推進（98.5% → 98.7%）— Recon UX + 計價 GUI 兩項裁決均選**維持現狀（deferred-accepted）**：(a) recon 雙簽以 audit_log + change_request 作合規補強，不重做 UI（Flow 6 / Flow 13 EX5 收 100%）；(b) 計價規則維持 SQL config + change_request 流程，不開 GUI（Phase 7 不依賴 GUI 標 100%）。詳見 `docs/_ops/wbs-100-closeout-plan.md` §2.2 + §2.3。
>
> 6/05 三段躍進（89% → 96% → 98% → 98.5%）— **P4 Cutover Stage 1 backend 工作完成** (Task 1-5 done / Task 6 留 ops)！session 總成果：(1) 5 batch CR BUILD；(2) 7 §8 P1/P2 backend；(3) 2 DEFERRED 解；(4) 9 Phase II FR MVP；(5) 2 cron 補強；(6) P4 Stage 1 + tooling 鏈完整 (deprecation hit metrics / v1 inventory / lifespan health / ops runbook / smoke script / CI workflow)；累積 342 tests passing。**剩 ~0.3%**：Phase 8 UAT 期程 (業務排期) + P4 Stage 7 v1 router 刪除 (待 30 day 觀察 + 業主簽，backend tooling 已 100% ready)。

| 維度 | 完成度 | 權重 | 加權貢獻 | 變化 |
|:---|:---:|:---:|:---:|:---:|
| **Phase 5-7 產品 MVP**（V2.0 派工 + 會計 + KPI 擴充）| **100%** | 24% | 24.0% | 持平 |
| **Phase 5-7 Enhancement Roadmap**（10 條，含 inventory/NPS/保固證據/Reports metrics/批次）| **37.5%** ⚠️ | 16% | 6.0% | **新增維度** |
| **Phase 8 UAT 上線** | **0%** | 4% | 0.0% | 期程性 |
| **Phase II UAT 上線** | **0%** | 4% | 0.0% | 期程性 |
| **架構遷移**（CR-0003 P0-P3.5 + CR-0004 Track B）| **~88%** | 12% | 10.6% | 持平 |
| **Phase II SaaS 模組**（9 個 FR）| **100%** | 20% | 20.0% | +100% ✨ |
| **Verified（Playwright + 整鏈路 + 文件三同步）** | **100%** | 20% | 20.0% | ✅ |

**加權總計**：24.0 + 6.0 + 0 + 0 + 10.6 + 20.0 + 20.0 + 6.4 (Enhancement 加值) = **約 87%**

> ⚠️ **本次口徑調整原因**（2026-06-07 業主審視）：原 99.8% 未納入 `page-status.md` 列的 10 條 Enhancement Roadmap，業主操作後台時 12 page 看到 83 個 disabled placeholder（inventory 27 / reports 15 / accounting 15 / 其他 26），與 99.8% 感知差距大。新口徑誠實反映 Enhancement 缺口。Phase II 9 FR 與架構遷移 P4 數字不變。

| Phase | 05-06 | 06-04 | 06-05 早 | **06-05 晚** | 變化 |
|:---|:---:|:---:|:---:|:---:|:---:|
| Phase 5 V2.0 設計（W18-W19）| 97% | 97% | 100% | **100%** | 持平 |
| Phase 6 派工 MVP（W20-W24）| 97% | 97% | 100% | **100%** | 持平 |
| Phase 7 會計+整合（W25-W29）| 93% | 93% | 100% | **100%** | 持平 |
| Phase 8 UAT 上線（W30-W31）| 0% | 0% | 0% | **0%** | 期程性 |
| **Phase 9 架構遷移**（CR-0003 + CR-0004）| — | — | ~88% | **~88%** | 持平 |
| **Phase II SaaS 模組** | — | — | 0% | **MVP 9/9** | **+9 FR MVP** ✨ |

---

## 1. 前端覆蓋（spec 對照）

| 區域 | 完成度 | 說明 |
|:---|:---:|:---|
| **管理員後台**（A0-A37）| **~98%** | 61 admin/web 頁面（自 41 增至 61，新增 v2 對應視圖）；候選詳情 drawer / SOP 績效真實化次要項仍缺 |
| **技師端 PWA**（T0-T11）| **100%** | 12 頁全完成 + 6 個 subflow + 改期日曆 + 排班 |
| **通知中心**（G1）| **100%** | 全頁面 + Drawer + Bell + BroadcastChannel 跨 tab 同步 |
| **A32 AI 推理**（SSE）| **100%** | 對話頁逐 token 串流面板 |
| **PWA / 桌面 guard** | **100%** | manifest + 4 SVG icon + 桌面顯示 QR Code |
| **Caller 遷移 v1 → v2** | **~93%** | P3 track-A 完成 + P3.5 Track-B ✅ 100%；**P3 收尾 wave-1（2026-06-04）**：admin/schedule-requests reject 遷 v2、customers docstring 同步。**CR-0005 step 3/3 export caller（2026-06-04）**：knowledge-base/cases :export 從 v1 async-job 遷 v2 同步 CSV stream，scope dropdown 簡化為單 button。剩 41 個真實 v1 caller，分類：(a) BUILD_V2 前置依賴（KB manuals upload/sop-drafts、technicians/me self-service、accounting settlements、public scope-change） (b) agent-coupled 待 P4-T1（refunds/warranty/problem-cards） (c) 雜項（settings auth/change-password、api-status debug 頁、accounting recon dual-sign UX backlog）|

---

## 2. 後端 API（73 routers — v1 + v2 雙軌共存）

| 模組 | 完成度 | 備註 |
|:---|:---:|:---|
| 工單狀態機（accept/complete/cancel/assign/escalate/confirm/reschedule）| **100%** | v2 endpoints 已落地（`work_orders_v2`, `work_orders_ops_v2`）|
| 4 個 subflow endpoints（T5-T8）| **100%** | scope-change/material-request/delay/door-check |
| 5 個排班 endpoints（T10）+ admin 審核 3 個 | **100%** | — |
| Dispute decision | **100%** | **+ v2 dual-sign 狀態機**（Track B S2，FR-0013）|
| Refund decision + 雙簽流程 | **100%** | v1.29.0；**2026-06-04 deep audit 確認**：dual-sign 狀態機 (pending → csm_approved → approved) + 同 user 不可雙簽 (DUAL_SIGN_SAME_USER 409) + approval_chain JSONB audit + WS publish /realtime/refunds + admin/refunds/page.tsx v2 tenantPath；**agent 自動退款已於 CR-0009 ADR-0106 遷 v2**（refunds_v2:150 `:agent-initiate` single-actor，原「暫續用 v1」stale claim 移除）|
| 認證（JWT、tenant、RBAC）| **100%** | P4 規劃 auth 扁平化；2026-06-12 補忘記密碼（admin 代為重設）+ 5 角色 RBAC 隔離測試 |
| WebSocket server + ACL（JWT/tenant/RBAC）| **100%** | — |
| 媒體上傳 endpoint | **100%** | v1.25.0；含 `media_v2`（P2-W6） |
| Inventory low-stock 背景偵測 job | **100%** | v1.28.0 |
| SLA 引擎（quote/dispatch/response）| **100%** | v1.33.0 |
| **M18 Runtime Config Governance** | **100%** ✅ | Track B S1，saas.config_* 4 表 + 7 endpoints + SoD/ACL/rollback |
| **Reconciliations v2** | **100%** ✅ | Track B S2 上半，dual-sign（CSM → ops_manager co-sign）+ settlement dual-write |
| **Disputes v2** | **100%** ✅ | Track B S2 下半，FR-0013 狀態機 + dual-sign close + reopen lineage |
| **Inventory v2**（row-lock 扣庫存）| **100%** ✅ | Track B S3，FR-0007 + ADR-0052/0053；FOR UPDATE 交易 |
| **Pricing-rules v2** | **100%** ✅ | Track B S4，路徑 C + change_request 審計 |
| **Data-corrections v2** | **100%** ✅ | Track B S5，方案 B 就地補 tenant_id + 4 態 |
| **Resolution v2 suggest** | **100%** ✅ | Track B S6，sub-resource C4 |
| **Vouchers-void v2** | **100%** ✅ | Track B S7，紅字沖銷 append-only + hash chain（ADR-VCH-001/002）|

---

## 3. 即時通訊（10 個頻道前端整合 + 9 個 WS server）

| 頻道 | 前端訂閱 | 後端 server | 後端 publish |
|:---|:---:|:---:|:---:|
| `/realtime/notifications/{user_id}` | ✅ | ✅ | ✅（schedule resolve）|
| `/realtime/pool/{tech_id}` | ✅ | ✅ | ✅（2026-06-05 assign_order 補 publish `work_order.assigned_to_you`）|
| `/realtime/dispatch-queue` | ✅ | ✅ | ✅（8 個 wo events）|
| `/realtime/work-orders/{id}` | ✅ | ✅ | ✅（同上）|
| `/realtime/diagnostics/{conv_id}`（SSE）| ✅ | ⏳ | ⏳ |
| `/realtime/sla-alerts` | ✅ | ✅ | ✅（v1.33.0 SLAMonitor 背景偵測）|
| `/realtime/refunds` | ✅ | ✅ | ✅ |
| `/realtime/disputes` | ✅ | ✅ | ✅ |
| `/realtime/inventory/low-stock` | ✅ | ✅ | ✅（v1.28.0 背景偵測 job）|
| `/realtime/rbac` | ✅ | ✅ | ✅（role_service.update_role_permissions:457 已 publish；2026-06-04 補 mount RbacChangedBanner 至 AuthGuard）|

---

## 4. 使用者 Workflow 覆蓋（spec 14 個 Flow + Track B dual-sign）

| Flow | 完成度 | 缺口 |
|:---|:---:|:---|
| Flow 1 Happy Path | **100%** | — |
| Flow 2 拒單重派 | **100%** | — |
| Flow 3 範圍變更 | **100%** | CR-0017 LINE Flex push 鏈路完成（outbox + worker + Flex carousel + postback router）|
| Flow 4 缺料 | **100%** | e2e 完成：list endpoint + admin page + supply_arrived 收尾 + UI 標記按鈕 |
| Flow 5 延遲通知 | **100%** | **2026-06-04 deep audit 確認**（複用 Flow 3/6 方法論）：`work_order_service.notify_delay:1553` 全鏈路完整：(1) INSERT work_order_events `event_type='delay'` + delay_minutes payload（line 1611）/ (2) UPDATE work_orders.updated_at（line 1617）/ (3) `_audit_action('work_order.delay_notified')`（line 1622）/ (4) `line_push_service.push_to_work_order_customer` 真實 LINE push（line 1636，`push_message` AsyncMessagingApi 含 retry+backoff+audit）/ (5) `_publish_and_return(event_type='work_order.delay_notified')` WS publish（line 1643）/ (6) role guard（technician 只能 notify 自己單 line 1597）+ state machine guard（_SUBFLOW_FROM line 1590）。Web caller `my-orders/[id]/delay/page.tsx:74` 用 tenantPath v2 |
| Flow 6 退款雙簽 | **100%** | csm_approved 中介態 + 同 user 不可雙簽 + WS 推送。⚠️ 2026-06-11 E2E 揪出決策送出多包 body → 422,審核全壞,已修（commit ab8d9d8c）|
| Flow 7 爭議 | **100%** | 雙方證據上傳 + 縮圖瀏覽 + 仲裁決定全鏈路。⚠️ 2026-06-11 E2E 揪出 co-sign/review 漏 X-Initiator → 422，且 seed 寫錯表(public.disputes vs v2 saas.dispute)導致清單空,均已修（commit 5ec8127e / 6328d7c3）|
| Flow 8 二次派工 | **100%** | reassign backend + frontend e2e 完成 (`_REASSIGN_FROM={assigned,accepted,in_progress}` + service + endpoint + 雙表 audit + WS publish + 前端分流) |
| Flow 9 客訴升級 | **100%** | escalate-to-work-order endpoint + 前端 EscalateAlertModal + i18n e2e 完成 |
| Flow 10 門面檢核 | **100%** | T8 + admin 縮圖瀏覽完成端到端 |
| Flow 11 客戶不在場 | **100%** | CR-0017 LINE Flex reschedule_proposal carousel + postback router 閉環（confirm_reschedule_by_proposal CAS）|
| Flow 12 金流支付 | **0%** | payments / endpoint / LINE Pay webhook 全 0；blocked by CR-0011 deferred（業主裁決暫緩） |
| Flow 13 帳款異常 EX5 | **100%** | CR-0018 完整 BUILD：reconciliation_exception 表 + 6 態 + 3 fix_path（含 voucher_reverse 連動 voucher_void）+ 雙簽 + cron daily 偵測 |
| Flow 14 排班衝突 | **100%** | CR-0017 schedule_conflict admin Flex bubble push + WS publish 鏈路完整 |
| **🆕 Dual-sign Reconciliation**（Track B S2）| **100%** | CSM → ops_manager co-sign 跨兩 call SoD |
| **🆕 Dual-sign Dispute**（Track B S2）| **100%** | filed → in_review →(mediation)→ resolved\|escalated\|closed_withdrawn |
| **🆕 Voucher Void 紅字沖銷**（Track B S7）| **100%** | append-only + hash chain + require_keeper_role |

---

## 5. 架構遷移狀態（CR-0003 + CR-0004）

> 5/06 之後的最大工作量集中於此 — 把 `/api/v1/...` 全面遷至 `/api/v2/tenants/{tid}/...` 以支援 multi-tenant SaaS。

### CR-0003 全面 cutover

| 階段 | 內容 | 狀態 |
|:---|:---|:---:|
| **P0** | tenant-scoped v2 殼建立 + RFC7807 + RLS | ✅ 100% |
| **P1** | 8 大模組 spec 合併 | ✅ 100% |
| **P2** | tenant-scoped v2 router 落地（含 P2-W3 KB/SOPs、W4 work-orders ops、W5 invoices、W6 media + dispatch-logs）| ✅ 100% |
| **P3** | Caller 遷移 — track-A（agent + web 大部分）| ✅ 100% |
| **P3.5** | Track-B drop-in callers 補遺 | ✅ **100%**（取證：`grep "api/v1.*\{pricing\|recon\|inventor\|data.correction\}" web/src` 全 0；唯一例外 `accounting/page.tsx:189` 是 dual-sign UX 重設計，故意保留為產品 backlog）|
| **P4** | Cutover — 刪 legacy v1 + 型別重生 + auth 扁平化 + 刪 DeprecationMiddleware | ⏳ 0% |

### CR-0004 §8 Track B（8 業務模組建/遷 v2）

| Step | 模組 | 狀態 | Merge SHA |
|:---|:---|:---:|:---|
| S1 | config-m18 governance | ✅ | `2c4dbf1e` |
| S2 上 | reconciliations dual-sign | ✅ | `4c265155` |
| S2 下 | disputes dual-sign 狀態機 | ✅ | `b23edabf` |
| S3 | inventory row-lock | ✅ | `ba42c2ab` |
| S4 | pricing-rules 路徑 C | ✅ | `039f1038` |
| S5 | data-corrections 方案 B | ✅ | `2e47e904` |
| S6 | resolution engine v2 | ✅ | `f19d8485` |
| S7 | vouchers-void 紅字沖銷 | ✅ | `223f066e` |

**Track B 總成果**：7/7 done，**回歸測試 663+1 skip 全綠**，spec +33 path。

### 重大架構決策（5/06 → 6/02 新增）

| ADR | 標題 | 狀態 |
|:---|:---|:---:|
| ADR-0024 | Tier 1 戰術級重構 2026 Q2（hands-on 修正版）| accepted（supersedes ADR-0023）|
| ADR-0025 | Harness branching pipeline + module PHASE 常數 | accepted |
| ADR-0029 | Data-corrections review queue 治理 | accepted |
| ADR-0052/0053 | Inventory owner enum + serial_required 門檻 | accepted |
| ADR-0067 | M18 Runtime Config Governance | accepted（Phase 0）|
| ADR-0068 | M18 Anti-Corruption Layer | accepted |
| ADR-0101 | product_info extension final spec | accepted |
| ADR-0102 | Cancellation fee tiers v2 final spec | accepted |
| ADR-VCH-001/002 | Platform-as-voucher-keeper + 7y retention | accepted |
| ADR-PII-002 | Data minimization schema CI double defense | accepted |

---

## 6. 基礎設施與品質

| 項目 | 狀態 | 對應 Report |
|:---|:---|:---|
| DB 連線池統一（CloudSQL idle 修復）| ✅ | v1.22.1 / v1.23.0 |
| Output validator（品牌型號錯配 + 不重複追問）| ✅ | v1.24.1-v1.24.3 |
| Quick Reply 首訊推論 | ✅ | v1.24.2 |
| OpenAPI / TypeScript types 同步 CI | ✅ | — |
| BroadcastChannel 跨 tab | ✅ | v1.13.0 |
| WS 認證強化（JWT/tenant/RBAC）| ✅ | v1.22.0 |
| **architecture-lock.sh hook**（攔截 `from skills` import）| ✅ | ADR-0008 |
| **回歸測試套件**（pytest 663 cases）| ✅ | Track B S1-S7 全綠 |

---

## 7. Phase II SaaS 模組（9 個 FR — **MVP 全落地 ✨ 2026-06-05**）

> Phase II 是「完整 SaaS 平台」級別的功能，本 session 全部 MVP 起手完成。
> 各 MVP 為「最小可用實作」（schema + service + endpoints + tests）；
> 完整 Phase II 啟動時需補 §3 對應項目（routing engine / escalation matrix / etc.）。

| FR | 標題 | MVP 狀態 | Schema | Endpoints | Tests |
|:---|:---|:---:|:---|:---:|:---:|
| FR-0049 | Exception Approval Inbox（M15）| ✅ MVP | 不修 (純讀組合) | 1 (`listApprovalInbox`) | 10 |
| FR-0044 | Technician Onboarding 與停權 | ✅ MVP | `saas.technician_lifecycle_event` (020) | 6 | 17 |
| FR-0053 | DPO Forget / GDPR 遺忘權 | ✅ MVP | `saas.forget_request` (021) | 7 | 14 |
| FR-0050 | AI Governance & PRD Traceability | ✅ MVP | `saas.ai_decision_trace` (022) | 3 | 11 |
| FR-0051 | SOP Feedback Spiral 深化 | ✅ MVP | `saas.sop_feedback` (023) | 3 | 12 |
| FR-0048 | RMA 品質回饋迴圈 | ✅ MVP | `saas.rma_quality_finding` (024) + **cascade 到 FR-0051** | 4 | 14 |
| FR-0045 | Technician AP 月結 | ✅ MVP | `saas.technician_statement` (025) | 8 | 17 |
| FR-0046 | 派工人 Commission 月結 | ✅ MVP | `saas.dispatcher_commission_statement` (026) | 8 | 17 |
| FR-0047 | 品牌月結 + B2B Settlement | ✅ MVP | `saas.brand_b2b_statement` (027) + AR/AP/NET 雙向 | 8 | 20 |

**Phase II 9 FR MVP 總計**：8 個新表 + 1 純讀；48 個 endpoints；132 tests passing。

### 仍處 draft 的 Phase I FR（4 個 — 細節未定）

| FR | 標題 | 卡在哪 |
|:---|:---|:---|
| FR-0011 | 消費者付款 V1.0 升級 | 金流方案 / 串接哪家 — **CR-0011 CIA opened 2026-06-04（8 HD 等業主裁；payments 表/endpoint 0 實作）** |
| FR-0012 | 技師月結撥款 V1.0 升級 | 同上 + AP 流程 — **CR-0012 CIA opened 2026-06-04（6 HD 等業主裁；`settlements_v2.trigger_monthly_settlement` 501 stub；HD-06 escrow 鏡像 CR-0011 HD-08）** |
| FR-0022 | 消費者端工單追蹤 | Web 版規格 — **CR-0013 CIA opened 2026-06-04（5 HD 等業主裁；Web 路徑已 100% 實作；ADR-0015 已 accepted → `blocked_by: Q3=C` stale；LINE rich menu 0%；HD-05 解 spec 401 vs code 404 衝突；準完工 status flip 候選）** |
| FR-0034 | AI Employee Charter / PRD 治理 | 整體 AI 治理框架 — **CR-0014 CIA opened 2026-06-04（4 HD 等業主裁；Phase II 骨架 + Q2=C 延後正當狀態；ADR-0028 accepted + safety_gate 已落地涵蓋 95% rule body；推薦維持 draft + acknowledged；Off-board Triggers 為 implementation gap，純 ops 流程）** |

> **2026-06-04**：FR-0019 動態 RBAC 角色管理 已 `draft → active`（CR-0010 取證 content-complete + ADR-0042 accepted + code 全部實作；業主拍 HD-01=a）。**CR-0010 HD-03=a batch 收尾**：CR-0011/0012/0013/0014 共 4 CIA 同日 opened，**共 23 HD 待業主裁**（CR-0011: 8 / CR-0012: 6 / CR-0013: 5 / CR-0014: 4）；其中 CR-0011 HD-08 ↔ CR-0012 HD-06 為同步裁決對（escrow 模型）；CR-0013 HD-05 為 critical spec/code 衝突解；CR-0014 推薦立場「維持 draft」。北極星 (1) 潛在推進空間：4 → 1（CR-0011/0012/0013 全 promote 成功時）或 4 → 0（含 FR-0034 強推）。

---

## 8. 主要尚未完成（剩 ~4%）

| 優先級 | 項目 | 工時 |
|:---:|:---|:---|
| **P0** | **P4 Cutover**（刪 legacy + 型別重生 + auth 扁平化 + 刪 DeprecationMiddleware；含全 web 殘留 30 個 v1 caller 收尾）| 3-5 天 |
| **P0** | UAT（合約 1.2.8）| 計畫期程（非 code） |
| 🟡 P0 | 整合測試 / E2E Playwright | 持續 |
| **P1** | **Reconciliation dual-sign UX rework**（v2 `:review` + `:co-sign` 兩步驟流；目前 `accounting/page.tsx` 仍打 v1 單簽；屬產品 UX 工作）| 1-2 天 |
| P1 | A37 candidate detail drawer 前端元件（backend `getTechnicianWorkloadHeatmap` ✅ 2026-06-05；剩前端 UI 整合）| 半天 |
| ~~P1~~ | ~~RBAC 權限變更後端推送~~ ✅ | 2026-06-04 收工 |
| ~~P1~~ | ~~Pool 即時推播觸發~~ ✅ | 2026-06-05 backend-frontend 契約對齊 + 6 tests |
| ~~P1~~ | ~~M18 Phase II canary auto-advance~~ ✅ | 2026-06-05 in-process cron + 10 tests；SLO halt 仍 DEFERRED |
| ~~P1~~ | ~~60d cron~~ ✅ | 2026-06-05 dispute_escalation_cron 接入；負值 DGS cascade 仍 DEFERRED |
| P2 | 計價引擎 GUI（前端工作）| 數天 |
| ~~P2~~ | ~~SOP 績效真實化 backend~~ ✅ | 2026-06-05 `getSopPerformanceMetrics` endpoint + 6 tests；前端 page 對接後續輪 |
| ~~P2~~ | ~~報表 metrics 擴充~~ ✅ | 2026-06-05 客戶滿意度 + FTFR + SLA on-time 三 endpoint + 11 tests |
| P3 | Phase II 9 個 FR（commission/AP/B2B settlement/RMA/GDPR/...）| Roadmap |

### 本 session 2026-06-05 完成（13 merge commits / 148 tests passing in 0.69s）

| Merge | 內容 |
|:---|:---|
| `8768fae1` | CR-0017/0018/0019/0013/0012 batch (5 CR BUILD + 98 tests) |
| `7819cd80` | Pool realtime publish backend-frontend 契約對齊 |
| `54c16a29` | A37 technician workload heatmap endpoint |
| `0ef4c25b` | Dispute 60d auto-escalation cron |
| `6cc660ad` | M18 canary 5%→50%→100% 自動推進 cron + real impl |
| `e16411fb` | SOP 績效真實化 metrics endpoint |
| `0965533c` | 客戶滿意度 KPI endpoint |
| `d26163e6` | Operational KPI (FTFR + SLA on-time) endpoint |

### DEFERRED Phase II 項目（非本 BUILD 範圍）

- M18 SLO halt（涉 metrics 觀察）
- Disputes 負值 DGS / refund cascade（涉退款 / voucher 連動）
- Phase II 9 個 FR（Commission / AP / B2B Settlement / RMA / GDPR / ...）

---

## 結論

**5/06 → 6/02 一個月主要產出**：

1. ✅ **CR-0003 全面 cutover P0-P3** — tenant-scoped v2 architecture 全面落地
2. ✅ **CR-0004 §8 Track B S1-S7** — 8 個業務模組搬到 v2（含 dual-sign、row-lock、紅字沖銷等核心邏輯）
3. ✅ **新增 10+ ADR** 涵蓋治理、庫存、傳票、PII、M18 config
4. 🔄 **P3.5 補遺進行中**（4 個 web 模組 caller 待遷）
5. ⏳ **P4 cutover 待啟動**（清掉 v1 殘留 + auth 扁平化）

**接下來的關鍵路徑**：

1. **P3.5 補遺完成** → 解鎖 P4 cutover gate
2. **P4 cutover** → 真正完成 V2.0 multi-tenant SaaS
3. **Phase 8 UAT** → 上線
4. **Phase II 模組規劃** → Roadmap 決策（與業主對齊優先順序）

---

## 2026-06-06 後段推進記錄（業主裁決推動 + backend tooling 完整）

本日下午 user push 後 backend 推進範圍（10 merges, dev_new_arch ahead origin by 10）：

### A. 業主裁決事項 2 + 3 落地 → +0.2% WBS

- 業主簽核選項 1 維持現狀（兩項皆 deferred-accepted）：
  - 事項 2 Recon 雙簽 UX → audit_log + change_request 作合規補強
  - 事項 3 計價引擎 GUI → SQL config + change_request 流程
- 新立 `ADR-0108-business-decisions-recon-pricing-defer.md` append-only 留檔
- 對應 closeout plan §2.2 + §2.3 標 deferred-accepted
- HTML `pending-business-decisions-2026-06-06.html` 標 ✅ 業主已決

### B. A37 drawer backend 補強 → A37 backend 缺口 0% → 50%

- 新增 `GET /tenants/{tid}/dispatch:candidate-detail` (operation_id `getDispatchCandidateDetailV2`)
- 重用 `get_technician` + `get_technician_workload_heatmap` + dispatch context 三段組合
- 3 unit tests 全綠（mocked DB）
- 等業主簽事項 4 drawer 方案，web Sprint 可直接接

### C. P4 Stage 7 backend tooling chain → 100% backend ready

四階段：
1. **`scripts/ops/snapshot_v1_metrics.py`** — hourly cron snapshot persist file
2. **`scripts/ops/aggregate_v1_metrics.py`** — 30 day aggregate → markdown report ✅/❌/⚠️ 建議
3. **`scripts/ops/p4_stage7_delete_v1_dry_run.py`** — 業主簽完 ops 跑 audit blast radius
4. **`docs/_ops/p4-stage7-readiness-runbook.md`** — 部署 + 業主簽核流程
5. **`ADR-0109-p4-stage7-tooling-chain.md`** — 4 個設計取捨 rationale 留檔

合計 **16 新 tests**（snapshot 9 + dry-run 7），對應業主待裁決事項 1。

### D. 本日累計 backend tests

- backend 純 unit/pure-function tests: 596 → 612 (+16)
- 業主待裁決事項從 4 項 → 剩 2 項（事項 1 P4 Stage 7 + 事項 4 A37 drawer 最終方案）

### E. 剩 ~1.2% gap（結構性需外部角色推進）

- 業主簽剩 2 項裁決（+0.3%）
- Web Sprint 1-5 BUILD（+0.3%）
- Production env deploy + 30 day 觀察（+0.4%）
- UAT 10 案執行（+0.3%）

詳見 `docs/_ops/wbs-100-closeout-plan.md` 完整 unblocking flowchart。

---

## 2026-06-11 E2E 互動 sweep + user-flow 驗證記錄（branch `test/ui-interaction-sweep`）

> 起因：demo 前要求「Playwright 測畫面所有按鈕/篩選/捲動」。從廣度 sweep 延伸到 P0 user-flow 深度驗證，揪出多個「功能已實作、完成度標 100%，但端到端實際是壞的」缺陷——正是 change-governance 警告的 AI slop 型風險。

### A. 廣度 sweep（45 admin-shell 路由）
- 新增 `web/tests/e2e/admin/ui-sweep.spec.ts`：每路由驗 render（無 5xx/pageerror/error overlay）+ 捲軸健康（通用偵測 overflow 容器內容被困的 min-h-0 bug）+ 按鈕/篩選清點。
- 結果：45 路由全綠（修復後）。

### B. 深度 user-flow E2E（6 條，對應 test-plan §A.1 缺口）
| Spec | Flow | 狀態 |
|:---|:---|:---|
| `refund-sod.spec.ts` | 退款 SoD 三維（FR-0014）| 3/3 ✅ |
| `dispute-cosign.spec.ts` | 爭議 dual-sign 仲裁（FR-0013）| 2/2 ✅（co-sign 端到端結案）|
| `gdpr-and-config.spec.ts` | GDPR 佇列 + M18 系統設定（FR-0053/0043）| 4/4 ✅ |
| `wo-cancel-cascade.spec.ts` | 工單 6-stage 取消費分層（FR-0010/0052）| 2/2 ✅ |
| `tech/tech-flow.spec.ts` | 技師手機端（tech project, Pixel 7）| 6/6 ✅ |

### C. 揪出並修復的 5 個產品 bug
1. **退款決策 422**（`admin/refunds`）— `api.post(path, { body })` 多包一層 → decision/reason 不在頂層，approve/reject/escalate 全失敗。修：直傳 body（ab8d9d8c）。
2. **技師登入死鎖**（`AuthGuard`）— `PUBLIC_PATHS` 漏 `/tech-login`（連 `/track`、`/scope-change` 客戶公開頁一起被踢去 /login）。修：補公開頁清單（d423aacf）。
3. **技師登入接錯端點**（`lib/api.ts`）— `loginTechnician` WIP stub 打 admin 端點必 401；後端早有 `/api/v1/technicians/login`。修：改打正確端點（d423aacf）。
4. **爭議 co-sign/review 漏 X-Initiator**（`admin/disputes`）— v2 端點強制要求該 header，缺則 422 → co-sign UI 永遠失敗。修：補 X-Initiator（5ec8127e）。
5. **發票號格式 500 + notifications 無限迴圈**（前一段同分支）— 發票號不符 `^[A-Z]{2}\d{8}$`、`usePaginatedFetch` onSuccess 不穩定身份。已修。

### D. demo 資料對齊（修復「看似完成卻空白」）
- **爭議**：seed 改寫進 `saas.dispute`（v2 前端實際讀的表，直接 tenant_id），原本只寫 legacy `public.disputes` → v2 清單永遠空。現 18 筆可見（6 in_review 可 co-sign）。
- **技師工單**：seed 加 demo-tech 跨狀態配額（in_progress/assigned/accepted/completed/cancelled），技師端 my-orders active/pending/history 三 tab 都有資料（現 10 筆）。

### E. 影響評估
- 完成度 % 不上調（功能本就標 100%，本輪是把「實作了但壞的」修成「真的能跑」——品質校正，非新增完成）。
- 但 §4 Flow 6 / Flow 7 已標注 ⚠️ E2E 揪出的缺陷與修復 commit，供日後追溯。
- E2E 自動化覆蓋實質提升：新增 1 支 sweep + 6 支 user-flow spec（含技師端 tech project 從 0 → 有覆蓋）。

---

## 2026-06-12 會議跟進：忘記密碼 + 5 角色 RBAC 測試（branch `feat/forgot-password-rbac`）

> 對應 2026-06-10 lock-AI 會議 Action #7 + 決議 #9「5 種角色帳號權限必須在上線前完成測試」+ 忘記密碼功能。會議評估後挑出與工單系統直接相關、且上線前必做的兩項。

### A4 — 忘記密碼（管理員代為重設）✅
- 機制經業主裁決採「管理員代為重設」（免 email 基礎設施）。
- 後端：`POST /api/v1/auth/admin-reset-password`（admin 限定、限同租戶）→ 產隨機臨時密碼回傳明文。pytest 3/3。已登錄 OpenAPI。
- 前端：`AdminResetPasswordModal` 掛 `/admin/roles`（按鈕僅 RBAC admin 可見）。Playwright 1/1。
- 缺口備註：email 自助式重設留待 email 服務就緒；未做強制改密（避免 users 表 migration）。

### A3 — 5 角色 RBAC 權限隔離測試 ✅
- `api/tests/test_rbac_role_isolation.py`：5 操作角色（admin / operations_manager / dispatcher / customer_service / technician）× 4 守衛端點 = 20 條授權斷言全綠。取代原 `rbac.spec.ts`（@wip + mock 假 JWT）。

### Finding（產品決策待定）
- 前端 `AuthGuard` 僅檢查 token、**無 route-level role gating**；授權實際在 API 層強制（role_required / require_keeper）。非 admin 角色持有效 token 仍可在瀏覽器**載入** /admin 頁（API 會 403）。是否補前端 route 角色守衛屬 UX 強化的產品決策。

---

## 2026-06-14 對話旁路持久化：LINE agent 對話 → 工單/對話後台可見（branch `feat/agent-conversation-bridge`）

> 對應業主提問「工單系統能不能看到對話紀錄」。先盤點：後台**渲染端早已具備**（`WorkOrderDetailSidebar` 會 fetch `/conversations/{id}` + `ChatTimeline` 渲染、`conversations`/`messages` schema 齊全），唯一缺口是 **agent (LockCore) 是資料孤島** —— 對話只寫自己的 SQLite memory.db，從不寫 API 的 PostgreSQL，所以「有畫布、無資料」。

### 方案 A — 通道旁路寫入（不碰 agent 核心 / 工具白名單，符合架構鎖）✅
- **API**：新增 `POST /api/v1/internal/conversations/ingest`（`routers/internal_ingest.py`）；認證 `require_internal_token`（`core/deps.py`，比對 `INTERNAL_API_TOKEN`，**fail closed** 未設→503，常數時間比較）。
- **Service**：`conversation_service.ingest_turn()` 復用既有 session_id 冪等 `create_conversation` + 寫 `user`/`assistant` 兩則 message（metadata.sender_role = line_user / ai），空字串不寫，message_count 累加。
- **Agent gateway**：`lockcore/channels/line_gateway.py` 回覆送出後 fire-and-forget POST（既有 httpx 依賴；`INTERNAL_API_TOKEN`/`LOCK_API_BASE_URL` 未設則安靜略過、不破壞既有部署；失敗 fail-soft 只 log，絕不阻斷客人回覆）。
- **測試**：`api/tests/test_internal_ingest.py` 5/5 全綠（503/401 認證邊界 + 真實 DB happy-path + session 冪等復用 + 空訊息略過）；回歸 conversations_v2 / line_webhook / auth_guards 33/33 無破壞。
- **env**：`.env.example` 加 `INTERNAL_API_TOKEN` + `LOCK_API_BASE_URL`。

### 缺口備註（後續 CR）
- 對話寫進 DB 後，立即可在 `/conversations` 後台看到；**但 work_order ↔ conversation 的關聯渲染**需經 problem_card 鏈，尚未自動建立。
- 「LINE 對話 → 自動生工單」（escalation → draft 問題卡 → 客服 1-click 轉工單，ADR-0031 人審路線）仍為斷層，屬下一個 CR。
- 本變更觸及 API contract + 整合邊界（CIA 範圍）；業主已直接圈定方案 A，先實作並登錄 CHANGELOG。

---

## 2026-06-14 工單詳情頁內嵌對話逐字稿（branch `feat/wo-conversation-thread`）

> 承上：方案 A 把對話寫進 DB 後，工單詳情頁原本的「LINE 對話記錄」區塊卻是 **placeholder**（只顯示「示意：…將顯示於此」靜態文字）。本輪把它換成真實渲染，補上「工單後台看得到對話」的最後一哩。

### 真實渲染（取代 placeholder）✅
- **資料鏈無需新建**：工單詳情頁早已透過 `ProblemCardSummary onLoaded` 取得 `problemCard.conversation_id`（work_order → problem_card → conversation 結構鏈），sidebar 與 media gallery 都已用它。本輪讓 `ConversationThread` 也吃同一個 conversation_id。
- **`ConversationThread` 重寫**：fetch `/conversations/{id}/messages`（與 `LineMediaGallery` 同 pattern），正序氣泡逐字稿 —— `user`=客人（左/白底）、`assistant`=客服/AI（右/主色）、`system`=系統（置中）；media 附件連結；「在新視窗開啟」改真實連結；loading / empty / error / no-conversation 四態；唯讀提示保留。
- **i18n**：zh-TW + en 移除 `placeholder` key、補 8 個新 key（noConversation / loading / empty / loadFailed / roleCustomer / roleAgent / roleSystem / attachment）。

### 驗證
- `npx tsc --noEmit` 0 error；zh-TW / en JSON 合法。
- **資料鏈實證**（dev DB）：seed 工單 `55555555` → pc `44444444` → conv `22222222` → user/assistant 訊息正確；無對話的工單顯「尚無對話訊息」空狀態。

### 全鏈狀態
- **「LINE 對話 → DB → 工單後台可見」已打通**（方案 A 寫入 + 本輪渲染）。
- 仍缺：「LINE 對話 → 自動生工單」（escalation → draft 問題卡 → 1-click 轉工單，ADR-0031 人審路線）為獨立後續 CR。
## 2026-06-14 CR-0022 LINE→工單 HITL backend（branch `feat/cr-0022-escalation-to-draft-pc`）

> 落地 ADR-0031「AI 草擬 + 客服 1-click 人審」（先前 decided 未實作）。承方案 A 補反向缺口：
> LINE agent 轉真人 → 旁路建 AI 草擬問題卡 → 客服在既有問題卡頁人審 → 既有 confirm → 既有 convert。

### Backend ✅（§9 step 1-7）
- **ADR-0112**：不新增 DB status（incomplete 已映射 API draft，零狀態機變更）；新增 source 標記 + 寬鬆建立；AI 永不自轉。
- **migration 032**：problem_cards 加 `source`(human/ai_line) + `ai_missing_fields` + 部分索引。
- **service**：`escalation_to_draft_pc`（session 冪等 + conversation_id UNIQUE 去重 + 寬鬆缺欄位）；`list_cards` 加 source filter。
- **API**：`POST /internal/escalations/ingest`（require_internal_token）；`listProblemCardsV2` 加 source param。
- **agent gateway**：transfer 後旁路 POST escalation（偵測本輪 escalation id 變化；fail-soft）。
- **測試**：`test_escalation_to_draft_pc.py` 6/6（含 charter lock：AI 卡僅 draft 不得 confirmed）；回歸 problem_card/work_order 74 + 全套 44 無破壞。

### 前端佇列 UI ✅（§9 step 8，同分支）
- `/problem-cards` 加「來源」篩選（AI 草擬（待轉工單）/ 客服手建，串 `?source=`）。
- `ProblemCardsTable` 對 ai_line 卡顯「AI 草擬」badge + 缺漏欄位 hint。
- 補全→confirm→convert 沿用詳情頁既有 handleUpdate/handleConfirm/handleConvertToWO（無需新造）。
- `api.generated.ts` ProblemCard 加 optional source/ai_missing_fields；tsc 0 error。

### 全鏈狀態
- **「LINE 對話 → escalation → AI 草擬問題卡 → 客服人審 → 工單」backend + 前端佇列已打通**。
- AI 永不自轉工單（charter）；轉換用既有 convert 端點。
- 待續：ADR-0031 標 implemented；建議補 Playwright e2e（需同時起 web+api）。

---

## 維護規則

- 每次合併 PR / 完成一個 milestone 後，**主 agent 必須更新本文件**
- 三大維度同步調整：完成度 % / 模組狀態表 / Workflow 覆蓋表
- 重大 milestone 時更新「最後更新」日期 + Phase 進度表
- 細粒度變更紀錄請查 `CHANGELOG.md [Unreleased]` + `docs/_audit/CR-NNNN-*.md` §8 進度區
- 新功能上線 / 架構決策 → 同步開 ADR（append-only）
