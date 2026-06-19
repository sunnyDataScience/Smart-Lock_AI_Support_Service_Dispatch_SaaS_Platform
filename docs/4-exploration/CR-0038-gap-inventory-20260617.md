---
title: CR-0038 缺口盤點與補完 Roadmap（對齊 20260617資料）
status: active
tier: 4-exploration
created: 2026-06-19
owner: 啟恆 / Sunny 裁決
method: 35-agent 對抗式驗證 workflow（17 需求面 × 盤點+查證 兩階段 + 綜整），用 file:line 與真 DB 查證，不信完成度文件自評
sources:
  - 20260617資料/01-workorder-erp-final-spec-20260520.xlsx（M01-M20 模組地圖 + BR 編碼必做 + Phase I/II scope）
  - 20260617資料/02-phased-test-plan-alpha-beta-rc-ga-20260617.xlsx（四階段測試矩陣 + 實作x覆蓋掃描）
  - 20260617資料/AI_Blue_鎖匠ERP_報價資料庫_PhaseI/II（esales 報價/金流主檔，含 AR/AP/佣金/月結 ledger）
  - 20260617資料/20260617 lock-AI 會議記錄.md（Action 1-13 + 決議 1-12）
---

> ⚠️ 本文件為 tier-4 exploration：讀作補完動機與起點，**不可當作 current behavior 的事實**。實作前個別 CR 仍須走 CIA。

## 盤點規模

| 指標 | 值 |
|---|---|
| 查證需求 item 總數 | **245** |
| 涵蓋需求面 | 17（M01-M20 + 會議 Action + esales + 測試計畫 + multi-tenant）|
| 動用 agent | 35（17×盤點 + 17×對抗查證 + 1×綜整）|

### 狀態分佈（嚴格定義見下）

| 狀態 | 數量 |
|---|---|
| DONE_VERIFIED | 21 |
| DEFERRED_OK | 11 |
| PARTIAL | 74 |
| MOCK_ONLY | 25 |
| BROKEN | 39 |
| MISSING | 75 |

> **DONE_VERIFIED 僅 21/245（≈9%）** —— 這就是會議自評「99.8%」與「放大鏡下都是洞」的量化落差。
> 狀態定義：DONE_VERIFIED=code+migration 套用+真測試端到端可動；BROKEN=code 在但 migration 未套/斷鏈/測試跑不了；MOCK_ONLY=僅 mock seed 或佔位；PARTIAL=部分做；MISSING=完全沒有；DEFERRED_OK=規格明示後續 Phase。

---

# 智慧鎖 AI 工單派工 SaaS — 誠實缺口盤點與補完計畫

## 1. 總評

會議自評 99.8% 是**檔案存在率**，不是**端到端可動率**。逐 file:line 與真 DB 查證後，真實可信賴完成度約落在 **55-60%**（以「DONE_VERIFIED 且非 mock」計），且集中在工單狀態機、RBAC、退款/取消雙簽、庫存 row-lock、報價狀態機骨架這幾塊。三大系統性問題讓「綠燈」不可信：

1. **Migration 標記與實際套用脫鉤（audit trail 斷鏈）**。`MIGRATION_REGISTRY.md` 把 035/045 標 🟢 idempotent，但 `to_regclass('password_reset_tokens')`、`to_regclass('technician_payout_rule')` 在 dev DB 皆為 NULL — 實跑 `test_password_reset.py` / `test_cr_0037_payout_rules.py` 直接 `UndefinedTable` FAIL。🟢 idempotent 只代表「設計可重套」，不代表「已套用」。另有 014-027 標 🟡 pending-apply 卻多數已存在於 dev DB，028-032 / 036-041 整批「registry 待補登」無狀態 — **雙向漂移並存**，沒人知道哪個環境真有哪張表。

2. **金流 Flow 12 = 0 核心實作**。`api/services/payment*` / `api/routers/payment*` 不存在，`grep CREATE TABLE payment` → 0 hits。唯二 `line_pay` 是 invoice 的 filter enum 字串。所有 AR/AP/佣金/品牌月結/代收代付的 service 都在「等一個不存在的 payment 表來核銷」，且 80/20 拆帳、退款 5-tier 門檻、取消費 matrix 全部 **hardcode 在 Python 常數**（違反會議「不可寫死 money/refund rules」紅線）。

3. **Mock 未轉正式 + 測試是 mock 假綠**。報價/拆帳/finance config 三批主檔全 `is_mock=TRUE`，正式價待 esales Q-01~Q-12 業主回覆。CI 只跑 226 純 unit（還指錯路徑跑已刪的 `tests/unit/harness`），945 個 component/contract 測試 **CI 0 執行**；21 個 Phase II 測試用 `FakeConn` mock DB，不驗 schema 存在。所謂「測試綠」只覆蓋約 19% 且不碰真表。

---

## 2. 缺口總表（去重後依 bucket 分組）

### P1-公單

