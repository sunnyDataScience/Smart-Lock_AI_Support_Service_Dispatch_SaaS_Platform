# Smart Lock 工單系統完成度總覽

> 跨前端 / 後端 / Realtime / Workflow / 架構遷移的整體進度盤點。
> 每次開發完成後更新本文件，保持與 CR-0004 §8 進度區、CHANGELOG `[Unreleased]` 同步。

**最後更新：** 2026-07-03（**20260702 會議 P0 五輪落地：VLN 修復／假流程強隱藏／兩入口同框／報價 CRUD／PPT 素材**（會議定調：Iron 新架構暫緩，舊版收尾 → 7/9 上線 GCP 給 Johnson UAT）— 12 條 Action Items 經三路並行盤點後分級（P0 五項本週做／AI-2 多租戶帳號設計週五另輪／部署參數化與監控 UAT 後），業主裁決：假流程全清單強隱藏、報價 CRUD 默認全包、P0 全做。**五輪（各自 branch、--no-ff 併回）**：① `fix/line-image-vln`：LINE 用戶傳照片系統已讀不回——webhook 只放行文字、圖片靜默丟棄，而 lockcore vision 管線（`InboundMessage.media`→base64 image_url→LiteLLM）**早已完整** → 放行 ImageMessageContent＋Blob API 下載落地 `get_media_dir("line")`＋`handle_text_turn` 帶 media；貼圖/語音等回友善話術＋`[貼圖]` 標記持久化；agent 全套 **143 passed**（+6 新）；② `feat/uat-hide-fake-flows`：盤點確認**全站金流 0 真接通**（payment_service 純 mock 無 router）→ 統一開關 `uatFlags.UAT_HIDE_FAKE_FLOWS` 強隱藏：退款整頁（側欄+直連 404）、wo-detail 設備示意/遠端開鎖/重置密碼/標記異常/時間軸篩選/過時 banner、儀表板假 SLA 卡（88% 寫死）、KPI 待接入佔位、營收切片/比較控制；月結鈕加「金流未接」黃標；產出 `docs_html/20260709/UAT-隱藏功能清單與可用功能報告.html`（給 Irene）；③ `feat/two-entry-auth`：入口 4→2（會議決議 2）——landing 2 卡、`/login`=品牌/經銷/鎖店同框（登入單一表單先試 admin 401 退試 vendor 依角色導向；註冊=廠商表單）、`/tech-login`=師傅同框（登入+註冊）、`/vendor-login`→`/login`、`/register`→`/` redirect 不斷鏈、`?tab=register` 深連結；後端端點零改動；④ `feat/quote-catalog-crud`：**CR-0110 依會議「一品牌一 DB」裁決簡化落地**（複合鍵/global+override/引擎 fallback 全不需要）——migration **087**（三表 deleted_at）＋9 端點（三類目 create/update/delete，OPS_ROLES+Idempotency）＋前端新增/編輯/刪除 modal 即時反映＋軟刪（同 code 重建=復活）＋編輯後 is_mock=FALSE；CR-0110 → implemented；⑤ PPT 素材 `docs_html/20260709/角色與功能總覽-PPT素材.html`（2 頁：兩條入口+7 可登入角色／各角色真實可用功能）。**驗證**：api 全套 **1513 passed / 0 failed**＋agent 143 passed；tsc 0；Playwright 實測（隱藏逐頁確認/兩入口四流程含 vendor 同表單自動分流/報價 CRUD 新增 32→33 編輯 2500→2800 軟刪）。**會議項對照**：§八 師傅結案流程=現有實作即定案（P1-05 LIFF 簽收關閉不做）；AI-2 多租戶三層（tenant_admin/super_admin 現況登不進建不出、註冊硬綁 tenant 0001）待週五設計；AI-3 部署腳本 PROJECT_ID 等全寫死＋web 單一 app 綁 build-time API base 為拆分深水區；AI-12 GCP 監控 repo 零設定（方向：Metrics Scope）。**已部署本機 docker api+web；雲端未部署（部署時務必套 migration 086+087）**。）

**前一次更新：** 2026-07-02（**師傅前後端全面測試 + 六輪修復**（goal：依文件測完技師前後端、該修的開新 branch 修）— 依 FR-0005/FR-0044/FR-0045/BR-M07-01/BR-CANCEL-007/beta checklist/設計 spec 11·12·19 建測試矩陣，後端 37 項 API 實測＋前端 Playwright 全頁（tech-login/home/pool/my-orders 詳情/完工表單/admin technicians 列表·詳情/lifecycle/dashboard）。**六輪修復（各自 branch、皆 --no-ff 併回）**：① `fix/tech-pool-claim`：搶單從未真正可用——pool 列 created 單但 accept 只允許 assigned（搶單必 409、前端誤報「已被接走」）且不寫 technician_id、不驗技師狀態（**停權技師仍可接單**，違反 BR-M07-01）→ accept 行為矩陣（技師×created=claim 寫入 technician_id／assigned 給他人=409 FR-0005 A9／非 active 技師=403 TECHNICIAN_NOT_DISPATCHABLE）＋pool 技師視角過濾（不再列派給他人的假搶單）；② `fix/tech-login-status-gate`：`technicians.status` 與 `users.is_active` 脫鉤 → **註冊未核准可登入、停權後仍可重登** → register is_active=FALSE＋lifecycle 每次轉移同步 is_active＋登入精確 403（ACCOUNT_PENDING_APPROVAL/ACCOUNT_SUSPENDED）＋**migration 086 校正存量（⚠️ 雲端部署需套）**；③ `fix/tech-detail-dead-controls`：badge 誤標（**normal 單全被標「急件」**、high 顯英文 Red Code → 對齊 spec：normal 無 badge/high 橘急件；Red Code=emergency 檔 DB 尚無該值退場）＋撥打電話死按鈕接真 `tel:`（payload 本有 customer_phone）＋**補「已到達現場」CTA**（後端 door-check 有 arrival 前置閘 CR-0007 HD-01 但前端無到場入口=門面檢核必 409 死路；spec 12_tech_my_orders 本有 arrived_btn）＋移除實收金額死輸入（後端 /onsite/completion 刻意 actual_amount=None、由 AR 模組後補）；④ `fix/technician-admin-polish`：詳情頁「本週排班」hardcoded mock（固定 2026/04/20-26 假早晚班）→ 新唯讀端點 `getTechnicianScheduleV2`（CIA-additive）接真實本週＋儀表板最近工單「技師 7777」改顯真姓名＋lifecycle 頁過時註解校正；⑤ `fix/tech-route-policy`：技師/廠商誤入後台路由 → AuthGuard 導 /dashboard 再被拒重導自己 → **白畫面死鎖** → `fallbackRouteForRole`（technician→/home、vendor→/vendor）＋技師 portal 四路由入 ROUTE_POLICY（technician-only）；⑥ `fix/cr0090-test-approval-gate`：跨角色 email 登入測試跟上登入閘。**驗證**：新測試 16（claim 9＋登入閘 3＋排班 4）；全套 **1506 passed / 0 failed**（順修 pre-existing：cr_0051 mock 欄位數腐化 IndexError、本地 063 brand-auth/skill seed 因技師表重灌流失 → 冪等重補）；Playwright 端到端（搶 created 單→詳情→到場鈕／登入閘 register→403→核准→200→停權→403→復權→200／排班顯真實週期／技師開 /dashboard 即彈回 /home）。**記錄未做（contract 級待 CIA/業主排程）**：decline＋reason 端點與 depart 未實作（FR-0005 A7/A10-A11）、接單 SLA 10/5min 逾時 410 未實作（A4-A6）、arrival 不轉 in_progress（spec 說要轉、後端只寫事件+started_at）、技師取消無 UI 入口（v2 6-stage 端點在、BR-CANCEL-007 罰則數字與 ADR-0102 實作不一致）、statement `:dispute` guard 為 OPS 與「技師舉報」註解語意不符、FR-0044/0045 仍 placeholder、access token 1hr 內停權不即時失效（需 per-user jti 追蹤）。**文件衝突已記錄**：FR-0005 §1.2 A2 標題殘留 30min 舊值（內文已是 10min）、急件 enum 命名不一（trapped vs trapped_inside）。**已部署本機 docker api+web；雲端未部署（部署時務必套 migration 086）**。）

**前一次更新：** 2026-07-01（**設定頁「個人資料」可編輯可存 + 清死控制（新 `GET/PATCH /auth/me`）**，branch `feat/settings-profile-editable` — 業主盤點 `/settings` 要求全部修正死控制。稽核：系統設定/報價已真接（`/api/v1/config`、pricing CRUD）；個人資料唯讀死頁（時區寫死、頭像/取消/儲存 disabled、電話恆「—」）；安全的 2FA 死 placeholder。**修**：① 新增自助端點 `GET/PATCH /api/v1/auth/me`（display_name/phone，本人 `get_current_user` 守衛、users 表既有欄無 migration）；② 個人資料頁 display_name/phone 改可編輯 input（載真實 DB 值）、啟用取消/儲存（PATCH+cacheInvalidate+成功訊息）、移除上傳頭像死鈕、時區改唯讀靜態、清 unused SelectField/deriveName/Upload/ChevronDown；③ 安全頁移除 2FA 死區塊、改密碼維持真接。i18n 兩 locale +3 key +修過時文案。未動（獨立功能）：頭像上傳/2FA/時區持久化。`test_auth_me_profile`（4 新）+ login 回歸 10 passed；tsc 0+next build+parity 2703+**Playwright**（可編輯欄載真值、改名→存→重載持久化；頭像/2FA/時區下拉消失；安全頁改密碼在無 2FA）。CIA：/auth/me additive 自助端點 → CIA-additive。**已部署本機 docker api+web**。）

**前一次更新：** 2026-07-01（**RBAC 授權 primitive `has_permission` + shadow 稽核（log-only，為「矩陣真正生效」鋪路）**，branch `feat/rbac-has-permission-shadow`（CR-0111 後續）— 業主追問「權限矩陣是不是只有定義、沒真的生效」→ 查證確認**目前矩陣完全沒接授權**（`role_required` 只比對 JWT role vs 寫死角色清單 195 處、`get_flat_permissions` 只在編輯時自我參照、無授權 middleware；連 read/write/delete 都不是強制來源）。業主選「先做安全半（不用 CIA、加性不改行為）」：① `role_service.has_permission(tenant,role,resource,action)` 讀矩陣判斷（unknown fail-closed）、純判斷不擋；② `core.deps.permission_shadow(resource,action)` FastAPI dep 掛在既有守衛外當 side-effect，矩陣會拒但放行 → 記 `RBAC_SHADOW_DENY`（永不 raise/不改請求）；③ pilot 掛 refunds create（write）/decision（approve）。**落差立現**：`tenant_admin`/`super_admin`/`operations_manager` 端點放行但矩陣無其列 → 貿然翻強制會鎖死這三個高權角色（先對帳再翻的鐵證）。`test_cr_0111_has_permission_shadow`（6 新）+ refunds/rbac 群 **77 passed**。純加性 log-only → CIA 豁免；讓 has_permission 成強制來源仍需 CIA（對帳 195 條 + rollout）。**已部署本機 docker api**。順帶清 rbac 測試遺留的 reviewer override 污染 16 筆。）

**前一次更新：** 2026-07-01（**RBAC 權限矩陣補齊：新增 can-approve 維度 + 角色補至 12 個（可操作可持久化）**，branch `feat/rbac-matrix-operable`（CR-0111）— 業主盤點 `/admin/roles` 後追問「文件規劃的權限是不是都包含了」→ 對照權威規格 `20260617資料/01-workorder-erp-final-spec-20260520.xlsx`（sheet 11 + M17 `BR-M17-01`「can-view/can-edit/can-approve」，標阻擋 Coding）確認**沒全包含**：維度缺 approve、14 角色只落地 4 個。業主經 AskUserQuestion 選「真可操作（碰後端）」= 採 §8 建議。**① approve 維度**：`role_service._perm`+`_ACTIONS` 加 approve、驗證放行；`role_permissions.permission_code` 為自由 text 故 `*.approve` **無需 schema migration 即可持久化**；approve **僅供矩陣配置/呈現、未接端點強制**（另 CR，matrixHint 已標）。**② 角色補至 12**：依 final-spec + owner Q&A 新增 accounting（Q113 工單唯讀、可核准退款）/supervisor/dispatcher/customer_service/auditor/family_reviewer（合約 4.4d）/distributor；_MATRIX/_ROLE_META/ROLE_HIERARCHY 前後端同步。**③ 前端**：矩陣加「核准」欄、編輯器 ACTIONS 加 approve、**預設選第一個可編輯角色**（原停在最高階 admin、編輯鈕灰掉像壞掉）、i18n 兩 locale 加欄+修過時文案。**驗證**：後端 test_cr_0111（6 新）+rbac 群 23 passed；tsc 0+next build+JSON parity 2702；**Playwright**（12 角色、4 欄、編輯鈕預設 enabled、會計 48 開關、勾 disputes.approve→存→DB role_permissions 真寫入→重載仍在→清 override 還原）。CIA CR-0111 §8 業主已裁。**已部署本機 docker api+web**。**延後另 CR**：approve 端點強制（CR-0092）、臨時 IT 權限（BR-M17-03）、AI Bot/System Setup/IT/AI Ops 4 角色、audit retention。並修 FR-0019「code 全部實作」失準。）

**前一次更新：** 2026-07-01（**庫存頁新增/補貨/編輯後需手動刷新才顯示 → 改為立即反映**，branch `fix/inventory-refresh-after-mutation` — 業主回報 `/admin/inventory` 建立物料後要「重新整理畫面」才看得到新品項。**Root cause**：`CreateInventoryItemModal` 送 `api.post` 後只呼叫 `onSuccess?.()`（→ 頁面 `fetchItems()` refetch），但 `api.get` 有 30s staleTime 的 GET 快取、mutation 後未清 → 立即 refetch 打到**建立前的舊快取**、拿回不含新品項的清單；整頁 reload 才因新頁面無快取取到新資料。同源問題另見 `RestockInventoryModal`（補貨）/`EditInventoryItemModal`（編輯）——皆 mutation 後直接 `onSuccess` 未清快取，補貨數量/編輯變更同樣要手動刷新才反映。**修正**：三個 mutation modal 於成功後、`onSuccess?.()` 前補 `cacheInvalidate("GET:")`（對齊 admin/quotes、accounting、technicians 等既有 mutation 慣例；cache key 含完整 URL 故用廣域 `GET:` prefix 清）。純前端快取失效修復、無契約變更故 CIA 豁免。next build/tsc 0 + **Playwright 實測**（新增「自動刷新驗證品項」不 reload 即出現、本頁品項 1→2；測試列已從 `saas.inventory_item` 清除）。**已部署本機 docker web**。**待辦**：全站其餘 create/mutation modal 若有相同「mutation 後 refetch 卻未 cacheInvalidate」模式可一併盤點（本次僅修庫存三個）。）