| id | title | status | evidence | gap | effort |
|---|---|---|---|---|---|
| BR-M02-02 | 保固 Device 主檔 | MOCK_ONLY | `grep CREATE TABLE device`→0；`device_warranty.py:10-12` 自註「表尚未建，留 P3」，GET best-effort、PATCH 回 None 佔位 | 建 device 表 + customer/site/warranty 關聯 + 接真資料；先 CIA | L |
| G037-completeness-score | PC completeness_score 影響派工 | MISSING | `grep completeness`→0；`032:9`「不做信心分數，延後」；convert-to-WO(`problem_cards_v2.py:325-351`)無 gate | 三層欄位定義+計分函式+阻擋報價/派工 gate | M |
| Q015-required-fields-tiers | 必填欄位三層分級 | PARTIAL | create 僅要 brand/model/symptom/urgency；無「派工前必填」gate；ai_missing_fields 只是 hint | 三層分級+缺欄位禁報價/派工 gate | M |
| Q022/Q023/Q024-photo-video-gate | 照片/影片 gate | MISSING | `media_urls` 純存陣列；`grep video_required`→0；`line_gateway.py:243-245` 只收 TextMessage，圖片/影片被丟棄 | media 完整度 gate+override 端點；line_gateway 接 Image/Video content | L |
| BR-M03-01-status-gate | PC 完整度語意狀態 | PARTIAL | 只有技術態 draft/confirmed/resolved；無 Ready-for-Quote/Need-Info/Need-Photo/Need-Human/Closed-Remote | status 語意層擴充 | M |
| BR-M04-01 | 內外部報價成本拆項 | PARTIAL | 成本只有 `unit_price` 單欄(`037:24`)；未拆 labor/material/travel/margin/brand cost | 擴 quote_line_items 成本維度或加 internal breakdown 表 | M |
| esales-Q12-customer-quote-text | 客戶報價固定文案+同意 gate | MISSING | `quotes/[token]/page.tsx:188-255` 只裸金額表，無抬頭/電話/保固/取消費條款/同意勾選 | 文案定稿+payload 補欄+前端條款區+同意 gate | M |
| Q032-validity-period | 報價有效期分級 | PARTIAL | 只 14d/3d 二元寫死；無依案件類型 7/15/30 天 | 依 case type 分級+移入 config | S |
| BR-M05-01-statemachine | 集中狀態機治理 | DONE→建議重構 | 7 組散落 `_*_FROM` 集合(`work_order_service.py:359-372`)，無集中 transition 圖 | 抽成單一 `_ALLOWED_TRANSITIONS` dict | M |
| BR-M05-01-reasongate | cancel/escalate/reschedule/reassign 強制 reason | PARTIAL | cancel/escalate 強制 422；reschedule 走 `reason_text` 無 min_length；reassign reason 只寫 note 未落 status_reason | reschedule/reassign 也強制 reason 並寫 status_reason | S |
| BR-M05-02-reopen | Reopen/返修連回原工單 | PARTIAL | `parent_work_order_id` 欄+FK 已套用 dev DB，讀取有 map；但無 reopen 建單端點/service | 新增 reopen service+端點，由原 WO 衍生子 WO | M |
| M05-Q052-completion-substatus | 完工六段細狀態 | PARTIAL | `completion_status` 欄已套用；無轉移/enforcement/白名單 | 六段狀態機+gate；complete 驅動細狀態 | M |
| BR-M08-01/Q056 | GPS 到場打卡業務語意 | PARTIAL | `work_orders_v2.py:611-647` 把 GPS 塞進 freeform door_check；無地址範圍判定/offline queue | 地址範圍判定+客戶不在場流程+offline fallback | M |
| BR-M08-03/Q059 | 完工套件(照片≥3/簽名/用料/教學/付款證明) | BROKEN | `_CompletionSubmitRequest` 只要 photo min_length=1；`complete_order` 把 summary 塞字串，不驗照片數/簽名/serial | 照片≥3 硬閘+簽名驗證+materials 必填+教學紀錄；前後端雙驗 | L |
| Q060/TI-M08-03 | 客戶 LIFF 簽名+fallback 鏈 | PARTIAL | `signature_service.py` 完整(sha256+409)；但前端是技師端同機 canvas，非客戶 LIFF；`grep liff/fallback`→0 | LIFF→QR→紙本 fallback 鏈+audit；補 service unit test | L |
| BR-M08-02-tier | 現場 scope change 分級閘門 | MOCK_ONLY | `record_scope_change` 對任何金額一律 pending；`grep 501/2000/50%`→0；無 30min timeout cron | tier 規則(501-2000/>2000/≥50%)+timeout 暫停 cron | L |
| BR-M08-02-customer-confirm | scope change 確認前阻擋完工 | PARTIAL | `respond_public` 客戶 accept→in_progress 有；但 complete_order 無 pending scope 硬阻擋 | pending scope 期間阻擋 complete+三件套驗證 | M |
| Q063-auto-confirm | 客戶未回 48h 自動結案 cron | MISSING | `grep auto.confirm/48h`→命中皆無關；confirm_order 為手動 | 48h auto-confirm cron(排除客訴/保固/退款/爭議) | M |
| Q107-warranty-serial | 序號→保固期自動反查 | PARTIAL | 5-mode 起算(含 handover_date)已做，003 ✅done；但 `warranty_claims` 無 serial 欄、無 serial 反查邏輯 | serial→保固期反查引擎 | M |
| Q108-warranty-redispatch | 保固返修派工編排 | PARTIAL | 返修保固期重算+parent_work_order_id 讀取已做；`grep 返修派工/fallback 資深`→0 | RMA→自動建返修工單+派原師傅 fallback 資深 | M |
| BR-M09-02/Q026 | Evidence 角色可見性分流 | MISSING | `media_files`(`Schema_media.sql:18-41`)無 visibility/role 欄；list 回全部 media | media 加 audience 欄+依角色過濾(P0 阻擋) | M |
| BR-M09-03/Q027 | Evidence 保存期政策(1年/2年) | MISSING | `media_files` 只有 created_at，無 retention_until；`grep retention`→0 | 加 retention_until+清除 cron(仿 gdpr forget) | M |
| Q022/Q024/G021-evidence-package | checklist gate+結案 evidence package | MOCK_ONLY | `record_door_check` 是 freeform placeholder；`grep evidence_package`→0 | 結構化 checklist 驗證+結案自動組裝 package | L |
| G024/BR-M16-02 | 電話口頭確認限制 | MISSING | `grep verbal/口頭/require.*confirmation`→0；改價/改期/取消無「必須補 LINE」gate | 改價/改期/取消/退款加 system/LINE confirmation gate | M |
| media-upload-v2 | 媒體上傳/下載/列表 | PARTIAL | route+tenant guard 真實(`media_v2.py:57-185`)；但 component 測試「無 DB 503=pass」，表在 `Schema_media.sql` 非編號 migration | 補編號 migration 納 registry+真 DB round-trip 測試；prod 換 GCS | M |
| BR-M15-01 | Exception return path(9選1) | MOCK_ONLY | `generated.py:584-602` 有完整 Exception 模型+return_to_stage，但 `grep ExceptionType in routers/services`→0；`exceptions_v2.py` 實為師傅排班 | 以 generated.py schema 落地 exception 表+9-value return_path+接 cancel/dispute/scope/reassign | L |
| BR-M15-03 | High-risk stop rule | MISSING | `grep high.risk/pause/stop.rule`→0；WO 狀態機無 high_risk_hold 中間態 | 加 high_risk_hold 態+5 觸發條件+approval inbox | L |
| Q066 | Onsite 異常回報固定順序 | MISSING | `grep report.exception/異常類型`→0；scope_changes 非五步驟流程 | 師傅端 5 步驟異常回報+照片 gate | M |
| Q064/G026 | Exception taxonomy 異常代碼 | MOCK_ONLY | `generated.py:544-554` ExceptionType 10 值存在但零接線；與 Q065 12 類有缺口 | 擴至 12 類+落 dim 表/config 供 return-path 路由 | S |
| Q068 | 必須暫停的異常先 pause | MISSING | `grep pause`→0；唯一終態化是直接 cancel | 隨 high_risk_hold 一併實作 | M |
| gate12 | Gate12 已選 return path 才可 approve | BROKEN | BR-M15-01 未接線→無統一 return-path gate | exception 落地後於狀態機加 gate12 | M |
| Q011-斷點 | M15 斷點控制點(不可 hardcode money) | PARTIAL | audit 部分到位、cancellation fees config 驅動；但 approvals 未統一、goodwill 門檻未強制 | 完成 BR-M15-01/02/03 串閉環+門檻接真 gate | M |
| spec-completeness-score | M03 completeness≥0.85 轉 WO gate | MISSING | `grep completeness_score`→0；Alpha exit 阻塞項 | 計分+≥0.85 gate+測試 | M |
| spec-m10-serial-gate | serial gate at WO complete | MISSING | `inventory_v2_service.py:23` 明示 follow-up；complete_order 無 serial 檢查 | 跨模組 gate 接入 complete 路徑 | M |
| Action-1 | 公單欄位補齊(CR-0026) | DONE(dev) | dev DB 已套 036 全欄+`test_cr_0026` 4 案 PASS | prod 未套+registry 未登 036+數值 is_mock 待覆核 | S |
| CR-0033 | 三段免責同意+PDF | BROKEN | service/端點/PDF/web 齊全，043 🟢 idempotent；但 043 未證實套到 test DB | 確認 043 套用→component test 轉綠 | S |

### P1-Lite核心

| id | title | status | evidence | gap | effort |
|---|---|---|---|---|---|
| BR-M02-01 | Customer 去重(phone+LINE ID) | MISSING | `customer_service.py:322-333` 只查 line_user_id，phone 不去重；可建重複客戶(P0) | phone+line match/merge+人工合併端點 | M |
| Q008 | 一進線即建 Customer | PARTIAL | CRUD 真實(`customer_service.py:313`)；但 `line_webhook.py` 不 INSERT，僅 admin 手動建 | 各渠道進線接 create_customer(含去重) | M |
| customer-master-crud | 客戶 4-filter | DONE(風險) | 端到端可動；惟 030 registry 未登 apply+filter 欄靠 roadmap worker 多回空 | 確認 030 apply+worker 填值 | S |
| BR-M07-01 | 師傅 onboarding 必填(bank/skill/brand auth) | PARTIAL | `create_technician` 只 INSERT name/phone/email/cap/region，**不寫 user_id** | 補 bank/skill matrix/brand auth+寫 user_id(連修 FR-0044 斷鏈) | L |
| G004/G005-eligibility | 派工前 eligibility gate | MISSING | `_is_excluded_by_circuit` 只剔 3 態；不擋 pending/suspended，不查 brand auth | status active+技能等級+品牌授權 gate | M |
| BR-M16-01/Q073 | 對話可見性分流 | MISSING | `grep visibility/audience`→0；只有 channel 來源；無品牌/會計頻道 | message/note 加 visibility scope+依角色過濾 | L |
| notifications-v2 | In-app 通知中心 | PARTIAL | route 可動；但 component「503=pass」未驗 DB；type free-form 無 registry | 確認表套用+真測試；type 9 模板 registry | M |
| conversation-persist-bridge | LINE 對話旁路持久化 | PARTIAL | persist code 在；但 DB round-trip 未在此環境實證 | 真 DB 整合測試驗 persist 後查得回 | M |
| BR-M13-XX dispute dual-sign | 爭議雙簽狀態機 | DONE(caveat) | 6 態+SoD+reopen，006 ✅done，單檔 33 pass；併跑因 `core/db.py:23` 全域 _conn 污染 21 fail | conftest 加 _conn fixture reset | S |
| BR-M17-01 | 14 角色 RWA 矩陣 | PARTIAL | `_perm` 只 read/write/delete/locked 無 approve；5 系統角色 vs spec 14 vs test 5 三方命名不一 | 正規化角色 enum+補 approve 維度+CIA | L |
| BR-M17-03 | IT 臨時授權 time-limited | MISSING | `grep it_support/temporary/jit/break.glass`→0；無 it_support 角色/表 | 新表 it_temporary_access+到期失效+audit+CIA | L |
| web-route-role-gating | 前端 route gating | MISSING | `web/src/middleware.ts` 不存在；只在 API 層擋 | 加 middleware 依 JWT role redirect | M |
| BR-M18-02 | Change request 生效日排程 | PARTIAL | reason+rollback 有；`grep effective_date`→0，無未來生效排程 | config 加 effective_at+scheduler+rollback_note 獨立欄 | M |
| BR-M18-03 | 初始建置匯入工具 | MISSING | `grep bulk.import/initial.setup`→0；唯一 onboard 是師傅 lifecycle | 最小匯入 CLI(price/regions/roles) | L |
| esales-NPS | 滿意度/NPS | PARTIAL | service+test 有；但算 1-5 rating proxy 非標準 NPS；前端零 caller | 前端接線+0-10 問卷欄位 | M |
| BR-M20-01 | AI knowledge owner+version | PARTIAL | SOP draft 有版本+雙簽；但 FAQ/price range/escalation/forbidden 無治理物件 | 其餘知識物件加 owner+version 治理 | M |
| exceptions_v2-misnamed | exceptions_v2 誤命名 | BROKEN | tag 'M15 Exception' 但 delegate technician_schedule(請假/待命) | 改名 technician_schedule；M15 由真 exception 框架承載 | S |
| Q047 | 客戶不在/師傅延遲 return path | PARTIAL | `reassign_order` 已存在；但未被 exception 框架編排 | reassign 接成 exception return path 分支 | M |
| Q014-remote-close | 遠端關閉需客戶 LINE 確認 | PARTIAL | `resolve_card` 支援遠端結案；但無客戶 LINE 確認 gate | 加客戶 LINE 確認 gate | S |
| Action-3 | 廠商/師傅雙路註冊(CR-0029) | DONE(dev) | dev DB vendors 表+`test_cr_0029` 6 案 PASS | prod 未套 038+registry 未登 | S |
| Action-7/CR-0030 | 派工模式切換 | BROKEN | `dispatched_via` 真寫入 assign(`work_order_service.py:832-846`)；但 migration 039 未登 registry/未確認套用 | 登錄 039+確認套用→升 DONE | S |
| Action-4 | 忘記密碼+5角色隔離(CR-0025) | BROKEN | 5 角色隔離 PASS；但 `password_reset_tokens` 表 dev DB 不存在，`test_password_reset` 7 案 FAIL | 套用 035 到 dev/prod+配 SMTP | S |

### P1-測試