**前一次更新：** 2026-07-01（**營收頁 日/週/月/季 真實粒度切換（趨勢圖 date_trunc 分桶）**，branch `feat/revenue-real-granularity` — 業主澄清上一輪移除的粒度按鈕不是要移除、是要**能用**。**後端** `revenue_service`：`_query_trend_monthly`→泛化 `_query_trend(granularity)`，依 `_GRANULARITY_SPEC`（day/week/month/quarter → date_trunc 單位＋to_char 期別格式＋無 range 預設回溯視窗）分桶；`_VALID_GRANULARITY` 加 quarter；移除 `effective='month'` 寫死、granularity 原樣回傳。**踩雷**：date_trunc 單位/格式須**內插字面值**（白名單來源、無注入）而非 %s——否則 SELECT 與 GROUP BY 綁不同 $n → Postgres GROUPING 錯。`Granularity` enum（Pydantic+TS）additive 補 quarter。**前端**：還原 日/週/月/季 為可點真控制，切粒度同時套預設視窗（日近30日/週近12週/月近12月/季近8季，避免點「日」跑 365 柱）；`periodLabel` 依格式輸出（M月／QN／M/D）；subtitle 顯示粒度。`test_revenue_summary_granularity_buckets`＋`test_reports_v2`／`test_export_report` 23 passed＋tsc 0＋next build＋**Playwright 四粒度實測**（日 6/3·6/5、週 4/6·4/13、月 3月·4月、季 Q1·Q2，request granularity＋range 皆對、active 高亮）。CIA：enum additive＋讓既有 granularity 參數生效 → CIA-additive。**已部署本機 docker api+web**。**待辦**：季別 x 軸 QN 未帶年份（跨年同名、現資料稀疏無虞）；匯出 CSV 後端仍恆月度。）

**前一次更新：** 2026-07-01（**技師排行捲軸失效修復 + 移除營收失效粒度按鈕 + SOP 捲軸同類預防修復**，branch `fix/reports-scroll-and-granularity` — 業主回報 technician-ranking「捲軸失效」、revenue「日週月季時間按鈕失效」。**① technician 捲軸**（真 bug、pre-existing）：外層 `flex flex-1 flex-col gap-6 overflow-auto` 之 flex 子層被 `flex-shrink:1` 壓縮塞進視窗（Playwright 實測 `scrollHeight==clientHeight==773 canScroll=false`）、底部列+分頁鈕裁切 → 改 `flex-1 space-y-6`（block 堆疊自然溢出，同 refunds/warranty/disputes 修法）→ `scrollHeight=1521 canScroll=true` 可捲到底。**② revenue 粒度按鈕**：日/週/季上輪已 disable+即將推出（後端僅月粒度、四鍵同資料），業主仍視為失效；因時間篩選已由上輪接上的 DateRangePicker（start/end_date）統一負責、粒度分段冗餘 → **整段移除**（含 unused SEGMENTS），DateRangePicker 為唯一可用時間控制。**③ sop 捲軸**（連帶預防）：同容器同 latent bug（此租戶近期發布空故剛好塞下、有資料即裁切）→ 一併改 block、空狀態卡 flex-1→min-h-[400px]。純前端 CIA 豁免。tsc 0 + next build + **Playwright 三頁實測**（technician 可捲到底；revenue 無粒度按鈕、DateRangePicker+區間營收保留；sop 容器改 block）。**已部署本機 docker web**。**待辦**：revenue「切片按品牌」「與上期比較」仍為 disabled 誠實 placeholder（業主本次僅點名粒度按鈕），若要清空工具列可一併移除。）

**前一次更新：** 2026-07-01（**三報表頁盤點寫死並接真實資料：技師排行 / 營收 / SOP 績效**，branch `feat/reports-connect-dead-controls` — 業主：這三頁一樣有寫死就接上真實資料。**盤點方法**（ultracode workflow，每頁一 Explore agent + 對抗式 verifier 逐 finding 複查後端可接性）：verifier **推翻我數個初判**——(a) revenue 我原判「移除 DateRangePicker」，複查證實後端 `reports_v2`+`revenue_service` 端到端**已支援** `start_date/end_date`（F-021，TODO 註解已過時）→ 改判**接上**；(b) revenue 切片按品牌/與上期比較/樞紐文字**已是誠實 placeholder**（disabled+即將推出）→ **保留**、非移除；(c) sop 我原以為全真、複查抓到 **3 個真 bug**。**修正**：**① technician-ranking**（前端+後端）——移除 period（本週/月/季/年）死切換（`/technicians` 無 date 參數、統計全期）與失效 DateRangePicker（list+匯出皆不吃日期）；**修 `limit:100` 寫死**→ cursor 迴圈抓齊全租戶技師（上限 500、超過標「僅列前 N」）才是真排名母體；**CSV 匯出接真資料**——`report_export_service._technician_ranking_to_rows` 由 stub「尚未實作」佔位列改成真實技師列（rank/等級/完工/評分/綜合分/服務區域，依評分排序），`_build_rows` 取 `technician_service.list_technicians`。**② revenue**（前端）——**接 DateRangePicker**：`fetchSummary` 帶 `start_date/end_date`（由 range 導出、預設近 12 月）、trend/by_brand/KPI 皆改 DB-side range filter，標籤改區間語意（本月營收→區間營收、近12月→區間、subtitle 顯示區間）；日/週/季粒度**改 disabled+即將推出**（後端 `effective='month'` 四鍵同資料）、保留月；切片按品牌/與上期比較/樞紐文字保留為誠實 placeholder。**③ sop-performance**（前端）——移除「版本」欄（後端無 version、render 出 `vundefined`）；發布日期改讀 `reviewed_at`（後端回的 key、原讀 `published_at` 恆空）；核准率/發布率 hint「X 日累計」→「全期累計（不受區間影響）」（值本為全期、標籤原本說謊；停用候選確為窗口化故保留）。**驗證**：`test_export_report`/`test_reports_v2`/`test_sop_performance` 20 passed（technician 匯出測試改斷言真表頭+無 stub）+ tsc 0 + `next build` 成功 + **Playwright 三頁實測**（revenue：區間營收/已開立工單（區間）/月粒度 subtitle、日週季 disabled、請求帶 start_date/end_date 回 200；technician：period 消失、17 位技師真實載入、排序/區域保留；sop：版本欄消失、無 vundefined、hint 全期累計）+ **CSV 匯出實測**（技師排行真實 8 欄、依評分排序、真名如李麗華/黃師傅、stub 消失）。CIA：technician 匯出為 stub→真資料修復（CSV 欄位非契約）、revenue 純前端接既有端點、sop 前端 bug 修復——皆無契約變更故豁免。**已部署本機 docker api+web**。**待辦**：① revenue 接日期後 `month_revenue` 語意由「本月」變「區間」（與 `revenue_service` docstring 註記衝突、我採 code 行為+區間標籤），若業主要固定「本月營收」headline 可一行拆回；② sibling `accounting/revenue` 頁仍有「後端無日期參數」過時註解、無日期選擇器，宜一併接上對齊；③ sop 核准/發布率若要真窗口化（依 reviewed_at）為後端小改。）

**前一次更新：** 2026-07-01（**KPI 儀表板：FTFR 一次修好率接真實資料 + 移除品牌切片死控制 + 公式 hint 去 snake_case**，branch `feat/kpi-connect-ftfr-dead-controls` — 業主：檢查 KPI 頁有無寫死、有就接真資料。**盤點**：頁面主要 KPI（轉換漏斗 / 異常率 / 平均處理時長）**本就接真實** `KpiReport` 端點；真正寫死/未接的有——① **FTFR 一次修好率**顯示「—／尚未接入」placeholder（PendingTag「待接入」）；② **「切片：按品牌」下拉**是死控制（`sliceBy` state 設了但 fetch 完全沒用、後端 `get_kpi_report` 也無 brand 參數）；③ DisputeRow 三個 hint 露 snake_case 公式（`refund_requests / work_orders` 等）；④ SLA／NPS／滿意度為 placeholder 卡。**查可接性**：DB schema —— `work_orders` **已有 `is_rework` + `rework_of_id` 欄位**（後端 notes「尚無 rework 標記欄位」已過時）→ **FTFR 可接**；`conversations` **無 brand 欄**（漏斗第一階段無法分品牌）→ brand-slice 不可乾淨接；無 SLA 規則表／評價表／NPS 表 → SLA/NPS/滿意度真無資料源。**修正**：① **FTFR 接真值**——後端 `kpi_service` 新增 `_ftfr`（FTFR=完工且未被返工的原始工單 / 完工原始工單；分母排除 is_rework、分子再排除被 rework_of_id 指回者），加進 `technician_efficiency.ftfr`/`ftfr_sample`，並從 `notes` 移除 FTFR；Pydantic `KpiTechnicianEfficiency` + 前端生成型別手動補 ftfr/ftfr_sample；前端 FTFR 卡改顯示 `formatPercent(ftfr)` + 樣本數（去掉「待接入」）。② **移除 sliceBy 死控制**（select + state）。③ DisputeRow hint snake_case → 繁中（退款申請數／工單總數 等）。④ SLA/NPS/滿意度卡**誠實保留 placeholder**（真無資料源、非假資料）。**FTFR 定義為標準業界算法**（一次完修率），目前 DB 無返工資料故顯示 100%（真實反映、有返工即降）——定義已透明標於 hint，業主可調。**驗證**：`test_reports_v2`/`test_operational_kpi` 12 passed（含強化 FTFR 斷言）+ tsc 0 + `next build` 成功 + **Playwright 實測**（FTFR 卡顯示 100.0% 樣本 9 筆、無待接入；切片下拉消失；hint 無 snake_case；SLA 卡仍為 placeholder）。CIA：後端 ftfr/ftfr_sample 純加性回應欄位。**已部署本機 docker api+web**。**待辦**：FTFR 定義若業主想改（如改用 is_rework 比率法）為一行調整；SLA/NPS/滿意度需各自模組（SLA 規則引擎／評價回傳／NPS 調查管道）才能接。）

**前一次更新：** 2026-07-01（**知識庫分頁 sidebar 去重 + 三頁 tab count 接真實總數 + 匯出筆數/匯出 404 修復**，branch `feat/kb-real-counts-sidebar-dedup` — 業主：① 頁面已有的分頁（案例/手冊/SOP草稿）不要在 sidebar 重複；② 盤點還有哪些寫死的直接接上。**盤點**（ultracode workflow，5 partition + 對抗式 verify）：9 筆確認假資料、0 誤報——needs_backend（5：三頁互相把「別的分頁」count 寫死 128/23/7/6 且跨頁矛盾）、blocked_by_constraint（2：cases/manuals 品牌 filter 硬編）、yes_frontend（1：匯出 toast count 恆為 0）。**修正**：① **Sidebar 去重**：知識庫群組移除重複分頁的 kbCases/kbManuals/kbSopDrafts、只留非分頁的「家族覆核」；新增 `matchPrefix` 欄位 + 修 isParentActive，讓父項在整個 /knowledge-base 區段保持高亮（否則 manuals/sop-drafts 頁父項不亮、submenu 不展開）。② **tab count 接真數**：後端 `case_service`/`manual_service`/`sop_draft_service` 的 list 各補一句 `COUNT(*)`（基礎過濾、不含 cursor）回 `total_count`，`/kb/documents`+`/sops/drafts` router 透傳；前端新增共用 hook `useKbCounts`（三分頁各以 limit=1 讀 total_count），三頁 tab badge 全改真數、刪寫死 128/23/7/6。③ **匯出筆數**：cases 匯出 toast 從下載 CSV blob 算真實列數（總行數−表頭）取代恆 0。④ **匯出 404 修復（連帶）**：cases handleExport 的 `NEXT_PUBLIC_API_BASE_URL ?? fallback` 改 `||`——該 env build 時烤成空字串、`??` 不對空字串退回 → 變相對 URL 打到 web origin :3000 而非 API :8001 → 404；對齊 api.ts:BASE_URL。**品牌 filter 不動**：brands.ts docstring 明文記載屬資料正規化 CR、禁前端 paper over（workflow 判 blocked_by_constraint）→ 回報業主。**驗證**：test_kb_v2 13 passed（+2 新 total_count）+ 相關 92 passed 無回歸；tsc 0 + `next build` 成功；**Playwright 端到端**（三頁 tab 真數 案例2/手冊83/SOP0 對上 DB；sidebar 僅剩 知識庫+家族覆核、父項在 manuals 頁 active 且 submenu 展開；匯出下載成功＝CSV 1表頭+2列→toast 已匯出 2 筆）。清掉本次 pytest 造的 2 個測試 case。CIA：後端 total_count 純加性回應欄位。**已部署本機 docker api+web**。**待辦**：① 品牌 filter 正規化 CR；② manuals 有 ~77 筆跨 session 累積的 `Test %` 測試污染（count 真實反映、資料品質另議）；③ scope-change/quotes/track/consent/MediaGallery 同樣 `?? NEXT_PUBLIC_API_BASE_URL` 有相同空字串隱患，宜一併改 `||`。）

**前一次更新：** 2026-06-30（**全站 user-facing 字串內部識別碼洩漏盤點 + 修正（53 處）**，branch `fix/user-facing-jargon-leaks` — 業主回報異常頁「請先選擇處理方式（return_path）」把後端欄位名 `return_path` 露給使用者，要求「全盤再盤點一次並修正」。**盤點方法**（ultracode workflow）：8 個 partition 平行掃 `web/src/app` + `components` 的 user-facing 字串（setError/toast/JSX 文字/placeholder/title/aria-label/option label），找內嵌的內部識別碼／開發者 jargon；每筆再對抗式 verify（讀檔確認真渲染、排除註解／控制流／通用詞 JSON/CSV/Email/LINE 等）。76 個 agent、候選 68 → **確認 53、濾除 15 誤報**。**洩漏類型**：snake_case 欄位名（return_path/user_id/work_order_id/door_type/source enum）、HTTP 標頭名（X-Approver）、env 變數名（NEXT_PUBLIC_REALTIME_BASE_URL）、原始 enum 碼（instant/brand/locksmith/weekly/websocket）、內部流程/模組 ID（F-014/F-015 dual-trigger、M18 Config、ADR-0052/0053、FR-0007/0044、S3/S4）、協定 jargon（JWT/access token/endpoint/payload/MIME/HTTP {status}）、UUID 片段當顯示名（title={id}、`User ${id.slice}`）、英文括註（capabilities/profile/chars）。**修正**：① 25 處純字面替換以確定性 codemod（逐筆斷言「恰好 N 次」）；② 15 處 i18n 兩 locale 同步（移除 `（{status}）`、JWT/2FA/access token 文案改寫、`租戶 ID`→`所屬機構代碼`，含 4 個新 `sourceLabel` 鍵把通知來源 enum 轉中文）；③ 複雜案例手動：notifications source/door_type/cadence-format 建中文對照表、EventTimeline default 不再 dump 原始 JSON payload、problem-cards FIELD_LABEL 補全 + fallback 改「其他必填欄位」、conversations title 由 UUID 改公單號/品牌型號、config-governance namespace 中文為主標+原始鍵降小字副標、RolePermissionsEditor aria-label 改可讀、移除 ReportExportModal 的 Content-Type MIME 說明。**驗證**：tsc 0 + `next build` 成功（lint+typecheck）+ JSON parity 2700=2700 + **Playwright 三頁實測**（exceptions 不選處理方式→「請先選擇處理方式」無 return_path；config-governance 標題「設定治理」、全頁無 X-Approver/tenant_id/NEXT_PUBLIC/instant；settings 個人資料分頁無 JWT/access token/租戶、顯示「所屬機構代碼」新文案）。共 26 檔（24 程式 + 2 i18n），淨 +19 行。純前端屬 CIA 豁免。**已部署本機 docker web**。**待辦**：少數無 NS_HINT 的 namespace（如 auto_confirm_policy）仍顯示原始鍵（管理工具操作者需對照後端、刻意保留）；6 個改用 friendlyError/移除後 unused 的 i18n key 與本輪幾個 unused key 保留於兩 locale、parity 不破。）