| id | title | status | evidence | gap | effort |
|---|---|---|---|---|---|
| CI-test-suite-unit-job | CI unit job 指向已刪 harness | BROKEN | `.github/workflows/test-suite.yml:48` 跑 `tests/unit`；實跑 5 collection ERROR `No module named harness` | testpaths 改 `api/tests` 跑 `-m unit`；刪殘留+建 component job | M |
| api-tests-never-run-in-ci | 945 component/contract 測試 CI 0 執行 | BROKEN | test-suite.yml 註解「留 nightly」但無 test nightly | 建 nightly：postgres container+套全 migration+`-m component/contract` | L |
| migration-apply-drift-045-035 | 035/045 標綠未套用→test FAIL | BROKEN | dev DB `to_regclass`=NULL；`test_cr_0037` 實跑 UndefinedTable | 各環境 `psql -f` 套 035/045+建 schema_migrations 追蹤 | S |
| migration-registry-reality-mismatch | registry 與實際雙向不一致 | BROKEN | 014-027 標 pending 卻已套；028-032/036-041「待補登」 | 全面 reconcile 逐表核對+統一狀態欄 | M |
| FR-0044-lifecycle | 師傅生命週期狀態機 | BROKEN | 020 🟡 pending；`_fetch_status` JOIN users 但 create 不寫 user_id→永遠 404；測試全 FakeCur mock | 套 020+修 create 寫 user_id+真表整合測試 | M |
| phaseII-CR-tests-db-mocked | 21 個 FR 測試 FakeConn mock | MOCK_ONLY | `grep FakeConn`→21 檔；不驗 schema 存在 | 補 component 真 DB smoke(套 020-027 後 INSERT→讀回) | M |
| migration 019/025/026/027 apply | M12 四支 migration | BROKEN | 全 🟡 pending；四 statement 表 DB 不存在→端到端斷鏈 | 依序套用+登 registry+四套測試 | M |
| FR-0045 Tech AP Statement | 師傅 AP 月結 | BROKEN | 狀態機/dispute window code 完整但測試 DB-mocked；025 未套 | 套 025+真表端到端 | S |
| FR-0046 Dispatcher Commission | 派工佣金 | BROKEN | net=base+bonus-penalty；金額靠參數傳入；026 未套 | 套 026+佣金自動計算(讀 config 0.08) | M |
| FR-0047 Brand B2B | 品牌月結 | BROKEN | AR/AP/NET 邏輯有；金額參數傳入；027 未套 | 套 027+品牌案件自動彙整 | M |
| FR-0048/BR-M13-03 | Quality feedback loop | BROKEN | `rma_quality_finding` INSERT 有；024 🟡 pending→表未建；cascade 只實打 sop_feedback | 套 024+補真正回寫師傅評分/dispatch eligibility | M |
| statement_auto_approval_cron | dispute window 過期 auto-approve cron | BROKEN | cron 已 start 進 lifespan；但依賴 025/026/027 未套→query 不存在的表 | 套表後驗證 cron | S |
| CR-0037 test | 拆帳規則測試 | BROKEN | `test_cr_0037` component 需 045；045 未套→UndefinedTable | 套 045 跑 69 筆 seed+RBAC | S |
| P2-UAT-003/005 | M12 UAT(代收未繳/月結鎖定) | MISSING | 兩 UAT 無測試；代收 ledger+batch 鎖定機制本身缺 | 補 UAT(需先有代收 ledger+鎖定) | M |
| CR-0032-state-machine | 報價狀態機 | BROKEN | code+測試可 collect；041 未登 registry+無 DB | 登 037/040/041+套用+跑 component | S |
| CR-0032-snapshot-freeze | pricing snapshot 凍結 | BROKEN | code 完整；依賴 041 未驗；只凍 line items 無 surcharge(因加價沒接) | 套 041+加價引擎接後重驗 | S |
| CR-0032-PhaseC-consumer | 客戶端報價查看 | BROKEN | token/API/前端三端齊；依 041 未驗 | 套 041+端到端測試 | S |
| CR-0034-catalog | 報價基礎主檔 | BROKEN/MOCK | RBAC+前端展示完整；040 未登 registry；全 is_mock | 套 040+正式價待 Q-01/02 | S |
| CR-0027-quote-line-items | 公單成本拆項 | BROKEN | 表+RBAC 設計正確；037/041 未登 | 套 037/041+財務覆核 | S |
| CR-0035-invoice-from-quote | 報價→應收發票 | BROKEN | create_from_quote 完整；稅 mock 0；042 未確認套用 | 套 042+跑 component | S |
| CR-0036-deposit-config | 訂金 config 治理 | BROKEN | _resolve_deposit 讀 config 正確；044 未確認套用 | 套 044+跑 test+二階段 deposit→balance | S |
| CR-0012 Monthly Close | 月結批次 | BROKEN | generate_monthly_batch+CSV+manual paid 實作；用 80/20 split；019 未套 | 套 019+接真 payout 公式 | M |
| settlements-monthly-501 | 月結 trigger 接線 | BROKEN | 端點回 202；底層 monthly_settlement_batch(019)未套 | 套 019 | M |
| Action-6/CR-0028 | 公單派出→回 LINE 鏈路 | PARTIAL | 四節點 enqueue+resolver bug fix；測試純函式/mock，resolver 4-table JOIN 從未對真 DB 跑 | 起 stack 真 DB smoke(建單→派工→驗 outbox row+resolver+mock LINE) | M |
| CR-0017 | LINE Flex push outbox | PARTIAL | enqueue/worker/builder/postback 齊；表在 `Schema_v2_extensions.sql` 非編號 migration | 補編號 migration 納 registry+確認 prod 套用 | S |
| CR-0027-completion-push | 完工通知 LINE | PARTIAL | builder+enqueue 接線完成過 dispatch 單測；缺端到端真送 | 同 CR-0028 端到端驗證 | S |
| outbox-worker-resilience | worker retry/backoff/dead | DONE(caveat) | backoff/dead/SKIP LOCKED 有硬斷言測試 | resolver SQL 仍 mock-only；prod 需配 token | S |
| pwd-reset-selfservice | 自助 email reset | BROKEN | code 齊；035 未套→7 failed+6 errors | 套 035 重跑轉綠 | S |
| KPI/coverage-none | revenue/family/scheduled/signature/scope_change 0 專屬測試 | PARTIAL | service+router 存在但無對應測試(02 dump 標 none) | 補各 service unit+endpoint 測試 | S-M each |
| contract-test-zero | contract test 0 個 | MISSING | `grep mark.contract`→0；schemathesis 僅 YAML 結構檢查 | 57 endpoint 真打 contract test | L |
| fe-coverage-none-pages | 前端 12+ 頁無 e2e | PARTIAL | conversations/dispatch-manual/reports 等頁存在無 spec | 補 Playwright e2e | L |
| e2e-main-flow-4 | 4 條跨模組 E2E | MISSING | 各段獨立測，無貫穿 spec | 建 4 條 main flow(進線→AI→PC→WO→結案;財務月結) | L |
| KPI-formula-owner(BR-M19-01) | KPI formula ownership | MISSING | `grep formula_owner`→0；公式硬寫 SQL | kpi_definition 表+owner+official 審批 | L |
| BR-M19-02 | Report download audit | PARTIAL | role gate 有；`grep download_audit`→0 無稽核(BR 標阻擋) | 建 report_download_audit 表+寫入 | M |
| BR-M20-03/FR-0050/sop_feedback | AI trace/feedback 生產者 | MOCK_ONLY | 表 EXISTS 但 0 筆；`loop.py` 零接 log_decision；無前端/CSM 生產者 | agent loop 接 trace+前端 feedback 入口 | M-L |
| Action-2 | Excel 功能盤點→四階段測試 plan | MISSING | `grep Alpha.*Beta.*RC.*GA`→0 對應 0617 產出 | 跑功能盤點產出 Alpha/Beta/RC/GA plan | L |
| Action-11 | 啟動 Alpha+Beta 測試骨架 | MISSING | 無階段化跑+coverage gate；依賴 Action-2 | 補洞後建 Alpha 骨架+Beta 點測流程 | L |
| alpha/beta-exit-criteria | Alpha/Beta exit 不可達成 | BROKEN | spec 缺口未實作+CI 跑不到真測試 | 補 spec-but-not-implemented 5 項+修 CI+套 migration | L |
| test-count-discrepancy | 99.8% 自評不可信 | BROKEN | 1171 tests 只 226 unit 能在 CI 跑且路徑錯 | 完成度以「CI 真跑綠數」計分 | M |

### P2-金流

| id | title | status | evidence | gap | effort |
|---|---|---|---|---|---|
| Flow12-payments-core | payments 代收代付核心 | MISSING | `grep CREATE TABLE payment`→0；無 payment router/service | 建 payments 表+service+router(BR-M11-01 核銷對象) | L |
| Q088/spec-three-track | 三軌支付 | MOCK_ONLY | 唯二 line_pay 是 invoice enum；無收款流程/proof | 各 method 收款記錄+現金代收繳回 | L |
| Flow12-linepay-webhook | LINE Pay 整合/webhook | MISSING | `grep linepay/checkout`→0 | LINE Pay request/confirm+webhook 對帳 | L |
| P2-05-AR-status-9state | AR 9 態狀態機 | MISSING | `grep ar_status/ar_ledger`→0；invoices 只 4 態 | 建 AR ledger(sheet27)+9 態 | L |
| BR-M11-01-reconciliation | payment 核銷到 WO/訂金/尾款 | BROKEN | 現有 reconciliation 是師傅結算非客戶 payment；無 payment 表可核銷 | 先建 payments 表才能核銷 | L |
| P2-01-deposit-trigger | 訂金 trigger+二階段 | MISSING | _resolve_deposit 只算金額不判斷「哪些需訂金」 | deposit-required 判定引擎+balance due 流 | M |
| P2-04-payment-proof | Payment proof 欄位 | MISSING | `grep 末五碼/payment_proof`→0；無 payment 表 | proof 欄位(末五碼/截圖/收款人/確認人) | M |
| BR-M11-02-refund-tier | 退款 5-tier 核准 | BROKEN | 5-tier+SoD 邏輯正確、002 ✅done；但 thresholds[1k/5k/30k/100k] **hardcode**(紅線) | 仿 CR-0036 入 M18 config | M |
| P2-06-cancellation-matrix | 取消費 6 階段 matrix | BROKEN | 階段化結構完整、001 ✅done；但費用值 **hardcode**(`:42-48`) | 費用入 config | M |
| P2-08-travel-inspection-fee | 車馬費三級+80/20 拆帳 | PARTIAL | 只 min/max/per_km 線性；80/20 **硬編** `payout_rule_service.py:6` ADR-0041 | 三級分+拆帳接 045 表+獨立 ledger | M |
| P2-12-refund-reason-code | 退款原因 9 類 | PARTIAL | reason_code 用於冪等；但無 9 類 enum 驗證/主檔 | reason_code config namespace+enum 驗證 | S |
| esales-sheet27-ar-ledger | Customer AR Ledger | MISSING | `grep customer_ar`→0；invoices 非 AR ledger | 建 customer AR ledger(可 mock-first) | M |
| BR-M11-03-invoice-responsibility | 發票責任歸屬 | MISSING | `grep issuer/invoice_responsibility`→0 | 加 issuer_type 欄(mock-first) | S |
| invoice-tax-Q07 | 發票稅額 | MOCK_ONLY | `invoice_service.py:37` tax=0.0 mock；esales 規格無稅率值 | 待 Q-07 提供稅率後接入 | S |
| P2-13-upcharge-refusal | 現場加價拒絕 return path | MISSING | `grep 加價` 全是報價時 modifier；無拒絕 return path | 加價不同意走 Exception approval | M |
| settlements-monthly-cron(P2-20) | 月結 cutoff cron | MISSING | `main.py` lifespan 未掛 generate_monthly_batch；只 manual endpoint | 建 monthly_settlement_cron.py+掛 lifespan | M |
| P2-29-ai-finance-guardrail | AI 金流護欄測試 | MISSING | guardrail trace 是事後記錄，非主動斷言；工具白名單間接安全 | 補主動阻擋斷言測試 | S |
| BR-M12 payout formula engine | 師傅 payout 自動重算 | MOCK_ONLY | net 純減法，金額全參數傳入；無引擎從 WO/recon 算 | 建重算引擎(查 payout_rule+加成+扣款) | L |
| CR-0037/sheet21 payout wiring | 拆帳規則接 reconciliation | MOCK_ONLY | 69 筆 seed 全 is_mock；`payout_rule_service.py:6` 自承 NOT wired | reconciliation 改查 payout_rule 取代 80/20 | M |
| BR-M12-02 cash collection offset | 代收現金抵扣月結 | MOCK_ONLY | cash_collection_deduction 純參數；無代收 ledger 表 | 建代收 ledger+逾期 hold+派工暫停檢查 | L |
| BR-M12-03/P2-22 dispute withholding | 爭議暫扣只扣 disputed amount | PARTIAL | 月結整筆排除有 dispute 的 settlement；`grep fraud/severe`→0 | 改只扣 disputed_amount+fraud 分級 | M |
| esales-sheet28~32 ledgers | AP/commission/refund/brand/monthly ledger | PARTIAL | 表+service 在但數值未接 config，硬編 80/20；多支 migration 未套 | 套 migration+對齊 esales 欄位+接 config | M each |
| esales-sheet24-commission-unused | 佣金 config(0.08)未讀 | MISSING | 044 seed 0.08；`dispatcher_commission_service` 零讀 config | 佣金引擎讀 config 算 base | M |
| esales-sheet04-pricing_matrix | 價格矩陣+車馬/急件套用 | MISSING | 無 matrix 表；`add_line:90-117` 只 copy 售價不套 surcharge→金額系統性偏低 | 建 matrix 或 add_line 接 surcharge_rule | L |
| esales-Q03~Q06-surcharge-engine | 加價套用引擎 | MISSING | surcharge_rule 只是唯讀 catalog；quote engine 從不讀 | recompute 依案件 context 套加價 | L |
| BR-M13-01/Q100 | 獨立 RMA case(編號+連結) | MISSING | `grep rma_number/RMA-YYYYMM`→0 | 建 saas.rma_case+編號產生器+生命週期 | L |
| BR-M13-02 | RMA 責任矩陣(7 分類, P0) | MISSING | `grep responsibility/liability`→0(全 repo) | 責任矩陣 enum+比例 split+初判規則+CIA | L |
| Q106 | RMA 結果連帳務 | MISSING | 決策只 approve/reject；無結果→金額調整 wiring | 結果 enum+連 refund/工單金額/inventory/重派 | L |
| Q101/Q109 | 客訴分類統一+證據連動 | PARTIAL | complaints 5 分類無接線；dispute_type 另一套 | 統一分類 enum+連責任矩陣 | M |
| BR-M10-01-bom | 兩層 BOM | MISSING | `grep service_bom`→0；esales sheet18 9 筆 BOM 無 seed | 建 service_bom 表+seed | M |
| Q079/SKU/supplier master | 品牌/SKU/供應商成本主檔 | MISSING | `grep brand_master/sku_master/supplier_cost`→0;esales sheet15-17 | 建各主檔+seed | M each |
| Q084/Q083/usage variance | 現場用料登記+庫存 soft gate+差異 | MISSING | `grep material_usage/reservation`→0;sheet25/26 | 建 usage 表(依賴 BOM)+派工前預檢 | M |
| CR-0030-platform-paid-billing | 平台代派計費引擎 | MOCK_ONLY | 只標 `dispatched_via='platform'`；無計費 | 計費規則(待業主)+接 AP/AR ledger | L/M |
| BR-M05-03-paymentgate/Flow-Gate | 付款 gate 控派工 | MISSING | `grep payment.gate`→0;assign 無付款檢查;依賴金流 | payments 狀態就緒後加 customer-confirm+paid gate | L |
| esales-sheet33-uat | Phase II UAT 5 案 | MISSING | sheet33 全 Pending;依賴未建引擎 | UAT 測試(引擎落地後) | L |