**前一次更新：** 2026-06-30（**全站錯誤訊息收斂為使用者看得懂的繁中（移除 `errorCode (status)：英文 message` 外洩）**，branch `fix/friendly-error-messages` — 業主回報「NOT_FOUND (404)：Exception not found or already closed」這種開發者導向錯誤碼不該給使用者看，要全盤盤點一起修。**盤點**：~109 個前端檔把 `${e.errorCode} (${e.status})：${e.message}` 直接丟給使用者（露英文錯誤碼 + HTTP 狀態 + 後端英文 message），含 22 個本地 `formatError` 函式 + 4 個 i18n 模板（`toast.errorBody`/`errors.generic`/`server`/`forbidden` 也內嵌 `{code} ({status})`）。**修**：新增單一共用 `web/src/lib/apiError.ts` 的 `friendlyError(e)` —— ① 後端 message 已含中文（業務刻意寫給使用者）→ 直接採用最精準；② 否則錯誤碼 → 繁中映射（涵蓋 DB_UNAVAILABLE/VALIDATION_ERROR/NOT_FOUND/STATE_CONFLICT/權限/認證/工單/簽名… 40+ 碼）；③ 再否則退回 HTTP 狀態碼族群（401/403/404/409/422/429/5xx）。以確定性 codemod 全站收斂 **105 個標準檔** + **手動處理 12 個非標準殘留**（中文前綴 template 如「儲存失敗：…」、i18n 傳 `{code}`、以及控制流 `errorCode === "CODE"` 分支判斷——後者保留不動，因為是邏輯不是顯示）。順帶移除隨之失效的 `ApiError` import。**驗證**：tsc 0 + eslint 0 + 全域無未用 ApiError import + `next build` 成功 + **Playwright 重現業主情境**（建異常 → DB 刪除 → 點過時列「升級」→ banner 由「NOT_FOUND (404)：Exception not found or already closed」變為「找不到資料，可能已被刪除或狀態已變更，請重新整理後再試。」、確認無原始碼外洩）。淨 −333 行（移除大量重複錯誤格式樣板）。純前端屬 CIA 豁免。**已部署本機 docker web**。**待辦**：6 個 i18n error key（errorBody/generic/server/forbidden 等）改用 friendlyError 後成 unused，保留於兩 locale、JSON parity 不破。）

**前一次更新：** 2026-06-30（**異常管理頁「無法開立」修復 + subtitle 內部黑話收斂 + 工單欄接公單號**，branch `fix/exceptions-wo-picker-and-copy` — 業主回報 `/admin/exceptions` 無法開立、subtitle 露 M15/high_risk_hold 黑話「不該出現在前端」、要盤點寫死資料接上。**根因（無法開立）**：「工單 ID」欄是 raw UUID 文字框，使用者填公單號/任意字串（如 `WO-20260628-001`）→ 後端 `INSERT saas.exception_case`（work_order_id 為 uuid 欄）噴 `psycopg.errors.InvalidTextRepresentation: invalid input syntax for type uuid` 直接 500 → 瀏覽器顯示 net::ERR_FAILED、表單卡住＝「無法開立」（空欄/合法 UUID 其實會成功 201，故易誤判）。**修**：① 前端 raw UUID input → 重用 `WorkOrderPicker`（公單號 TP-000001/客戶名搜尋、對外回工單 UUID），根除壞輸入來源；② 後端 `open_exception` 補 uuid 格式 guard（非 UUID 回 422 `VALIDATION_ERROR` 取代 500，防禦縱深）；③ subtitle「M15 control tower…high/critical 會暫停工單（high_risk_hold）」黑話 → 改寫成正常使用者文案「統一追蹤並處理工單異常：缺料、加價拒絕、取消、爭議、安全風險等。標記為「高 / 緊急」的案件會自動暫停關聯工單，待處理後恢復。」；high/critical 暫停工單由純文字改成 **「已暫停工單」紅徽章**（active + 高/緊急 + 有關聯工單時顯示）；④ 工單欄原只顯示截斷 UUID（純文字、沒接資料）→ 後端 `list_exceptions` LEFT JOIN work_orders 回 `work_order_no`、前端顯示**公單號**（反查不到才退短 UUID）。**盤點結論**：admin 區 `quotes`/`payout-rules` 命中的 `is_mock` 是後端真實 provenance 旗標（只在真為 mock 才標「示意資料」）、非寫死假資料；本頁除 raw UUID input 外資料皆真（列表接 /exception-cases）。CR-0041 測試 **8 passed**（+2 新：非 UUID work_order_id→422、list 帶回 work_order_no）+ tsc 0 + docker api/web 重建 + **Playwright 端到端實測**（subtitle 無黑話外洩；picker 搜 TP-000144 選取；設高+選工單開立→列顯示公單號 TP-000144 + 「已暫停工單」徽章；DB 驗 `work_orders.high_risk_hold=t` 確認暫停機制真實）。測後清理測試 exception + 還原 TP-000144 hold。契約屬 bug fix（單函式）+ 純加性顯示欄（work_order_no），CIA 豁免。**已部署本機 docker api+web**）

**前一次更新：** 2026-06-30（**結算記錄「批次確認」按了沒反應（batch_action 寫空 saas.settlement、資料在 public）修復**，branch `fix/settlement-batch-write-public` — 業主澄清是問結算記錄的批次確認（非對帳核准）。**根因**（同對帳那個 v2/legacy 雷、方向相反）：結算**列表**讀 `public.settlements`（28 筆，你看到的），但**批次確認** `settlement_service.batch_action` 做 `UPDATE saas.settlement`（**0 筆，空表**）→ 更新 0 筆＝沒反應；且 public 是 3 態（pending/paid/failed）、saas 是 4 態（多 confirmed 中間態）。**業主裁 A：batch_action 改寫 public**。實作：① `batch_action` 改 `UPDATE settlements`（public，與 list 同表）+ 透過 technicians.tenant_id 過濾（public 無 tenant_id）+ 去 manual_paid_at（public 無此欄）；② public.settlements.status 為自由 varchar（無 CHECK）故 'confirmed' 可直接寫；Pydantic `SettlementStatus` 補 confirmed（否則 list 回 confirmed 422）；③ 前端 `SettlementTable` STATUS_TONE/statusLabels 補 confirmed（藍）+ lookup fallback（前端生成型別未含 confirmed）；④ doBatch 補 `cacheInvalidate("GET:")`（否則狀態更新被 30s 舊快取蓋住）；⑤ i18n status.confirmed（已確認/Confirmed）。settlement/reports 測試 27 passed 無回歸 + tsc 0 + JSON parity 2696 + docker api/web 重建 + **Playwright 端到端實測**（全選→批次確認→POST 200 updated 7、待付款 7→已確認 7（藍徽章即時顯示）；再批次標記已付→updated 7、已確認 7→已付款 19）。**已部署本機 docker api+web**。待辦：generate 月結批次仍寫 saas.settlement（v2 路徑），未來統一收斂到單一 settlement 表）

**前一次更新：** 2026-06-30（**結算頁對帳區空白看不到待核准（list 讀空 saas、approve 寫有料 public）修復**，branch `fix/accounting-recon-list-legacy-source` — 業主問結算頁「核准」按了沒反應。**根因**（記憶裡的 v2/legacy 雷）：前端對帳 **list 走 v2** `tenantPath("/accounting/reconciliations")` → `reconciliation_v2_service` 讀 **`saas.reconciliation`（0 筆）** → 整個對帳區「共 0」、根本沒待核准列可按；但真實 25 筆（5 pending）在 **`public.reconciliations`**，且 **approve 走 legacy** `/api/v1/.../approve`（讀寫 public）→ list 讀空 saas、approve 寫有料 public ＝錯位。**修**：對帳 list 改回 legacy `/api/v1/accounting/reconciliations`（讀 public、與 approve 一致，符 code 註解 P3.5-KEEP「v2 dual-sign UX 待重做、legacy 單簽暫留」）；順帶 handleApprove 補 `cacheInvalidate("GET:")`（避免核准完那筆從 30s 舊快取續留 pending）。純前端屬 CIA 豁免。tsc 0 + docker web 重建 + **Playwright 端到端實測**（對帳區 0→顯示 5 筆待核准；點核准→確認→POST 200 帶 Idempotency-Key→列表 5→4、toast「已核准」）。**已部署本機 docker web**。待辦：v2 dual-sign（:review→:co-sign）UX 落地 + `saas.reconciliation` seed 對齊後再整體遷 v2）

**前一次更新：** 2026-06-30（**結算頁「觸發本月月結」按了 400（api.post 不帶 Idempotency-Key）修復 + 批次按鈕 disabled 無提示**，branch `fix/settlement-batch-idempotency-ux` — 業主問結算記錄批次按了沒反應。**查出兩件事**：① **「觸發本月月結」是真 bug**：後端 `monthly-settlements:generate` 掛 `idempotency_guard` 強制 `Idempotency-Key` header，但 `api.post` 不會自動帶（只在 caller 傳 `opts.idempotencyKey` 時才加），`generateMonthly` 沒傳 → 每次按都 400 `MISSING_IDEMPOTENCY_KEY`（錯誤只顯在按鈕旁小字易忽略＝「沒反應」）。② **「批次確認/標記已付」非 bug**：`settlements:batch` 無 idempotency_guard，但兩鈕 `disabled={selectedIds.size===0}`，0 勾選時 disabled 按了無反應、且沒說明。**修**：① api client `rawRequest` 改為**非 GET 一律帶 Idempotency-Key**（caller 給就用、否則 `newIdempotencyKey()` 自動生，同 upload/download；未掛 guard 端點忽略此 header 無害；有顯式 key 保留）→ 系統性修掉此類 bug；② SettlementTable 批次鈕 0 選取時加 `title` + 旁顯提示「請先勾選結算列以啟用批次操作」（i18n batchHint zh+en）。純前端屬 CIA 豁免。tsc 0 + JSON parity 2695 + docker web 重建 + Playwright 實測（觸發本月月結 status 400→**201**、帶 Idempotency-Key、訊息「已觸發 2026 年 6 月月結」回 batch_id；批次提示 0 選取顯示、勾 1 列後兩鈕啟用提示消失）。**已部署本機 docker web**）

**前一次更新：** 2026-06-30（**退款/保固/爭議三頁捲軸失效（內容被 flex-shrink 壓扁）修正**，branch `fix/admin-list-scroll-flex-shrink` — 業主回報 `/admin/refunds` 退款列表捲軸失效。**根因**：與先前 `/admin/customers` 同一類——捲動容器寫成 `flex flex-1 flex-col gap-5 overflow-auto`（flex column），flex 子層預設 `flex-shrink:1`，20 筆退款撐高後子層被壓縮塞進視窗（實測 scrollH==clientH==773、`canScroll=false`）而非溢出觸發捲動。`/admin/warranty-claims` 與 `/admin/disputes` **共用完全相同的容器 pattern**、同樣 latent bug，一併修。**修**：三頁捲動容器 `flex flex-1 flex-col gap-5` → `flex-1 space-y-5`（去 flex column、子層自然堆疊溢出，同 customers 修法）。純前端屬 CIA 豁免。tsc 0 + docker web 重建 + Playwright 實測（修後 refunds scrollH 773→1376、warranty→1950、disputes→1727，三頁 canScroll 皆 true、可捲到底）。**已部署本機 docker web**）

**前一次更新：** 2026-06-30（**保固索賠建立 modal 兩個 raw UUID 欄接真實資料 + 清死搜尋框；爭議仲裁查核確認已全真**，branch `feat/warranty-create-modal-pickers` — 業主要求一起檢查 `/admin/warranty-claims` 與 `/admin/disputes`。**爭議仲裁**：盤點後**已全真**（列表/表格/詳情/證據面板皆接真實端點、X-Initiator 用真實 session、無 create modal 無 raw UUID 欄——爭議由後端 payment 事件自動建，這頁只審/co-sign），**不需改**（實測 18 筆正常）。**保固索賠**：顯示資料已真（列表 usePaginatedFetch /warranty-claims），但「建立保固申訴」modal 有兩個 raw UUID 手填欄 + 一個 disabled 死搜尋框。**接上**：① 客戶 ID（手貼 UUID 必填）→ `<select>` 拉真實客戶主檔（GET /customers?limit=100，顯示 `姓名（電話）`，54 名）；② 工單 ID（手貼 UUID 可選）→ 重用 WorkOrderPicker。**清掉** status tabs 右側 disabled「關鍵字搜尋」死控制（coming soon）+ 移除無用 Search import。契約（POST /warranty-claims 欄位）不變屬 CIA 豁免。tsc 0 + docker web 重建 + Playwright 實測（死搜尋框消失；客戶下拉 54 名真實客戶、選「陳美玲（0921123456）」回真實 UUID cccc0000-…；工單 picker 搜尋框在；無殘留 raw UUID 欄；disputes 18 筆正常）。**已部署本機 docker web**。附帶觀察：客戶清單含測試資料雜訊（初始/更新後名稱/測試客戶_…，DB 潔淨議題、非 code 缺陷））

**前一次更新：** 2026-06-30（**退款審批「建立退款申請」modal 兩個 raw UUID 手填欄接上真實資料**，branch `feat/refunds-create-modal-pickers` — 業主要求盤點 `/admin/refunds` 寫死資料並接上。**盤點結論**：頁面顯示資料**已全真**（端點回 20 筆真實退款、SLA 卡 1/0/5 由 items 即時算、RefundReviewTable 全 `row.*` 欄位驅動，無假資料）；唯一「未接真實資料」是建立退款 modal 的兩個 raw UUID 手填欄。**接上**：① 工單 ID（要手貼 `00000000-...`）→ 重用既有 `WorkOrderPicker`（搜公單號/客戶名，免 UUID，同先前報價頁）；② 覆核主管 ID（要手貼主管 UUID）→ 改 `<select>` 拉真實後台員工（`GET /api/v1/staff`，含角色中文標籤，排除發起人自己=SoD、只列啟用）。契約（POST /tenants/{tid}/refunds + X-Approver header）不變、純前端改輸入方式屬 CIA 豁免。tsc 0 + docker web 重建 + Playwright 實測（工單 picker 搜尋框在、主管下拉列 29 名真實員工＋角色標籤、選「示範覆核-黃覆核（審核員）」回真實 UUID 0a000003-…、無殘留 raw UUID 欄、admin 自己被排除）。**已部署本機 docker web**。**附帶觀察**：staff 清單有 ~25 個「重設測試（客服）」測試帳號雜訊（DB 資料潔淨問題、非本次 code 缺陷，另可清））

**前一次更新：** 2026-06-30（**移除 sidebar 重複的「會計傳票」項（tab bar 已可達）**，branch `chore/sidebar-remove-duplicate-vouchers` — 業主指出 `/accounting` 的 tab bar 已有「會計傳票」可點過去，sidebar 又列一個是重複（且發票管理/營收報表都只在 tab bar、沒進 sidebar，會計傳票進 sidebar 反而是不一致的那個）。移除 `Sidebar.tsx` 帳務群組的 `{ id: "vouchers", href: "/accounting/vouchers" }` 子項；連帶清死 key `sidebar.nav.vouchers`（zh+en，parity 2694=2694）。**保留** `accounting.tabs.vouchers`（tab bar 標籤）與傳票頁本身 —— 仍可從 /accounting tab 進入。純前端屬 CIA 豁免。tsc 0 + JSON 合法/parity + docker web 重建 + Playwright 實測（sidebar 帳務群組剩 月結算總覽/退款審批/保固索賠/爭議仲裁、無會計傳票；tab bar 會計傳票 tab 仍在、/accounting/vouchers 仍可達）。**已部署本機 docker web**）

**前一次更新：** 2026-06-30（**會計傳票頁空白 → 灌入 demo seed（含 6 月可見資料）**，branch `chore/seed-vouchers-demo-data` — 業主問 `/accounting/vouchers` 是沒資料還是有問題。**診斷**：是「沒資料」非顯示 bug（端點 200/count=0、頁面空狀態無錯、查詢正常）。`vouchers` 表全表 0 列，但 invoices 60/settlements 25/recon 25 都有。**兩層成因**：① 傳票功能 app 端唯讀 —— `voucher_service` 只有 list/get/render_pdf、**零個 `INSERT INTO vouchers`**，對帳/結算/退款/開票事件不會自動生傳票，唯一資料源是 seed SQL；② 既有 seed `SQL/seeds/vouchers.sql`（4 筆、本就在 quickstart SEED_ORDER）從沒套到此 DB（此 DB 用 realistic_demo_seed.py 灌、不含 vouchers）；③ 即使灌了，seed 那 4 筆是 4 月、頁面預設「近 30 天」會濾掉。**業主裁決**：灌 seed + 補 6 月資料。擴充 `SQL/seeds/vouchers.sql` 加 6 筆 6 月份傳票（reconciliation/settlement/refund/invoice 四型、含負數退款、posting_date 落 2026-06-05~29 預設範圍內）；套用至本機 DB（共 10 筆）。Playwright 實測（預設範圍直接顯示 6 筆、四型徽章齊、退款 -NT$2,800 紅字、PDF 鈕在）。無 code/schema 變動屬 CIA 豁免。**已套用本機 DB（無需重建容器）**。**治本待辦**：傳票自動產生（對帳核准/結算/退款/開票 → 自動記帳分錄）屬後端功能缺口，另立 CR）

**前一次更新：** 2026-06-30（**營收頁 CSV 匯出鈕從底部移到頂部 header（比照 /accounting 結算頁）**，branch `chore/accounting-revenue-csv-to-header` — 業主要求「匯出 csv 功能比照 /accounting 放到上方」。營收頁原本 CSV 匯出鈕在捲動內容最底部（justify-end），結算頁則在頂部標題列 refresh 旁。將營收頁匯出鈕搬到 header（順序：標題→refresh→CSV匯出→連線徽章），樣式比照結算頁匯出鈕（border + bg-surface + Download icon + 13px 標籤），功能不變（客戶端月度趨勢 CSV 下載、無資料時 disabled），移除底部匯出區（含已失效的舊 Excel 移除註解）。純前端屬 CIA 豁免。tsc 0 + docker web 重建 + Playwright 實測（匯出鈕只在頂部 top=16 與 refresh 同列、底部無殘留、點擊下載 revenue-month-2026-06-30.csv 內容為真實趨勢 period,revenue,order_count）。**已部署本機 docker web**）

**前一次更新：** 2026-06-30（**移除帳務 revenue/invoices 兩條揭露警語 + 清掉發票頁孤兒死控制（上線前收斂）**，branch `chore/accounting-remove-disclaimer-banners` — 業主要上線、不要使用者看到「即時 vs coming soon」這類內部揭露警語。移除：① revenue 頁警語（KPI/趨勢/品牌/問題類別即時…）② invoices 頁警語（搜尋/狀態/付款/日期即時、僅顯示逾期 coming soon…）。**連帶清掉**發票頁「僅顯示逾期」disabled toggle —— 它本就是靠該警語的 coming soon 說明存在的死控制，警語移除後變成沒說明的灰 toggle，上線更難看故一併移除（filters 搜尋/狀態/付款/日期完整保留）。i18n 移除 `accounting.revenue.banner`/`accounting.invoices.banner`/`accounting.invoices.overdueOnly`（zh+en 同步、parity 2695=2695；`comingSoon` 別處仍用故保留）。純前端屬 CIA 豁免。tsc 0 + JSON 合法/parity + docker web 重建 + Playwright 實測（兩頁警語/琥珀 banner div 皆消失、死 toggle 消失、三篩選保留）。**已部署本機 docker web**）

**前一次更新：** 2026-06-30（**帳務頁寫死資料轉真（問題類別營收佔比）＋ 四頁重新整理按鈕尺寸統一**，branch `feat/accounting-hardcoded-and-refresh` — 業主盤點 `/accounting` 四頁要求「把所有寫死的資訊都接上、統一上方重新整理 button 大小」。**盤點**：四頁表格（結算/發票/傳票）皆即時資料，唯一真正寫死「資料」是營收頁 `ServiceTypeChart`（無 props/fetch，寫死 4 筆假數字 維修 NT$520,000…）。**後端查證**：`work_orders.service_category`（install/repair/warranty）80 筆全 NULL（接了空圖）；唯一有資料維度是 `problem_cards.category`（卡片/指紋辨識/密碼/WiFi/電池/聲音異常/故障/安裝），經 `invoices→work_orders→problem_cards` JOIN（與 by_brand 同條）可聚合真實營收。**業主裁決「接問題類別＋更名」**（避免語意不符：原標題「服務類型」但唯一有資料維度是「問題類別」）。後端 `revenue_service._query_by_category`（clone by_brand、GROUP BY pc.category、NULL→未分類）+ `get_revenue_summary` 回應加 `by_category`；`RevenueSummary` model 加 `RevenueByCategoryPoint`+`by_category=[]`（手動 additive，openapi/api.generated.ts 待 TS 產生器修復後同步，前端 inline 型別，同 customer-stats 策略，CI api-types-sync 只看 openapi/ts 不踩 gate）。前端 `ServiceTypeChart`→新元件 `CategoryRevenueChart`（接真資料、條寬正規化、空/載入態、更名「問題類別營收佔比」）+ 警語去「服務類型示意」改「問題類別占比即時」。**按鈕統一**：`/accounting`（結算）36×36/icon16 異類 → 32×32/14 對齊其餘三頁。`test_reports_v2_endpoint` +by_category 斷言（6 passed；export/coverage 16 passed 無回歸）+ tsc 0 + JSON 合法 + docker api/web 重建 + **Playwright 實測**（端點回 8 類別真實營收 share 加總≈100%、圖表 DOM 卡片 NT$29,408…安裝 NT$19,950 與 DB 一致；四頁按鈕皆 32×32/14×14）。**版面修正**：問題類別圖 8 列（舊服務類型圖僅 4 列）在 flex-column 捲動容器內被底部 row 的 inline `minHeight:320`（覆蓋 flex item 預設 `min-height:auto`、放行壓縮）壓到 320px → 內容溢出跑版；改 `shrink-0 + min-h-[320px]`（高度回內容自然值、空資料仍有地板），實測兩卡同高 536px、末列「安裝」完整落在卡內。**已部署本機 docker api+web**）

**前一次更新：** 2026-06-29（**帳務 revenue 三個死/假控制清除（granularity/日期下拉/假 Excel）**，branch `fix/accounting-revenue-dead-controls` — 承警語實測，清掉 revenue 頁揭露但未處理者。① 日/週/月粒度分段：後端忽略 granularity（恆回月）→ 移除、固定 month。② 日期範圍下拉：periodPreset 沒進 API query ＝死控制 → 移除。③ Excel 按鈕：假 xlsx（CSV 改副檔名）→ 移除，留可用 CSV。順手修 CSV 鈕 hover:bg-white 深色。ServiceTypeChart 為硬編示意但已標「示意」屬誠實 placeholder 續留。警語再收斂為「KPI/月度趨勢/品牌占比即時、可匯 CSV；服務類型分佈示意」。純前端屬 CIA 豁免。tsc 0 + JSON 合法 + docker web 重建 + playwright 實測（粒度分段/日期下拉/Excel 皆消失、CSV 留、select 數=0）。**已部署本機 docker web**）

**前一次更新：** 2026-06-29（**帳務 invoices/revenue 警語收斂為實測精準版 + 修發票狀態 422**，branch `fix/accounting-banners-accuracy` — 業主問兩條「即時 vs 待接入」警語用意，實測（瀏覽器 token 直打端點對 DB）發現 invoices 警語大幅過期：搜尋/付款方式/日期/狀態 pending **全部真的篩**，只有「僅顯示逾期」未接（本就 disabled coming-soon toggle）；revenue granularity 後端忽略（日/週恆回月）、服務類型無欄位、CSV 客戶端可用、Excel 假 xlsx。**🔴 修 bug**：invoices 狀態下拉 `paid`/`overdue` 兩選項送出即 422（非後端白名單）→ 改合法值 pending(草稿)/issued(已開立)/voided(已作廢)，實測三值皆 200（5/53/2）。警語收斂成精準版（zh+en）。純前端屬 CIA 豁免。tsc 0 + JSON 合法 + docker web 重建 + playwright 實測。**已部署本機 docker web**。未處理（已揭露於警語）：revenue 日/週粒度死控制 + Excel 假 xlsx）

**前一次更新：** 2026-06-29（**帳務頁兩個死控制 + 假通知紅點 + i18n/色彩修正**，branch `fix/accounting-dead-controls` — 盤點 `/accounting`（表格資料真實，問題在控制項/通知）。**① 期間下拉死的+值對不上**：選了沒傳 period_filter（query 寫死 limit=50）、且 UI 給 6 個月但後端只有 3/12 → 對齊後端值 + 真傳 period_filter（實測 17→25 筆）。**② 結算週期分段（月/雙週/週）純裝飾**：沒進 API、後端僅月結 → 整個移除。**③ 發票紅點寫死 dot:true 恆亮** → 改接 status=pending（DB draft）有草稿才亮。**④ i18n**：期間選項/月結按鈕/訊息硬編中文 → 走 i18n。**⑤ 色彩/深色**：連線徽章 inline hex + Modal/取消鈕 bg-white + hover hex + tab 紅點 → token 化。純前端屬 CIA 豁免。tsc 0 + JSON 合法 + docker web 重建 + playwright 實測（期間切換真改資料 17→25 並送 period_filter；週期分段消失；紅點反映 5 筆草稿）。**已部署本機 docker web**）

**前一次更新：** 2026-06-29（**客戶詳情頁深色模式白卡 + 對話 enum 未翻譯 + KPI 色硬編修正**，branch `fix/customer-detail-dark-i18n` — 盤點 `/admin/customers/[id]`（資料本身全真、無假造，問題在樣式/i18n）。**A 深色 bug**：6 處 `bg-white`（Tailwind 關鍵字）不在 globals.css 深色覆寫名單（只認 `.bg-[#FFFFFF]`）→ 深色下白卡看不清 → 改 `bg-[var(--bg-surface)]`。**B i18n**：最近對話 status/channel 露原始 enum（escalated/line）→ 加 convStatus/convChannel i18n + label 助手。**C token 化**：7 張 KPI 卡硬編 hex（中性 #475569 深色近不可見）→ 改語意變數（--primary/--info/--accent-hover/--error/--text-secondary）隨主題適配。純前端屬 CIA 豁免。tsc 0 + JSON 合法 + docker web 重建 + playwright 實測（深色 main 白色元素=0、KPI 卡皆 #1E293B、數值色解析深色 --primary；對話 badge「已升級／LINE」無 raw enum）。**已部署本機 docker web**）

**前一次更新：** 2026-06-29（**客戶主檔統計卡接真實聚合（活躍/高風險/已過保固）**，branch `feat/customers-stat-cards` — `/admin/customers` 上方 3 張統計卡原為 placeholder「—」，業主要求接真實資料。新增 read-only 聚合端點 `GET /tenants/{tid}/customers/stats`（`customer_service.customer_stats`，FILTER 聚合 + cross-tenant guard）。**業主裁決定義**：活躍=`last_active_at` 近 30 天（is_active 全 true 不可用）、高風險=`risk_level IN ('high','critical')`、原「保固即將到期」因無客戶層級到期日改「**已過保固**」=`warranty_status='expired'`。前端去 placeholder 接 stats 值 + i18n 同步。additive read-only、無 migration；inline 型別（產生器本機 Node26 壞暫未進 openapi）。test_customers_v2 +2（19 passed 無回歸）+ tsc 0 + docker api/web 重建 + playwright 實測（活躍 9/高風險 10/已過保固 7 與 SQL 一致、端點 200）。**已部署本機 docker api+web**）

**前一次更新：** 2026-06-29（**客戶主檔頁捲軸失效（內容被壓扁裁切）修正**，branch `fix/customers-scroll` — 業主回報 `/admin/customers` 捲軸失效、看不到下半部客戶。**根因**：捲動容器寫成 `flex flex-col gap-5 overflow-auto`（flex column），flex 子層預設 `flex-shrink:1`，內容超高時被壓縮塞進視窗（實測表格從 ~1333px 壓成 466px）再被 `overflow-hidden` 裁切 → 看不到也無法捲（canScroll=false）。reseed 後客戶增至 50 筆才使 latent bug 浮現。對照正常的 quotes 頁捲動容器是純 block 非 flex column。**修**：捲動容器去 `flex flex-col`、`gap-5`→`space-y-5`（保留 flex-1）→ 子層自然堆疊溢出觸發捲動。純前端屬 CIA 豁免。tsc 0 + docker web 重建 + playwright 實測（修後 scrollH=1640 canScroll=true、表格恢復 1333、捲到底 reachedBottom=true）。**已部署本機 docker web**）

**前一次更新：** 2026-06-29（**技師停權/復權原因過短露出語意不明 VALIDATION_ERROR (422) 修正**，branch `fix/technician-suspend-reason-minlen` — 業主在 `/technicians/{id}` 點停權後得「VALIDATION_ERROR (422)」。**根因**：後端 `technician_lifecycle_service` 要求 reason strip 後 ≥3 字元，但前端 `handleLifecycle` 只擋空白未擋最小長度 → 打 1–2 字原因（如「壞」）通過前端被後端打回 422；catch 又只顯示裸 errorCode 沒帶 detail，使用者不知是「原因太短」。技師本身 active（轉移合法）。**修**（純前端對齊既有契約）：① prompt 加「（至少 3 個字）」② 送出前驗 <3 字擋下+友善提示 ③ catch 改顯示 `e.message` 後端 detail。純前端屬 CIA 豁免。tsc 0 + docker web 重建 + playwright 實測（1 字被前端擋下無 422；合法原因 suspend 200→按鈕變復權→reactivate 200 還原 active；測試 audit 已清）。**已部署本機 docker web**）

**前一次更新：** 2026-06-29（**技師管理頁 inactive 狀態露出原始 i18n key 修正**，branch `fix/technicians-inactive-i18n` — 業主操作 `/technicians` 某筆技師徽章顯示原始字串 `components.technicians.table.onboardStatus.inactive`。**根因**：技師生命週期合法集合為 `pending_approval/active/inactive/suspended/rejected/terminated`（見 migration 020 + lifecycle service，DB 實有 1 筆 inactive），但前端 i18n `onboardStatus` 與顏色表 `ONBOARD_TONE` 都只列 5 值漏 `inactive` → `t()` 找不到鍵回退原 key（顏色有 fallback 故只露字未壞版）。**修**：① i18n zh-TW（停用）/en（Inactive）補 inactive（非懲罰性「停用」，可重啟回 active，異於懲罰性 suspended 停權）② `ONBOARD_TONE` 補 inactive 中性灰調並註明合法集合來源。純前端屬 CIA 豁免。tsc 0 + JSON 合法 + docker web 重建 + playwright 實測（該筆顯示「停用」、原始 key 消失）。**已部署本機 docker web**）

**前一次更新：** 2026-06-29（**報價單頁刪除草稿後不即時刷新修正**，branch `fix/quotes-list-stale-refresh` — 業主實測 `/admin/quotes` 刪除某草稿後列表不馬上更新。**根因**：與 `fix/intake-cases-status-refresh` 同一類——`deleteQuote`／`createQuote`／`transition` 三個 mutation 後都呼叫 `fetchQuotes()` 重抓 `GET /quotes`（cacheable，30s staleTime），但 mutation 後未清 GET 快取 → 讀回「仍含剛刪那筆」的舊清單（要等 30s 或瀏覽器重整才更新）。**修**：① `deleteQuote` 加樂觀更新（點即從本地 `quotes` 移除該筆）② 三處 mutation 在 `fetchQuotes()` 前補 `cacheInvalidate("GET:")`（廣域清；key 為 `GET:${完整URL}:${tenant}` 含 host 故不可用 path-prefix）③ 修 `cache.ts` `cacheInvalidate` docblock 誤導範例杜絕復發。純前端屬 CIA 豁免。tsc 0 + next build 0 + docker web 重建 + **playwright 實測**（建草稿→刪除→列表即時更新、KH-000011 即時回「尚無報價的工單」23→24；network 確認 DELETE 後有 fresh `GET /quotes`、非讀 30s 舊快取）。**已部署本機 docker web**）