### P3-多租戶

| id | title | status | evidence | gap | effort |
|---|---|---|---|---|---|
| BR-M01-01 | Channel source 8 渠道綁 Case | PARTIAL | ConversationChannel enum 只 line/web/voice 3 值;非 Case 級 | 定義 8 值 enum+承載實體+NOT NULL+CIA | M |
| BR-M01-02/Q006 | 先建 Case 再進報價+全渠道入口 | MISSING | 唯一 case 表是 KB;`line_webhook` 不建案;7 渠道無入口 | 新增 Case 實體(source_channel+SLA clock)+各渠道接線+CIA | L |
| Q012 | 案件歷史保留 1 年 | PARTIAL | 歷史聚合可查;但無 Case 層歷史+無 1 年保存規則 | Case 層歷史+保存規則 | M |
| BR-M02-03 | Site Group(建商/社區) | MISSING | `grep site/community/builder`→0 表;僅 1 boolean 旗標 | 建 site_group 表+batch 操作 | L |
| Q013/Q017-triage | AI 五向分診結果存儲 | PARTIAL | 分診停留在 SOP prompt;`grep triage_result`→0 結構化落地 | triage_result 欄/表+agent 萃取器 | L |
| BR-M03-02-escalation | 3 次失敗循環轉真人 | PARTIAL | 團隊刻意 prompt 推翻;transfer 無計數 | 業主確認補計數器或接受 prompt-only | M |
| Q019-rma-complaint | 客訴獨立 RMA case | PARTIAL | API intent enum 無 complaint 值 | 擴 intent+complaint→RMA 串接 | M |
| BR-M06-eligibility-matching | 媒合引擎(skill/area/rating) | PARTIAL | 加權評分有;不查 inventory/suspension/brand 經驗;distance 示意非 GIS | 擴查資格維度+ST_Distance | M |
| BR-M06-02-grab-order | 搶單池 | MISSING | realtime pool 是 per-tech 個人佇列非競爭池 | grab pool 表+FOR UPDATE 防重領+low-risk 分類 | L |
| BR-M06-03-acceptance-sla | 接單 SLA+逾時自動改派(P0) | MISSING | `grep acceptance_sla/auto_reassign`→0;timeout 只是 log enum | accept_deadline+逾時 reassign+SLA 違約記錄 | L |
| BR-M07-03 | Performance feedback 影響排序 | PARTIAL | 排序只單一 rating;on-time/acceptance/rejection 未進 | 排序公式擴入多維 feedback | M |
| esales-G007/G008/G009 | 三類租戶型別主檔 | PARTIAL | saas.tenant 只 3 欄無 tenant_type;以 vendor_type 局部代替;038 未登 | 三類租戶主檔+CR-0031 | L |
| 會議§3.3 DB 隔離 | 公單/師傅池共享 vs 客戶/報價/memory 隔離 | DEFERRED | 全靠 tenant_id 邏輯欄;無物理隔離 | CR-0031+ADR-0030(會議定調延後) | L |
| Action-13 | LINE Webhook URL+Token 分發 | MISSING | 單一 channel secret/token;`grep per-tenant channel`→0;無接入文件 | per-tenant channel 主檔+多租戶簽章+接入文件 | L |
| CR-0013/migration 018 | LINE binding | BROKEN | code 完整;saas.line_binding(018) 🟡 pending 未套 | 套用 018 | S |
| BR-M20-02 | AI forbidden guardrail | MOCK_ONLY | 只 prompt/knowledge 軟性指示;loop 無 output guardrail block | loop output 加 guardrail+寫 trace | L |
| FR-0050 trace store | AI Governance Trace | MOCK_ONLY | 表 EXISTS 0 筆;loop 零接 log_decision | loop 接 trace(best-effort) | L |
| spec-a01-debounce | 進線 1.5s debounce/flood | MISSING | `grep debounce/flood`→0 業務 hit | 1.5s 視窗合併+24h dedup+測試 | M |

---

## 3. 已驗證完成（可信賴的綠燈）

這些在 dev 環境真能端到端動，有對真 DB 跑的測試：

- **工單狀態機核心**（`work_order_service.py`）：7 組 action 都以 409 STATE_CONFLICT 擋非法轉移；派工前必填 gate（`_assert_dispatch_ready` 422）；migration 036 欄位已套 dev DB；`test_cr_0026` 4 案真 DB PASS。
- **派工模式 set/get + dispatched_via 標記**（CR-0030，dev-verified）：round-trip 測試+assign→`platform` 真寫入。
- **庫存品項 + 異動 ledger**（FR-0007）：007 ✅done 已套用；`FOR UPDATE` row-lock + serial 422 + INSUFFICIENT 409 真實；29 test 可跑。
- **退款雙簽 + 5-tier SoD + 取消費 6 階段**（migration 001/002 ✅done）：狀態機+同 user 防重簽完整（唯費用值 hardcode 待入 config）。
- **爭議 dual-sign 狀態機**（006 ✅done）+ **保固 5-mode + claim create/decision**（003 ✅done）+ web 三頁齊全。
- **RBAC 守衛 + 動態權限端點**（034 已 prod 套用）：`role_required` 真 raise 403；越權/階層/locked 三重防護;56+35 passed。
- **多角色登入/註冊 + admin 代重設**：四登入頁齊;後端白名單隔離。
- **M18 config 治理**（004 ✅done + 044 idempotent）：live DB config_version=63/audit=153;訂金/佣金/月結參數入 config + invoice 真讀;canary 自動推進 cron。
- **audit_events 查詢/匯出/保留期** + **outbox worker 韌性**（backoff/dead/SKIP LOCKED 有硬斷言）。
- **客戶主檔 CRUD** + **知識庫 SOP ID 外洩修復**（commit 9a58d390）。

⚠️ 注意：上述多數 migration 在 **prod 未追蹤套用**，且測試套件因 `core/db.py` 全域 `_conn` 被 FakeConn 跨檔污染，**併跑不可靠一次過**（單檔可過）。

---

## 4. 合理延後（DEFERRED_OK）

| 項目 | 為何現在不做 |
|---|---|
| **Partner Portal 全套**（BR-M14-01/02、BR-M01-03 external scope、P2-18）| 會議 #11 明示 Phase III;品牌/經銷/建商自助入口非當前 single-tenant Beta 範圍 |
| **Multi-tenant 分庫/RLS**（Action-12/CR-0031、§3.3 隔離）| 會議定調「先補洞→Beta 綠燈→再轉 multi-tenant」;CR-0031 尚未開,004-rls 🔒 預留待 ADR-0030 |
| **auto_match 自動執行**（Report 2）| 規格明示 Report 2 後續;現在只保留模式設定值+候選計算 |
| **CR-0033 派工前 hard-gate + 簽名圖留痕 + legal_text 版本主檔** | CR-0033 §8 明示「另 CR」,設計性延後 |
| **供應商成本主檔 / 品牌SKU/BOM/等級主檔**（sheet15-20、17）| esales sheet23 標 Phase II;無 consumer 端依賴 |
| **退換瑕疵料完整狀態機 / Q07 稅 / Q12 文案** | esales 規格待業主回答,不捏造 |
| **Ops/外部任務**（Action-5 已完成除外):Action-8 發 URL+QR、Action-9 Irene 點測、Action-10 文件整理 | 非 code 產出,owner=業主/Irene |

---

## 5. 補完 Roadmap（嚴格對齊會議拍板順序）

> effort 加總用 S=0.4d / M=1.25d / L=3d 估算。標 `[ops]` 為非 code。

### 階段 0（前置・必做，否則後面全是假綠）— 約 3-4d
**套用 migration + 修 CI**，這是所有「BROKEN 因 migration 未套」item 的共同前置：
- `migration-apply-drift-045-035`、`migration-registry-reality-mismatch`、`CI-test-suite-unit-job`
- 套用 035/045/018/019/020/024/025/026/027 到 dev+prod，補登 registry，建 schema_migrations 追蹤表
- **交付驗收**：`test_password_reset` / `test_cr_0037` / FR-0044~0048 component 測試由 FAIL→PASS;CI `-m unit` 指向 `api/tests` 跑 226 unit 綠

### 階段 1 — 補公單收尾 — 約 12-15d
- **公單欄位/成本/電子工單/免責收尾**：Action-1（prod 套+登 registry）、CR-0033（確認 043）、Action-6（端到端 smoke）、CR-0027/CR-0017
- **完工硬閘**：BR-M08-03（照片≥3/簽名/serial gate）、Q060（LIFF fallback）、spec-m10-serial-gate、M05-Q052
- **Evidence 治理**：BR-M09-02（角色可見性,P0）、BR-M09-03（保存期,P0）、Q022/G021、Q023 影片 gate
- **M15 異常框架**：BR-M15-01（以 generated.py 落地）、BR-M15-03 high_risk_hold、exceptions_v2 改名、Q064/Q066/gate12
- **PC 智能層**：G037 completeness gate、Q015 三層必填、spec-completeness-score
- **交付驗收**：公單從進線→完工每個 gate 可擋;完工缺照片/簽名 422;異常必選 return path

### 階段 2 — Excel 功能盤點 + 測試 plan（Action-2）— 約 3d
- 跑 esales sheet 全表盤點對映 implementation,產出 Alpha/Beta/RC/GA 四階段 plan（對齊 `/tmp/xlsxdump/02` 矩陣）
- **交付驗收**：committed 測試計畫文件;coverage Dashboard 對接

### 階段 3 — 廠商/師傅雙路註冊（Action-3，已 dev-done）— 約 1d
- prod 套用 038+登 registry;BR-M07-01 補 onboarding 必填欄位（含寫 user_id 連修 FR-0044 斷鏈）;G004/G005 eligibility gate
- **交付驗收**：兩路註冊→核准→登入分表;師傅完整資料才可派工

### 階段 4 — 密碼 + 權限隔離（Action-4，CR-0025/0021）— 約 2-3d
- 套 035（階段 0 已含）+配 SMTP `[ops]`;BR-M17-01 角色矩陣正規化+approve 維度;BR-M17-03 IT 臨時授權;web-route-role-gating
- **交付驗收**：自助忘密碼 8 案綠;5 角色越權 403;前端 route redirect