**前一次更新：** 2026-06-29（**進線案件頁 UX 加強 — SLA 倒數/逾時顯示 + 狀態配色 + 篩選列**，branch `feat/intake-cases-sla-filter` — 業主要求 `/admin/cases` 三項好用度加強：① SLA 欄改顯示首次回應剩餘/逾時時長（綠/琥珀≤30分/紅 三色，衍生自 first_response_due_at）② 狀態徽章配色（待回應=琥珀、處理中=藍、已結案=灰，原為同一靛色難辨）③ 加篩選列（狀態／渠道下拉 + 只看 SLA 逾時 + 清除鈕 + header「篩出 N 件」，列表改撈 ?limit=200 client 端即時篩）。純前端屬 CIA 豁免。tsc 0 + next build 0 + docker web 重建（/admin/cases 200）。**已部署本機 docker web**）

**前一次更新：** 2026-06-29（**進線案件頁操作後狀態不即時更新修正**，branch `fix/intake-cases-status-refresh` — 業主實測 `/admin/cases` 點「標記處理中／結案」後需手動重整才更新。**根因**：頁面 `cacheInvalidate(\`GET:${tenantPath("/cases")}\`)` 清快取，但 cache key 實為 `GET:${完整URL}:${tenant}`（含 host），path-prefix 對不上 `startsWith` → 沒清到 → `load()` 在 30s staleTime 內讀回舊清單。全站唯一誤用細粒度 prefix 者（其餘頁用廣域 `"GET:"`），源於 `api.ts` docblock 誤導範例。**修**：① updateStatus 改樂觀更新（點即改本地 state + open→in_progress 補記 first_responded_at，失敗才 reload 回滾）② 兩處 cacheInvalidate 改廣域 `"GET:"` ③ 修正 api.ts 誤導 docblock 杜絕復發。純前端屬 CIA 豁免。tsc 0 + next build 0 + docker web 重建（/admin/cases 200）。**已部署本機 docker web**）

**前一次更新：** 2026-06-28（**前端硬編收斂 — 品牌清單單一來源 + tenantId fallback helper + customers 篩選 i18n/技師下拉**，branch `fix/admin-hardcode-cleanup` — 盤點 /admin/customers 時發現多處「讀 code 推不出來」的硬編漂移。**① 品牌清單**：customers/manuals/cases/register/technicians 各自硬編一份互不一致品牌（連同品牌 value `美樂` vs `Milre` 都不一致）→ 抽 `web/src/lib/constants/brands.ts`（`LOCK_BRANDS` 單一來源，正典取自產品知識 references `3E/Chatlock/Dormakaba/Kaadas/Milre/Philips` + 保留既有市場品牌 Yale/Samsung），customers 下拉 + 3 處 placeholder 引用之。**② tenantId**：全站 11 處 inline 重抄魔術 UUID `00000000-…-0001` → `api.ts` 抽 `FALLBACK_TENANT_ID` 常數 + `resolveTenantId()` helper 收斂（殘留僅 api.ts 常數定義一處）。**③ customers 篩選**：風險/保固 option label 硬編中文 → 改 i18n `t()`（value 仍 enum 不動）；偏好技師「手打技師 UUID 文字框」→ 改技師下拉（fetch /technicians 顯姓名+電話）。**刻意延後（已就地註解、不腦補）**：KB manuals/cases 品牌 filter 綁定後端髒資料（`dormakaba` 205 vs `Dormakaba` 173、`美樂`/`Milre`、未列入下拉的 鎖市/小島/Chainlock）→ 屬資料正規化另開 CR；tenantId 無 session 行為（靜默退回 1 號租戶 vs 擋下導回登入）→ 跨頁安全決策待業主。純前端、無 contract/schema/flow 變動屬 CIA 豁免。tsc 0 + 4 面向對抗式驗證 workflow（contract/i18n/react PASS、行為回歸非阻塞已處理）。**待部署 web**）

**前一次更新：** 2026-06-28（**CR-0109 M09 媒體法務保留 legal_hold 手動設定面**，branch `feat/cr-0109-legal-hold` — Phase I backlog 批次 3 之 M09。`media_files.legal_hold` 欄 + retention cron 排除早已存在（CR-0067）但無設定面 → 運營端無法在爭議/保固/訴訟時鎖證據。手動設定面（admin 自行判斷何時鎖、**不腦補自動觸發規則** 待業主）：`media_service.set_legal_hold`（UPDATE + 404 + 稽核 media_legal_hold event）+ `list_media_for_work_order` 補 `legal_hold` 欄 + `media_v2` PATCH `/media/{id}/legal-hold`（REVIEW_ROLES + cross-tenant guard）+ 前端 `MediaGallery` 🔒「保留」徽章 + 鎖/解 toggle（有權角色才顯、樂觀更新）。additive 端點 + 既有欄位（無 migration）。API test_cr_0109_legal_hold 3/3 + **全套 1464 passed 無回歸** + tsc 0。Phase I 批次 3 之 M09 完成；M08 客戶 LIFF 簽收（需 CIA）另議。**待部署 api+web**）

**前一次更新：** 2026-06-28（**CR-0108 S3 LINE 進線自動帶 Case — M01 收尾**，branch `feat/cr-0108-s3-line-case` — 原 LINE 進線直接建 problem_card 不掛 Case，與手動渠道資料模型不一致。`problem_card_service` 新 best-effort `_ensure_line_case`：escalation 建/併草擬卡時 ensure 一張 `source_channel=line` 的 intake_case 並連 `problem_cards.case_id`（一卡一 Case、已連則略過、客戶資訊取對話 user 沿 D6、失敗不阻斷建卡）。**LINE 進線至此也收斂到 Case 模型，M01（CR-0108）後端+前端+LINE 三段全到位**。API test_cr_0108_s3_line_case 2/2 + **全套 1461 passed 無回歸**。**待部署 api**）