### 階段 5 — 派工模式切換（Action-7，已 dev-done）— 約 0.5d
- 登錄 039+確認 prod 套用（platform_paid 計費引擎延後 P2）
- **交付驗收**：三模式切換 UI+dispatched_via 真寫入

### 階段 6 — Alpha + Beta 測試（Action-11，下下週）— 約 8-10d
- `api-tests-never-run-in-ci`（建 nightly component/contract job）、`contract-test-zero`、`e2e-main-flow-4`、`fe-coverage-none-pages`、coverage=none 補洞、`phaseII-CR-tests-db-mocked`
- Irene+Johnson 點測 `[ops/外部]`（Action-8/9 解鎖）
- **交付驗收**：Alpha exit（P0 happy 100%+S0=0）;Beta exit（P1≥90%+integration≥80%）

### 下一輪（Beta 綠燈後）— P2 金流 + P3 多租戶
- **P2 金流**（依賴鏈最深,先建 payments 表）：Flow12-payments-core → BR-M11-01 核銷 → AR/AP ledger → 三表月結接真公式 → 拆帳/退款/取消費**入 config 解除 hardcode** → 月結 cron → pricing_matrix/surcharge 引擎（解決金額系統性偏低）→ RMA case+責任矩陣
- **P3 多租戶**（Action-12/CR-0031）：三類租戶主檔 → DB 隔離 → Action-13 LINE channel 分發 → auto_match 自動執行

**P2 金流總工時粗估 ~40-50d（L 居多）**,**P3 ~25-30d**。

---

## 6. 關鍵風險與建議

1. **【最該先動】先套 migration、再談任何完成度**。035/045 標綠未套用直接讓 `test_password_reset`/`test_cr_0037` FAIL,這是「99.8% 假象」的最直接證據。在套用 + 建 schema_migrations 追蹤表之前,**任何「✅完成」都不可信**。階段 0 不做,後面全是假綠。成本最低（~3-4d）、解鎖最多。

2. **CI 是說謊的綠燈,優先修**。`test-suite.yml:48` 跑已刪的 `tests/unit/harness`（5 collection ERROR）,945 個 component/contract 測試 **0 執行**,21 個 FR 測試用 FakeConn 不碰真表。目前「CI 綠」只代表 19% 純 unit 且路徑錯。不修 CI,Alpha/Beta exit criteria 永遠無法客觀判定。

3. **金流是最大黑洞,但依賴鏈最深,不要急著開**。payments 表不存在 → AR/AP/佣金/月結全部「等一個不存在的表來核銷」,80/20 拆帳+退款 tier+取消費全 hardcode（會議紅線）。建議嚴守會議順序——**Beta 綠燈後才動 P2**;但現在可做的零成本準備是把已有的 refund/cancellation hardcode 值**搬進 M18 config**（CR-0036 已示範路徑）,先解除紅線。

4. **完工硬閘是公單的真實風險點**。`complete_order` 把簽名/照片串成字串塞 service_report,不驗照片數/簽名/serial — 意味師傅可無照片無簽名完工。這是 Beta §46 明列驗收項,且是客訴/帳務爭議的源頭,階段 1 優先。

5. **測試 infra 的 `_conn` 全域污染要修**。`core/db.py` 全域 `_conn` 單例被 FakeConn 跨檔污染,導致 disputes_v2/warranty 等真實完成的模組**併跑 21 fail**（單檔過）。這讓即使做對的模組在套件層也顯紅,在 conftest 加 `_conn` fixture reset 是低成本高回報。

---

## 7. Playwright 實機驗證新增發現（2026-06-19，階段0 收尾）

業主要求「補完前先用 Playwright 確認一次流程」。實跑揪出**兩個本盤點未涵蓋的系統性問題**——皆屬「code 已 commit 但實際不可用」,正是會議警告的核心型態：

### 7.1 【第 4 大假綠根源】本機/prod stack 落後 HEAD 約 12 個 CR（部署落差）

- 跑著的 docker 三容器（web/api/agent）**全是 2026-06-16 build**,從未重建。CR-0025（忘記密碼）→ CR-0037 共 ~12 個 CR 的成果**一個都沒部署**（連本機都沒有,prod 也停在 6-16 首次上線）。
- 鐵證:重建前 `/auth/request-password-reset`、`/payout-rules` 實機 **404**;web bundle 只有 `login`/`tech-login`,無 `register`/`forgot-password`/`vendor-login`/`reset-password`。
- **這與 migration drift 同源**:團隊一直 commit code,但**無任何自動部署**,「完成度」算的是 commit 數,不是「跑得到的東西」。
- **建議**:把「rebuild + 套 migration + smoke」納入每輪收尾 checklist;否則 Beta 點測永遠在測舊畫面。重建後 `/payout-rules`(CR-0037)+`request-password-reset`(CR-0025) 實機已 **200**。

### 7.2 【真 bug 已修 commit d94ba262】AuthGuard 公開白名單漏列 → 註冊/忘記密碼 100% 不可達

- `AuthGuard.tsx` 的 `PUBLIC_PATHS` 只有 `/login`+`/tech-login`。CR-0029 的 `/register`、`/vendor-login` 與 CR-0025 的 `/forgot-password`、`/reset-password` **從未加入** → 未登入者一進就 `router.replace("/login")` 彈回。
- 致命處:這些頁的使用者（新師傅/廠商、忘記密碼者、點 email 連結者）**本就未登入** → 功能對目標使用者 100% 不可達。頁面與後端端點都做好了,只差白名單一行。
- 與 2026-06-11 補 `/tech-login` 是**同一類 bug**(漏列公開頁),當時補一條卻沒補齊其餘四條。
- **修復+驗證**:四條加入 `PUBLIC_PATHS`;rebuild web 後 Playwright 實證 `/register`(師傅/廠商切換+表單)、`/forgot-password`(提交→enumeration-safe 訊息)皆可達且端到端可動。

### 7.3 確認可信賴的綠燈（fresh login，0 console error）

- admin 登入 → dashboard（真實 KPI/圖表/最近工單）→ `/work-orders`（20+ 真實工單,0 error）。
- 後端 v2 API 帶正確 token + `X-Tenant-ID` 全 200;缺 header 是 400 非 401。
- 初載的 v2 401 查清為**測試瀏覽器殘留過期 token**,非產品 bug（minor UX:token 過期應導回登入而非顯示舊資料+靜默 401,可列 backlog）。WS realtime 403 為 localhost 未配 WS,屬部署面。