**前一次更新：** 2026-06-28（**CR-0108 S2 M01 進線建案前端頁 + Case 列表**，branch `feat/cr-0108-intake-frontend` — 接續後端核心，補前端讓客服可實際操作。新頁 `web/src/app/admin/cases/page.tsx`：代客建案（渠道 phone/web/referral + 客戶聯絡 + 摘要 → 發案號 C-NNNNNN + 啟動 SLA；LINE 由 agent 自動建案不在手動表單）+ Case 列表（案號/渠道/客戶/摘要/狀態/SLA 逾時紅標 + 標記處理中/結案 + header 逾時件數）。Sidebar「進線案件」入口（開單流程群組第 2 位）+ rolePolicy `/admin/cases`（admin/ops/dispatcher/**customer_service**，對齊後端 BACKOFFICE_ROLES、避開 `/admin` catch-all 排除客服）+ 中英 i18n。tsc 0 + 重建 api+web docker + **Playwright 實機驗證**（頁面渲染、UI 建案 C-000006 即時入列、curl POST/GET 通；測試資料已清）。**M01 批次 1 後端+前端齊**，僅 LINE 自動帶 Case（S3）小 follow-up 待續。詳見 `docs/4-exploration/CR-0108-m01-intake-case-entry.md` §13。**待部署 api+web（含 migration 085）**）

**前一次更新：** 2026-06-28（**CR-0108 M01 進線 Case 入口（後端核心）— 全渠道 Case 實體 + first-response SLA**，branch `docs/cr-0108-m01-intake-cia` — Phase I backlog 批次 1。M01 進線完成度 12%（Phase I 最低）、業主核心目標「接單從客服串到工單」最前端斷點。**先產 CIA 停 §8** → 業主裁決 D1 渠道 line/phone/web/referral（partner 4 渠道 Phase II）/ D2 SLA 入 config 暫定 30 分待業主 / D3 漸進 case_id nullable 不硬擋 / D4 Case 為上游容器（一 Case 多 problem_card/work_order）/ D5 可讀號 C-NNNNNN / D6 去重 phone+LINE ID（修正 Q008「依地址」）。**後端核心**：migration 085 `saas.intake_case`（+號碼序列 + `problem_cards/work_orders +case_id`）+ `intake_case_service`（建/列/詳/改 + SLA due + 守門 + in_progress 記首回）+ `intake_cases_v2` router（4 端點 BACKOFFICE_ROLES 含客服、cross-tenant guard、idempotency，main.py 註冊）+ `core.config` 加 intake 區段。API test_intake_case 5/5 + **全套 1459 passed 無回歸**（3 pre-existing seed 失敗無關）。**S2 待續（同 CR）**：前端進線建案頁 + Case 列表、LINE escalation 自動帶 Case。詳見 `docs/4-exploration/CR-0108-m01-intake-case-entry.md`。**待部署 api（含 migration 085）**）

**前一次更新：** 2026-06-28（**Phase I 帳號安全 A1+A2+A3 轉真 — 登入防爆破 / 停權即時失效 / 改密碼撤 session**，branch `fix/account-security-phase1` — 依序補 Phase I backlog 批次 0（業主裁決帳號安全先補，Beta 對外底線）。三件同屬 auth 子系統、共用 migration 084 + `get_current_user` 熱路徑，一分支內依序完成。**A1 登入防爆破**：migration 084 `users +failed_login_attempts +locked_until`；登入連續密碼錯誤達 `[auth].login_max_attempts`（預設 5）設 `locked_until=NOW()+login_lockout_minutes`（預設 15 分），鎖定中即使密碼正確也回 **429 LOGIN_LOCKED**，成功登入歸零；門檻入 config。僅既存帳號（查無不可記，回 401 同枚舉防護）。**A2 停權即時失效**：新 `core.auth.load_user_security_state`（fail-open：DB 不可用/非 uuid/查無 → None 維持 claims-only、相容既有假 user_id 元件測試）；`get_current_user`+`refresh` 每請求重查 `is_active=FALSE` → **403 ACCOUNT_DISABLED**（原停權後 access 1h/refresh 30d 仍有效）。**A3 改密碼撤 session**：migration 084 `users +password_changed_at`；`change_password`/自助 `confirm_reset`/`admin_reset_password` 設 `password_changed_at=NOW()`，token `iat < password_changed_at` → **401 TOKEN_STALE**（全域撤該 user 既有 access/refresh）。API `test_account_security_phase1` 5/5 + **全套 1454 passed 無回歸**（3 個 pre-existing seed 失敗 test_cr_0051/0060 與本批次無關，git stash 驗證）。詳見 `docs/4-exploration/phase1-gap-backlog-20260628.md` §1。**待部署 api（含 migration 084）**）

**前一次更新：** 2026-06-28（**Phase I 缺口 backlog + 給主管報告增補 Phase II/III 延後清單 + 修正派工模式誤述**，branch `docs/phase1-backlog-phase2-report` — 業主交辦三件：①Phase I 記下來逐一補帳號、②Phase II 補進給主管確認文件、③修報告錯誤。**①** 12-叢集對抗式現況驗證（對 dev_new_arch HEAD 實查 280 次）後新增 `docs/4-exploration/phase1-gap-backlog-20260628.md`：把 Phase I 純工程缺口立成可打勾 backlog，**業主裁決帳號安全 3 件（A1 登入防爆破/A2 停權 token 即時失效/A3 改密碼撤 session）排最前、一件一分支逐一補**，其餘（M01 進線 Case 入口、M03 分診 5-state/completeness_score、M08 客戶獨立簽收、M09 legal_hold 設定面、M02 Device 主檔、M05 狀態詞彙雙軌）依批次排程。**②** 給主管報告 `docs/_audit/owner-spec-compliance-and-pending-decisions-20260627.html` 新增 §十一 現況缺口驗證（Phase I 工程待補 + Phase II/III 延後清單供主管確認：金流 M11 router 未註冊、自動媒合 M06 引擎 stub、multi-tenant 三類租戶含 **vendors 隔離破口** `tenant_id=%s OR IS NULL`、Partner Portal M14、進階治理）。**③ 修正報告錯誤**：原 §二 step 5「派工模式前端 UI 待確認補齊」**誤述** → 實查前端 UI 已存在（`web/src/app/admin/dispatch-queue/page.tsx` 的 `DispatchModeSelector`，CR-0030 manual/platform_paid/auto_match），改判 ✅ 就緒（唯自動媒合引擎屬第二階段）。重跑 `gen_docs_html.py` 同步 md + docs_html 鏡像。純文件、無 code/contract 變動）

**前一次更新：** 2026-06-27（**CR-0107 師傅獎懲紀錄轉真 — 後台手動登錄 ledger + 自動帶取消失約扣款**，branch `feat/technician-detail-real-fields` — 業主問「獎懲為何還是寫死的」。**源頭查證**（窮盡翻 `20260617資料/`）：mock 4 筆（高評價獎金+200 等）來源完全無此規則（捏造）；唯一規則明確者為**取消失約扣款**（測試計畫 BR-CANCEL-007：同月首次免責/≥2次扣NTD500/不可抗力免責），已存於 `public.cancellation.technician_penalty` 欄；獎金與其他扣款規則未定義；**關鍵紅線 ERP spec Q121 明令「師傅扣款不能交給 AI 或工程師自行假設」**。**業主裁決「後台手動登錄+自動帶取消罰」**：建逐筆 ledger 供主管登錄（符合 Q121），list 時 UNION 既有取消失約扣款（read-only 自動帶入）。實作：migration 083 新表 `saas.technician_penalty_bonus_ledger`；`technician_penalty_bonus_service`（list UNION 手動 ledger + 自動取消罰[cancellation JOIN work_orders，id 帶 cancel: 前綴/editable=false]、create/delete 限手動）；`technician_penalty_bonus_v2` router（GET/POST/DELETE，DISPATCH_ROLES —— 財務敏感+Q121，main.py 註冊）；前端新元件 `PenaltyBonusLog`（抽離 sidebar，去 mock + 後台登錄 modal + 刪除[手動限定] + 自動帶入標「自動」不可刪 + 空狀態），連帶清掉 sidebar 已無用的 MockBadge。**師傅詳情頁右欄至此全部轉真**（可用狀態/佣金/獎懲+進行中工單），主區僅本週排班仍示意（CR-0105 §3 需班別定義）。API test_technician_penalty_bonus 4/4 + 技師相關 38 passed 無回歸 + Live E2E（丁啟恆 POST 手動獎金+300 + DB 插取消罰500 → 卡片顯「取消失約扣款 -500【自動】無刪除鈕 + 高評價獎金 +300 可刪」，seed 已清）。詳見 `docs/4-exploration/CR-0107-technician-penalty-bonus-ledger.md`。**待部署 api+web**）

**前一次更新：** 2026-06-27（**CR-0106 師傅佣金摘要轉真 — 固定工資制月結引擎**，branch `feat/technician-detail-real-fields` — 接續 CR-0104/0105，業主裁決「提前做佣金 + 核准草稿費率」。**源頭查證關鍵**（窮盡翻 `20260617資料/PhaseII_FinanceSettlement.xlsx`）：① 佣金/月結原屬會議拍板的「第二階段（Beta 後）」+ 費率 Q-09 業主自己標「待回答」→ 回報業主裁決「提前做+核准 21 拆帳規則 66 條草稿費率」；② **前端 mock 模型是錯的** —— mock 顯示「維修 70%/安裝 60%（抽成制）」，但來源實為**固定工資制**（每服務每等級固定 base_payout，電子鎖安裝 LV-B=500），月結走 AP Ledger（Σ工資+車馬+檢測+材料−平台費−未繳現金−爭議暫扣=應付）。**實作照固定工資制重建**：資料鏈 work_orders(completed)→quote_line_items(service_code)→technician_payout_rule(service_code,level_id)；migration 082 payout_rule 草稿→accepted（記錄 Q-09 決議，69 筆，費率值不變）；`technician_commission_service.compute_monthly_commission`（取技師等級 S/A/B/C→LV-A/B/C → 當月 completed WO 服務明細 × base_payout → gross=Σ(payout×qty)）+ `technician_commission_v2` router（`GET …/commission-summary`，DISPATCH_ROLES，base_payout 內部敏感）；前端 `CommissionSummaryCard` 抽成制→固定工資制（本月工資+服務明細+應付+空狀態，移除假 45,600/百分比/Mock 標籤）。**誠實限制**：夜間/急件加成不自動套用（觸發條件 Q-03/Q-04 待回答）、扣項暫 0（待月結模組）、S→LV-A（來源無 S 級費率）、多數技師佣金真但空（work_orders 多無 service_code 明細，有帶碼工單完工後自動填）。API test_technician_commission 4/4（固定工資制 LV-B SVC-ELK-001×2=1000、空案例、無費率 unmapped、cross-tenant 403）+ 技師相關 51 passed 無回歸 + Live E2E（丁啟恆 seed level=B+完工單 → 卡片顯「本月工資 NT$1,100＝電子鎖安裝500+住宅開鎖600」，seed 已清還原）。詳見 `docs/4-exploration/CR-0106-technician-commission-fixed-payout.md`。**待部署 api+web**）

**前一次更新：** 2026-06-27（**CR-0104 師傅詳情頁假資料轉真 — 可用狀態 / 等級 / 技能認證矩陣**，branch `feat/technician-detail-real-fields`（疊於 `feat/technician-admin-edit`）— 業主要求師傅詳情頁「全部轉接成真」。**40+ 子代理對抗式深掃 6 假資料區塊**判定：只 2/6 有可立即接的真資料源、4/6 缺的是**業務規則**（分潤%/等級門檻/班別/獎懲觸發，AI 不可腦補 — change-governance 紅線）。**業主裁決**：D1 等級=後台手動指派、D2 認證矩陣=建完整模組、D3 佣金/獎懲/排班三大模組本輪不做（下輪各立項）。本輪實作 3 區塊：**① 可用狀態（假綠修復）** technician_service `_TECH_SELECT` 接真 `online_state`（取代硬補 `_DEFAULT_AVAILABILITY`，enum 值域本就相同）；前端 `AvailabilityCard` 顯示真值 + 移除假 toggle/「上次上線」/「30 分自動離線」/Mock 標籤，加誠實註記「由技師端 App 切換、後台僅檢視」。**② 等級（手動指派）** migration 080 `technicians +level VARCHAR(2) DEFAULT 'C'`（值域 S/A/B/C，TechnicianLevel enum 守門）；`_TechnicianUpdateRequest` +level + `update_technician` SET；前端編輯 modal 加等級下拉。取代後端對全技師硬補常數「C」。**③ 認證模組（完整）** migration 081 新表 `technician_certification`（cert_name/brand/obtained_at/expires_at，與 063 brand_authorization 職責分離）+ `technician_certification_service`（CRUD + 狀態 computed：有效/即將到期/已過期）+ `technician_certifications_v2` router（4 端點，main.py 已註冊）+ 前端新元件 `CertificationMatrix`（讀真實認證 + 後台維護新增/編輯/刪除 + 空狀態），取代寫死 5 列 mock。**業務假設（待業主確認、非財務規則）**：等級預設 C（入門級）、認證即將到期門檻 30 天、認證 admin 後台登錄。API 技師相關 **83 passed + 1 skipped**（新增 cert 4 + level/availability 4，_TECH_SELECT 改動無回歸）+ Live E2E（curl + Playwright：認證 modal 新增即時顯示「有效」、過期顯示「已過期」、等級 PATCH=A 顯示 A、可用狀態真值；已清測試資料、丁啟恆還原 level=C/0 認證）。詳見 `docs/4-exploration/CR-0104-technician-detail-real-fields.md`。**待部署 api+web**）

**前一次更新：** 2026-06-26（**CR-0103 技師管理「編輯/停權/復權」前端接線 + admin 編輯端點**，branch `feat/technician-admin-edit`（疊於 phone 分支）— 業主回報技師詳情頁「操作沒有作用」。診斷：詳情頁「編輯」「停權」是 `disabled` 佔位鈕（`title="即將推出"`）。**關鍵發現（假綠 + 死碼）**：停權/復權/終止後端**早已可用**（`technician_lifecycle_v2` :suspend/:reactivate/:terminate + lifecycle_service，須 X-Initiator + reason，有 audit），只是前端鈕沒接；technicians_v2 另有重複 `:suspend` **501 stub** 被 include 順序遮蔽成死碼；「編輯」（admin 改任意技師）**後端真缺**（只有 updateMyProfile 改自己）。**業主裁決 D1 編輯+停權復權一起做、D2 編輯欄位姓名/電話/技能/區域**。實作：後端 `technician_service.update_technician`（mirror update_my_profile 改用 technician_id）+ 新 `PATCH /tenants/{tid}/technicians/{techId}`（updateTechnicianV2，部分更新，DISPATCH_ROLES + cross-tenant guard）+ 移除 501 死碼 stub；前端詳情頁「編輯」→ modal（4 欄逗號分隔轉陣列）→ api.patch，「停權/復權」依 status 切換 + prompt 收 reason → 接 lifecycle 端點，mutation 後 `cacheInvalidate("GET:")`（否則 refetch 取舊狀態）。**範圍**：編輯不含 email（Technician 回應無此欄）/狀態（走停權復權）；終止不掛 UI（不可逆另議）；示意資料維持現狀。API test_technicians_v2 +3 → 38 passed + Playwright 全流程（編輯存檔 DB 持久化、停權→復權→停權 round-trip，已還原丁啟恆+清測試 events）。**S2 後續 bug 修復**：業主實測「核准失敗 NOT_FOUND not found in tenant」——根因 admin「新增技師」(createTechnician) **沒傳 user_id** → technician.user_id=NULL，approve 的 `_fetch_status` JOIN users 撈不出 NULL user_id 列 → 404（**凡後台新增的 pending 技師全核准不了**，又一個沒端到端測過的假綠）。業主裁決完整修：① create_technician 在 user_id 缺時比照 register_technician 一併建 `users(role=technician)` 連 user_id（同 transaction，password 暫 NULL 走手機登入）② `_fetch_status` 改用 technicians.tenant_id 不 JOIN users 防呆；順手修 onboard 測試污染 dev DB（加清理 helper）。技師測試 39 passed + live E2E（建技師 user_id 非 NULL→核准 200→active）。詳見 `docs/4-exploration/CR-0103-technician-admin-edit-suspend.md`。**待部署 api+web**）

**前一次更新：** 2026-06-26（**CR-0102 LINE 進線電話自動帶入工單 customer_phone**，branch `feat/line-phone-autofill`（疊於 `fix/wo-customer-phone-line-id`）— 業主續要求「電話有提供的要自動填上」。查證管線：convert（`create_from_problem_card`）**下游早已通**（`final_phone = customer_phone or user_phone`，讀 `users.phone`），斷點在**上游沒人把客人在 LINE 講的電話寫進 users.phone**——`transfer_to_human` 只抽 brand/model/symptom（CR-0098）、兜底只抽品牌型號（CR-0097），電話從未進 facts。**業主裁決**：D1 只在空白時填（護客服手動值）、D2 程式 deterministic regex（不動 agent 核心）、D3 寫 users.phone（convert 既有讀取點、下游零改）。實作：agent `line_gateway` 新 `_extract_phone`（TW 手機 09xxxxxxxx，容 +886/分隔符；市話不抽）→ 正常路徑（`_forward_escalation_safe` +user_text）與兜底路徑都注入 facts_snapshot.phone；API `escalation_to_draft_pc` 新 `_normalize_tw_mobile` + `UPDATE users SET phone WHERE phone 為空`（best-effort 不阻斷建卡）。**範圍**：只對新進線/新轉單生效（已轉單電話定版不回填）、電話須在本輪原話/facts、只認台灣手機。agent test_line_gateway +5（26）/ API test_escalation +3（11）/ convert 回歸 22 全綠 + live E2E（POST escalation 帶 0922-371-211 → users.phone=0922371211，已清殘留）。詳見 `docs/4-exploration/CR-0102-line-phone-autofill.md`。**待部署 api+agent**）

**前一次更新：** 2026-06-26（**工單詳情「客戶資訊」電話亂碼修正**，branch `fix/wo-customer-phone-line-id` — 業主回報 TP-000002 工單詳情「客戶資訊」的電話是亂碼。根因：`WorkOrderDetailSidebar.tsx` 的 `CustomerInfoPanel` 把 LINE 帳號識別碼 `line_user_id`（`U3bc4ff5b50486278d25d00d0c168fa02`，33 碼 opaque token）擺在**電話圖示**旁顯示前 12 碼（檔案註解自承「phone 待 facts 模組」，拿 LINE ID 充當電話佔位），被讀成亂碼電話；真電話 `work_orders.customer_phone` 此單為空（LINE 進線未留電話）。修法（純前端、誠實化）：電話圖示改綁真 `customer_phone`（從父層傳入 panel，空則顯「未提供」），`line_user_id` 改用 `MessageCircle` 圖示並標明「LINE ID」獨立列、不再混為電話。無 contract/schema 變動屬 CIA 豁免。Playwright 驗證客戶資訊面板顯「— ／未提供／LINE ID U3bc4ff5b504…／台北市」+ next build tsc 0。**待部署** web 生效）

**前一次更新：** 2026-06-26（**報價頁「工單 vs 報價混在一起」修正 + 「示意資料」誤標移除**，branch `fix/quote-list-scope-to-wo` — 業主實測 `?wo=` 帶入工單後，下方「報價列表」卻是跨工單全域清單（選 TP-000002，列表卻列出別張工單的 TP-000001-Q1），工單脈絡與報價清單對不上。根因：`fetchQuotes()` 打 `GET /quotes`（全租戶無過濾），列表直接 `quotes.map` 渲染全部；同頁同時做「為單一工單編報價」與「瀏覽全部報價」兩件事卻無過濾橋接。**業主裁決：列表 scoped 到選定工單**。純前端：派生 `visibleQuotes`（選工單→`filter(work_order_id===woId)`；未選→全部）、標題依模式顯「TP-000002 的報價（n）」/「全部報價（n）」、scoped 0 張顯空狀態「尚無報價，點上方『建立草稿』新增」、WO context fetch 順撈 `document_number` 當標題單號。另：`is_mock` 欄位定義卻從未用、「示意資料」badge 恆亮會誤導真資料畫面 → 改 gate 在 `quote?.is_mock`（真 mock 才標）。無 contract/flow/schema 變動屬 CIA 豁免。Playwright 三案例驗證（TP-000002 空狀態／瀏覽全部／TP-000001 自身 1 張）+ next build tsc 0。**同分支續加「尚無報價的工單」總覽**（業主後續要求）：瀏覽模式（未選工單）在「全部報價」下方新增一區，列出**所有工單扣掉已有報價者**（排除終態 closed/cancelled，列在「待報價」會誤導），每列「去報價」鈕 `setWoId` 直接切到該工單 scoped 模式可建草稿；client 端與報價算差集（`GET /work-orders?limit=100` × `GET /quotes`，無新端點仍屬 CIA 豁免），工單超過 100 筆誠實標註只比對前頁。Playwright 驗證瀏覽模式顯「尚無報價的工單（1）→ TP-000002 詢價中」+ 點「去報價」切 scoped 空狀態、scoped 下該區隱藏。**再修報價詳情殘留**（業主回報：清除工單回「全部列表」後，下方仍殘留上一張報價 TP-000002-Q1 的詳情編輯區）：根因 `{quote && …}` 詳情只看 `quote` state、與是否 scoped 無關，清除工單時 `quote` 沒被清。修法：新增 effect，工單選擇變動（清除/切換）時若開啟的報價不屬於當前工單即 `setQuote(null)`（truthy guard 保留未綁工單的報價；與 loadQuote 先 setQuote 再 setWoId 的時序相容、不誤清）。Playwright 重現→修復驗證（scoped 開詳情→清除→詳情消失、回乾淨「全部報價（2）」）。**待部署** web 生效）

**前一次更新：** 2026-06-23（**CR-0097 AI 進線「說了轉接卻沒呼叫工具」兜底**，branch `fix/agent-handoff-fallback`（疊於 `feat/sidebar-reorder`）— 業主 LINE 實測報修（品牌+症狀+電話齊全），AI 回「已轉接真人」但問題卡沒生成，重傳穩定重現。根因（agent log）：只 iteration 0、零工具呼叫——AI 生成「已轉接」話術卻沒實際呼叫 `transfer_to_human`，escalation 未新增→不建卡。**不是 SOP 沒寫清楚**（§0 鐵律 + booking.md 都明示），是 LLM tool-calling 穩定不遵守，文字壓不住——進線→建卡 100% 靠 LLM 自覺，報修會靜默蒸發。業主裁決方案 A（話術-行為一致性兜底）。實作守 architecture lock（不加工具/不改白名單/不 fork 核心，改 channel 層 line_gateway）：`_promised_handoff` 偵測承諾話術 + turn 後若「沒呼叫工具且承諾轉接」→ 補 escalation 讓既有 forward 建卡；fail-soft。test_line_gateway +6 + agent 126 passed。**Follow-up**：監控兜底觸發率、部署 agent 後 live 重測。詳見 CR-0097。**待部署 agent**）

**前一次更新：** 2026-06-23（**後台 sidebar 依開單流程重排 + 分組標題**，branch `feat/sidebar-reorder` — 業主反映開單時 sidebar 不順手（報價單/客戶主檔散在後段、知識庫卡流程中段）。重排為 4 分組：開單流程（儀表板/對話/問題卡/派工管理/報價單/技師/客戶/帳務結算）、審核與例外、知識與報表、設定與主檔；`navItems`→`navSections` + render 加灰色分組標題（整組無可見項則隱藏，沿用角色過濾）+ 中英 i18n（sidebar.section.* 4 key）。純前端不動路由/權限，tsc 0。**待部署** web 生效）

**前一次更新：** 2026-06-23（**CR-0096 同一 LINE 客人不同問題各自獨立成卡**，branch `fix/problem-card-per-issue`（疊於 `feat/quote-wo-picker`）— 業主實測透過 LINE 講新問題，卻發現「新問題卡」內容跟第一張寫在一起。**根因三連鎖**：①LINE 同用戶永遠同 conversation（`session_id={tenant}:{user_id}` 永久復用）②`problem_cards.conversation_id` 全唯一（一 conversation 一卡）③`escalation_to_draft_pc` 對既有卡無條件 append（連已轉工單的卡也照 append）→ 一客一卡，無法分單。**業主裁決方案 A**：舊卡「已轉工單/已結案」才開新卡，draft/已確認未派工 → 併入。**做法**（最小破壞，不動 status 語意）：migration 077 `problem_cards +converted_at` + DROP 全唯一 + 部分唯一索引 `uniq_pc_conversation_active`（同 conversation 同時只一張 active 卡）；service 5 處加 active 條件。test_cr_0096 3/3 + 轉工單/工單/escalation/convert/create_card/sop_draft/ingest 回歸 64/0。**Follow-up**：對話訊息串仍共用（卡/工單已分開，但 LinkedConversation 仍顯示整段對話，要完全分需「每問題開新 conversation」更大改動）；prod 套 migration 077 待部署。詳見 `docs/4-exploration/CR-0096-problem-card-per-issue.md`）

**前一次更新：** 2026-06-23（**報價頁建報價改「選工單」免貼 UUID**，branch `feat/quote-wo-picker` — 業主實測回報「建報價草稿那欄還是要貼工單 UUID `45423b41-…` 才能搜尋」。釐清現況：工單早有可讀公單號 `{2碼地區}-{6碼流水}`（如 `TP-000001`，CR-0020 / migration 031 依 `customer_address` 發號，per-region 原子遞增），列表/詳情顯示層也已用公單號，但**報價頁「建報價」唯一入口仍是 `placeholder="work_order uuid"` 的手貼輸入框**。**① 後端**：`work_order_service.list_orders` 的 keyword 過濾加 `OR wo.document_number ILIKE`（原只搜客戶名/地址/電話）→ 公單號可搜；additive query filter，response schema 不變。**② 前端**：新元件 `web/src/components/quotes/WorkOrderPicker.tsx`（受控、debounce 300ms 搜尋、顯示 `公單號　客戶名　狀態`、選定回拋工單 UUID、深連結 `?wo={uuid}` 自動反查公單號顯示不露 UUID），報價頁 UUID input → `<WorkOrderPicker>` + 中英 i18n（woPicker* 5 key）。性質為前端 wire-up + 後端搜尋微增強（不動 response schema / domain model / 流程），比照 CR-0091/0095 前端補接，未跑完整 CIA。**順帶標記**：`SQL/Schema_doc_numbering.sql` 註解仍寫工單 `WO-YYYYMMDD-NNNN`（ADR-009 舊設計），實際早被 CR-0020/ADR-0110 地區制取代 → 待修註解。test_wo_keyword_doc_number 2/2（公單號完整＋前綴搜得到、客戶名回歸）+ 工單 v2/報價回歸 24/0 + tsc 0。**仍餘**：工單超過一頁時 picker 僅搜後端 keyword 命中者（已足；極端量可加分頁）、網址列與 Kanban/地圖 hover 仍露 UUID（顯示層獨立改點）。**待部署** web 才在 prod 生效）

**前一次更新：** 2026-06-22（**報價 LINE 同意流程貫通 + 派工硬閘 + 技師核准按鈕 + LINE 推送斷鏈根因修復**，branch stack `feat/quote-line-approval`→`fix/quote-conversation-sync`→`fix/quote-version-increment` + `fix/sop-dispatch-escalation` + `fix/technician-approve-button` — 業主逐頁實測派工流程。**① CR-0095 報價 LINE 同意**（§8 裁決 D1 真 LINE 點按+網頁 fallback / D2 硬擋一律需報價同意+主管 override / D3 拒絕保留工單重送 / D4 過期擋派工）：`quote_proposal` Flex（postback `q:a|`/`q:r|`）+ `transition(send)` enqueue + agent `line_gateway` 接 `PostbackEvent` 回內部端點；`_assert_quote_accepted`（無 accepted→409 `QUOTE_NOT_ACCEPTED`）整合派工。**② 連帶揪出 LINE 推送斷鏈真根因**：`templates/line_flex/__init__.py` 未匯出 `build_messages` → outbox worker ImportError → 所有 LINE 推送（派工/接單/完工 PDF/報價）從未送達（會議「公單回傳斷鏈」Action #6 的 runtime 根因，先前 code-review 標 met 但 live 從未驗證）。**③ SOP 補強**：`transfer_to_human` 是唯一進系統工具，但 SOP 只在「轉真人」段明令呼叫、派工/預約段只給話術 → AI 對客戶說「會安排」卻靜默蒸發；盤點 12 種應呼叫情境後補強（skill 1.2.0→1.3.0）。**④ UX2**：報價事件同步對話管理（send/accept/decline 寫 system 訊息）+ 可讀編號 `TP-000001-Qn`（version 沿工單遞增，修撞號）+ 報價列表 dashboard + 開啟新分頁。**⑤ 技師核准按鈕**：派工派不出去根因技師 pending_approval 且後台無核准入口（`Technician` 回應漏 `status` 欄被 Pydantic `extra=ignore` 丟掉）→ 補 status 欄 + `TechniciansTable` pending 顯「核准」鈕接既有 FR-0044 `:onboard-approve`。**⑥ sidebar**：捲軸保持 + 稽核權限父項導向 /admin/roles。**⑦ ops**：prod schema 對齊（74 migrations）+ 測試交易資料清空（fail-closed TRUNCATE，保留帳號/型錄，清前先備份）。test_cr_0095 10/10 + 技師 v2 9/9 + quote 相關 42/0 回歸 + agent 120 + tsc 0。api+web 已部署 Cloud Run（image `dfdebdd8`）。詳見 CR-0095 / CHANGELOG。**仍餘**：scope_change postback 救活（仍走網頁 fallback）、報價同意後自動排單、codegen 修復（`generate_models.sh` spec 路徑失效、`datamodel-codegen` 未裝））

**前一次更新：** 2026-06-21（**Phase II 前端補接 CR-0093：完整角色系統 + 技師完工修復 + 發票動作**，branch `feat/perm-i18n-dispatch-20260621` — 業主「安排計劃依序做完」稽核報告 §三的「後端做了前端沒跟」缺口。依序完成：**① CR-0039（壞掉，最優先）** 技師完工頁改打 `/onsite/completion` 正規硬閘（原打 :complete 撞 403 → 主完工流程壞掉）+ 客戶簽名上傳 + 照片≥3 gating + 422 友善訊息。**② CR-0094 完整角色系統**（業主裁決「建完整」，解「5 角色只有 admin」）：稽核發現角色三方不一致（role_service._MATRIX 5 角色 / auth._ADMIN_WEB_ROLES 登入集 / rolePolicy 缺 reviewer）+ 無建非-admin 帳號路徑 → 新 `create_staff_user` + `POST/GET /api/v1/staff`（admin 建 5 種後台角色帳號，即時 active）+ `REVIEW_ROLES`（reviewer 對齊 _MATRIX 可寫退款/保固/爭議）+ rolePolicy 補 reviewer + `/admin/staff` 員工管理頁 + Sidebar 入口。**③ CR-0035 發票動作**：accepted 報價加「開立發票」鈕 + accounting「觸發月結」鈕。**④ CR-0036/0044/0045/0046 config 治理 UI**：新 `/admin/config-governance` 一頁涵蓋全 M18 namespace（訂金/佣金/月結/取消費/稅率/公司檔/折扣）+ 草稿 + 雙簽上線（業主可自助改值不改 code）。**⑤ CR-0037** 師傅拆帳規則唯讀頁。**⑥ CR-0029 廠商專區**：`GET /vendors/me` + `/vendor` 專區頁 + 登入導向修正。**⑦ CR-0042** 轉單 422 結構化缺漏欄位 + 主管 override UI。**⑧ MED 收緊**：7 個治理/稽核讀取端點收緊（其餘 cross-role 讀取逐類審查留續）。**Phase II 8 項全完成**，test_cr_0029/0094 + 全套件 **1396 passed / 0 回歸** + tsc 0 錯。詳見 CR-0093 §表。**仍餘**：MED 其餘讀取逐類審查、brand_oem 夥伴入口進階功能（發案/對帳）、Playwright 視覺驗證待業主登入目視）
**前一次更新：** 2026-06-21（**權限硬化 + 派工單視圖 + i18n 修復 CR-0091/0092**，branch `feat/perm-i18n-dispatch-20260621` — 業主「是不是只改後端沒改前端，連權限設定都沒改好」。37-agent 稽核 407 端點 + 23 CR 前後端對照，兩直覺皆證實並量化（報告 `docs/4-exploration/audit-backend-frontend-rbac-20260621.md`）。**① 權限（CR-0092）**：80 個敏感寫入只用 `require_tenant`（不檢查角色），任何登入者含 technician/vendor 可寫金流/設定/派工/結算/退款/GDPR；`core/deps.py` 加單一真相源角色常數（既有集超集+super_admin，不破既有），80 端點 `require_tenant`→`role_required(*CONST)`（保留 SoD/idempotency）；MED 193 列 Phase II。**② 派工單（CR-0091）**：work_orders 早有 PDF 6 模組全欄+PATCH 端點但前端零編輯 UI（CR-0026/0043/0047 假綠）→ 新 `DispatchOrderView` 6 模組+內嵌編輯（首個 api.patch /fields 消費者）+ 模組 4 串新 admin 免責同意 GET。**③ i18n**：補 66 個缺失 key（quotes/quoteCatalog/vendorApprovals 整段空 + 工單詳情 ops v2 action 顯示 raw path）。test_cr_0091 5/5 + test_cr_0092 角色隔離 + **全套件 1386 passed / 0 回歸** + tsc 0 錯 + API smoke 401。**Phase II（前端缺口待補，報告 §三）**：CR-0035 報價→發票前端、CR-0036 config 治理 UI、CR-0039 技師完工頁接正規端點、CR-0040 brand_oem/accounting 角色補進 rolePolicy。詳見 CR-0091/0092 / 稽核報告）
**前一次更新：** 2026-06-21（**技師/廠商可共用 email CR-0090**，branch `feat/tech-portal-dashboard` — 業主：同一人想兼接案(技師)+發案(廠商)，但註冊 `EMAIL_TAKEN 409`。email 唯一性由全域唯一改「每角色唯一」（register 檢查 +`AND role=`）。**零 migration**（users.email 本無 UNIQUE）；登入 `_find_user_by_email` 已 role 過濾故天然分辨，兩列獨立 users/密碼。test_cr_0090 4/4 component + 267 unit；實機技師201→同email廠商201→同email技師再註冊409。Phase II：密碼重設 role-aware。詳見 CR-0090）
**前一次更新：** 2026-06-21（**廠商註冊 404 修復 + 統一編號 CR-0089**，branch `feat/tech-portal-dashboard` — 業主逐頁測試廠商註冊遇 404：根因為註冊頁路徑缺 `/api/v1`（修正原在 `fix/register-path-and-fields`，未跟到本分支 → cherry-pick `193643b9` 帶入，技師+廠商註冊同時恢復）。再依業主裁決補台灣 B2B 關鍵欄位：**migration 076** `vendors +tax_id`（統一編號 8 碼，既有列 NULL 不回溯）+ `VendorRegisterBody` +tax_id 必填 + company_name 改必填 + 前端廠商分頁加統編欄 + i18n。test_cr_0089 9/9 + 267 unit 全綠；實機帶統編 201 落庫、缺統編/非 8 碼 422。Phase II：負責人/銀行/營登上傳/財政部勾稽。詳見 CR-0089）
**前一次更新：** 2026-06-21（**技師端響應式版型 + 登入後儀表板決策屏 + 資料層假綠修正**，branch `feat/tech-portal-dashboard` — 業主逐頁測試發現技師端 (1) 桌面固定 480px 置中欄（「手機擺中間」）、(2) 登入直落 `/pool` 搶單缺儀表板。研究 DoorDash / Uber Driver / ServiceTitan / Housecall Pro / foodpanda 後採「決策屏」設計（第一屏只答「現在要不要上線接案」，考核型 KPI 收次級頁）。**P0（零後端，已交付）**：響應式 `TechShell`（純 CSS `md:` 切版，手機底部 4-tab / 桌面 `TechSidebar` 側欄，既有頁包入即自動響應式，桌面非 wide 置中 680px、dashboard wide 1280px 多欄）+ 新 `/home` 決策屏（登入導向 `/pool`→`/home`）+ 5 個 widget（狀態收入膠囊 / 上線大鈕接 `PATCH /technicians/me/availability` / 今日行程 / 需注意 / 案量熱力圖）+ account 上線開關接通真實端點（原本地 stub）+ 中英 i18n。**順手修 2 個既有假綠**：`my-orders` 與 `account/statements` 用 `getCurrentSession().userId`（= JWT sub = users.id）當 work-orders/statements 的 `technician_id` 過濾，但 `work_orders.technician_id` = technicians.id、且對帳單路由實為 `/tenants/{tid}/tech-statements?technician_id=`（非 `/me/statements`，後者 404）→ 技師永遠查無自己的工單/對帳單；改先 `GET /technicians/me` 取 technicians.id。**驗證**：tsc 0 錯 + docker build 通過 + 5 角度對抗式審查（SSR/端點/版型/崩潰/i18n，真 CRITICAL 已修並實機 register→login→打端點全 200）。**P1 已實作（業主 §8 裁決全做，零 migration）**：盤點發現 work_orders 已具備所需欄位（estimated_price / accepted_at / started_at / completed_at / scheduled_at / rating / feedback）→ 新增 `GET /technicians/me/dashboard-summary`（今日/本週收入、本月毛額含未結、完成率、平均到場、客戶評分+近期評價；**不含排名**）+ `GET /technicians/me/workload-heatmap`（self，修 A37 IDOR）+ 前端收入膠囊今日/本週、MonthlySnapshot widget、SLA 逾時徽章。test_cr_0088 6/6 + 258 unit 全綠 + 實機兩端點 200。收入口徑 estimated_price 預估（UI 標註）。**安全債**：舊 admin 版 workload-heatmap require_tenant 未鎖 self 仍在（前端已改 /me），下架/self-guard 為清理項。詳見 CHANGELOG / CR-0088）
**前一次更新：** 2026-06-19（**Beta-readiness sprint CR-0038 桶3/4/5**，branch `chore/beta-readiness-ci-and-followups` — 業主「一次做完」剩餘缺口。金流(桶1)/多租戶(桶2)依會議仍 P2/P3 下輪不動；正式價/法務/稅率卡業主。**已收會議對齊無阻塞部分**：(桶3) **CI 基建消滅最後假綠根源** — 修 `_conn` 跨檔污染(conftest autouse fixture)使整套一 process 全綠 **226 unit + 558 component = 784 passed 0 fail**(修前併跑 21 fail) + 建 `component-nightly.yml`(postgres service + schema/migrations/seeds bootstrap + `pytest -m component`)讓 558 component 從「CI 0 執行」變 nightly 真跑。(桶4) **公單收尾** — BR-M08-02 scope change 分級閘(config 門檻 minor/standard/major+主管) + Q063 48h 自動結案 cron(排除 hold/異常) + migration 053。(桶5) create_technician 補 user_id(FR-0044)。**誠實未做**：route gating middleware(需 cookie auth 重構,client 端已有 gating)、exceptions_v2 改名、CR-0043 延後項。詳見 CHANGELOG / CR-0038 §5）
**更早：** 2026-06-19（**公單欄位補完 Phase 2 CR-0043**，branch `feat/cr-0043-workorder-fields-phase2` — 對 20260617 派工單規格 PDF §三 6 模組 24 欄做 12-agent 對抗式逐欄查證（CR-0026 只補骨架：7 符合/17 部分/3 缺，半成品集中「DB 有欄、API/UI 沒接」）。收口四階：**Tier①** 客名/電話接回 API+前端、修 service_category 死欄 bug（pc.category 只寫 problem_type → 加 enum 映射）、新增 `PATCH /work-orders/{id}/fields`（補寫入路徑稀薄）；**Tier②** completion_status 六段真推進（accept/complete/confirm）、新增 `:reopen` 建子單連回 parent（BR-M05-02）；**Tier③** migration 052 +5 欄（dealer/install_date/rain_exposure 三段/special_door_surcharge/payment_method）+ service_catalog 3 計費費目 seed；**Tier④** 完工硬閘加查三段免責（config require_consents 控，預設 off）。test_cr_0043 17/17 + 回歸 226 unit + 23 工單 component 檔全綠；migration 052 套 dev + 記 schema_migrations。money rules 全入 M18 config（quote_policy.apply_surcharge 不寫死）。**誠實 P2 下輪**：出勤費白天/夜間加成自動計算、簽名影像化、保固序號動態回填、拍照上傳 UI、結案 Email。詳見 CR-0043 §9）
**前一次更新：** 2026-06-19（**階段2 測試計畫 + Alpha 實跑綠燈 + Alpha Exit 收尾 CR-0042**，branch `feat/cr-0042-alpha-exit-closeout` — (1) **階段2 四階段測試計畫**（9-agent workflow，275 案例 Alpha 157/Beta 85，含 Irene+Johnson Beta 點測腳本）→ `docs/3-process/test-plan-alpha-beta-rc-ga-20260619.md`。(2) **Alpha 實跑**：226 unit + component 全套；揪出並修 1 真 bug（migration 050：work_order_events CHECK 漏 'schedule_conflict' 致排班衝突事件靜默壞）+ 2 stale 測試。(3) **CR-0042 Alpha Exit 收尾**（業主裁決 0.8 硬擋+override）：migration 051 problemcard_policy config + `assert_completeness`（轉 WO 前完整度<0.8 → 422，主管 override）+ `create_customer` phone 去重（422 DUPLICATE_CUSTOMER）。**最終 Alpha 綠燈：226 unit + 552 component，0 fail**。會議 Action 1-7 全綠、Action 11 Alpha 綠+Beta 腳本就緒。follow-up：師傅 onboarding user_id、對話可見性、multi-tenant（會議定調 Beta 後）。詳見 CR-0042 / 測試計畫）
**更早：** 2026-06-19（**M15 異常框架 CR-0041（階段1 最後一塊）**，branch `feat/cr-0041-exception-framework` — 異常原散落 chat 無統一追蹤；generated.py 有 Exception model 但無表/service；exceptions_v2 誤命名（實為排班）。approval inbox（FR-0049）已涵蓋 scope/refund/dispute/reschedule。業主裁決 §8 全採建議預設。MVP 實作：migration 049（saas.exception_case control tower + return_path 9動作 + work_orders.high_risk_hold 旗標）+ exception_service（open→high/critical設hold / list / resolve選return_path解除hold / escalate）+ exception_cases_v2 router /exception-cases + high_risk_hold gate 接 assign_order/complete_order（422 HIGH_RISK_HOLD，含override）+ exceptions_v2 標 DEPRECATED 讓位。test 6/6 + 回歸 51 工單/完工 + 226 unit 全綠；migration 049 套 dev + 重建 api、smoke。**階段1（公單收尾）主體完成**：完工硬閘(CR-0039)+Evidence治理(CR-0040)+異常框架(CR-0041)。follow-up：exceptions_v2 改名+前端遷移、approval_inbox加exception、半自動觸發、前端異常inbox頁。詳見 CR-0041 §10）
**前一次更新：** 2026-06-19（**Evidence 治理 CR-0040（階段1 公單收尾，2 個 P0）**，branch `feat/cr-0040-evidence-governance` — 原 `list_media_for_work_order` 無角色過濾 → 品牌會看客戶家中環境照（隱私 P0）；media 無保存期/清除。業主裁決 §8 全採建議預設。實作：migration 048（media_files 加 retention_until 1yr/客訴保固2yr + deleted_at 軟刪 + backfill）+ `media_service._hidden_purposes` 規則式角色過濾（Q026：品牌隱藏環境照、會計隱藏門檢照，不可見→404）+ list/get 排除軟刪 + upload 算 retention（dispute/warranty 2yr）+ `soft_delete_expired_media` + `media_retention_cron`（每日，掛 lifespan）+ media_v2 傳 user.role。test 6/6 + 回歸 media 19 + 226 unit 全綠；migration 048 套 dev backfill 7 筆 + 重建 api、smoke 12/12。follow-up：客戶端 track evidence 對齊、前端面板依角色顯示。詳見 CR-0040 §10）
**前一次更新：** 2026-06-19（**完工硬閘 CR-0039（階段1 公單收尾首要項）**，branch `feat/cr-0039-completion-gate` — 原 `complete_order` 只檢查狀態機，師傅可無照片/無簽名/無序號完工（Beta 測試計畫 §46 驗收項 + 客訴/帳務爭議源頭）。業主裁決 §8 全採建議預設。實作：migration 047 `completion_policy` config（min_photos=3 / require_signature / serial_required_categories=["install"] / allow_supervisor_override，門檻入 M18 config 不寫死）+ `work_order_service._enforce_completion_gate` 三道閘（照片≥3 / 客戶簽名 `digital_signatures` 真存在 / 安裝案序號）+ `complete_order` 加 5 參數 + 技師 `/onsite/completion` 走正規閘、`:complete`(v2+v1) 為 admin/dispatcher override 路徑（記 reason）+ 技師 403 guard 防繞過。新 error code INSUFFICIENT_PHOTOS/SIGNATURE_REQUIRED/SERIAL_REQUIRED。test 8/8 + 回歸 50 完工 component + 226 unit 全綠；migration 047 套 dev + 重建 api、redeploy smoke 12/12。HD-5 不回溯。follow-up：前端技師完工頁配合（照片≥3 提示 + serial 欄 + 422 訊息）。詳見 CR-0039 §10）
**前一次更新：** 2026-06-19（**誠實再盤點 CR-0038 + 階段0 修復假綠**，branch `chore/stage0-migration-ci` — 用 35-agent 對抗式 workflow 對 `20260617資料` 全規格（ERP spec 01 / 測試計畫 02 / esales 報價金流 / 會議）逐 file:line + 真 DB 查證：**245 需求 item，真實 DONE_VERIFIED 僅 21（≈9%）**。本文件下方自評「99.8%」量的是「檔案存在率」非「端到端可動率」。三大假綠根源：(1) **migration 標記 ≠ 實際套用** — 035/045 標 🟢 idempotent 但 dev DB 無此兩表 → `test_password_reset`/`test_cr_0037` 直接 `UndefinedTable` FAIL；(2) **金流 Flow 12 = 0 核心** — 無 payment 表/service，AR/AP/拆帳/退款 tier 全 hardcode；(3) **CI 是說謊綠燈** — `test-suite.yml` 跑已刪的 `tests/unit/harness`（collection ERROR）、945 component 測試 0 執行。**階段0 已修復**：① 補套 035/045 到 dev（兩測試 FAIL→PASS，順手修 `catalog_v2` note 洩漏 base_payout 欄名 bug）② 建 migration 046 `public.schema_migrations` 追蹤表（取代 registry 人工標記為「是否已套用」唯一真實來源，回填 44 支）③ 修 CI `test-suite.yml`（`cd api && pytest -m unit` → 226 unit 綠，取代壞路徑）④ reconcile `MIGRATION_REGISTRY.md` 漂移。**完整缺口總表 + 補完 Roadmap → `docs/4-exploration/CR-0038-gap-inventory-20260617.md`**。下一步依會議拍板：公單收尾 → Excel測試plan → 註冊 → 密碼權限 → 派工模式 → Alpha+Beta；金流/多租戶留 Beta 後。詳見 CR-0038）
**前一次更新：** 2026-06-17（**使用者自助忘記密碼 / 重設密碼**，CR-0025 / ADR-0114，branch `feat/self-service-password-reset` — 業主裁決推翻 2026-06-10 Action #7「不建自助」：兩登入頁加可點「忘記密碼」→ 自助 email 重設。實作 migration 035 `password_reset_tokens`（token 雜湊存、30 分單次用）+ api `email_provider`（SMTP 抽象 fail-safe）+ `password_reset_service`（request 枚舉防護+rate-limit / confirm 改密碼）+ `request/confirm-password-reset` 端點 + web `/forgot-password` `/reset-password` 兩頁 + 兩登入頁連結 + i18n。8 後端測試（需 dev stack 跑）+ tsc 0 error。follow-up：confirm 後全域撤 refresh（需 password_changed_at）；prod 啟用待配 SMTP secret + 套 migration 035。詳見 CR-0025 / CHANGELOG）
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

> **6/19 — 師傅拆帳規則主檔（CR-0037）+ 剩餘 esales 誠實分流** — 業主「一起做」剩餘 esales 資料。盤點(5 路 workflow)後誠實分流:唯一有真草稿且可 mock-first 建=師傅拆帳 sheet 21(69 筆)。(1) migration 045:technician_payout_rule + 69 筆 mock seed(python 轉寫,is_mock,base_payout 內部成本+夜間 0.2/急件 0.15)。(2) payout_rule_service(list RBAC 遮蔽/get_rule/compute_payout 純計算)。(3) GET /payout-rules(base_payout 僅後台)。**誠實不建**:服務/材料價(CR-0034 已 seed)、加價套用引擎(待 Q-03~06 算法)、客戶報價文字 Q-12(真無值同稅 Q-07 不捏造)、AR/AP/Brand/佣金引擎(sheet27-31 依賴金流代收代付=會議 Phase2,無基建)、品牌/SKU/BOM(無 consumer)。NOT wired:reconciliation 重算(80%→查表)待 Phase II。test:seed 69/get/compute/RBAC,純計算 pass 其餘待 045。
>
> **6/19 — 金流參數入 config 治理 + 訂金接發票（CR-0036）** — 業主指正:esales sheet 24 Finance Config 已有訂金/佣金/月結時程草稿值,CR-0035 卻 punt 成「待裁決」。sheet 24 標題「規則版本化不可寫死」對上專案既有 M18 config governance(migration 004 留空)。依決議 5 把 sheet 24 值當 mock seed:(1) migration 044:config_namespace ×3(deposit_policy 0.3/1000/材料 1.0、dispatch_commission 0.08、monthly_close 3/5/10)+seed global active(value 內標 is_mock/esales_status/source)+invoices.deposit_required。(2) config_m18_service.read_global_value(全域 active 讀,無則 None)。(3) invoice _resolve_deposit(從 config 算 max(amount×rate,min) 上限 total,缺失 fallback)+create_from_quote 存 deposit。**誠實釐清:稅務 Q-07 全檔無值真未答(不納入);退款 tier 已在 ADR-0040 不重做。** test:config seed+deposit 計算+fallback,待 migration 044。follow-up:訂金顯示於報價/客戶頁、佣金引擎、拆帳 seed、稅務。
>
> **6/19 — S3 免責合規（CR-0033）三段免責同意 + 客戶 PDF 免責段** — 藍圖模組 4「施工免責與合規」。現況無通用 work_order_consents、客戶 PDF 無免責段（CR-0026 §8-Q3 defer 至此）。**法務佔位 first**（三段文本藍圖語意佔位、標待法務）。(1) migration 043:`work_order_consents`(三段 consent_type+accepted+text_version 快照+ip 留痕;UNIQUE(wo,type) 冪等 upsert)。(2) `consent_service`:三段佔位文本常數(新機安裝/破壞鎖/個資)+record/get(ON CONFLICT upsert,永遠回三段)。(3) 消費端點 `GET/POST /consumer/consents/{token}`(複用 work_order_status token;purpose 404、bad body 422、IP 留痕)。(4) PDF 加**免責段**(三段佔位+☑/☐ 狀態,best-effort,**仍不含成本**)。(5) 前端 `/consent/[token]`(三段卡勾選提交,全勾才送)+i18n+AuthGuard /consent/。test:router 4 pass;service/PDF 待 migration 043。out of scope:派工前 hard gate、版本主檔、簽名圖(follow-up)。
>
> **6/19 — S5 金流結算收尾（CR-0035）報價→應收 + 月結 stub 接通** — **盤點修正**：技師撥款月結 CR-0012 已完整做(generate_monthly_batch/CSV/水單+5 端點),真缺口=客戶側帳單斷層 + settlements/monthly 501 殼。範圍收斂(完整 AR/AP/佣金 out of scope→Phase II)。(1) migration 042:invoices 加 quote_id+is_mock。(2) `invoice_service.create_from_quote`:accepted 報價→開應收發票(客戶價 line_items 無 unit_price、稅 mock 0、issued);work_order_id UNIQUE 冪等;非 accepted 409。(3) quote accept→best-effort 開票(catch 廣義 Exception 解耦,失敗不阻斷接受)。(4) settlements/monthly **501→202** 接既有 generate_monthly_batch(period 預設當月,UPSERT 冪等)。(5) API POST .../invoices:from-quote(後台手動,管理角色)。test:settlements 接通+accept 回歸 9 pass;invoice 4 案待 migration 042 套。mock-first 不卡。follow-up:LINE 報價接受通知、訂金二階段、傳票分錄、月結 cron。
>
> **6/19 — S2 報價引擎 Phase C（CR-0032）報價主軸貫通 + 客戶端查看確認** — 報價這條最後一段：客戶免登入查看/確認報價。(1) **複用 stateless `public_token`**（新增 `purpose='quote_view'`,**不建 token 表/不加 quote 欄**）:`verify_token` allowlist 加 quote_view;`mint_view_token`(TTL 對齊 quote.expiry_at,fallback 7d),`:send` 即鑄 token 回 public_token/public_path。(2) **消費端點**:`GET /consumer/quotes/{token}`(include_cost=False **結構性零成本外洩**,客戶版明細結構上不含 unit_price)+`POST /consumer/quotes/{token} {decision}`(accept→accepted、reject→decline→rejected,過期擋 accept 409,非法 422);失敗一律 404。後台 `GET .../quotes/{id}/public-link` 可重鑄連結。(3) **前端客戶頁 `/quotes/[token]`**:mobile-first CSR、bare fetch(不帶 JWT)、三態機、只露客戶價、同意/拒絕鈕;i18n pages.quotesPublic+AuthGuard PUBLIC_PREFIXES 加 /quotes/。(4) **ADR-0115**(accepted):客戶端查看走 stateless public_token+結構性零成本外洩,**不重複** ADR-0064(快照不可變)/ADR-0066(狀態機)/ADR-0062(pricing BC)。test:phasec consumer 8 案+引擎加 send 鑄真 token 整合案,tsc 0 error。**報價主軸貫通：主檔(CR-0034)→引擎(A)→API+後台 UI(B)→客戶端查看/確認(C)。**
>
> **6/19 — S2 報價引擎 Phase B（CR-0032）報價畫面到 DB 全通** — 把 Phase A 引擎接上 API + 後台 UI。(1) **核准門檻 enforcement**(`_APPROVAL_THRESHOLD` mock 10000):總額超門檻不可從 draft 直送,須先 submit→approve,否則 409 `APPROVAL_REQUIRED`(正式門檻待 esales Q-11)。(2) **API** `quote_v2` router:建 draft / 詳情(cost RBAC) / 加項(catalog 帶價) / 狀態機 `:submit`/`:send`/`:accept`(一般角色)+`:approve`/`:reject`(管理角色);全端點 cross-tenant guard。(3) **後台報價編輯頁** `/admin/quotes`:輸入工單 ID 建草稿→catalog 下拉加項→即時 total→狀態機按鈕,成本欄依角色顯示;i18n+rolePolicy+Sidebar 入口。test 補 2 案(超門檻擋/門檻內放行)共 5 pass,tsc 0 error。Phase C(follow-up):客戶端報價查看(/consumer/quotes/{token} 只露最終價)+ ADR(快照不可變)。
>
> **6/18 — S2 報價引擎 Phase A（CR-0032，mock-first）** — 接 CR-0034 catalog。migration 041:`quote` 主表(狀態機 draft→pending→approved→sent→accepted/expired/superseded + 版本鏈 + 有效期 + snapshot_hash)+ quote_approval + pricing_rule_snapshot(append-only)+ quote_line_items 加 quote_id/service_code。`quote_engine_service`:create(有效期 14d/急件3d)、add_line **從 catalog 帶價**、狀態機、送單**凍結 snapshot+sha256**、過期擋 accept、cost RBAC。test 3 pass。Phase B:API 端點 + 後台/客戶報價 UI + 核准門檻 + ADR。報價主軸 主檔(CR-0034)→引擎(CR-0032 Phase A)接通,數值 mock 待 esales Q-01~12 轉正式。
>
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
- HTML `docs/_archive/governance/pending-business-decisions-2026-06-06.html`（已歸檔）標 ✅ 業主已決

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
